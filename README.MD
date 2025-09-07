# Sistema de Mensagens Distribuídas

## Descrição

Sistema distribuído de publicação e leitura de mensagens entre múltiplos nós, implementando consistência eventual e autenticação básica. Desenvolvido para a disciplina de Sistemas Distribuídos do IFBA - Campus Santo Antônio de Jesus.

## Arquitetura

- **3 nós distribuídos** (Node1, Node2, Node3)
- **Comunicação TCP** entre nós (portas 8001, 8002, 8003)
- **Interface Web HTTP** (portas 9001, 9002, 9003)
- **Cliente terminal** para interação avançada
- **Replicação assíncrona** de mensagens
- **Consistência eventual** com sincronização automática

## Pré-requisitos

- Python 3.8+
- Sistema operacional: Windows
- Portas 8001-8003 para login e 9001-9003 para interface web disponíveis

## Estrutura do Projeto

```bash
sistema-distribuido-de-mensageria/
├── client/
│   ├── client.py              # Cliente terminal interativo
│   └── __init__.py
├── core/
│   ├── auth.py                # Sistema de autenticação
│   ├── message.py             # Estrutura das mensagens
│   ├── node.py                # Lógica principal dos nós
│   └── __init__.py
├── frontend/
│   ├── index.html             # Interface web
│   ├── app.js                 # JavaScript do frontend
│   └── styles.css             # Estilos CSS
├── logs/                      # Logs do sistema (criado automaticamente)
├── nodes/
│   ├── node1/run.py          # Executor do Node1
│   ├── node2/run.py          # Executor do Node2
│   └── node3/run.py          # Executor do Node3
├── iniciar_programa.py        # Script principal de inicialização
└── README.md                # Este arquivo
```

## Como Executar

### Método 1: Execução Automática (Recomendado)

1. **Clone o repositório:**

```bash
git clone <URL_DO_REPOSITORIO>
cd sistema-distribuido-de-mensageria
```

2. **Execute o script principal:**

```bash
python iniciar_programa.py
```

3. **O sistema irá:**
   - Iniciar os 3 nós automaticamente
   - Abrir o cliente terminal em nova janela
   - Disponibilizar interfaces web em:
     - <http://localhost:9001> (Node1)
     - <http://localhost:9002> (Node2)
     - <http://localhost:9003> (Node3)

### Método 2: Execução Manual

1. **Terminal 1 - Node1:**

```bash
python nodes/node1/run.py
```

2. **Terminal 2 - Node2:**

```bash
python nodes/node2/run.py
```

3. **Terminal 3 - Node3:**

```bash
python nodes/node3/run.py
```

4. **Terminal 4 - Cliente:**

```bash
python client/client.py
```

## 👤 Usuários Disponíveis

| Usuário | Senha | Descrição |
|---------|-------|-----------|
| admin | admin123 | Administrador |
| user1 | password1 | Usuário 1 |
| user2 | password2 | Usuário 2 |
| test | test | Usuário de teste |

## 🎮 Como Usar

### Interface Terminal

1. **Login em um nó:**

```python
login admin admin123 8001
```

2. **Enviar mensagem pública:**

```python
post Olá, pessoal!
```

3. **Enviar mensagem privada:**

```python
postpv Mensagem confidencial
```

4. **Ler mensagens:**

```python
read                    # Ler mensagens do nó atual
read 8002              # Ler mensagens do Node2
readpub 8003           # Ler apenas mensagens públicas do Node3
```

5. **Gerenciar múltiplos usuários:**

```python
login user1 password1 8002    # Login em outro nó
switch                        # Alternar entre usuários
```

6. **Simular falhas:**

```pyhon
simulate                # Simular falha do nó atual
simulate                # Reconectar (recupera mensagens perdidas)
```

7. **Comandos úteis:**

```python
status                  # Ver status de todos os nós
help                    # Ver todos os comandos
quit                    # Sair
```

