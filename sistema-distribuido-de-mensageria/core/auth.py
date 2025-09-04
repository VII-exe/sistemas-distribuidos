import hashlib
from typing import Dict, Optional


class AuthManager:
    def __init__(self):
        # Usuários pré-cadastrados (usuário: senha_hash)
        self.users = {
            'admin': self._hash_password('admin123'),
            'user1': self._hash_password('password1'),
            'user2': self._hash_password('password2'),
            'test': self._hash_password('test')
        }
        
        # Usuários atualmente logados (token: usuário)
        self.logged_users = {}
    
    def _hash_password(self, password: str) -> str:
        """Gera hash simples da senha"""
        return hashlib.md5(password.encode()).hexdigest()
    
    def _generate_token(self, username: str) -> str:
        """Gera token simples para o usuário"""
        return hashlib.md5(f"{username}_{len(self.logged_users)}".encode()).hexdigest()
    
    def login(self, username: str, password: str) -> Optional[str]:
        """
        Faz login do usuário
        Retorna: token se sucesso, None se falha
        """
        if username not in self.users:
            return None
        
        password_hash = self._hash_password(password)
        if self.users[username] != password_hash:
            return None
        
        # Gera token e adiciona usuário logado
        token = self._generate_token(username)
        self.logged_users[token] = username
        return token
    
    def logout(self, token: str) -> bool:
        """
        Faz logout do usuário
        Retorna: True se sucesso, False se token inválido
        """
        if token in self.logged_users:
            del self.logged_users[token]
            return True
        return False
    
    def is_authenticated(self, token: str) -> bool:
        """Verifica se token é válido"""
        return token in self.logged_users
    
    def get_username(self, token: str) -> Optional[str]:
        """Retorna username do token ou None se inválido"""
        return self.logged_users.get(token)
    
    def add_user(self, username: str, password: str) -> bool:
        """
        Adiciona novo usuário
        Retorna: True se adicionado, False se já existe
        """
        if username in self.users:
            return False
        
        self.users[username] = self._hash_password(password)
        return True
