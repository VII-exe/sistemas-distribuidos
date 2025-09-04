"""
Módulo core do Sistema de Mensagens Distribuídas

Este módulo contém as funcionalidades principais:
- Node: Classe principal do nó distribuído
- Message: Estrutura das mensagens
- AuthManager: Sistema de autenticação
"""

from .node import Node
from .message import Message
from .auth import AuthManager

__all__ = ['Node', 'Message', 'AuthManager']