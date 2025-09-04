import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import socket
import json
import time
import threading
from typing import Dict, Optional, List

def clear_screen():
    """Clear terminal screen on Windows and Unix-like systems."""
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except Exception:
        pass


class MessageClient:
    def __init__(self):
        self.host = 'localhost'
        self.logged_users: Dict[int, Dict] = {}  # {porta: {'username': '', 'token': '', 'node_id': ''}}
        self.current_session: Optional[int] = None  # Sessão ativa atual
        self._stop_loading = False

    def _send_request(self, port: int, request: Dict, timeout: int = 10) -> Dict:
        """Envia requisição para um nó específico"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self.host, port))

            sock.send(json.dumps(request).encode('utf-8'))
            response = sock.recv(4096).decode('utf-8')

            return json.loads(response)
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
        request = {
            'action': 'login',
            'username': username,
            'password': password
        }

        print(f"🔐 Fazendo login como {username} no nó porta {port}...")
        response = self._send_request(port, request)

        if response.get('status') == 'success':
            # Salvar sessão
            self.logged_users[port] = {
                'username': username,
                'token': response.get('token'),
                'node_id': response.get('node_id'),
                'port': port
            }

            # Definir como sessão atual se for a primeira
            if self.current_session is None:
                self.current_session = port

            print(f"✅ Login bem-sucedido! {username} conectado ao {response.get('node_id')} (porta {port})")
            return True
        else:
            print(f"❌ Falha no login: {response.get('message', 'Erro desconhecido')}")
            return False

    def logout(self, port: int) -> bool:
        """Faz logout de um nó específico"""
        if port not in self.logged_users:
            print("❌ Você não está logado neste nó!")
            return False

        session = self.logged_users[port]
        request = {
            'action': 'logout',
            'token': session['token']
        }

        response = self._send_request(port, request)

        if response.get('status') == 'success':
            username = session['username']
            node_id = session['node_id']

            # Remover sessão
            del self.logged_users[port]

            # Atualizar sessão atual se necessário
            if self.current_session == port:
                self.current_session = next(iter(self.logged_users.keys())) if self.logged_users else None

            print(f"✅ Logout realizado! {username} desconectado do {node_id}")
            return True
        else:
            print(f"❌ Erro no logout: {response.get('message', 'Erro desconhecido')}")
            return False

    def post_message(self, content: str) -> bool:
        """Posta mensagem usando a sessão atual"""
        if self.current_session is None:
            print("❌ Você precisa fazer login primeiro!")
            return False

        session = self.logged_users[self.current_session]
        request = {
            'action': 'post_message',
            'token': session['token'],
            'content': content
        }

        print(f"📤 Enviando mensagem de {session['username']} via {session['node_id']}...")

        # Mostrar animação de carregamento
        loading_thread = threading.Thread(target=self._show_loading, daemon=True)
        self._stop_loading = False
        loading_thread.start()

        response = self._send_request(self.current_session, request, timeout=30)

        # Parar animação
        self._stop_loading = True
        time.sleep(0.1)

        if response.get('status') == 'success':
            delivery_report = response.get('delivery_report', {})
            print(f"\n✅ {delivery_report.get('message', 'Mensagem enviada')}")
            return True
        else:
            print(f"\n❌ {response.get('message', 'Erro ao enviar mensagem')}")
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

    def read_messages(self) -> bool:
        """Lê mensagens usando a sessão atual"""
        if self.current_session is None:
            print("❌ Você precisa fazer login primeiro!")
            return False

        session = self.logged_users[self.current_session]
        request = {'action': 'get_messages'}

        response = self._send_request(self.current_session, request)

        if response.get('status') == 'success':
            messages = response.get('messages', [])
            if messages:
                print(f"\n📋 MURAL ({session['node_id']}):")
                print("-" * 60)
                for msg in messages:
                    author = msg.get('author', 'Desconhecido')
                    content = msg.get('content', '')
                    timestamp = time.strftime('%H:%M:%S', time.localtime(msg.get('timestamp', 0)))
                    print(f"[{timestamp}] {author}: {content}")
                print("-" * 60)
                print(f"Total: {len(messages)} mensagens\n")
            else:
                print("📭 Nenhuma mensagem encontrada\n")
            return True
        else:
            print(f"❌ Erro ao ler mensagens: {response.get('message', 'Erro desconhecido')}")
            return False

    def switch_user(self):
        """Permite alternar entre usuários logados"""
        if not self.logged_users:
            print("❌ Nenhum usuário logado!")
            return

        print("\n👥 USUÁRIOS LOGADOS:")
        print("-" * 50)

        active_nodes = self._get_all_active_nodes()

        for i, (port, session) in enumerate(self.logged_users.items(), 1):
            # Verificar se nó está ativo
            node_status = self._get_node_status(port)

            if node_status and node_status.get('active'):
                status_icon = "🟢"
                if node_status.get('simulate_offline'):
                    status_icon = "🟡⚠️"
            else:
                status_icon = "🔴"

            current_marker = " ← ATUAL" if port == self.current_session else ""

            print(f"{i}. {status_icon} {session['username']} @ {session['node_id']} (porta {port}){current_marker}")

        print("-" * 50)

        # Mostrar outros nós ativos (sem login nosso)
        other_active = []
        for node_info in active_nodes:
            if node_info['port'] not in self.logged_users:
                status_icon = "🟢"
                if node_info.get('simulate_offline'):
                    status_icon = "🟡⚠️"
                other_active.append(f"{status_icon} {node_info.get('user','?')} @ {node_info.get('node_id','?')} (porta {node_info.get('port')})")

        if other_active:
            print("👥 OUTROS USUÁRIOS ONLINE:")
            for user_info in other_active:
                print(f"   {user_info}")
            print("-" * 50)

        try:
            choice = input("Escolha o número do usuário para alternar (0 para cancelar): ").strip()

            if choice == '0':
                return

            choice_num = int(choice)
            if 1 <= choice_num <= len(self.logged_users):
                port = list(self.logged_users.keys())[choice_num - 1]
                old_session = self.logged_users.get(self.current_session, {})
                new_session = self.logged_users[port]

                self.current_session = port
                print(f"✅ Alternado de {old_session.get('username', '?')} para {new_session['username']} ({new_session['node_id']})")
            else:
                print("❌ Opção inválida!")

        except ValueError:
            print("❌ Digite um número válido!")

    def _get_all_active_nodes(self) -> List[Dict]:
        """Obtém lista de todos os nós ativos"""
        active_nodes: List[Dict] = []
        ports = [8001, 8002, 8003]

        for port in ports:
            try:
                response = self._send_request(port, {'action': 'get_active_nodes'}, timeout=2)
                if response.get('status') == 'success':
                    nodes = response.get('active_nodes', [])
                    for node in nodes:
                        if node not in active_nodes:
                            active_nodes.append(node)
            except Exception:
                pass

        return active_nodes

    def _get_node_status(self, port: int) -> Optional[Dict]:
        """Obtém status de um nó específico"""
        try:
            response = self._send_request(port, {'action': 'check_status'}, timeout=2)
            if response.get('status') == 'success':
                return response
        except Exception:
            pass
        return None

    def toggle_offline_simulation(self):
        """Liga/desliga simulação de falha no nó atual"""
        if self.current_session is None:
            print("❌ Você precisa estar logado primeiro!")
            return

        response = self._send_request(self.current_session, {'action': 'toggle_offline'})

        if response.get('status') == 'success':
            print(f"✅ {response.get('message')}")
        else:
            print(f"❌ Erro: {response.get('message', 'Erro desconhecido')}")

    def show_system_status(self):
        """Mostra status completo do sistema"""
        clear_screen()
        print("\n📊 STATUS COMPLETO DO SISTEMA:")
        print("=" * 60)

        active_nodes = self._get_all_active_nodes()
        all_ports = [8001, 8002, 8003]

        for port in all_ports:
            node_status = self._get_node_status(port)

            if node_status:
                if node_status.get('active'):
                    if node_status.get('simulate_offline'):
                        status_icon = "🟡⚠️"
                        status_text = "ATIVO (simulando falha)"
                    else:
                        status_icon = "🟢"
                        status_text = "ATIVO"

                    user = node_status.get('user', 'Desconhecido')
                    our_login = " (SEU LOGIN)" if port in self.logged_users else ""
                    current_marker = " ← SESSÃO ATUAL" if port == self.current_session else ""

                else:
                    status_icon = "🔴"
                    status_text = "INATIVO"
                    user = "---"
                    our_login = ""
                    current_marker = ""

                node_id = node_status.get('node_id', f'Node{port-8000}')
            else:
                status_icon = "❌"
                status_text = "DESCONECTADO"
                user = "---"
                our_login = ""
                current_marker = ""
                node_id = f"Node{port-8000}"

            print(f"{status_icon} {node_id} (:{port}) - {status_text}")
            print(f"   Usuário: {user}{our_login}{current_marker}")
            print()

        print("=" * 60)

        total_active = len([n for n in active_nodes if not n.get('simulate_offline', False)])
        total_offline_sim = len([n for n in active_nodes if n.get('simulate_offline', False)])

        print(f"📈 Resumo: {total_active} nós ativos, {total_offline_sim} simulando falha")
        print(f"👤 Suas sessões: {len(self.logged_users)} ativas")
        print()
        print("💡 Digite qualquer comando para continuar...")
        print()

    def show_help(self):
        """Mostra comandos disponíveis"""
        clear_screen()
        print("\n📖 COMANDOS DISPONÍVEIS")
        print("=" * 50)
        print("🔐 AUTENTICAÇÃO:")
        print("  login <usuario> <senha> <porta>  - Fazer login em nó específico")
        print("  logout <porta>                   - Fazer logout de nó específico")
        print("  switch                           - Alternar entre usuários logados")
        print()
        print("💬 MENSAGENS:")
        print("  post <mensagem>                  - Enviar mensagem (sessão atual)")
        print("  read                             - Ler mensagens (sessão atual)")
        print()
        print("🔧 SISTEMA:")
        print("  status                           - Ver status de todos os nós")
        print("  simulate                         - Simular falha no nó atual")
        print("  clear                            - Limpar tela")
        print("  help                             - Mostrar esta ajuda")
        print("  quit                             - Sair do cliente")
        print()
        print("🔐 USUÁRIOS DISPONÍVEIS:")
        print("  admin/admin123, user1/password1, user2/password2, test/test")
        print()
        print("💡 DICAS:")
        print("  - Faça login em múltiplos nós para simular conversa")
        print("  - Use 'switch' para alternar entre suas sessões")
        print("  - Use 'simulate' para testar falhas de conexão")
        print("  - Portas disponíveis: 8001, 8002, 8003")
        print("  - O sistema mostra mensagens não lidas ao fazer login")
        print()


def main():
    client = MessageClient()

    clear_screen()
    print("🎯" + "=" * 58 + "🎯")
    print("🎯  SISTEMA DE MENSAGENS DISTRIBUÍDAS - CLIENTE AVANÇADO  🎯")
    print("🎯" + "=" * 58 + "🎯")
    print()
    print("💡 Funcionalidades implementadas:")
    print("   ✅ Nós inativos por padrão (ativam com login)")
    print("   ✅ Contador de mensagens não lidas")
    print("   ✅ Detecção de perda de conexão após envio")
    print("   ✅ Usuário único por nó")
    print("   ✅ Feedback detalhado de entrega")
    print("   ✅ Múltiplas sessões simultâneas")
    print("   ✅ Simulação de falhas de conexão")
    print("   ✅ Limpeza automática de tela")
    print("   ✅ Sistema de presença em tempo real")
    print()
    print("🚀 Digite 'help' para ver todos os comandos")
    print("🔗 Comece com: login <usuario> <senha> <porta>")
    print()

    while True:
        try:
            # Mostrar prompt com sessão atual
            if client.current_session:
                session = client.logged_users[client.current_session]
                prompt = f"[{session['username']}@{session['node_id']}] > "
            else:
                prompt = "[sem login] > "

            command = input(prompt).strip()

            if not command:
                continue

            parts = command.split(' ', 3)
            cmd = parts[0].lower()

            if cmd in ['quit', 'exit']:
                clear_screen()
                print("👋 Fazendo logout de todas as sessões...")
                # Logout de todas as sessões ativas
                for port in list(client.logged_users.keys()):
                    client.logout(port)
                print("👋 Até mais!")
                break

            elif cmd == 'clear':
                clear_screen()
                print("✅ Tela limpa!")

            elif cmd == 'help':
                client.show_help()

            elif cmd == 'login':
                if len(parts) < 4:
                    print("❌ Uso: login <usuario> <senha> <porta>")
                    print("   Exemplo: login admin admin123 8001")
                else:
                    try:
                        username, password, port_str = parts[1], parts[2], parts[3]
                        port = int(port_str)
                        if port in [8001, 8002, 8003]:
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
                        port = int(parts[1])
                        client.logout(port)
                    except ValueError:
                        print("❌ Porta deve ser um número")

            elif cmd == 'switch':
                client.switch_user()

            elif cmd == 'post':
                if len(parts) < 2:
                    print("❌ Uso: post <mensagem>")
                else:
                    message = ' '.join(parts[1:])
                    client.post_message(message)

            elif cmd == 'read':
                client.read_messages()

            elif cmd == 'status':
                client.show_system_status()

            elif cmd == 'simulate':
                client.toggle_offline_simulation()

            else:
                print(f"❌ Comando desconhecido: {cmd}")
                print("💡 Digite 'help' para ver os comandos disponíveis")

        except KeyboardInterrupt:
            print("\n👋 Até mais!")
            break
        except EOFError:
            print("\n👋 Até mais!")
            break


if __name__ == "__main__":
    main()