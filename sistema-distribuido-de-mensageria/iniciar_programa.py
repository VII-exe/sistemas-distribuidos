import sys
import os
import time
import threading
import subprocess
from core.node import Node


def find_project_directory():
    """Encontra o diretório correto do projeto"""
    # Lista de possíveis caminhos
    possible_paths = [
        os.getcwd(),  # Diretório atual
        os.path.join(os.getcwd(), "sistema-distribuido-de-mensageria"),
        os.path.join(os.getcwd(), "distributed-message-system"),
        "C:\\Users\\Vinicius\\Documents\\GitHub\\sistemas-distribuidos\\sistema-distribuido-de-mensageria",
        "C:\\Users\\Vinicius\\Documents\\GitHub\\sistemas-distribuidos\\distributed-message-system"
    ]
    
    for path in possible_paths:
        if os.path.exists(os.path.join(path, "core", "node.py")):
            return path
    
    return None


def setup_project_directory():
    """Configura o diretório do projeto"""
    project_dir = find_project_directory()
    
    if project_dir is None:
        print("❌ Não foi possível encontrar o diretório do projeto!")
        print("   Certifique-se de que está na pasta correta do projeto")
        return False
    
    # Mudar para o diretório do projeto
    os.chdir(project_dir)
    
    # Adicionar ao path do Python
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    
    print(f"📂 Diretório do projeto: {project_dir}")
    return True


def start_client_window():
    """Abre o cliente em uma nova janela"""
    try:
        client_path = os.path.join("client", "client.py")
        
        if not os.path.exists(client_path):
            print(f"❌ Arquivo {client_path} não encontrado!")
            return False
        
        print("🎯 Abrindo cliente em nova janela...")
        
        # Comando para abrir nova janela com o cliente
        if os.name == 'nt':  # Windows
            subprocess.Popen([
                'cmd', '/k', 
                f'python {client_path}'
            ], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Linux/Mac
            subprocess.Popen([
                'gnome-terminal', '--', 
                'python3', client_path
            ])
        
        return True
    except Exception as e:
        print(f"❌ Erro ao abrir cliente: {e}")
        return False


def main():
    """Ponto de entrada principal do Sistema de Mensagens Distribuídas"""
    
    print("🚀" + "=" * 58 + "🚀")
    print("🚀  SISTEMA DE MENSAGENS DISTRIBUÍDAS - INICIALIZAÇÃO  🚀")
    print("🚀" + "=" * 58 + "🚀")
    print()
    
    # 1. Configurar diretório do projeto
    if not setup_project_directory():
        input("Pressione Enter para sair...")
        return
    
    # 2. Criar pasta logs se não existir
    os.makedirs('logs', exist_ok=True)
    
    # Configuração dos 3 nós
    nodes_config = [
        ("Node1", 8001, [8002, 8003]),
        ("Node2", 8002, [8001, 8003]),
        ("Node3", 8003, [8001, 8002])
    ]
    
    nodes = []
    
    try:
        # 3. Iniciar todos os nós
        print("📡 Iniciando nós do sistema distribuído...")
        
        for node_id, port, peers in nodes_config:
            print(f"   🖥️  Iniciando {node_id} na porta {port}...")
            
            # Criar e iniciar nó
            node = Node(node_id, port, peers)
            node.start()
            nodes.append(node)
            
            time.sleep(0.5)  # Pequeno delay entre os nós
        
        print("\n✅ Todos os nós iniciados com sucesso!")
        
        # 4. Aguardar sincronização inicial
        print("⏳ Aguardando sincronização inicial dos nós...")
        time.sleep(2)
        
        # 5. Abrir cliente automaticamente
        print("\n🎯 Abrindo interface do cliente...")
        time.sleep(1)
        
        client_opened = start_client_window()
        
        if client_opened:
            print("✅ Cliente aberto em nova janela!")
        else:
            print("⚠️  Não foi possível abrir o cliente automaticamente")
            print("   Execute manualmente: python client/client.py")
        
        # 6. Mostrar informações do sistema
        print("\n📋 SISTEMA ATIVO:")
        print("   🖥️  Node1: localhost:8001")
        print("   🖥️  Node2: localhost:8002") 
        print("   🖥️  Node3: localhost:8003")
        
        print("\n🔐 USUÁRIOS DISPONÍVEIS:")
        print("   👤 admin/admin123")
        print("   👤 user1/password1")
        print("   👤 user2/password2")
        print("   👤 test/test")
        
        if client_opened:
            print("\n💡 COMO USAR:")
            print("   1. Use a janela do CLIENTE que abriu")
            print("   2. Faça login: login admin admin123")
            print("   3. Envie mensagens: post Olá mundo!")
            print("   4. Leia mensagens: read")
            print("   5. Troque de nó: node 8002")
            print("   6. Simule falhas: simulate")
        else:
            print("\n💡 PARA USAR O SISTEMA:")
            print("   1. Abra outro terminal")
            print("   2. Execute: python client/client.py")
            print("   3. Faça login e comece a usar!")
        
        print("\n🔄 FUNCIONALIDADES ATIVAS:")
        print("   ✅ Replicação automática entre nós")
        print("   ✅ Consistência eventual")
        print("   ✅ Autenticação por token")
        print("   ✅ Simulação de falhas")
        print("   ✅ Logs detalhados em logs/")
        
        print("\n⏹️  Pressione Ctrl+C para parar o sistema")
        print("🟢 Sistema rodando...")
        
        # 7. Manter sistema rodando
        while True:
            time.sleep(1)
            
            # Verificar se todos os nós ainda estão rodando
            running_nodes = sum(1 for node in nodes if node.running)
            if running_nodes == 0:
                print("❌ Todos os nós pararam. Encerrando...")
                break
                
    except KeyboardInterrupt:
        print("\n\n🛑 PARANDO SISTEMA...")
        print("   Por favor aguarde...")
        
        # Parar todos os nós
        for i, node in enumerate(nodes, 1):
            if node.running:
                print(f"   🖥️  Parando Node{i}...")
                node.stop()
        
        print("✅ Sistema encerrado com sucesso!")
        print("📋 Logs salvos em logs/ para evidências do relatório")
        
    except Exception as e:
        print(f"\n❌ Erro ao iniciar sistema: {e}")
        print("   Verifique se você está no diretório correto do projeto")
        
        # Parar nós que conseguiram iniciar
        for node in nodes:
            if hasattr(node, 'running') and node.running:
                node.stop()
    
    finally:
        print("\n👋 Obrigado por usar o Sistema Distribuido de Mensageria!")
        input("Pressione Enter para finalizar...")


if __name__ == "__main__":
    main()