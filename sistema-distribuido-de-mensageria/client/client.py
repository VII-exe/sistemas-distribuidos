# client.py - cleaned single-definition client with helper and CLI
import sys
import os
import socket
import json
import time
import threading
from typing import Dict, Optional, List

# optional path adjust if project layout requires it
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
        print(f"❌ Falha no login: {resp.get('message', 'Erro desconhecido')}")
        return False

    def logout(self, port: int) -> bool:
        if port not in self.logged_users:
            print("❌ Você não está logado neste nó!")
            return False
        session = self.logged_users[port]
        resp = self._send_request(port, {'action': 'logout', 'token': session.get('token')})
        if resp.get('status') == 'success':
            username = session.get('username')
            node_id = session.get('node_id')
            del self.logged_users[port]
            if self.current_session == port:
                self.current_session = next(iter(self.logged_users.keys())) if self.logged_users else None
            print(f"✅ Logout realizado! {username} desconectado do {node_id}")
            return True
        print(f"❌ Erro no logout: {resp.get('message', 'Erro desconhecido')}")
        return False

    def _show_loading(self):
        chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        i = 0
        while not self._stop_loading:
            print(f"\r📤 Enviando... {chars[i % len(chars)]}", end="", flush=True)
            i += 1
            time.sleep(0.1)
        print("\r", end="", flush=True)

    def post_message(self, content: str, visibility: str = "public") -> bool:
        if self.current_session is None:
            print("❌ Você precisa fazer login primeiro!")
            return False
        session = self.logged_users[self.current_session]
        req = {'action': 'post_message', 'token': session.get('token'), 'content': content, 'visibility': visibility}
        print(f"📤 Enviando mensagem de {session['username']} via {session['node_id']}...")
        self._stop_loading = False
        t = threading.Thread(target=self._show_loading, daemon=True)
        t.start()
        resp = self._send_request(self.current_session, req, timeout=30)
        self._stop_loading = True
        t.join(timeout=0.2)
        if resp.get('status') == 'success':
            print(f"\n✅ {resp.get('delivery_report', {}).get('message', 'Mensagem enviada')}")
            return True
        print(f"\n❌ {resp.get('message', 'Erro ao enviar mensagem')}")
        return False

    def read_messages(self, port: Optional[int] = None, public_only: bool = False) -> bool:
        if port is None:
            if self.current_session is None:
                print("❌ Você precisa fazer login primeiro!")
                return False
            port = self.current_session
        req = {'action': 'get_messages', 'public_only': public_only}
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
                    print(f"[{timestamp}] {author}: {content}")
                print("-" * 60)
                print(f"Total: {len(messages)} mensagens\n")
            else:
                print("📭 Nenhuma mensagem encontrada\n")
            return True
        print(f"❌ Erro ao ler mensagens: {resp.get('message', 'Erro desconhecido')}")
        return False

    def _get_all_active_nodes(self) -> List[Dict]:
        active = []
        for p in [8001, 8002, 8003]:
            try:
                resp = self._send_request(p, {'action': 'get_active_nodes'}, timeout=2)
                if resp.get('status') == 'success':
                    for n in resp.get('active_nodes', []):
                        if n not in active:
                            active.append(n)
            except Exception:
                pass
        return active

    def _get_node_status(self, port: int) -> Optional[Dict]:
        try:
            resp = self._send_request(port, {'action': 'check_status'}, timeout=2)
            if resp.get('status') == 'success':
                return resp
        except Exception:
            pass
        return None

    def switch_user(self):
        if not self.logged_users:
            print("❌ Nenhum usuário logado!")
            return
        print("\n👥 USUÁRIOS LOGADOS:")
        print("-" * 50)
        for i, (port, s) in enumerate(self.logged_users.items(), start=1):
            node_status = self._get_node_status(port)
            if node_status and node_status.get('active'):
                icon = "🟢" if not node_status.get('simulate_offline') else "🟡⚠️"
            else:
                icon = "🔴"
            cur = " ← ATUAL" if port == self.current_session else ""
            print(f"{i}. {icon} {s['username']} @ {s['node_id']} (porta {port}){cur}")
        print("-" * 50)
        try:
            choice = input("Escolha o número do usuário para alternar (0 para cancelar): ").strip()
            if choice == '0' or choice == '':
                return
            idx = int(choice) - 1
            ports = list(self.logged_users.keys())
            if 0 <= idx < len(ports):
                old = self.logged_users.get(self.current_session, {}).get('username', '?')
                new = self.logged_users[ports[idx]]['username']
                self.current_session = ports[idx]
                print(f"✅ Alternado de {old} para {new}")
            else:
                print("❌ Opção inválida!")
        except ValueError:
            print("❌ Digite um número válido!")

    def toggle_offline_simulation(self):
        if self.current_session is None:
            print("❌ Você precisa estar logado primeiro!")
            return
        resp = self._send_request(self.current_session, {'action': 'toggle_offline'})
        if resp.get('status') == 'success':
            print(f"✅ {resp.get('message')}")
        else:
            print(f"❌ Erro: {resp.get('message', 'Erro desconhecido')}")

    def show_system_status(self):
        clear_screen()
        print("📊 STATUS COMPLETO DO SISTEMA")
        print("=" * 60)
        active_nodes = self._get_all_active_nodes()
        for port in [8001, 8002, 8003]:
            node_status = self._get_node_status(port)
            if node_status:
                if node_status.get('active'):
                    if node_status.get('simulate_offline'):
                        icon, text = "🟡⚠️", "ATIVO (simulando falha)"
                    else:
                        icon, text = "🟢", "ATIVO"
                    user = node_status.get('user', 'Desconhecido')
                    our_login = " (SEU LOGIN)" if port in self.logged_users else ""
                    cur = " ← SESSÃO ATUAL" if port == self.current_session else ""
                else:
                    icon, text, user, our_login, cur = "🔴", "INATIVO", "---", "", ""
                node_id = node_status.get('node_id', f'Node{port - 8000}')
            else:
                icon, text, user, our_login, cur = "❌", "DESCONECTADO", "---", "", ""
                node_id = f'Node{port - 8000}'
            print(f"{icon} {node_id} (:{port}) - {text}")
            print(f"   Usuário: {user}{our_login}{cur}\n")
        print("=" * 60)
        total_active = len([n for n in active_nodes if not n.get('simulate_offline', False)])
        total_offline = len([n for n in active_nodes if n.get('simulate_offline', False)])
        print(f"📈 Resumo: {total_active} nós ativos, {total_offline} simulando falha")
        print(f"👤 Suas sessões: {len(self.logged_users)} ativas\n")

    def show_help(self):
        clear_screen()
        print("📖 COMANDOS DISPONÍVEIS")
        print("=" * 50)
        print("🔐 AUTENTICAÇÃO:")
        print("  login <usuario> <senha> <porta>  - Fazer login em nó específico")
        print("  logout <porta>                   - Fazer logout de nó específico")
        print("  switch                           - Alternar entre usuários logados")
        print()
        print("💬 MENSAGENS:")
        print("  post <mensagem>                  - Enviar mensagem (sessão atual)")
        print("  postpv <mensagem>                - Enviar mensagem privada")
        print("  read                             - Ler mensagens (sessão atual)")
        print("  readpub <porta>                  - Ler mensagens públicas de um nó")
        print()
        print("🔧 SISTEMA:")
        print("  status                           - Ver status de todos os nós")
        print("  simulate                         - Simular falha no nó atual")
        print("  clear                            - Limpar tela")
        print("  help                             - Mostrar esta ajuda")
        print("  quit                             - Sair do cliente")
        print()
        print("💡 DICAS: Portas disponíveis: 8001, 8002, 8003")
        print()


