import socket
import threading
import json
import time
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Optional
from .message import Message
from .auth import AuthManager


class SimpleHTTPHandler(BaseHTTPRequestHandler):
    """Handler HTTP simplificado"""
    
    def __init__(self, node, *args, **kwargs):
        self.node = node
        super().__init__(*args, **kwargs)
    
    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    def do_GET(self):
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
    
    def serve_static_file(self, file_path, content_type):
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
            print(f"Erro ao servir arquivo: {e}")
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
            else:
                data = {}
            
            if self.path == '/api/login':
                data['action'] = 'login'
                response = self.node._process_request(data)
                self.send_json(response)
            elif self.path == '/api/logout':
                data['action'] = 'logout'
                response = self.node._process_request(data)
                self.send_json(response)
            elif self.path == '/api/post':
                data['action'] = 'post_message'
                response = self.node._process_request(data)
                self.send_json(response)
            elif self.path == '/api/toggle_offline':
                data['action'] = 'toggle_offline'
                response = self.node._process_request(data)
                self.send_json(response)
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
                
        except Exception as e:
            print(f"Erro no POST: {e}")
    
    def handle_get_messages(self):
        try:
            token = self.headers.get('Authorization')
            request = {'action': 'get_messages'}
            if token:
                request['token'] = token
            response = self.node._process_request(request)
            self.send_json(response)
        except Exception as e:
            self.send_json({'status': 'error', 'message': str(e)})
    
    def handle_get_status(self):
        try:
            response = self.node._handle_check_status()
            self.send_json(response)
        except Exception as e:
            self.send_json({'status': 'error', 'message': str(e)})
    
    def send_json(self, data):
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except Exception as e:
            print(f"Erro ao enviar JSON: {e}")
    
    def log_message(self, format, *args):
        pass  # Suprimir logs HTTP


