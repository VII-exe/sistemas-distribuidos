"""
Módulo client do Sistema de Mensagens Distribuídas

Contém o cliente para interagir com os nós:
- MessageClient: Cliente para login, postar e ler mensagens
"""

from .client import MessageClient

__all__ = ['MessageClient']