def main():
    client = MessageClient()
    clear_screen()
    print("🎯" + "=" * 58 + "🎯")
    print("🎯  SISTEMA DE MENSAGENS DISTRIBUÍDAS - CLIENTE AVANÇADO  🎯")
    print("🎯" + "=" * 58 + "🎯\n")
    print("🚀 Digite 'help' para ver todos os comandos\n")

    while True:
        try:
            if client.current_session:
                s = client.logged_users[client.current_session]
                prompt = f"[{s['username']}@{s['node_id']}] > "
            else:
                prompt = "[visitante] > "
            command = input(prompt).strip()
            if not command:
                continue
            parts = command.split(' ', 3)
            cmd = parts[0].lower()

            if cmd in ('quit', 'exit'):
                clear_screen()
                print("👋 Fazendo logout de todas as sessões...")
                for p in list(client.logged_users.keys()):
                    client.logout(p)
                print("👋 Até mais!")
                break

            if cmd == 'clear':
                clear_screen()
                print("✅ Tela limpa!")
            elif cmd == 'help':
                client.show_help()
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
            elif cmd == 'switch':
                client.switch_user()
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
            elif cmd == 'status':
                client.show_system_status()
            elif cmd == 'simulate':
                client.toggle_offline_simulation()
            else:
                print(f"❌ Comando desconhecido: {cmd}. Digite 'help'.")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Até mais!")
            break


if __name__ == "__main__":
    main()