class Node:
    def __init__(self, node_id: str, port: int, peers: List[int]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.host = 'localhost'
        
        # Estados SIMPLES do nó
        self.active = False
        self.current_user = None
        self.simulate_offline = False
        
        # Armazenamento local - MURAL
        self.messages = []
        self.message_ids = set()
        
        # Sistema de autenticação básica
        self.auth_manager = AuthManager()
        
        # Controle do servidor
        self.server_socket = None
        self.running = False
        
        # Setup logging simples
        self._setup_logging()
    
    def _setup_logging(self):
        os.makedirs('logs', exist_ok=True)
        self.logger = logging.getLogger(f'Node-{self.node_id}')
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        file_handler = logging.FileHandler(f'logs/{self.node_id}.log')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(f'[{self.node_id}] %(asctime)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.propagate = False
    
    def start(self):
        """Inicia o nó"""
        self.running = True
        self.logger.info(f"INICIANDO: {self.node_id} na porta {self.port}")
        
        # Servidor TCP
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        # Servidor HTTP
        http_port = self.port + 1000
        try:
            def create_handler(*args, **kwargs):
                return SimpleHTTPHandler(self, *args, **kwargs)
            
            self.http_server = HTTPServer((self.host, http_port), create_handler)
            http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            http_thread.start()
            
            print(f"🌐 {self.node_id}: http://localhost:{http_port}")
        except Exception as e:
            self.logger.error(f"Erro HTTP: {e}")
        
        print(f"🔴 {self.node_id} INATIVO (porta {self.port})")
        
        # Thread TCP
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
        
        self.logger.info(f"PARADO: {self.node_id}")
    
    def _accept_connections(self):
        """Aceita conexões TCP"""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True).start()
            except Exception:
                break
    
    def _handle_client(self, client_socket):
        """Processa requisições TCP"""
        try:
            data = client_socket.recv(4096).decode('utf-8')
            if data:
                request = json.loads(data)
                response = self._process_request(request)
                client_socket.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Erro cliente: {e}")
        finally:
            client_socket.close()
    
    def _process_request(self, request: Dict) -> Dict:
        """Router de requisições"""
        action = request.get('action')
        
        if action == 'login':
            return self._handle_login(request)
        elif action == 'logout':
            return self._handle_logout(request)
        elif action == 'post_message':
            return self._handle_post_message(request)
        elif action == 'get_messages':
            return self._handle_get_messages(request)
        elif action == 'check_status':
            return self._handle_check_status()
        elif action == 'sync':
            return self._handle_sync(request)
        elif action == 'toggle_offline':
            return self._handle_toggle_offline()
        else:
            return {'status': 'error', 'message': 'Ação inválida'}
    
    def _handle_login(self, request: Dict) -> Dict:
        """Login básico com verificação simples"""
        username = request.get('username')
        password = request.get('password')
        
        self.logger.info(f"LOGIN: {username}")
        
        # Verificar se já está logado NESTE nó
        if self.current_user == username:
            return {'status': 'error', 'message': f'Usuário {username} já logado neste nó'}
        
        # Verificar se está logado em OUTROS nós (verificação simples)
        for peer_port in self.peers:
            if self._is_user_logged_in_peer(peer_port, username):
                return {
                    'status': 'error', 
                    'message': f'Usuário {username} já está conectado em outro nó'
                }
        
        token = self.auth_manager.login(username, password)
        if token:
            self.active = True
            self.current_user = username
            
            self.logger.info(f"LOGIN OK: {username}")
            print(f"🟢 {self.node_id} ATIVO - {username}")
            
            return {
                'status': 'success', 
                'token': token, 
                'username': username,
                'node_id': self.node_id
            }
        else:
            return {'status': 'error', 'message': 'Credenciais inválidas'}
    
    def _handle_logout(self, request: Dict) -> Dict:
        """Logout simples"""
        token = request.get('token')
        
        if not self.auth_manager.is_authenticated(token):
            return {'status': 'error', 'message': 'Token inválido'}
        
        username = self.auth_manager.get_username(token)
        self.auth_manager.logout(token)
        
        self.active = False
        self.current_user = None
        
        self.logger.info(f"LOGOUT: {username}")
        print(f"🔴 {self.node_id} INATIVO")
        
        return {'status': 'success', 'message': 'Logout OK'}
    
    def _handle_post_message(self, request: Dict) -> Dict:
        """Posta mensagem e replica"""
        token = request.get('token')
        content = request.get('content')
        message_type = request.get('message_type', 'public')
        
        if not self.active:
            return {'status': 'error', 'message': 'Nó inativo'}
        
        if self.simulate_offline:
            return {'status': 'error', 'message': 'Erro de envio, conexão do nó foi perdida'}
        
        if not self.auth_manager.is_authenticated(token):
            return {'status': 'error', 'message': 'Token inválido'}
        
        username = self.auth_manager.get_username(token)
        message = Message(content, username, message_type)
        
        # Adicionar ao mural local
        self._add_message_to_mural(message)
        
        self.logger.info(f"MENSAGEM: [{username}] {content}")
        
        # Replicação assíncrona para outros nós
        delivery_report = self._replicate_to_peers(message)
        
        return {
            'status': 'success',
            'message': 'Mensagem enviada',
            'delivery_report': delivery_report
        }
    
    def _handle_get_messages(self, request: Dict) -> Dict:
        """Retorna mensagens do mural"""
        token = request.get('token')
        is_authenticated = token and self.auth_manager.is_authenticated(token)
        
        if is_authenticated:
            # Usuário logado: todas as mensagens
            messages_data = [msg.to_dict() for msg in self.messages]
        else:
            # Visitante: apenas públicas
            public_messages = [msg for msg in self.messages if msg.message_type == "public"]
            messages_data = [msg.to_dict() for msg in public_messages]
        
        return {
            'status': 'success', 
            'messages': messages_data,
            'node_id': self.node_id
        }
    
    def _handle_sync_all_messages(self) -> Dict:
        """Retorna TODAS as mensagens para sincronização (incluindo privadas)"""
        if not self.active or self.simulate_offline:
            return {'status': 'error', 'message': 'Nó indisponível'}
        
        # Para sincronização entre nós: retornar TODAS as mensagens
        all_messages = [msg.to_dict() for msg in self.messages]
        
        self.logger.info(f"SYNC_ALL: Enviando {len(all_messages)} mensagens")
        
        return {
            'status': 'success',
            'messages': all_messages,
            'node_id': self.node_id
        }
    
    def _handle_check_status(self) -> Dict:
        """Status do nó"""
        return {
            'status': 'success',
            'node_id': self.node_id,
            'port': self.port,
            'active': self.active,
            'user': self.current_user,
            'simulate_offline': self.simulate_offline
        }
    
    def _handle_sync(self, request: Dict) -> Dict:
        """Sincronização entre nós"""
        if not self.active or self.simulate_offline:
            return {'status': 'error', 'message': 'Nó indisponível'}
        
        peer_messages = request.get('messages', [])
        new_count = 0
        
        for msg_data in peer_messages:
            message = Message.from_dict(msg_data)
            if self._add_message_to_mural(message):
                new_count += 1
                print(f"📨 [{self.node_id}] Nova: {message.author}: {message.content}")
        
        if new_count > 0:
            self.logger.info(f"SYNC: {new_count} mensagens recebidas")
        
        return {'status': 'success'}
    
    def _handle_toggle_offline(self) -> Dict:
        """Simula falha do nó"""
        self.simulate_offline = not self.simulate_offline
        
        if self.simulate_offline:
            print(f"⚠️  {self.node_id} SIMULANDO FALHA")
            self.logger.info("SIMULAÇÃO: Falha ativada")
            
            # Ao simular falha, sincronizar com peers para não perder mensagens
            self._sync_before_offline()
            
        else:
            print(f"✅ {self.node_id} RECONECTADO")
            self.logger.info("SIMULAÇÃO: Falha desativada")
            
            # Ao reconectar, buscar mensagens perdidas
            self._sync_after_reconnect()
        
        return {
            'status': 'success',
            'simulate_offline': self.simulate_offline,
            'message': f'Simulação {"ativada" if self.simulate_offline else "desativada"}'
        }
    
    def _add_message_to_mural(self, message: Message) -> bool:
        """Adiciona mensagem ao mural (sem duplicatas)"""
        if message.id not in self.message_ids:
            self.messages.append(message)
            self.message_ids.add(message.id)
            # Manter ordem cronológica
            self.messages.sort(key=lambda m: m.timestamp)
            return True
        return False
    
    def _replicate_to_peers(self, message: Message) -> Dict:
        """Replicação assíncrona para peers"""
        active_peers = []
        offline_peers = []
        sent_to = []
        failed_to = []
        
        # Verificar estado dos peers
        for peer_port in self.peers:
            peer_status = self._get_peer_status(peer_port)
            if peer_status:
                if peer_status.get('active') and not peer_status.get('simulate_offline'):
                    active_peers.append({
                        'port': peer_port,
                        'user': peer_status.get('user'),
                        'node_id': peer_status.get('node_id')
                    })
                else:
                    offline_peers.append({
                        'port': peer_port,
                        'user': peer_status.get('user'),
                        'node_id': peer_status.get('node_id')
                    })
        
        # Enviar para peers ativos
        for peer in active_peers:
            try:
                response = self._send_to_peer(peer['port'], {
                    'action': 'sync',
                    'messages': [message.to_dict()]
                })
                
                if response.get('status') == 'success':
                    sent_to.append(peer)
                else:
                    failed_to.append(peer)
                    
            except Exception:
                failed_to.append(peer)
        
        # Gerar relatório simples
        if len(active_peers) == 0:
            return {'message': 'Mensagem enviada e não recebida, não encontrei nenhum outro nó ativo'}
        elif len(sent_to) == len(active_peers):
            return {'message': 'Mensagem enviada com sucesso, todos receberam'}
        elif len(sent_to) > 0:
            users = [f"{p['user']}({p['port']})" for p in sent_to]
            return {'message': f'Mensagem enviada, recebida por {", ".join(users)}'}
        else:
            return {'message': 'Mensagem não foi entregue a nenhum nó ativo'}
    
    def _sync_before_offline(self):
        """Sincroniza antes de ficar offline"""
        # Não faz nada especial - só para manter consistência
        pass
    
    def _sync_after_reconnect(self):
        """Sincroniza após reconectar - CONSISTÊNCIA EVENTUAL"""
        try:
            self.logger.info("RECONECTANDO: Buscando mensagens perdidas...")
            
            for peer_port in self.peers:
                peer_status = self._get_peer_status(peer_port)
                if peer_status and peer_status.get('active'):
                    try:
                        # Pedir todas as mensagens do peer
                        response = self._send_to_peer(peer_port, {'action': 'get_messages'})
                        
                        if response.get('status') == 'success':
                            messages = response.get('messages', [])
                            new_count = 0
                            
                            for msg_data in messages:
                                message = Message.from_dict(msg_data)
                                if self._add_message_to_mural(message):
                                    new_count += 1
                            
                            if new_count > 0:
                                print(f"📬 {new_count} mensagens recuperadas!")
                                self.logger.info(f"RECUPERADO: {new_count} mensagens")
                                
                    except Exception as e:
                        self.logger.debug(f"Erro sync com {peer_port}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Erro na reconexão: {e}")
    
    def _is_user_logged_in_peer(self, peer_port: int, username: str) -> bool:
        """Verifica se usuário está logado em outro nó"""
        try:
            status = self._get_peer_status(peer_port)
            return status and status.get('user') == username
        except:
            return False
    
    def _get_peer_status(self, peer_port: int) -> Optional[Dict]:
        """Obtém status de um peer"""
        try:
            response = self._send_to_peer(peer_port, {'action': 'check_status'})
            return response if response.get('status') == 'success' else None
        except:
            return None
    
    def _send_to_peer(self, peer_port: int, data: Dict) -> Dict:
        """Envia dados para outro nó via TCP"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Timeout baixo para ser rápido
        
        try:
            sock.connect((self.host, peer_port))
            sock.send(json.dumps(data).encode('utf-8'))
            response = sock.recv(4096).decode('utf-8')
            return json.loads(response)
        finally:
            sock.close()