// Sistema de Mensagens Distribuídas - Frontend JavaScript (Correção Simples)

// Estado global da aplicação
let state = {
    currentToken: null,
    currentPort: null,
    currentUsername: null,
    sentMessageCount: 0,
    autoRefreshInterval: null
};

// Senhas padrão dos usuários
const USER_PASSWORDS = {
    'admin': 'admin123',
    'user1': 'password1', 
    'user2': 'password2',
    'test': 'test'
};

// Configurações
const CONFIG = {
    HTTP_PORT_OFFSET: 1000,
    REFRESH_INTERVAL: 5000
};

// Utilitários
const utils = {
    getHttpPort: (tcpPort) => parseInt(tcpPort) + CONFIG.HTTP_PORT_OFFSET,
    
    escapeHtml: (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    formatTime: (timestamp) => {
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();
        
        if (isToday) {
            return date.toLocaleTimeString('pt-BR');
        } else {
            return `${date.toLocaleDateString('pt-BR')} ${date.toLocaleTimeString('pt-BR')}`;
        }
    },
    
    showToast: (message, type = 'info', duration = 5000) => {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;
        
        const toastId = `toast-${Date.now()}`;
        
        const typeStyles = {
            'success': 'bg-success',
            'danger': 'bg-danger', 
            'warning': 'bg-warning',
            'info': 'bg-info'
        };
        
        const bgClass = typeStyles[type] || 'bg-info';
        
        const toastHtml = `
            <div id="${toastId}" class="toast ${bgClass} text-white" role="alert">
                <div class="toast-header ${bgClass} text-white border-0">
                    <strong class="me-auto">Sistema</strong>
                    <small class="text-white-50">${new Date().toLocaleTimeString('pt-BR')}</small>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">${utils.escapeHtml(message)}</div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: duration
        });
        
        toast.show();
        
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
};

// API Client
const api = {
    async request(httpPort, endpoint, options = {}) {
        const url = `http://localhost:${httpPort}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            const response = await fetch(url, {
                ...config,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            if (endpoint.includes('/api/')) {
                return await response.json();
            } else {
                return await response.text();
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Timeout - servidor não respondeu');
            }
            throw new Error(`Conexão falhou: ${error.message}`);
        }
    },
    
    async login(username, password, tcpPort) {
        const httpPort = utils.getHttpPort(tcpPort);
        return await this.request(httpPort, '/api/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
    },
    
    async logout(token, httpPort) {
        return await this.request(httpPort, '/api/logout', {
            method: 'POST',
            body: JSON.stringify({ token })
        });
    },
    
    async sendMessage(token, content, messageType, httpPort) {
        return await this.request(httpPort, '/api/post', {
            method: 'POST',
            body: JSON.stringify({
                token,
                content,
                message_type: messageType
            })
        });
    },
    
    async getMessages(httpPort, token = null) {
        const headers = token ? { 'Authorization': token } : {};
        return await this.request(httpPort, '/api/messages', {
            method: 'GET',
            headers
        });
    },
    
    async getStatus(httpPort) {
        return await this.request(httpPort, '/api/status', {
            method: 'GET'
        });
    },
    
    async toggleOffline(token, httpPort) {
        return await this.request(httpPort, '/api/toggle_offline', {
            method: 'POST',
            body: JSON.stringify({ token })
        });
    }
};

// Sistema de autenticação
const auth = {
    async handleLogin(e) {
        e.preventDefault();
        
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const tcpPort = document.getElementById('nodePort').value;
        
        if (!username || !password || !tcpPort) {
            utils.showToast('Preencha todos os campos', 'warning');
            return;
        }
        
        try {
            const data = await api.login(username, password, tcpPort);
            
            if (data.status === 'success') {
                state.currentToken = data.token;
                state.currentPort = tcpPort;
                state.currentUsername = username;
                
                ui.switchToLoggedView();
                ui.updateCurrentUser(`${username}@Node${tcpPort - 8000}`);
                
                await Promise.all([
                    messaging.refresh(),
                    status.updateAll()
                ]);
                
                ui.startAutoRefresh();
                utils.showToast(`Login realizado! Bem-vindo, ${username}`, 'success');
                
            } else {
                utils.showToast(`Erro no login: ${data.message}`, 'danger');
            }
        } catch (error) {
            utils.showToast(error.message, 'danger');
            console.error('Login error:', error);
        }
    },
    
    async logout() {
        if (state.currentToken) {
            try {
                const httpPort = utils.getHttpPort(state.currentPort);
                await api.logout(state.currentToken, httpPort);
            } catch (error) {
                console.error('Logout error:', error);
            }
        }
        
        // Reset estado
        Object.assign(state, {
            currentToken: null,
            currentPort: null,
            currentUsername: null,
            sentMessageCount: 0
        });
        
        ui.stopAutoRefresh();
        ui.switchToLoginView();
        ui.resetForm();
        
        utils.showToast('Logout realizado com sucesso', 'success');
    }
};

// Sistema de mensagens
const messaging = {
    async send(messageType) {
        const content = document.getElementById('messageInput').value.trim();
        
        if (!content) {
            utils.showToast('Digite uma mensagem', 'warning');
            return;
        }
        
        if (!state.currentToken) {
            utils.showToast('Você precisa fazer login primeiro', 'warning');
            return;
        }
        
        const messageInput = document.getElementById('messageInput');
        const originalPlaceholder = messageInput.placeholder;
        
        try {
            messageInput.disabled = true;
            messageInput.placeholder = 'Enviando...';
            
            const httpPort = utils.getHttpPort(state.currentPort);
            const data = await api.sendMessage(state.currentToken, content, messageType, httpPort);
            
            if (data.status === 'success') {
                messageInput.value = '';
                state.sentMessageCount++;
                const sentCountElement = document.getElementById('sentCount');
                if (sentCountElement) {
                    sentCountElement.textContent = state.sentMessageCount;
                }
                
                // Mostrar relatório de entrega
                if (data.delivery_report?.message) {
                    utils.showToast(data.delivery_report.message, 'info', 7000);
                }
                
                await this.refresh();
            } else {
                utils.showToast(`Erro ao enviar: ${data.message}`, 'danger');
            }
        } catch (error) {
            utils.showToast(error.message, 'danger');
            console.error('Send error:', error);
        } finally {
            messageInput.disabled = false;
            messageInput.placeholder = originalPlaceholder;
            messageInput.focus();
        }
    },
    
    async refresh() {
        if (!state.currentToken && !this.isPublicRead) return;
        
        try {
            const httpPort = utils.getHttpPort(state.currentPort);
            const data = await api.getMessages(httpPort, state.currentToken);
            
            if (data.status === 'success') {
                ui.displayMessages(data.messages, data.authenticated);
                ui.updateLastUpdate();
                
                const connectionStatus = document.getElementById('connectionStatus');
                if (connectionStatus) {
                    connectionStatus.textContent = 'Online';
                    connectionStatus.className = 'badge bg-success';
                }
            }
        } catch (error) {
            console.error('Refresh error:', error);
            const connectionStatus = document.getElementById('connectionStatus');
            if (connectionStatus) {
                connectionStatus.textContent = 'Erro';
                connectionStatus.className = 'badge bg-danger';
            }
        }
    },
    
    async readPublic(tcpPort) {
        try {
            const httpPort = utils.getHttpPort(tcpPort);
            const data = await api.getMessages(httpPort);
            
            if (data.status === 'success') {
                this.isPublicRead = true;
                state.currentPort = tcpPort;
                
                ui.switchToLoggedView();
                ui.updateCurrentUser(`Visitante@Node${tcpPort - 8000}`);
                ui.displayMessages(data.messages, false);
                ui.disableMessageInput();
                
                utils.showToast(`Visualizando Node${tcpPort - 8000} - ${data.messages.length} mensagens públicas`, 'info');
            } else {
                utils.showToast(`Erro ao acessar Node${tcpPort - 8000}`, 'danger');
            }
        } catch (error) {
            utils.showToast(`Erro de conexão com Node${tcpPort - 8000}`, 'danger');
            console.error('Read public error:', error);
        }
    }
};

// Sistema de status (CORRIGIDO - com verificação segura de elementos)
const status = {
    async updateAll() {
        const statusContainer = document.getElementById('nodeStatus');
        if (!statusContainer) {
            console.warn('Container nodeStatus não encontrado');
            return;
        }
        
        const onlineContainer = document.getElementById('onlineUsers');
        const ports = [8001, 8002, 8003];
        
        let onlineUsers = [];
        
        for (const tcpPort of ports) {
            const httpPort = utils.getHttpPort(tcpPort);
            
            try {
                const data = await api.getStatus(httpPort);
                
                const { active, simulate_offline, user, node_id } = data;
                const displayUser = user || 'Nenhum';
                
                let statusIcon, statusText, cardClass;
                
                if (active) {
                    if (simulate_offline) {
                        statusIcon = '🟡';
                        statusText = 'SIMULANDO FALHA';
                        cardClass = 'node-offline';
                    } else {
                        statusIcon = '🟢';
                        statusText = 'ATIVO';
                        cardClass = 'node-active';
                        
                        if (user && user !== 'Nenhum') {
                            onlineUsers.push({
                                user,
                                node: node_id,
                                port: tcpPort,
                                isCurrent: tcpPort == state.currentPort
                            });
                        }
                    }
                } else {
                    statusIcon = '🔴';
                    statusText = 'INATIVO';
                    cardClass = 'node-inactive';
                }
                
                this.updateNodeCard(statusContainer, {
                    tcpPort,
                    node_id,
                    statusIcon,
                    statusText,
                    cardClass,
                    displayUser
                });
                
                // Atualizar botão de simulação se for o nó atual
                if (tcpPort == state.currentPort) {
                    this.updateOfflineButton(simulate_offline);
                }
                
            } catch (error) {
                // Nó desconectado
                this.updateNodeCard(statusContainer, {
                    tcpPort,
                    node_id: `Node${tcpPort - 8000}`,
                    statusIcon: '❌',
                    statusText: 'DESCONECTADO',
                    cardClass: 'node-inactive',
                    displayUser: 'Servidor offline'
                });
            }
        }
        
        if (onlineContainer) {
            this.updateOnlineUsers(onlineUsers);
        }
    },
    
    updateNodeCard(container, { tcpPort, node_id, statusIcon, statusText, cardClass, displayUser }) {
        const cardId = `node-card-${tcpPort}`;
        let nodeElement = document.getElementById(cardId);
        
        // Se o card não existe, criar
        if (!nodeElement) {
            const colElement = document.createElement('div');
            colElement.className = 'col-md-4 mb-2';
            colElement.innerHTML = `
                <div id="${cardId}" class="card node-status-card" onclick="messaging.readPublic(${tcpPort})" style="cursor: pointer;">
                    <div class="card-body text-center">
                        <h6 class="mb-1"><span class="status-icon"></span> <span class="node-name"></span></h6>
                        <small class="d-block status-text"><strong></strong></small>
                        <small class="text-muted user-info">Usuário: <span class="user-name"></span></small>
                        <small class="d-block text-muted">Porta: ${tcpPort}</small>
                    </div>
                </div>
            `;
            container.appendChild(colElement);
            nodeElement = document.getElementById(cardId);
        }
        
        // CORRIGIDO: Verificar se os elementos existem antes de usar
        if (nodeElement) {
            const card = nodeElement.querySelector('.card');
            const statusIcon_el = nodeElement.querySelector('.status-icon');
            const nodeName_el = nodeElement.querySelector('.node-name');
            const statusText_el = nodeElement.querySelector('.status-text strong');
            const userName_el = nodeElement.querySelector('.user-name');
            
            if (card) card.className = `card ${cardClass} node-status-card`;
            if (statusIcon_el) statusIcon_el.textContent = statusIcon;
            if (nodeName_el) nodeName_el.textContent = node_id;
            if (statusText_el) statusText_el.textContent = statusText;
            if (userName_el) userName_el.textContent = utils.escapeHtml(displayUser);
        }
    },
    
    updateOfflineButton(isOffline) {
        const offlineBtn = document.getElementById('offlineBtn');
        if (offlineBtn) {
            if (isOffline) {
                offlineBtn.textContent = '✅ Restaurar Conexão';
                offlineBtn.className = 'btn btn-success btn-sm';
            } else {
                offlineBtn.textContent = '⚠️ Simular Falha';
                offlineBtn.className = 'btn btn-warning btn-sm';
            }
        }
    },
    
    updateOnlineUsers(onlineUsers) {
        const container = document.getElementById('onlineUsers');
        if (!container) return;
        
        if (onlineUsers.length === 0) {
            container.innerHTML = '<small class="text-muted text-center d-block">👤 Nenhum usuário online</small>';
            return;
        }
        
        let html = '';
        onlineUsers.forEach(user => {
            const currentBadge = user.isCurrent 
                ? '<span class="badge bg-primary ms-1">Você</span>' 
                : '';
            
            html += `
                <div class="d-flex justify-content-between align-items-center mb-2 p-2 bg-light rounded">
                    <div>
                        <small><strong>${utils.escapeHtml(user.user)}</strong></small><br>
                        <small class="text-muted">${user.node}</small>
                    </div>
                    <div>
                        <span class="badge bg-success">Online</span>
                        ${currentBadge}
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
};

// Sistema de interface
const ui = {
    switchToLoggedView() {
        const loginSection = document.getElementById('loginSection');
        const loggedSection = document.getElementById('loggedSection');
        
        if (loginSection) loginSection.style.display = 'none';
        if (loggedSection) loggedSection.style.display = 'block';
    },
    
    switchToLoginView() {
        const loginSection = document.getElementById('loginSection');
        const loggedSection = document.getElementById('loggedSection');
        
        if (loginSection) loginSection.style.display = 'block';
        if (loggedSection) loggedSection.style.display = 'none';
    },
    
    updateCurrentUser(userInfo) {
        const element = document.getElementById('currentUser');
        if (element) element.textContent = userInfo;
    },
    
    resetForm() {
        const loginForm = document.getElementById('loginForm');
        const messageInput = document.getElementById('messageInput');
        const sentCount = document.getElementById('sentCount');
        
        if (loginForm) loginForm.reset();
        if (messageInput) {
            messageInput.disabled = false;
            messageInput.placeholder = 'Digite sua mensagem...';
        }
        if (sentCount) sentCount.textContent = '0';
    },
    
    disableMessageInput() {
        const input = document.getElementById('messageInput');
        if (input) {
            input.disabled = true;
            input.placeholder = 'Login necessário para enviar mensagens';
        }
    },
    
    displayMessages(messages, authenticated) {
        const container = document.getElementById('chatContainer');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (messages.length === 0) {
            container.innerHTML = '<div class="text-center text-muted p-3">📭 Nenhuma mensagem encontrada</div>';
            return;
        }
        
        messages.forEach(msg => {
            const isPrivate = msg.message_type === 'private';
            const icon = isPrivate ? '🔒' : '🌐';
            const cssClass = isPrivate ? 'message-private' : 'message-public';
            const timeDisplay = utils.formatTime(msg.timestamp);
            
            const msgElement = document.createElement('div');
            msgElement.className = `p-3 mb-2 ${cssClass} fade-in`;
            msgElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center mb-1">
                            <span class="badge bg-secondary me-2">${icon}</span>
                            <strong class="text-primary">${utils.escapeHtml(msg.author)}</strong>
                            <small class="text-muted ms-2">${timeDisplay}</small>
                        </div>
                        <div class="message-content">${utils.escapeHtml(msg.content)}</div>
                    </div>
                </div>
            `;
            
            container.appendChild(msgElement);
        });
        
        // Scroll para o final
        container.scrollTop = container.scrollHeight;
    },
    
    updateLastUpdate() {
        const element = document.getElementById('lastUpdate');
        if (element) {
            const now = new Date();
            element.textContent = now.toLocaleTimeString('pt-BR');
        }
    },
    
    startAutoRefresh() {
        this.stopAutoRefresh();
        state.autoRefreshInterval = setInterval(async () => {
            try {
                await Promise.all([
                    messaging.refresh(),
                    status.updateAll()
                ]);
            } catch (error) {
                console.error('Auto-refresh error:', error);
            }
        }, CONFIG.REFRESH_INTERVAL);
    },
    
    stopAutoRefresh() {
        if (state.autoRefreshInterval) {
            clearInterval(state.autoRefreshInterval);
            state.autoRefreshInterval = null;
        }
    }
};

// Funcionalidades específicas
async function toggleOffline() {
    if (!state.currentToken) {
        utils.showToast('Você precisa estar logado', 'warning');
        return;
    }
    
    try {
        const httpPort = utils.getHttpPort(state.currentPort);
        const data = await api.toggleOffline(state.currentToken, httpPort);
        
        if (data.status === 'success') {
            utils.showToast(data.message || 'Status da simulação alterado', 'info');
            await status.updateAll();
        } else {
            utils.showToast(`Erro: ${data.message}`, 'danger');
        }
    } catch (error) {
        utils.showToast(error.message, 'danger');
        console.error('Toggle offline error:', error);
    }
}

async function refreshMessages() {
    try {
        await messaging.refresh();
        utils.showToast('Chat atualizado', 'success', 2000);
    } catch (error) {
        utils.showToast('Erro ao atualizar chat', 'danger');
        console.error('Manual refresh error:', error);
    }
}

function sendMessage(type) {
    messaging.send(type);
}

function readPublic(tcpPort) {
    messaging.readPublic(tcpPort);
}

function logout() {
    auth.logout();
}

function showHelp() {
    const helpModal = new bootstrap.Modal(document.getElementById('helpModal'));
    helpModal.show();
}

// Event Listeners e Inicialização
function setupEventListeners() {
    // Auto-fill password quando usuário é selecionado
    const usernameSelect = document.getElementById('username');
    if (usernameSelect) {
        usernameSelect.addEventListener('change', function() {
            const passwordInput = document.getElementById('password');
            if (passwordInput) {
                passwordInput.value = USER_PASSWORDS[this.value] || '';
            }
        });
    }
    
    // Submit do formulário de login
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', auth.handleLogin);
    }
    
    // Enter para enviar mensagem pública
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage('public');
            }
        });
    }
}

// Inicialização da aplicação (CORRIGIDA - mais segura)
async function initializeApp() {
    console.log('🎯 Sistema de Mensagens Distribuídas - Frontend carregado');
    
    setupEventListeners();
    
    try {
        await status.updateAll();
    } catch (error) {
        console.error('Erro na inicialização:', error);
    }
    
    // Auto-refresh periódico do status
    setInterval(async () => {
        try {
            await status.updateAll();
        } catch (error) {
            // Silencioso
        }
    }, CONFIG.REFRESH_INTERVAL);
}

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', initializeApp);