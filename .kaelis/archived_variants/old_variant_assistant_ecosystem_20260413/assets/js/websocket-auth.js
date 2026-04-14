/**
 * Kaelis WebSocket Authentication
 * JWT身份认证模块 - Kaelis独立认证体系
 */

(function() {
    'use strict';

    // JWT Token管理
    class JWTTokenManager {
        constructor() {
            this.accessToken = null;
            this.refreshToken = null;
            this.expiresAt = null;
            this.tokenKey = 'kaelis_auth_token';
            this.refreshKey = 'kaelis_refresh_token';
        }

        // 从Kaelis获取Token
        async getTokenFromKaelis() {
            // 优先从Kaelis localStorage获取
            let token = localStorage.getItem(this.tokenKey);
            if (token) {
                this.accessToken = token;
                this.decodeToken(token);
                return token;
            }

            // 尝试从cookie获取
            const cookieToken = this.getCookie('kaelis_token') || this.getCookie('access_token');
            if (cookieToken) {
                this.accessToken = cookieToken;
                this.decodeToken(cookieToken);
                this.setToken(cookieToken);
                return cookieToken;
            }

            return null;
        }

        // 用户登录获取Token
        async login(credentials) {
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(credentials)
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.message || 'Login failed');
                }

                const data = await response.json();
                this.setToken(data.access_token, data.refresh_token);
                
                // 触发登录成功事件
                window.dispatchEvent(new CustomEvent('kaelis:login', { 
                    detail: { user: data.user } 
                }));
                
                return data;
            } catch (error) {
                console.error('[JWTTokenManager] 登录失败:', error);
                throw error;
            }
        }

        // 用户注册
        async register(userData) {
            try {
                const response = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(userData)
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.message || 'Registration failed');
                }

                return await response.json();
            } catch (error) {
                console.error('[JWTTokenManager] 注册失败:', error);
                throw error;
            }
        }

        // 解析Token
        decodeToken(token) {
            try {
                const base64Url = token.split('.')[1];
                const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                const jsonPayload = decodeURIComponent(
                    atob(base64).split('').map(c => {
                        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                    }).join('')
                );
                
                const payload = JSON.parse(jsonPayload);
                this.expiresAt = payload.exp * 1000;
                return payload;
            } catch (error) {
                console.error('[JWTTokenManager] Token解析失败:', error);
                return null;
            }
        }

        // 检查Token是否有效
        isTokenValid() {
            if (!this.accessToken) return false;
            if (!this.expiresAt) return false;
            return Date.now() < this.expiresAt - 60000; // 提前1分钟过期
        }

        // 检查Token是否即将过期
        isTokenExpiringSoon(thresholdMinutes = 5) {
            if (!this.expiresAt) return true;
            return Date.now() > this.expiresAt - (thresholdMinutes * 60000);
        }

        // 刷新Token
        async refreshAccessToken() {
            const refreshToken = localStorage.getItem(this.refreshKey);
            
            if (!refreshToken) {
                throw new Error('No refresh token available');
            }

            try {
                const response = await fetch('/api/auth/refresh', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ refresh_token: refreshToken })
                });

                if (!response.ok) {
                    throw new Error('Token refresh failed');
                }

                const data = await response.json();
                this.setToken(data.access_token, data.refresh_token);
                return data.access_token;
            } catch (error) {
                console.error('[JWTTokenManager] Token刷新失败:', error);
                this.clearToken();
                throw error;
            }
        }

        // 设置Token
        setToken(accessToken, refreshToken = null) {
            this.accessToken = accessToken;
            this.decodeToken(accessToken);
            localStorage.setItem(this.tokenKey, accessToken);
            
            if (refreshToken) {
                this.refreshToken = refreshToken;
                localStorage.setItem(this.refreshKey, refreshToken);
            }
        }

        // 清除Token
        clearToken() {
            this.accessToken = null;
            this.refreshToken = null;
            this.expiresAt = null;
            localStorage.removeItem(this.tokenKey);
            localStorage.removeItem(this.refreshKey);
        }

        // 获取Cookie
        getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return null;
        }

        // 获取当前Token
        getToken() {
            return this.accessToken;
        }

        // 获取Token信息
        getTokenInfo() {
            if (!this.accessToken) return null;
            return {
                token: this.accessToken.substring(0, 20) + '...',
                expiresAt: this.expiresAt,
                isValid: this.isTokenValid(),
                isExpiringSoon: this.isTokenExpiringSoon()
            };
        }
    }

    // WebSocket认证拦截器
    class WebSocketAuthInterceptor {
        constructor(tokenManager) {
            this.tokenManager = tokenManager;
            this.authCallbacks = {
                onAuthSuccess: [],
                onAuthFailure: [],
                onTokenExpired: []
            };
        }

        // 创建认证消息
        async createAuthMessage() {
            let token = this.tokenManager.getToken();

            // 如果没有token，尝试从Kaelis获取
            if (!token) {
                token = await this.tokenManager.getTokenFromKaelis();
            }

            // 如果token即将过期，尝试刷新
            if (token && this.tokenManager.isTokenExpiringSoon()) {
                try {
                    token = await this.tokenManager.refreshAccessToken();
                } catch (error) {
                    this.trigger('onTokenExpired', error);
                    throw error;
                }
            }

            if (!token) {
                throw new Error('No valid authentication token');
            }

            return {
                type: 'auth',
                payload: {
                    token: token,
                    timestamp: Date.now(),
                    clientInfo: {
                        userAgent: navigator.userAgent,
                        platform: navigator.platform
                    }
                }
            };
        }

        // 验证服务器响应
        validateAuthResponse(response) {
            if (response.type === 'auth_success') {
                this.trigger('onAuthSuccess', response.payload);
                return true;
            } else if (response.type === 'auth_failure') {
                this.trigger('onAuthFailure', response.payload);
                return false;
            }
            return null;
        }

        // 事件监听
        on(event, callback) {
            if (this.authCallbacks[event]) {
                this.authCallbacks[event].push(callback);
            }
            return this;
        }

        trigger(event, data) {
            if (this.authCallbacks[event]) {
                this.authCallbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error('[WebSocketAuthInterceptor] 回调错误:', error);
                    }
                });
            }
        }
    }

    // 增强版WebSocket客户端（带认证）
    class AuthenticatedWebSocketClient {
        constructor(options = {}) {
            this.url = options.url;
            this.role = options.role || 'control';
            this.clientId = options.clientId || `client_${Date.now()}`;
            
            this.tokenManager = new JWTTokenManager();
            this.authInterceptor = new WebSocketAuthInterceptor(this.tokenManager);
            
            this.ws = null;
            this.state = 'closed';
            this.authenticated = false;
            this.reconnectAttempts = 0;
            this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
            this.reconnectInterval = options.reconnectInterval || 3000;
            
            this.messageHandlers = new Map();
            this.pendingMessages = [];
            this.heartbeatInterval = null;
            
            this.eventCallbacks = {
                onOpen: [],
                onClose: [],
                onError: [],
                onMessage: [],
                onAuthSuccess: [],
                onAuthFailure: [],
                onReconnect: []
            };

            // 绑定认证事件
            this.setupAuthCallbacks();
        }

        setupAuthCallbacks() {
            this.authInterceptor
                .on('onAuthSuccess', (payload) => {
                    this.authenticated = true;
                    this.triggerEvent('onAuthSuccess', payload);
                    this.flushPendingMessages();
                    this.startHeartbeat();
                })
                .on('onAuthFailure', (payload) => {
                    this.authenticated = false;
                    this.triggerEvent('onAuthFailure', payload);
                    // 认证失败，不重连
                    this.reconnectAttempts = this.maxReconnectAttempts;
                })
                .on('onTokenExpired', () => {
                    this.authenticated = false;
                    this.triggerEvent('onAuthFailure', { reason: 'token_expired' });
                });
        }

        // 连接（带认证）
        async connect() {
            return new Promise(async (resolve, reject) => {
                try {
                    this.ws = new WebSocket(this.url);
                    this.state = 'connecting';

                    this.ws.onopen = async (event) => {
                        this.state = 'open';
                        this.reconnectAttempts = 0;
                        this.triggerEvent('onOpen', event);

                        // 发送认证消息
                        try {
                            const authMessage = await this.authInterceptor.createAuthMessage();
                            this.send(authMessage);
                        } catch (error) {
                            reject(error);
                            return;
                        }

                        resolve(event);
                    };

                    this.ws.onmessage = (event) => {
                        this.handleMessage(event.data);
                        this.triggerEvent('onMessage', event);
                    };

                    this.ws.onclose = (event) => {
                        this.state = 'closed';
                        this.authenticated = false;
                        this.stopHeartbeat();
                        this.triggerEvent('onClose', event);

                        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
                            this.scheduleReconnect();
                        }
                    };

                    this.ws.onerror = (error) => {
                        this.triggerEvent('onError', error);
                        reject(error);
                    };

                } catch (error) {
                    reject(error);
                }
            });
        }

        // 处理消息
        handleMessage(data) {
            try {
                const message = JSON.parse(data);

                // 处理认证响应
                const authResult = this.authInterceptor.validateAuthResponse(message);
                if (authResult !== null) return;

                // 处理心跳
                if (message.type === 'ping') {
                    this.send({ type: 'pong', timestamp: Date.now() });
                    return;
                }

                // 调用注册的消息处理器
                const handler = this.messageHandlers.get(message.type);
                if (handler) {
                    handler(message);
                }

            } catch (error) {
                console.error('[AuthenticatedWebSocketClient] 消息解析失败:', error);
            }
        }

        // 发送消息
        send(message) {
            const data = typeof message === 'string' ? message : JSON.stringify(message);

            if (this.state === 'open') {
                this.ws.send(data);
            } else {
                this.pendingMessages.push(data);
            }
        }

        // 刷新待处理消息
        flushPendingMessages() {
            while (this.pendingMessages.length > 0 && this.state === 'open') {
                const message = this.pendingMessages.shift();
                this.ws.send(message);
            }
        }

        // 注册消息处理器
        on(messageType, handler) {
            this.messageHandlers.set(messageType, handler);
            return this;
        }

        // 事件监听
        addEventListener(event, callback) {
            if (this.eventCallbacks[event]) {
                this.eventCallbacks[event].push(callback);
            }
            return this;
        }

        triggerEvent(event, data) {
            if (this.eventCallbacks[event]) {
                this.eventCallbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error(`[AuthenticatedWebSocketClient] 事件处理错误:`, error);
                    }
                });
            }
        }

        // 启动心跳
        startHeartbeat() {
            this.heartbeatInterval = setInterval(() => {
                if (this.state === 'open' && this.authenticated) {
                    this.send({
                        type: 'ping',
                        timestamp: Date.now()
                    });
                }
            }, 30000);
        }

        // 停止心跳
        stopHeartbeat() {
            if (this.heartbeatInterval) {
                clearInterval(this.heartbeatInterval);
                this.heartbeatInterval = null;
            }
        }

        // 计划重连
        scheduleReconnect() {
            this.reconnectAttempts++;
            const delay = Math.min(this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1), 30000);

            console.log(`[AuthenticatedWebSocketClient] ${delay}ms后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

            setTimeout(() => {
                this.triggerEvent('onReconnect', { attempt: this.reconnectAttempts });
                this.connect();
            }, delay);
        }

        // 断开连接
        disconnect() {
            this.stopHeartbeat();
            if (this.ws) {
                this.ws.close(1000, 'Client disconnect');
            }
        }

        // 获取状态
        getState() {
            return {
                state: this.state,
                connected: this.state === 'open',
                authenticated: this.authenticated,
                clientId: this.clientId,
                role: this.role,
                pendingMessages: this.pendingMessages.length,
                tokenInfo: this.tokenManager.getTokenInfo()
            };
        }

        // 登出
        logout() {
            this.tokenManager.clearToken();
            this.disconnect();
        }
    }

    // 导出
    window.JWTTokenManager = JWTTokenManager;
    window.WebSocketAuthInterceptor = WebSocketAuthInterceptor;
    window.AuthenticatedWebSocketClient = AuthenticatedWebSocketClient;

    console.log('[WebSocketAuth] JWT认证模块已加载');
})();
