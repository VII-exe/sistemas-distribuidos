# client.py - Cliente com suporte a múltiplos usuários
import sys
import os
import socket
import json
import time
import threading
from typing import Dict, Optional, List

# opcional path adjust se necessário
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


def clear_screen():
    """Clear terminal screen."""
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except Exception:
        pass


class MessageClient:
    def __init__(self):
        self.host = 'localhost'
        self.logged_users: Dict[int, Dict] = {}  # {port: {'username': ..., 'token': ..., 'node_id': ...}}
        self.current_session: Optional[int] = None
        self._stop_loading = False

    def _send_request(self, port: int, request: Dict, timeout: int = 10) -> Dict:
        """Send a JSON request to a node and return parsed JSON response or error dict."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self.host, port))
            sock.send(json.dumps(request).encode('utf-8'))
            data = sock.recv(65536).decode('utf-8')
            return json.loads(data)
        except socket.timeout:
            return {'status': 'error', 'message': 'Timeout - Nó não respondeu'}
        except Exception as e:
            return {'status': 'error', 'message': f'Erro de conexão: {e}'}
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def login(self, username: str, password: str, port: int) -> bool:
        """Faz login em um nó específico"""
        req = {'action': 'login', 'username': username, 'password': password}
        print(f"🔐 Fazendo login como {username} no nó porta {port}...")
        resp = self._send_request(port, req)
        
        if resp.get('status') == 'success':
            self.logged_users[port] = {
                'username': username,
                'token': resp.get('token'),
                'node_id': resp.get('node_id', f'Node{port - 8000}'),
                'port': port
            }
            if self.current_session is None:
                self.current_session = port
            print(f"✅ Login bem-sucedido! {username} conectado ao {self.logged_users[port]['node_id']} (porta {port})")
            return True
        else:
            print(f"❌ Falha no login: {resp.get('message', 'Erro desconhecido')}")
            return False

    def logout(self, port: int) -> bool:
        """Faz logout de um nó específico"""
        if port not in self.logged_users:
            print("❌ Você não está logado neste nó!")
            return False
            
        session = self.logged_users[port]
        resp = self._send_request(port, {'action': 'logout', 'token': session.get('token')})
        
        if resp.get('status') == 'success':
            username = session.get('username')
            node_id = session.get('node_id')
            del self.logged_users[port]
            
            # Se era a sessão atual, trocar para outra ou limpar
            if self.current_session == port:
                self.current_session = next(iter(self.logged_users.keys())) if self.logged_users else None
                
            print(f"✅ Logout realizado! {username} desconectado do {node_id}")
            return True
        else:
            print(f"❌ Erro no logout: {resp.get('message', 'Erro desconhecido')}")
            return False

    def _show_loading(self):
        """Mostra animação de carregamento"""
        chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        i = 0
        while not self._stop_loading:
            print(f"\r📤 Enviando... {chars[i % len(chars)]}", end="", flush=True)
            i += 1
            time.sleep(0.1)
        print("\r", end="", flush=True)

    def post_message(self, content: str, visibility: str = "public") -> bool:
        """Envia mensagem usando a sessão atual"""
        if self.current_session is None:
            print("❌ Você precisa fazer login primeiro!")
            return False
            
        session = self.logged_users[self.current_session]
        req = {
            'action': 'post_message', 
            'token': session.get('token'), 
            'content': content, 
            'visibility': visibility
        }
        
        print(f"📤 Enviando mensagem de {session['username']} via {session['node_id']}...")
        
        # Animação de loading
        self._stop_loading = False
        loading_thread = threading.Thread(target=self._show_loading, daemon=True)
        loading_thread.start()
        
        resp = self._send_request(self.current_session, req, timeout=30)
        
        self._stop_loading = True
        loading_thread.join(timeout=0.2)
        
        if resp.get('status') == 'success':
            delivery_report = resp.get('delivery_report', {})
            print(f"\n✅ {delivery_report.get('message', 'Mensagem enviada')}")
            return True
        else:
            print(f"\n❌ {resp.get('message', 'Erro ao enviar mensagem')}")
            return False

    def read_messages(self, port: Optional[int] = None, public_only: bool = False) -> bool:
        """Lê mensagens de um nó"""
        if port is None:
            if self.current_session is None:
                print("❌ Você precisa fazer login primeiro!")
                return False
            port = self.current_session

        req = {'action': 'get_messages', 'public_only': public_only}
        
        # Se estiver logado no nó, usar token
        if port in self.logged_users:
            req['token'] = self.logged_users[port]['token']
            
        resp = self._send_request(port, req)
        
        if resp.get('status') == 'success':
            messages = resp.get('messages', [])
            node_id = resp.get('node_id', f'Node{port - 8000}')
            
            if messages:
                print(f"\n📋 MURAL ({node_id}):")
                print("-" * 60)
                for msg in messages:
                    author = msg.get('author', 'Desconhecido')
                    content = msg.get('content', '')
                    timestamp = time.strftime('%H:%M:%S', time.localtime(msg.get('timestamp', 0)))
                    msg_type = msg.get('message_type', 'public')
                    icon = "🔒" if msg_type == "private" else "🌐"
                    print(f"[{timestamp}] {icon} {author}: {content}")
                print("-" * 60)
                print(f"Total: {len(messages)} mensagens\n")
            else:
                print("📭 Nenhuma mensagem encontrada\n")
            return True
        else:
            print(f"❌ Erro ao ler mensagens: {resp.get('message', 'Erro desconhecido')}")
            return False

    def switch_user(self):
        """Permite alternar entre usuários logados"""
        if not self.logged_users:
            print("❌ Nenhum usuário logado!")
            return

        print("\n👥 USUÁRIOS LOGADOS:")
        print("-" * 60)
        
        # Obter status atual de cada nó
        users_info = []
        for i, (port, session) in enumerate(self.logged_users.items(), start=1):
            # Verificar status do nó
            node_status = self._get_node_status(port)
            
            if node_status:
                if node_status.get('active'):
                    if node_status.get('simulate_offline'):
                        status_icon = "🟡⚠️"
                        status_text = "SIMULANDO FALHA"
                    else:
                        status_icon = "🟢"
                        status_text = "ATIVO"
                else:
                    status_icon = "🔴"
                    status_text = "INATIVO"
            else:
                status_icon = "❌"
                status_text = "DESCONECTADO"
            
            current_indicator = " ← ATUAL" if port == self.current_session else ""
            
            print(f"{i}. {status_icon} {session['username']} @ {session['node_id']} (porta {port}) - {status_text}{current_indicator}")
            users_info.append((port, session, status_text))
        
        print("-" * 60)
        
        try:
            choice = input("Escolha o número do usuário para alternar (0 para cancelar): ").strip()
            if choice == '0' or choice == '':
                return
                
            idx = int(choice) - 1
            if 0 <= idx < len(users_info):
                old_session = self.logged_users.get(self.current_session, {})
                old_user = old_session.get('username', 'Nenhum')
                
                selected_port = users_info[idx][0]
                selected_session = users_info[idx][1]
                new_user = selected_session['username']
                
                self.current_session = selected_port
                print(f"✅ Sessão alternada: {old_user} → {new_user}")
            else:
                print("❌ Opção inválida!")
        except ValueError:
            print("❌ Digite um número válido!")

    def _get_node_status(self, port: int) -> Optional[Dict]:
        """Obtém status de um nó"""
        try:
            resp = self._send_request(port, {'action': 'check_status'}, timeout=2)
            if resp.get('status') == 'success':
                return resp
        except Exception:
            pass
        return None

    def toggle_offline_simulation(self):
        """Liga/desliga simulação offline do nó atual"""
        if self.current_session is None:
            print("❌ Você precisa estar logado primeiro!")
            return
            
        session = self.logged_users[self.current_session]
        resp = self._send_request(
            self.current_session, 
            {'action': 'toggle_offline', 'token': session.get('token')}
        )
        
        if resp.get('status') == 'success':
            print(f"✅ {resp.get('message')}")
        else:
            print(f"❌ Erro: {resp.get('message', 'Erro desconhecido')}")

    def show_system_status(self):
        """Mostra status completo do sistema"""
        clear_screen()
        print("📊 STATUS COMPLETO DO SISTEMA")
        print("=" * 70)
        
        total_active = 0
        total_offline = 0
        
        for port in [8001, 8002, 8003]:
            node_status = self._get_node_status(port)
            
            if node_status:
                node_id = node_status.get('node_id', f'Node{port - 8000}')
                user = node_status.get('user', 'Nenhum')
                
                if node_status.get('active'):
                    if node_status.get('simulate_offline'):
                        icon, text = "🟡⚠️", "ATIVO (simulando falha)"
                        total_offline += 1
                    else:
                        icon, text = "🟢", "ATIVO"
                        total_active += 1
                else:
                    icon, text = "🔴", "INATIVO"
                    
                # Verificar se é uma das suas sessões
                our_login = ""
                current_indicator = ""
                if port in self.logged_users:
                    our_login = " (SEU LOGIN)"
                    if port == self.current_session:
                        current_indicator = " ← SESSÃO ATUAL"
                
            else:
                icon, text, user, our_login, current_indicator = "❌", "DESCONECTADO", "---", "", ""
                node_id = f'Node{port - 8000}'
            
            print(f"{icon} {node_id} (:{port}) - {text}")
            print(f"   Usuário: {user}{our_login}{current_indicator}")
            print()
        
        print("=" * 70)
        print(f"📈 Resumo: {total_active} nós ativos, {total_offline} simulando falha")
        print(f"👤 Suas sessões ativas: {len(self.logged_users)}")
        
        if self.current_session:
            current_user = self.logged_users[self.current_session]['username']
            current_node = self.logged_users[self.current_session]['node_id']
            print(f"🎯 Sessão atual: {current_user} @ {current_node}")
        
        print()

    def show_help(self):
        """Mostra ajuda dos comandos"""
        clear_screen()
        print("📖 COMANDOS DISPONÍVEIS")
        print("=" * 60)
        print("🔐 AUTENTICAÇÃO:")
        print("  login <usuario> <senha> <porta>  - Login em nó específico")
        print("  logout <porta>                   - Logout de nó específico")
        print("  switch                           - Alternar entre usuários")
        print("  logoutall                        - Logout de todas as sessões")
        print()
        print("💬 MENSAGENS:")
        print("  post <mensagem>                  - Enviar mensagem pública")
        print("  postpv <mensagem>                - Enviar mensagem privada")
        print("  read                             - Ler mensagens (sessão atual)")
        print("  read <porta>                     - Ler mensagens de nó específico")
        print("  readpub <porta>                  - Ler apenas mensagens públicas")
        print()
        print("🔧 SISTEMA:")
        print("  status                           - Ver status de todos os nós")
        print("  simulate                         - Simular falha (nó atual)")
        print("  clear                            - Limpar tela")
        print("  help                             - Mostrar esta ajuda")
        print("  quit                             - Sair do cliente")
        print()
        print("💡 DICAS:")
        print("  • Portas disponíveis: 8001, 8002, 8003")
        print("  • Use 'switch' para alternar entre usuários logados")
        print("  • Cada usuário só pode estar logado em um nó por vez")
        print("  • Mensagens privadas só são visíveis para usuários logados")
        print()

    def logout_all(self):
        """Faz logout de todas as sessões"""
        if not self.logged_users:
            print("❌ Nenhuma sessão ativa!")
            return
            
        print("🚪 Fazendo logout de todas as sessões...")
        ports_to_logout = list(self.logged_users.keys())
        
        for port in ports_to_logout:
            self.logout(port)
        
        self.current_session = None
        print("✅ Logout completo realizado!")


def main():
    client = MessageClient()
    clear_screen()
    
    print("🎯" + "=" * 68 + "🎯")
    print("🎯  SISTEMA DE MENSAGENS DISTRIBUÍDAS - CLIENTE MULTI-USUÁRIO  🎯")
    print("🎯" + "=" * 68 + "🎯\n")
    print("🚀 Digite 'help' para ver todos os comandos")
    print("💡 Novidade: Suporte a múltiplos usuários simultâneos!\n")

    while True:
        try:
            # Prompt mostra usuário/nó atual
            if client.current_session:
                session = client.logged_users[client.current_session]
                prompt = f"[{session['username']}@{session['node_id']}] > "
            else:
                prompt = "[visitante] > "
                
            command = input(prompt).strip()
            if not command:
                continue
                
            parts = command.split(' ', 3)
            cmd = parts[0].lower()

            # Comandos de controle
            if cmd in ('quit', 'exit'):
                clear_screen()
                client.logout_all()
                print("👋 Até mais!")
                break
            elif cmd == 'clear':
                clear_screen()
                print("✅ Tela limpa!")
            elif cmd == 'help':
                client.show_help()
                
            # Comandos de autenticação
            elif cmd == 'login':
                if len(parts) < 4:
                    print("❌ Uso: login <usuario> <senha> <porta>")
                else:
                    try:
                        username, password, port = parts[1], parts[2], int(parts[3])
                        if port in (8001, 8002, 8003):
                            client.login(username, password, port)
                        else:
                            print("❌ Porta deve ser 8001, 8002 ou 8003")
                    except ValueError:
                        print("❌ Porta deve ser um número")
                        
            elif cmd == 'logout':
                if len(parts) < 2:
                    print("❌ Uso: logout <porta>")
                else:
                    try:
                        client.logout(int(parts[1]))
                    except ValueError:
                        print("❌ Porta deve ser um número")
                        
            elif cmd == 'logoutall':
                client.logout_all()
                
            elif cmd == 'switch':
                client.switch_user()
                
            # Comandos de mensagens
            elif cmd == 'post':
                if len(parts) < 2:
                    print("❌ Uso: post <mensagem>")
                else:
                    client.post_message(' '.join(parts[1:]), visibility="public")
                    
            elif cmd == 'postpv':
                if len(parts) < 2:
                    print("❌ Uso: postpv <mensagem>")
                else:
                    client.post_message(' '.join(parts[1:]), visibility="private")
                    
            elif cmd == 'read':
                if len(parts) >= 2:
                    try:
                        port = int(parts[1])
                        client.read_messages(port=port)
                    except ValueError:
                        print("❌ Porta deve ser um número")
                else:
                    client.read_messages()
                    
            elif cmd == 'readpub':
                if len(parts) < 2:
                    print("❌ Uso: readpub <porta>")
                else:
                    try:
                        port = int(parts[1])
                        client.read_messages(port=port, public_only=True)
                    except ValueError:
                        print("❌ Porta deve ser um número")
                        
            # Comandos de sistema
            elif cmd == 'status':
                client.show_system_status()
                
            elif cmd == 'simulate':
                client.toggle_offline_simulation()
                
            else:
                print(f"❌ Comando desconhecido: {cmd}. Digite 'help' para ver comandos disponíveis.")
                
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Até mais!")
            break


if __name__ == "__main__":
    main()