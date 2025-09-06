import json
import time
from typing import Dict, Any, Optional


class Message:
    def __init__(self, content: str, author: str, message_type: str = "public", message_id: Optional[str] = None):
        self.id = message_id or str(int(time.time() * 1000000))  # timestamp microsegundos como ID
        self.content = content
        self.author = author
        self.message_type = message_type  # "public" ou "private"
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte mensagem para dicionário"""
        return {
            'id': self.id,
            'content': self.content,
            'author': self.author,
            'message_type': self.message_type,
            'timestamp': self.timestamp
        }
    
    def to_json(self) -> str:
        """Converte mensagem para JSON"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Cria mensagem a partir de dicionário"""
        msg = cls(
            data['content'], 
            data['author'], 
            data.get('message_type', 'public'),  # Compatibilidade com versões antigas
            data['id']
        )
        msg.timestamp = data['timestamp']
        return msg
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Cria mensagem a partir de JSON"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def is_public(self) -> bool:
        """Verifica se a mensagem é pública"""
        return self.message_type == "public"
    
    def is_private(self) -> bool:
        """Verifica se a mensagem é privada"""
        return self.message_type == "private"
    
    def __str__(self) -> str:
        privacy_indicator = "🔒" if self.is_private() else "🌐"
        return f"{privacy_indicator}[{self.author}] {self.content}"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Message):
            return False
        return self.id == other.id