import socket
import threading
import json
import time
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Set, Optional
from .message import Message
from .auth import AuthManager


class SimpleHTTPHandler(BaseHTTPRequestHandler):
    """Handler HTTP simplificado que serve arquivos estáticos e APIs"""
    
    def __init__(self, node, *args, **kwargs):
        self.node = node
        super().__init__(*args, **kwargs)
    
    def _set_cors_headers(self):
        """Define headers CORS"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        try:
            self.send_response(200)
            self._set_cors_headers()
            self.end_headers()
        except Exception as e:
            print(f"Erro no OPTIONS: {e}")
    
    def do_GET(self):
        """Handle GET requests - serve arquivos estáticos e APIs"""
        try:
            if self.path == '/' or self.path == '/index.html':
                self.serve_static_file('frontend/index.html', 'text/html')
            elif self.path == '/styles.css':
                self.serve_static_file('frontend/styles.css', 'text/css')
            elif self.path == '/app.js':
                self.serve_static_file('frontend/app.js', 'application/javascript')
            elif self.path == '/api/messages':
                self.handle_get_messages()
            elif self.path == '/api/status':
                self.handle_get_status()
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b'Not Found')
        except Exception as e:
            print(f"Erro no GET: {e}")
            self.send_error_response(str(e))
    
    def serve_static_file(self, file_path, content_type):
        """Serve arquivo estático da pasta frontend"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                self.send_response(200)
                self.send_header('Content-Type', f'{content_type}; charset=utf-8')
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(f'File not found: {file_path}'.encode('utf-8'))
        except Exception as e:
            print(f"Erro ao servir arquivo {file_path}: {e}")
            self.send_error_response(f"Erro ao carregar {file_path}")
    
    def do_POST(self):
        """Handle POST requests - apenas APIs"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
            else:
                data = {}
            
            if self.path == '/api/login':
                self.handle_api_request(data, 'login')
            elif self.path == '/api/logout':
                self.handle_api_request(data, 'logout')
            elif self.path == '/api/post':
                self.handle_api_request(data, 'post_message')
            elif self.path == '/api/toggle_offline':
                self.handle_api_request(data, 'toggle_offline')
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b'API endpoint not found')
                
        except Exception as e:
            print(f"Erro no POST: {e}")
            self.send_error_response(str(e))
    
    def handle_api_request(self, data, action):
        """Processa requisições da API"""
        try:
            data['action'] = action
            response = self.node._process_request(data)
            self.send_json(response)
        except Exception as e:
            print(f"Erro em {action}: {e}")
            self.send_json({'status': 'error', 'message': str(e)})
    
    def handle_get_messages(self):
        """Handle get messages API"""
        try:
            token = self.headers.get('Authorization')
            request = {'action': 'get_messages'}
            if token:
                request['token'] = token
            
            response = self.node._process_request(request)
            self.send_json(response)
        except Exception as e:
            print(f"Erro em get_messages: {e}")
            self.send_json({'status': 'error', 'message': str(e)})
    
    def handle_get_status(self):
        """Handle get status API"""
        try:
            response = self.node._handle_check_status()
            self.send_json(response)
        except Exception as e:
            print(f"Erro em get_status: {e}")
            self.send_json({'status': 'error', 'message': str(e)})
    
    def send_json(self, data):
        """Send JSON response"""
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except Exception as e:
            print(f"Erro ao enviar JSON: {e}")
    
    def send_error_response(self, message):
        """Send error response"""
        try:
            self.send_response(500)
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(f"Erro interno: {message}".encode('utf-8'))
        except:
            pass
    
    def log_message(self, format, *args):
        """Suppress HTTP logs"""
        pass


class Node:
    def __init__(self, node_id: str, port: int, peers: List[int]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.host = 'localhost'
        
        # Estados do nó - CORRIGIDO: cada nó gerencia seu próprio estado
        self.active = False
        self.current_user = None
        self.simulate_offline = False
        self.last_seen_message_count = 0
        self.was_offline = False
        
        # Armazenamento local
        self.messages = []
        self.message_ids = set()
        
        # Sistema de autenticação
        self.auth_manager = AuthManager()
        
        # Controle do servidor
        self.server_socket = None
        self.running = False
        
        # NOVO: Sistema de usuários globais para verificar logins duplicados
        self.global_users = {}  # {username: {'node_id': node_id, 'port': port}}
        
        # Criar pasta logs se não existir
        os.makedirs('logs', exist_ok=True)
        
        # Configurar logging específico para este nó
        self.logger = logging.getLogger(f'Node-{self.node_id}')
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        # Handler para arquivo
        file_handler = logging.FileHandler(f'logs/{self.node_id}.log')
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(f'[{self.node_id}] %(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(f'[{self.node_id}] %(asctime)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        self.logger.propagate = False
    
    def start(self):
        """Inicia o nó"""
        self.running = True
        self.logger.info(f"SERVIDOR INICIADO: {self.node_id} servidor TCP na porta {self.port}")
        
        # Criar socket servidor TCP
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        # Iniciar servidor HTTP (porta TCP + 1000)
        http_port = self.port + 1000
        try:
            def create_handler(*args, **kwargs):
                return SimpleHTTPHandler(self, *args, **kwargs)
            
            self.http_server = HTTPServer((self.host, http_port), create_handler)
            http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            http_thread.start()
            
            self.logger.info(f"SERVIDOR HTTP: Interface web na porta {http_port}")
            print(f"🌐 Interface Web: http://localhost:{http_port}")
        except Exception as e:
            self.logger.error(f"Erro ao iniciar servidor HTTP: {e}")
        
        print(f"🔴 {self.node_id} INATIVO na porta {self.port} (aguardando login)")
        
        # Thread para aceitar conexões TCP
        threading.Thread(target=self._accept_connections, daemon=True).start()
    
    def stop(self):
        """Para o nó"""
        self.running = False
        self.active = False
        
        if self.server_socket:
            self.server_socket.close()
        
        if hasattr(self, 'http_server'):
            self.http_server.shutdown()
            self.http_server.server_close()
        
        self.logger.info(f"SERVIDOR PARADO: {self.node_id} encerrado")
    
    def activate_node(self, username: str):
        """Ativa o nó quando usuário faz login"""
        was_inactive = not self.active
        self.active = True
        self.current_user = username
        
        current_message_count = len(self.messages)
        unread_count = current_message_count - self.last_seen_message_count
        
        self.logger.info(f"NÓ ATIVADO: {self.node_id} ativado por {username}")
        print(f"🟢 {self.node_id} ATIVO com usuário: {username}")
        
        # NOVO: Se o nó estava offline (simulate_offline), sincronizar ao ativar
        if self.was_offline and was_inactive:
            print(f"🔄 {self.node_id} reconectando e sincronizando...")
            self.logger.info(f"RECONEXÃO: {self.node_id} reconectando após período offline")
            
            # Executar sincronização em thread separada para não bloquear o login
            threading.Thread(target=self._sync_missed_messages, daemon=True).start()
            self.was_offline = False
        elif unread_count > 0:
            msg = f"📬 {unread_count} nova{'s' if unread_count > 1 else ''} mensagem{'ns' if unread_count > 1 else ''} não lida{'s' if unread_count > 1 else ''}"
            print(msg)
            self.logger.info(f"MENSAGENS NÃO LIDAS: {unread_count} para {username}")
        
        self.last_seen_message_count = current_message_count
    
    def deactivate_node(self):
        """Desativa o nó quando usuário faz logout"""
        username = self.current_user
        self.active = False
        self.current_user = None
        
        # Remover usuário da lista global
        if username and username in self.global_users:
            del self.global_users[username]
        
        self.logger.info(f"NÓ DESATIVADO: {self.node_id} desativado (logout {username})")
        print(f"🔴 {self.node_id} INATIVO (logout {username})")
    
    def _accept_connections(self):
        """Aceita conexões TCP"""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                threading.Thread(
                    target=self._handle_client, 
                    args=(client_socket,), 
                    daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro ao aceitar conexão: {e}")
    
    def _handle_client(self, client_socket):
        """Processa requisições dos clientes"""
        try:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                return
            
            request = json.loads(data)
            response = self._process_request(request)
            
            client_socket.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Erro ao processar cliente: {e}")
            response = {'status': 'error', 'message': str(e)}
            try:
                client_socket.send(json.dumps(response).encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()
    
    def _process_request(self, request: Dict) -> Dict:
        """Processa diferentes tipos de requisição"""
        action = request.get('action')
        
        # Armazenar token para uso em _handle_get_messages
        if 'token' in request:
            self._current_request_token = request['token']
        else:
            self._current_request_token = None
        
        if action == 'login':
            return self._handle_login(request)
        elif action == 'logout':
            return self._handle_logout(request)
        elif action == 'post_message':
            return self._handle_post_message(request)
        elif action == 'get_messages':
            return self._handle_get_messages()
        elif action == 'check_status':
            return self._handle_check_status()
        elif action == 'get_active_nodes':
            return self._handle_get_active_nodes()
        elif action == 'sync':
            return self._handle_sync(request)
        elif action == 'toggle_offline':
            return self._handle_toggle_offline()
        else:
            return {'status': 'error', 'message': 'Ação inválida'}
    
    def _handle_login(self, request: Dict) -> Dict:
        """Processa login - CORRIGIDO: verificação de usuário duplicado"""
        username = request.get('username')
        password = request.get('password')
        
        self.logger.info(f"TENTATIVA DE LOGIN: {username}")
        
        # CORRIGIDO: Verificar se usuário já está logado em QUALQUER nó
        for peer_port in self.peers:
            try:
                peer_status = self._get_peer_status(peer_port)
                if peer_status and peer_status.get('active') and peer_status.get('user') == username:
                    node_id = peer_status.get('node_id', f'Node{peer_port - 8000}')
                    self.logger.warning(f"LOGIN NEGADO: {username} já conectado em {node_id}")
                    return {
                        'status': 'error', 
                        'message': f'Usuário {username} já está conectado no {node_id} (porta {peer_port})'
                    }
            except:
                pass  # Nó peer não responde, continuar
        
        # Verificar se já está logado neste nó
        if self.current_user == username:
            self.logger.warning(f"LOGIN NEGADO: {username} já conectado neste nó")
            return {
                'status': 'error', 
                'message': f'Usuário {username} já está conectado neste nó'
            }
        
        token = self.auth_manager.login(username, password)
        if token:
            self.activate_node(username)
            self.global_users[username] = {'node_id': self.node_id, 'port': self.port}
            
            self.logger.info(f"LOGIN APROVADO: {username} (Token: {token[:8]}...)")
            return {
                'status': 'success', 
                'token': token, 
                'username': username,
                'node_id': self.node_id,
                'port': self.port
            }
        else:
            self.logger.warning(f"LOGIN NEGADO: Credenciais inválidas para {username}")
            return {'status': 'error', 'message': 'Usuário ou senha inválidos'}
    
    def _handle_logout(self, request: Dict) -> Dict:
        """Processa logout"""
        token = request.get('token')
        
        if not self.auth_manager.is_authenticated(token):
            self.logger.warning("LOGOUT NEGADO: Token inválido")
            return {'status': 'error', 'message': 'Token inválido'}
        
        username = self.auth_manager.get_username(token)
        self.logger.info(f"LOGOUT: {username} desconectando do {self.node_id}")
        
        self.auth_manager.logout(token)
        self.deactivate_node()
        
        return {'status': 'success', 'message': 'Logout realizado com sucesso'}
    
    def _handle_post_message(self, request: Dict) -> Dict:
        """Processa postagem de mensagem - CORRIGIDO: lógica de entrega"""
        token = request.get('token')
        content = request.get('content')
        message_type = request.get('message_type', 'public')
        
        if not self.active:
            self.logger.error("ENVIO NEGADO: Nó está inativo")
            return {'status': 'error', 'message': 'Nó está inativo'}
        
        # CORRIGIDO: Verificar simulação offline apenas DESTE nó
        if self.simulate_offline:
            self.logger.error("ENVIO NEGADO: Nó simulando falha de conexão")
            return {'status': 'error', 'message': 'Erro de envio, conexão do nó foi perdida'}
        
        if not self.auth_manager.is_authenticated(token):
            self.logger.warning("ENVIO NEGADO: Token inválido")
            return {'status': 'error', 'message': 'Token inválido'}
        
        username = self.auth_manager.get_username(token)
        message = Message(content, username, message_type)
        
        # Adicionar mensagem localmente
        self._add_message(message)
        
        type_indicator = "🔒" if message_type == "private" else "🌐"
        self.logger.info(f"MENSAGEM CRIADA: {type_indicator}[{username}] '{content}' (ID: {message.id})")
        
        # CORRIGIDO: Relatório de entrega mais preciso
        delivery_report = self._replicate_message_with_report(message)
        
        self.logger.info(f"REPLICAÇÃO CONCLUÍDA: {delivery_report['message']}")
        
        return {
            'status': 'success',
            'message': 'Mensagem processada',
            'delivery_report': delivery_report
        }
    
    def _handle_get_messages(self) -> Dict:
        """Retorna mensagens baseado na autenticação"""
        request_token = getattr(self, '_current_request_token', None)
        is_authenticated = False
        username = None
        
        # Verificar se há token na requisição atual
        if request_token and self.auth_manager.is_authenticated(request_token):
            is_authenticated = True
            username = self.auth_manager.get_username(request_token)
        
        # Filtrar mensagens baseado na autenticação
        if is_authenticated:
            # Usuário logado: pode ver todas as mensagens (públicas + privadas)
            messages_data = [msg.to_dict() for msg in self.messages]
            self.logger.info(f"LEITURA AUTENTICADA: {len(messages_data)} mensagens enviadas para {username}")
        else:
            # Usuário não logado: apenas mensagens públicas
            public_messages = [msg for msg in self.messages if msg.message_type == "public"]
            messages_data = [msg.to_dict() for msg in public_messages]
            self.logger.info(f"LEITURA PÚBLICA: {len(messages_data)} mensagens públicas")
        
        return {
            'status': 'success', 
            'messages': messages_data,
            'authenticated': is_authenticated,
            'node_id': self.node_id
        }
    
    def _handle_check_status(self) -> Dict:
        """Retorna status do nó"""
        return {
            'status': 'success',
            'node_id': self.node_id,
            'port': self.port,
            'active': self.active,
            'user': self.current_user,
            'simulate_offline': self.simulate_offline
        }
    
    def _handle_get_active_nodes(self) -> Dict:
        """Retorna lista de nós ativos"""
        active_nodes = self._get_active_nodes_info()
        return {'status': 'success', 'active_nodes': active_nodes}
    
    def _handle_toggle_offline(self) -> Dict:
        """Liga/desliga simulação offline - CORRIGIDO: apenas este nó"""
        self.simulate_offline = not self.simulate_offline
        status = "ATIVADA" if self.simulate_offline else "DESATIVADA"
        
        if self.simulate_offline:
            self.was_offline = True
            print(f"⚠️  {self.node_id} simulando FALHA DE CONEXÃO")
            self.logger.warning(f"SIMULAÇÃO OFFLINE: {self.node_id} iniciou simulação de falha")
        else:
            current_count = len(self.messages)
            unread_count = current_count - self.last_seen_message_count
            
            print(f"✅ {self.node_id} conexão RESTAURADA")
            self.logger.info(f"SIMULAÇÃO ONLINE: {self.node_id} restaurou conexão")
            
            if unread_count > 0:
                msg = f"📬 {unread_count} nova{'s' if unread_count > 1 else ''} mensagem{'ns' if unread_count > 1 else ''} não lida{'s' if unread_count > 1 else ''}"
                print(msg)
                self.logger.info(f"MENSAGENS PERDIDAS: {unread_count} mensagens durante offline")
                self.last_seen_message_count = current_count
        
        return {
            'status': 'success',
            'simulate_offline': self.simulate_offline,
            'message': f'Simulação de falha: {status}'
        }
    
    def _handle_sync(self, request: Dict) -> Dict:
        """Processa sincronização com outros nós"""
        if not self.active or self.simulate_offline:
            self.logger.debug("SYNC NEGADO: Nó indisponível")
            return {'status': 'error', 'message': 'Nó indisponível'}
        
        peer_messages = request.get('messages', [])
        new_count = 0
        
        for msg_data in peer_messages:
            message = Message.from_dict(msg_data)
            if self._add_message(message):
                new_count += 1
                print(f"\n🔔 [{self.node_id}] Nova mensagem de {message.author}: {message.content}")
                self.logger.info(f"MENSAGEM RECEBIDA: [{message.author}] '{message.content}' (ID: {message.id})")
        
        if new_count > 0:
            self.logger.info(f"SYNC REALIZADO: {new_count} novas mensagens recebidas")
        
        return {'status': 'success'}
    
    def _add_message(self, message: Message) -> bool:
        """Adiciona mensagem se não existir"""
        if message.id not in self.message_ids:
            self.messages.append(message)
            self.message_ids.add(message.id)
            # Ordena mensagens por timestamp para consistência eventual
            self.messages.sort(key=lambda m: m.timestamp)
            return True
        return False
    
    def _replicate_message_with_report(self, message: Message) -> Dict:
        """Replica mensagem para outros nós e retorna relatório de entrega - CORRIGIDO"""
        report = {
            'sent_to': [],
            'failed_to': [],
            'offline_nodes': [],
            'total_possible_recipients': 0
        }
        
        # Verificar quantos nós estão ativos (excluindo este nó)
        active_peers = []
        for peer_port in self.peers:
            try:
                peer_info = self._get_peer_status(peer_port)
                if peer_info and peer_info.get('active') and not peer_info.get('simulate_offline'):
                    active_peers.append({
                        'port': peer_port,
                        'user': peer_info.get('user'),
                        'node_id': peer_info.get('node_id')
                    })
                elif peer_info and peer_info.get('active') and peer_info.get('simulate_offline'):
                    report['offline_nodes'].append({
                        'port': peer_port,
                        'user': peer_info.get('user'),
                        'node_id': peer_info.get('node_id')
                    })
            except Exception as e:
                self.logger.debug(f"Não foi possível conectar com peer {peer_port}: {e}")
        
        report['total_possible_recipients'] = len(active_peers)
        
        # CORRIGIDO: Mensagens baseadas nos estados reais
        if len(active_peers) == 0:
            if len(report['offline_nodes']) > 0:
                offline_users = [f"{n['user']}({n['port']})" for n in report['offline_nodes']]
                return {
                    'message': f'Mensagem enviada, mas {", ".join(offline_users)} está simulando falha',
                    'type': 'recipients_offline'
                }
            else:
                return {
                    'message': 'Mensagem enviada e não recebida, não encontrei nenhum outro nó ativo',
                    'type': 'no_recipients'
                }
        
        # Tentar enviar para nós ativos
        for peer_info in active_peers:
            try:
                response = self._send_to_peer(peer_info['port'], {
                    'action': 'sync',
                    'messages': [message.to_dict()]
                })
                
                if response.get('status') == 'success':
                    report['sent_to'].append(peer_info)
                else:
                    report['failed_to'].append(peer_info)
                    
            except Exception as e:
                self.logger.error(f"ERRO DE REPLICAÇÃO para {peer_info['port']}: {e}")
                report['failed_to'].append(peer_info)
        
        # Gerar mensagem final baseada nos resultados
        sent_count = len(report['sent_to'])
        failed_count = len(report['failed_to'])
        
        if sent_count == len(active_peers) and failed_count == 0:
            if sent_count == 1:
                user_info = f"{report['sent_to'][0]['user']}({report['sent_to'][0]['port']})"
                return {
                    'message': f'Mensagem enviada, recebida por {user_info}',
                    'type': 'all_received'
                }
            else:
                users_info = [f"{r['user']}({r['port']})" for r in report['sent_to']]
                return {
                    'message': 'Mensagem enviada com sucesso, todos receberam',
                    'type': 'all_received'
                }
        elif sent_count > 0:
            sent_users = [f"{r['user']}({r['port']})" for r in report['sent_to']]
            failed_users = [f"{r['user']}({r['port']})" for r in report['failed_to']]
            
            if failed_count > 0:
                return {
                    'message': f'Mensagem enviada, recebida por {", ".join(sent_users)} mas não por {", ".join(failed_users)}',
                    'type': 'partial_received'
                }
            else:
                return {
                    'message': f'Mensagem enviada, recebida por {", ".join(sent_users)}',
                    'type': 'all_received'
                }
        else:
            return {
                'message': 'Mensagem não foi entregue a nenhum nó ativo',
                'type': 'delivery_failed'
            }
    
    def _get_active_nodes_info(self) -> List[Dict]:
        """Retorna informações dos nós ativos"""
        active_nodes = []
        
        # Incluir este nó se ativo
        if self.active:
            active_nodes.append({
                'node_id': self.node_id,
                'port': self.port,
                'user': self.current_user,
                'active': True,
                'simulate_offline': self.simulate_offline
            })
        
        # Verificar peers
        for peer_port in self.peers:
            try:
                peer_info = self._get_peer_status(peer_port)
                if peer_info and peer_info.get('active'):
                    active_nodes.append(peer_info)
            except:
                pass
        
        return active_nodes
    
    def _get_peer_status(self, peer_port: int) -> Optional[Dict]:
        """Obtém status de um peer"""
        try:
            response = self._send_to_peer(peer_port, {'action': 'check_status'})
            if response.get('status') == 'success':
                return response
        except:
            pass
        return None
    
    def _send_to_peer(self, peer_port: int, data: Dict) -> Dict:
        """Envia dados para outro nó"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        
        try:
            sock.connect((self.host, peer_port))
            sock.send(json.dumps(data).encode('utf-8'))
            response = sock.recv(4096).decode('utf-8')
            return json.loads(response)
        finally:
            sock.close()
    
    def get_status(self) -> Dict:
        """Retorna status completo do nó"""
        return {
            'node_id': self.node_id,
            'port': self.port,
            'running': self.running,
            'active': self.active,
            'current_user': self.current_user,
            'messages_count': len(self.messages),
            'simulate_offline': self.simulate_offline
        }