### Interface Web

1. **Acesse qualquer interface:**
   - <http://localhost:9001>
   - <http://localhost:9002>
   - <http://localhost:9003>

2. **Faça login ou visualize mensagens públicas**

3. **Envie mensagens públicas ou privadas**

4. **Simule falhas através do botão "Simular Falha"**

## Cenários de Teste

### Teste 1: Replicação Básica

1. Login user1 no Node1 e user2 no Node2
2. user1 envia: "Mensagem pública"
3. Verificar se aparece no chat do user2

### Teste 2: Mensagens Privadas

1. Login em dois nós diferentes
2. Enviar mensagem privada
3. Verificar visibilidade apenas para usuários logados

### Teste 3: Simulação de Falha

1. Login em Node1 e Node2
2. Simular falha no Node2
3. Enviar mensagens do Node1
4. Reconectar Node2 e verificar sincronização

### Teste 4: Consistência Eventual

1. Simular falha em 2 nós
2. Deixar 1 nó ativo e enviar várias mensagens
3. Reconectar nós offline
4. Verificar se todas as mensagens foram sincronizadas

### Teste 5: Login Duplicado

1. Tentar fazer login com mesmo usuário em múltiplos nós
2. Sistema deve impedir login duplicado

## Logs e Monitoramento

### Logs do Sistema

Os logs são salvos automaticamente em:

- `logs/Node1.log` - Logs do Node1
- `logs/Node2.log` - Logs do Node2  
- `logs/Node3.log` - Logs do Node3

### Informações nos Logs

- Tentativas de login
- Envio e recebimento de mensagens
- Operações de sincronização
- Simulações de falha
- Reconexões e recuperação

## Solução de Problemas

### Erro "Porta em uso"

```bash
# Verificar processos usando as portas
netstat -an | grep :8001
netstat -an | grep :9001

# Matar processos se necessário (Windows)
taskkill /f /pid <PID>
```

### Cliente não conecta

1. Verificar se os nós estão rodando
2. Verificar se as portas estão disponíveis
3. Tentar reiniciar o sistema

### Interface web não carrega

1. Verificar se a pasta `frontend/` existe
2. Verificar permissões de arquivo
3. Tentar acessar diretamente: <http://localhost:9001>

### Problemas de sincronização

1. Verificar logs em `logs/`
2. Reiniciar todos os nós
3. Testar com apenas 2 nós primeiro

## 🏗️ Tecnologias Utilizadas

- **Python 3.8+** - Linguagem principal
- **Socket TCP** - Comunicação entre nós
- **HTTP Server** - Interface web
- **Bootstrap 5** - Frontend responsivo
- **JSON** - Serialização de dados
- **MD5** - Hash de senhas (para simplicidade)
- **Threading** - Concorrência

## Funcionalidades Implementadas

### Requisitos Obrigatórios

- [x] Mínimo 3 nós distribuídos
- [x] Cópia local do mural em cada nó
- [x] Comunicação via sockets TCP
- [x] Replicação assíncrona
- [x] Consistência eventual
- [x] Autenticação básica
- [x] Leitura pública sem autenticação
- [x] Simulação de falhas
- [x] Reconciliação após reconexão

### Funcionalidades Extras

- [x] Interface web responsiva
- [x] Cliente terminal avançado
- [x] Múltiplos usuários simultâneos
- [x] Mensagens públicas e privadas
- [x] Logs detalhados para auditoria
- [x] Sistema de status em tempo real
- [x] Prevenção de login duplicado

## 👥 Autores

- **Aluno:** Vinicius X. e Kleberson J.
- **Disciplina:** Sistemas Distribuídos
- **Professor:** Felipe Silva
- **Instituição:** IFBA - Campus Santo Antônio de Jesus
- **Curso:** Superior de Tecnologia em Análise e Desenvolvimento de Sistemas - 5º Semestre
