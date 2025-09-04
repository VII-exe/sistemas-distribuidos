import socket
import threading
import json
import time
import logging
import os
from typing import List, Dict, Set, Optional
from .message import Message
from .auth import AuthManager


class Node:
    def __init__(self, node_id: str, port: int, peers: List[int]):
        self.node_id = node_id
        self.port = port
        self.peers = peers  # Lista das portas dos outros nós
        self.host = 'localhost'
        
        # Estados do nó
        self.active = False  # Nó inativo por padrão
        self.current_user = None  # Usuário logado neste nó
        self.simulate_offline = False  # Para simular falha
        
        # Armazenamento local
        self.messages = []  # Lista de mensagens do mural
        self.message_ids = set()  # IDs para evitar duplicatas
        
        # Sistema de autenticação
        self.auth_manager = AuthManager()
        
        # Controle do servidor
        self.server_socket = None
        self.running = False
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format=f'[{self.node_id}] %(asctime)s - %(message)s',
            handlers=[
                logging.FileHandler(f'logs/{self.node_id}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(f'Node-{self.node_id}')
    
    def start(self):
        """Inicia o nó (mas mantém inativo até login)"""
        self.running = True
        self.logger.info(f"Servidor {self.node_id} iniciado na porta {self.port} (INATIVO)")
        
        # Criar socket servidor
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        print(f"🔴 {self.node_id} INATIVO na porta {self.port} (aguardando login)")
        
        # Thread para aceitar conexões
        threading.Thread(target=self._accept_connections, daemon=True).start()
    
    def activate_node(self, username: str):
        """Ativa o nó quando usuário faz login"""
        self.active = True
        self.current_user = username
        self.logger.info(f"Nó {self.node_id} ATIVADO por {username}")
        print(f"🟢 {self.node_id} ATIVO com usuário: {username}")
        
        # Sincronizar com outros nós ativos
        threading.Thread(target=self._sync_with_active_peers, daemon=True).start()
    
    def deactivate_node(self):
        """Desativa o nó quando usuário faz logout"""
        username = self.current_user
        self.active = False
        self.current_user = None
        self.logger.info(f"Nó {self.node_id} DESATIVADO (logout {username})")
        print(f"🔴 {self.node_id} INATIVO (logout {username})")
    
    def stop(self):
        """Para o nó"""
        self.running = False
        self.active = False
        if self.server_socket:
            self.server_socket.close()
        self.logger.info(f"Nó {self.node_id} parado")
    
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
        """Processa login"""
        username = request.get('username')
        password = request.get('password')
        
        # Verificar se usuário já está logado em outro nó
        active_nodes = self._get_active_nodes_info()
        for node_info in active_nodes:
            if node_info['user'] == username:
                return {
                    'status': 'error', 
                    'message': f'Usuário {username} já está conectado no {node_info["node_id"]} (porta {node_info["port"]})'
                }
        
        token = self.auth_manager.login(username, password)
        if token:
            self.activate_node(username)
            self.logger.info(f"Login bem-sucedido: {username}")
            return {
                'status': 'success', 
                'token': token, 
                'username': username,
                'node_id': self.node_id,
                'port': self.port
            }
        else:
            self.logger.warning(f"Falha no login: {username}")
            return {'status': 'error', 'message': 'Usuário ou senha inválidos'}
    
    def _handle_logout(self, request: Dict) -> Dict:
        """Processa logout"""
        token = request.get('token')
        
        if not self.auth_manager.is_authenticated(token):
            return {'status': 'error', 'message': 'Token inválido'}
        
        username = self.auth_manager.get_username(token)
        self.auth_manager.logout(token)
        self.deactivate_node()
        
        return {'status': 'success', 'message': f'Logout realizado com sucesso'}
    
    def _handle_post_message(self, request: Dict) -> Dict:
        """Processa postagem de mensagem"""
        token = request.get('token')
        content = request.get('content')
        
        if not self.active:
            return {'status': 'error', 'message': 'Nó está inativo'}
        
        if self.simulate_offline:
            return {'status': 'error', 'message': 'Erro de envio, conexão do nó foi perdida'}
        
        if not self.auth_manager.is_authenticated(token):
            return {'status': 'error', 'message': 'Token inválido'}
        
        username = self.auth_manager.get_username(token)
        message = Message(content, username)
        
        # Adicionar mensagem localmente
        self._add_message(message)
        self.logger.info(f"Nova mensagem de {username}: {content}")
        
        # Tentar replicar para outros nós ativos
        delivery_report = self._replicate_message_with_report(message)
        
        return {
            'status': 'success',
            'message': 'Mensagem processada',
            'delivery_report': delivery_report
        }
    
    def _handle_get_messages(self) -> Dict:
        """Retorna todas as mensagens"""
        if not self.active:
            return {'status': 'error', 'message': 'Nó está inativo'}
        
        messages_data = [msg.to_dict() for msg in self.messages]
        return {'status': 'success', 'messages': messages_data}
    
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
        """Liga/desliga simulação offline"""
        self.simulate_offline = not self.simulate_offline
        status = "ATIVADA" if self.simulate_offline else "DESATIVADA"
        
        if self.simulate_offline:
            print(f"⚠️  {self.node_id} simulando FALHA DE CONEXÃO")
        else:
            print(f"✅ {self.node_id} conexão RESTAURADA")
        
        return {
            'status': 'success',
            'simulate_offline': self.simulate_offline,
            'message': f'Simulação de falha: {status}'
        }
    
    def _handle_sync(self, request: Dict) -> Dict:
        """Processa sincronização com outros nós"""
        if not self.active or self.simulate_offline:
            return {'status': 'error', 'message': 'Nó indisponível'}
        
        peer_messages = request.get('messages', [])
        new_count = 0
        
        for msg_data in peer_messages:
            message = Message.from_dict(msg_data)
            if self._add_message(message):
                new_count += 1
                # Notificar nova mensagem recebida
                print(f"\n🔔 [{self.node_id}] Nova mensagem de {message.author}: {message.content}")
        
        if new_count > 0:
            self.logger.info(f"Sincronizado {new_count} novas mensagens")
        
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
        """Replica mensagem para outros nós e retorna relatório de entrega"""
        report = {
            'sent_to': [],
            'failed_to': [],
            'lost_connection': [],  # Nós que perderam conexão após receber
            'total_active_nodes': 0
        }
        
        active_nodes = self._get_active_nodes_info()
        report['total_active_nodes'] = len([n for n in active_nodes if n['port'] != self.port])
        
        if report['total_active_nodes'] == 0:
            return {
                'message': 'Mensagem enviada e não recebida, não encontrei nenhum outro nó ativo',
                'type': 'no_recipients'
            }
        
        for peer_port in self.peers:
            try:
                # Verificar se o peer está ativo
                peer_info = self._get_peer_status(peer_port)
                if not peer_info or not peer_info.get('active'):
                    continue
                
                response = self._send_to_peer(peer_port, {
                    'action': 'sync',
                    'messages': [message.to_dict()]
                })
                
                if response.get('status') == 'success':
                    report['sent_to'].append({
                        'port': peer_port,
                        'user': peer_info.get('user'),
                        'node_id': peer_info.get('node_id')
                    })
                    
                    # Verificar se ainda está online após envio (pequeno delay)
                    time.sleep(0.5)
                    current_status = self._get_peer_status(peer_port)
                    
                    if not current_status or not current_status.get('active') or current_status.get('simulate_offline'):
                        # Nó perdeu conexão após receber
                        report['lost_connection'].append({
                            'port': peer_port,
                            'user': peer_info.get('user'),
                            'node_id': peer_info.get('node_id')
                        })
                        
                        # Remover dos enviados com sucesso
                        report['sent_to'] = [s for s in report['sent_to'] if s['port'] != peer_port]
                        
                else:
                    report['failed_to'].append({
                        'port': peer_port,
                        'user': peer_info.get('user'),
                        'node_id': peer_info.get('node_id')
                    })
                    
            except Exception as e:
                self.logger.warning(f"Falha ao replicar para porta {peer_port}: {e}")
                report['failed_to'].append({'port': peer_port, 'error': str(e)})
        
        # Gerar mensagem de status
        messages_parts = []
        
        if report['sent_to']:
            received_by = [f"{r['user']}({r['port']})" for r in report['sent_to']]
            messages_parts.append(f"recebida por {', '.join(received_by)}")
        
        if report['lost_connection']:
            lost_by = [f"{r['user']}({r['port']})" for r in report['lost_connection']]
            messages_parts.append(f"mas {', '.join(lost_by)} perdeu conexão")
        
        if report['failed_to']:
            failed_by = [f"{r['user']}({r['port']})" for r in report['failed_to'] if 'user' in r]
            if failed_by:
                messages_parts.append(f"não recebida por {', '.join(failed_by)}")
        
        if len(report['sent_to']) + len(report['lost_connection']) == report['total_active_nodes'] and not report['failed_to']:
            if report['lost_connection']:
                final_message = f"Mensagem enviada, {', '.join(messages_parts)}"
            else:
                final_message = "Mensagem enviada com sucesso, todos receberam"
            message_type = 'all_received'
        elif report['sent_to'] or report['lost_connection']:
            final_message = f"Mensagem enviada, {', '.join(messages_parts)}"
            message_type = 'partial_received'
        else:
            final_message = "Mensagem não foi entregue a nenhum nó"
            message_type = 'delivery_failed'
        
        return {
            'message': final_message,
            'type': message_type,
            'details': report
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
    
    def _sync_with_active_peers(self):
        """Sincroniza com outros nós ativos periodicamente"""
        while self.running and self.active:
            time.sleep(5)  # Sincroniza a cada 5 segundos
            
            if self.simulate_offline:
                continue
            
            for peer_port in self.peers:
                try:
                    peer_info = self._get_peer_status(peer_port)
                    if not peer_info or not peer_info.get('active'):
                        continue
                    
                    our_messages = [msg.to_dict() for msg in self.messages]
                    self._send_to_peer(peer_port, {
                        'action': 'sync',
                        'messages': our_messages
                    })
                    
                except Exception as e:
                    self.logger.debug(f"Sync error with {peer_port}: {e}")
    
    def _send_to_peer(self, peer_port: int, data: Dict) -> Dict:
        """Envia dados para outro nó"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)  # Timeout de 3 segundos
        
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