/**
 * Kaelis WebSocket Authentication Unified
 * 统一版JWT身份认证模块 - 整合基础版和增强版功能
 * 
 * 功能特性：
 * - JWT Token管理（获取、刷新、过期检查）
 * - 安全存储（XSS防护、内存降级）
 * - 设备管理（多设备限制、设备指纹）
 * - 速率限制（登录保护）
 * - Token黑名单
 * - WebSocket认证拦截器
 * - 自动重连与心跳
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.WebSocketAuth = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';

    // ==================== 配置常量 ====================
    const CONFIG = {
        TOKEN_REFRESH_WINDOW: 300,    // Token刷新窗口期（秒）
        MAX_DEVICES: 5,               // 最大设备数
        SESSION_TIMEOUT: 3600,        // 会话超时（秒）
        RATE_LIMIT_ATTEMPTS: 5,       // 登录尝试限制
        RATE_LIMIT_WINDOW: 300,       // 限制窗口（秒）
        HEARTBEAT_INTERVAL: 30000,    // 心跳间隔（毫秒）
        MAX_RECONNECT_ATTEMPTS: 10,   // 最大重连次数
        RECONNECT_BASE_DELAY: 3000    // 重连基础延迟（毫秒）
    };

    // 事件类型
    const AUTH_EVENTS = {
        LOGIN_SUCCESS: 'auth:login:success',
        LOGIN_FAILURE: 'auth:login:failure',
        TOKEN_REFRESH: 'auth:token:refresh',
        TOKEN_EXPIRED: 'auth:token:expired',
        LOGOUT: 'auth:logout',
        SESSION_INVALID: 'auth:session:invalid',
        DEVICE_LIMIT: 'auth:device:limit',
        SECURITY_ALERT: 'auth:security:alert',
        WS_AUTH_SUCCESS: 'ws:auth:success',
        WS_AUTH_FAILURE: 'ws:auth:failure',
        WS_RECONNECT: 'ws:reconnect'
    };

    // ==================== 安全存储类 ====================
    class SecureStorage {
        constructor(prefix = 'kaelis_') {
            this.prefix = prefix;
            this.memoryCache = new Map();
            this.useMemory = false;
        }

        isStorageAvailable(type) {
            try {
                const storage = window[type];
                const test = '__storage_test__';
                storage.setItem(test, test);
                storage.removeItem(test);
                return true;
            } catch (e) {
                return false;
            }
        }

        setItem(key, value, options = {}) {
            const fullKey = this.prefix + key;
            const data = {
                value: value,
                timestamp: Date.now(),
                expires: options.expires ? Date.now() + options.expires * 1000 : null,
                secure: options.secure || false
            };

            if (options.secure || this.useMemory) {
                this.memoryCache.set(fullKey, data);
                return;
            }

            if (this.isStorageAvailable('localStorage')) {
                try {
                    localStorage.setItem(fullKey, JSON.stringify(data));
                } catch (e) {
                    this.useMemory = true;
                    this.memoryCache.set(fullKey, data);
                }
            } else {
                this.memoryCache.set(fullKey, data);
            }
        }

        getItem(key) {
            const fullKey = this.prefix + key;

            if (this.memoryCache.has(fullKey)) {
                const data = this.memoryCache.get(fullKey);
                if (data.expires && Date.now() > data.expires) {
                    this.memoryCache.delete(fullKey);
                    return null;
                }
                return data.value;
            }

            if (this.isStorageAvailable('localStorage')) {
                try {
                    const item = localStorage.getItem(fullKey);
                    if (!item) return null;

                    const data = JSON.parse(item);
                    if (data.expires && Date.now() > data.expires) {
                        localStorage.removeItem(fullKey);
                        return null;
                    }
                    return data.value;
                } catch (e) {
                    return null;
                }
            }

            return null;
        }

        removeItem(key) {
            const fullKey = this.prefix + key;
            this.memoryCache.delete(fullKey);
            if (this.isStorageAvailable('localStorage')) {
                localStorage.removeItem(fullKey);
            }
        }

        clear() {
            this.memoryCache.clear();
            if (this.isStorageAvailable('localStorage')) {
                for (let i = localStorage.length - 1; i >= 0; i--) {
                    const key = localStorage.key(i);
                    if (key && key.startsWith(this.prefix)) {
                        localStorage.removeItem(key);
                    }
                }
            }
        }
    }

    // ==================== 设备管理器 ====================
    class DeviceManager {
        constructor(storage, maxDevices = CONFIG.MAX_DEVICES) {
            this.storage = storage;
            this.maxDevices = maxDevices;
            this.deviceId = this.getOrCreateDeviceId();
        }

        getOrCreateDeviceId() {
            let deviceId = this.storage.getItem('device_id');
            if (!deviceId) {
                deviceId = this.generateDeviceId();
                this.storage.setItem('device_id', deviceId, { expires: 365 * 24 * 3600 });
            }
            return deviceId;
        }

        generateDeviceId() {
            const components = [
                navigator.userAgent,
                navigator.language,
                screen.colorDepth,
                screen.width + 'x' + screen.height,
                new Date().getTimezoneOffset(),
                !!window.sessionStorage,
                !!window.localStorage,
                navigator.hardwareConcurrency || 'unknown'
            ];
            const fingerprint = components.join('###');
            return this.hashString(fingerprint);
        }

        hashString(str) {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                const char = str.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash;
            }
            return 'device_' + Math.abs(hash).toString(16);
        }

        getDevices() {
            return this.storage.getItem('devices') || [];
        }

        registerDevice() {
            const devices = this.getDevices();
            const deviceInfo = {
                id: this.deviceId,
                name: this.getDeviceName(),
                platform: navigator.platform,
                browser: this.getBrowserInfo(),
                registeredAt: Date.now(),
                lastActive: Date.now()
            };

            const existingIndex = devices.findIndex(d => d.id === this.deviceId);
            if (existingIndex >= 0) {
                devices[existingIndex] = deviceInfo;
            } else {
                if (devices.length >= this.maxDevices) {
                    throw new Error('DEVICE_LIMIT_EXCEEDED');
                }
                devices.push(deviceInfo);
            }

            this.storage.setItem('devices', devices, { secure: true });
            return deviceInfo;
        }

        removeDevice(deviceId) {
            const devices = this.getDevices().filter(d => d.id !== deviceId);
            this.storage.setItem('devices', devices, { secure: true });
        }

        getDeviceName() {
            return `${this.getBrowserInfo()} on ${navigator.platform}`;
        }

        getBrowserInfo() {
            const ua = navigator.userAgent;
            if (ua.includes('Chrome')) return 'Chrome';
            if (ua.includes('Firefox')) return 'Firefox';
            if (ua.includes('Safari')) return 'Safari';
            if (ua.includes('Edge')) return 'Edge';
            return 'Unknown';
        }
    }

    // ==================== 速率限制器 ====================
    class RateLimiter {
        constructor(maxAttempts = CONFIG.RATE_LIMIT_ATTEMPTS, 
                    windowMs = CONFIG.RATE_LIMIT_WINDOW * 1000) {
            this.maxAttempts = maxAttempts;
            this.windowMs = windowMs;
            this.attempts = new Map();
        }

        check(key) {
            const now = Date.now();
            const attempts = this.attempts.get(key) || [];
            const validAttempts = attempts.filter(t => now - t < this.windowMs);

            if (validAttempts.length >= this.maxAttempts) {
                const oldestAttempt = validAttempts[0];
                const retryAfter = Math.ceil((this.windowMs - (now - oldestAttempt)) / 1000);
                return { allowed: false, retryAfter };
            }

            return { allowed: true, remaining: this.maxAttempts - validAttempts.length };
        }

        record(key) {
            const now = Date.now();
            const attempts = this.attempts.get(key) || [];
            attempts.push(now);
            this.attempts.set(key, attempts);
        }

        reset(key) {
            this.attempts.delete(key);
        }
    }

    // ==================== JWT Token管理器 ====================
    class JWTTokenManager {
        constructor(options = {}) {
            this.storage = new SecureStorage(options.storagePrefix);
            this.deviceManager = new DeviceManager(this.storage, options.maxDevices);
            this.rateLimiter = new RateLimiter();
            this.tokenBlacklist = new Set();

            this.tokenKey = 'auth_token';
            this.refreshKey = 'refresh_token';
            this.accessToken = null;
            this.refreshToken = null;
            this.expiresAt = null;
            this.user = null;
            this.refreshPromise = null;
            this.eventListeners = new Map();

            this.init();
        }

        init() {
            this.restoreFromStorage();
            this.startTokenExpiryCheck();
            
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) {
                    this.checkTokenValidity();
                }
            });
        }

        restoreFromStorage() {
            const token = this.storage.getItem(this.tokenKey);
            const refreshToken = this.storage.getItem(this.refreshKey);
            if (token && refreshToken) {
                this.setToken(token, refreshToken, false);
            }
        }

        async login(credentials) {
            const identifier = credentials.email || credentials.username || 'unknown';
            const rateCheck = this.rateLimiter.check(`login:${identifier}`);
            
            if (!rateCheck.allowed) {
                this.emit(AUTH_EVENTS.SECURITY_ALERT, {
                    type: 'RATE_LIMIT_EXCEEDED',
                    message: `登录尝试过于频繁，请${rateCheck.retryAfter}秒后重试`
                });
                throw new Error(`RATE_LIMIT_EXCEEDED:${rateCheck.retryAfter}`);
            }

            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Device-ID': this.deviceManager.deviceId
                    },
                    body: JSON.stringify(credentials)
                });

                if (!response.ok) {
                    this.rateLimiter.record(`login:${identifier}`);
                    const error = await response.json();
                    this.emit(AUTH_EVENTS.LOGIN_FAILURE, { error: error.message });
                    throw new Error(error.message || 'Login failed');
                }

                const data = await response.json();

                if (data.deviceLimitReached) {
                    this.emit(AUTH_EVENTS.DEVICE_LIMIT, { devices: data.devices });
                    throw new Error('DEVICE_LIMIT_EXCEEDED');
                }

                this.setToken(data.access_token, data.refresh_token);
                this.user = data.user;
                this.deviceManager.registerDevice();
                this.rateLimiter.reset(`login:${identifier}`);
                this.emit(AUTH_EVENTS.LOGIN_SUCCESS, { user: data.user });

                return data;
            } catch (error) {
                if (!error.message.includes('RATE_LIMIT') && 
                    !error.message.includes('DEVICE_LIMIT')) {
                    this.rateLimiter.record(`login:${identifier}`);
                }
                throw error;
            }
        }

        async logout(options = {}) {
            const token = this.accessToken;
            
            if (token && !options.silent) {
                try {
                    await fetch('/api/auth/logout', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'X-Device-ID': this.deviceManager.deviceId
                        }
                    });
                } catch (error) {
                    console.warn('[JWTTokenManager] 服务器登出通知失败:', error);
                }
            }

            if (token) {
                this.tokenBlacklist.add(token);
            }

            this.clearToken();
            this.deviceManager.removeDevice(this.deviceManager.deviceId);
            this.emit(AUTH_EVENTS.LOGOUT, { user: this.user });
            this.user = null;
        }

        setToken(accessToken, refreshToken, persist = true) {
            this.accessToken = accessToken;
            this.refreshToken = refreshToken;

            const payload = this.decodeToken(accessToken);
            if (payload) {
                this.expiresAt = payload.exp * 1000;
                this.user = payload.user || null;
            }

            if (persist) {
                const expiresIn = this.expiresAt ? 
                    Math.floor((this.expiresAt - Date.now()) / 1000) : 3600;
                
                this.storage.setItem(this.tokenKey, accessToken, { 
                    expires: expiresIn,
                    secure: true 
                });
                this.storage.setItem(this.refreshKey, refreshToken, { 
                    expires: expiresIn * 2,
                    secure: true 
                });
            }
        }

        clearToken() {
            this.accessToken = null;
            this.refreshToken = null;
            this.expiresAt = null;
            this.storage.removeItem(this.tokenKey);
            this.storage.removeItem(this.refreshKey);
        }

        async refreshAccessToken() {
            if (this.refreshPromise) {
                return this.refreshPromise;
            }

            this.refreshPromise = this.doRefresh();

            try {
                const result = await this.refreshPromise;
                return result;
            } finally {
                this.refreshPromise = null;
            }
        }

        async doRefresh() {
            if (!this.refreshToken) {
                throw new Error('No refresh token available');
            }

            if (this.tokenBlacklist.has(this.refreshToken)) {
                this.emit(AUTH_EVENTS.SESSION_INVALID, { reason: 'TOKEN_BLACKLISTED' });
                throw new Error('TOKEN_BLACKLISTED');
            }

            try {
                const response = await fetch('/api/auth/refresh', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Device-ID': this.deviceManager.deviceId
                    },
                    body: JSON.stringify({ 
                        refresh_token: this.refreshToken,
                        device_id: this.deviceManager.deviceId
                    })
                });

                if (!response.ok) {
                    if (response.status === 401) {
                        this.emit(AUTH_EVENTS.SESSION_INVALID, { reason: 'REFRESH_FAILED' });
                        await this.logout({ silent: true });
                    }
                    throw new Error('Token refresh failed');
                }

                const data = await response.json();
                this.setToken(data.access_token, data.refresh_token);
                this.emit(AUTH_EVENTS.TOKEN_REFRESH, { user: this.user });

                return data.access_token;
            } catch (error) {
                console.error('[JWTTokenManager] Token刷新失败:', error);
                throw error;
            }
        }

        checkTokenValidity() {
            if (!this.accessToken) return false;
            if (this.tokenBlacklist.has(this.accessToken)) return false;
            if (!this.expiresAt) return false;
            return Date.now() < this.expiresAt - 300000; // 提前5分钟
        }

        shouldRefresh() {
            if (!this.expiresAt) return false;
            return Date.now() > this.expiresAt - (CONFIG.TOKEN_REFRESH_WINDOW * 1000);
        }

        startTokenExpiryCheck() {
            setInterval(() => {
                if (this.shouldRefresh()) {
                    this.refreshAccessToken().catch(error => {
                        console.warn('[JWTTokenManager] 自动刷新失败:', error);
                    });
                }
            }, 60000);
        }

        decodeToken(token) {
            try {
                const base64Url = token.split('.')[1];
                const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                const jsonPayload = decodeURIComponent(
                    atob(base64).split('').map(c => {
                        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                    }).join('')
                );
                return JSON.parse(jsonPayload);
            } catch (error) {
                return null;
            }
        }

        getToken() {
            return this.accessToken;
        }

        getTokenInfo() {
            if (!this.accessToken) return null;
            return {
                token: this.accessToken.substring(0, 20) + '...',
                expiresAt: this.expiresAt,
                isValid: this.checkTokenValidity(),
                isExpiringSoon: this.shouldRefresh()
            };
        }

        on(event, callback) {
            if (!this.eventListeners.has(event)) {
                this.eventListeners.set(event, []);
            }
            this.eventListeners.get(event).push(callback);
        }

        emit(event, data) {
            const listeners = this.eventListeners.get(event) || [];
            listeners.forEach(cb => {
                try {
                    cb(data);
                } catch (error) {
                    console.error(`[JWTTokenManager] 事件处理错误 [${event}]:`, error);
                }
            });
            window.dispatchEvent(new CustomEvent(event, { detail: data }));
        }

        getState() {
            return {
                isAuthenticated: !!this.accessToken,
                isTokenValid: this.checkTokenValidity(),
                shouldRefresh: this.shouldRefresh(),
                user: this.user,
                deviceId: this.deviceManager.deviceId,
                devices: this.deviceManager.getDevices()
            };
        }
    }

    // ==================== WebSocket认证客户端 ====================
    class AuthenticatedWebSocketClient {
        constructor(options = {}) {
            this.url = options.url;
            this.role = options.role || 'control';
            this.clientId = options.clientId || `client_${Date.now()}`;
            
            this.tokenManager = options.tokenManager || new JWTTokenManager();
            
            this.ws = null;
            this.state = 'closed';
            this.authenticated = false;
            this.reconnectAttempts = 0;
            this.maxReconnectAttempts = options.maxReconnectAttempts || CONFIG.MAX_RECONNECT_ATTEMPTS;
            this.reconnectInterval = options.reconnectInterval || CONFIG.RECONNECT_BASE_DELAY;
            
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
        }

        async connect() {
            return new Promise(async (resolve, reject) => {
                try {
                    this.ws = new WebSocket(this.url);
                    this.state = 'connecting';

                    this.ws.onopen = async (event) => {
                        this.state = 'open';
                        this.reconnectAttempts = 0;
                        this.triggerEvent('onOpen', event);

                        try {
                            const authMessage = await this.createAuthMessage();
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

        async createAuthMessage() {
            let token = this.tokenManager.getToken();

            if (!token) {
                throw new Error('No valid authentication token');
            }

            if (this.tokenManager.shouldRefresh()) {
                try {
                    token = await this.tokenManager.refreshAccessToken();
                } catch (error) {
                    this.emit(AUTH_EVENTS.TOKEN_EXPIRED, error);
                    throw error;
                }
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

        handleMessage(data) {
            try {
                const message = JSON.parse(data);

                // 处理认证响应
                if (message.type === 'auth_success') {
                    this.authenticated = true;
                    this.triggerEvent('onAuthSuccess', message.payload);
                    this.flushPendingMessages();
                    this.startHeartbeat();
                    return;
                } else if (message.type === 'auth_failure') {
                    this.authenticated = false;
                    this.triggerEvent('onAuthFailure', message.payload);
                    this.reconnectAttempts = this.maxReconnectAttempts; // 不重连
                    return;
                }

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

        send(message) {
            const data = typeof message === 'string' ? message : JSON.stringify(message);

            if (this.state === 'open') {
                this.ws.send(data);
            } else {
                this.pendingMessages.push(data);
            }
        }

        flushPendingMessages() {
            while (this.pendingMessages.length > 0 && this.state === 'open') {
                const message = this.pendingMessages.shift();
                this.ws.send(message);
            }
        }

        on(messageType, handler) {
            this.messageHandlers.set(messageType, handler);
            return this;
        }

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

        startHeartbeat() {
            this.heartbeatInterval = setInterval(() => {
                if (this.state === 'open' && this.authenticated) {
                    this.send({ type: 'ping', timestamp: Date.now() });
                }
            }, CONFIG.HEARTBEAT_INTERVAL);
        }

        stopHeartbeat() {
            if (this.heartbeatInterval) {
                clearInterval(this.heartbeatInterval);
                this.heartbeatInterval = null;
            }
        }

        scheduleReconnect() {
            this.reconnectAttempts++;
            const delay = Math.min(
                this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1), 
                30000
            );

            console.log(`[AuthenticatedWebSocketClient] ${delay}ms后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

            setTimeout(() => {
                this.triggerEvent('onReconnect', { attempt: this.reconnectAttempts });
                this.connect();
            }, delay);
        }

        disconnect() {
            this.stopHeartbeat();
            if (this.ws) {
                this.ws.close(1000, 'Client disconnect');
            }
        }

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
    }

    // ==================== 导出 ====================
    return {
        // 类定义
        JWTTokenManager,
        AuthenticatedWebSocketClient,
        SecureStorage,
        DeviceManager,
        RateLimiter,
        
        // 常量
        CONFIG,
        AUTH_EVENTS,
        
        // 便捷访问
        createTokenManager: (options) => new JWTTokenManager(options),
        createWebSocketClient: (options) => new AuthenticatedWebSocketClient(options)
    };
}));
