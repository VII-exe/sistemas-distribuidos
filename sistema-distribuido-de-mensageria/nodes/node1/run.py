import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from core.node import Node


def main():
    # Configuração do Nó 1
    node_id = "Node1"
    port = 8001
    peers = [8002, 8003]  # Portas dos outros nós
    
    # Criar e iniciar nó
    node = Node(node_id, port, peers)
    
    try:
        node.start()
        print(f"🚀 {node_id} iniciado na porta {port}")
        print("📋 Peers:", peers)
        print("🔐 Usuários disponíveis: admin/admin123, user1/password1, user2/password2, test/test")
        print("⏹️  Pressione Ctrl+C para parar")
        
        # Manter o nó rodando
        while True:
            try:
                command = input()
                if command.lower() in ['quit', 'exit', 'stop']:
                    break
            except EOFError:
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Parando nó...")
    finally:
        node.stop()
        print("✅ Nó parado")


if __name__ == "__main__":
    main()