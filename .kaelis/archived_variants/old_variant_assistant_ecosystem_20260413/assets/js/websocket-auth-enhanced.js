/**
 * Kaelis WebSocket Authentication Enhanced
 * 增强版JWT身份认证模块 - 参考socket.io-auth和jsonwebtoken最佳实践
 * 增加：Token黑名单、多设备管理、安全审计、CSRF防护
 */

(function() {
    'use strict';

    // 安全配置
    const SECURITY_CONFIG = {
        TOKEN_REFRESH_WINDOW: 300, // Token刷新窗口期（秒）
        MAX_DEVICES: 5,            // 最大设备数
        SESSION_TIMEOUT: 3600,     // 会话超时（秒）
        RATE_LIMIT_ATTEMPTS: 5,    // 登录尝试限制
        RATE_LIMIT_WINDOW: 300     // 限制窗口（秒）
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
        SECURITY_ALERT: 'auth:security:alert'
    };

    /**
     * 安全存储 - 防止XSS攻击的Token存储
     */
    class SecureStorage {
        constructor(prefix = 'kaelis_') {
            this.prefix = prefix;
            this.memoryCache = new Map();
            this.useMemory = false; // 内存模式（无痕浏览）
        }

        // 检测存储可用性
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

        // 设置项
        setItem(key, value, options = {}) {
            const fullKey = this.prefix + key;
            const data = {
                value: value,
                timestamp: Date.now(),
                expires: options.expires ? Date.now() + options.expires * 1000 : null,
                secure: options.secure || false
            };

            // 敏感数据仅内存存储
            if (options.secure || this.useMemory) {
                this.memoryCache.set(fullKey, data);
                return;
            }

            if (this.isStorageAvailable('localStorage')) {
                try {
                    localStorage.setItem(fullKey, JSON.stringify(data));
                } catch (e) {
                    // 存储已满，切换到内存模式
                    this.useMemory = true;
                    this.memoryCache.set(fullKey, data);
                }
            } else {
                this.memoryCache.set(fullKey, data);
            }
        }

        // 获取项
        getItem(key) {
            const fullKey = this.prefix + key;

            // 优先从内存获取
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

        // 删除项
        removeItem(key) {
            const fullKey = this.prefix + key;
            this.memoryCache.delete(fullKey);

            if (this.isStorageAvailable('localStorage')) {
                localStorage.removeItem(fullKey);
            }
        }

        // 清除所有
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

    /**
     * 设备管理器 - 多设备登录管理
     */
    class DeviceManager {
        constructor(storage, maxDevices = SECURITY_CONFIG.MAX_DEVICES) {
            this.storage = storage;
            this.maxDevices = maxDevices;
            this.deviceId = this.getOrCreateDeviceId();
        }

        // 获取或创建设备ID
        getOrCreateDeviceId() {
            let deviceId = this.storage.getItem('device_id');
            if (!deviceId) {
                deviceId = this.generateDeviceId();
                this.storage.setItem('device_id', deviceId, { expires: 365 * 24 * 3600 });
            }
            return deviceId;
        }

        // 生成设备ID
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

        // 简单哈希
        hashString(str) {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                const char = str.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash;
            }
            return 'device_' + Math.abs(hash).toString(16);
        }

        // 注册设备
        async registerDevice(token) {
            const devices = this.getDevices();

            // 检查设备限制
            if (devices.length >= this.maxDevices && !devices.find(d => d.id === this.deviceId)) {
                throw new Error('DEVICE_LIMIT_EXCEEDED');
            }

            const deviceInfo = {
                id: this.deviceId,
                name: this.getDeviceName(),
                platform: navigator.platform,
                browser: this.getBrowserInfo(),
                registeredAt: Date.now(),
                lastActive: Date.now()
            };

            // 更新设备列表
            const existingIndex = devices.findIndex(d => d.id === this.deviceId);
            if (existingIndex >= 0) {
                devices[existingIndex] = deviceInfo;
            } else {
                devices.push(deviceInfo);
            }

            this.storage.setItem('devices', devices, { secure: true });
            return deviceInfo;
        }

        // 获取设备列表
        getDevices() {
            return this.storage.getItem('devices') || [];
        }

        // 移除设备
        removeDevice(deviceId) {
            const devices = this.getDevices().filter(d => d.id !== deviceId);
            this.storage.setItem('devices', devices, { secure: true });
        }

        // 获取设备名称
        getDeviceName() {
            const platform = navigator.platform;
            const browser = this.getBrowserInfo();
            return `${browser} on ${platform}`;
        }

        // 获取浏览器信息
        getBrowserInfo() {
            const ua = navigator.userAgent;
            if (ua.includes('Chrome')) return 'Chrome';
            if (ua.includes('Firefox')) return 'Firefox';
            if (ua.includes('Safari')) return 'Safari';
            if (ua.includes('Edge')) return 'Edge';
            return 'Unknown';
        }

        // 更新活跃时间
        updateLastActive() {
            const devices = this.getDevices();
            const device = devices.find(d => d.id === this.deviceId);
            if (device) {
                device.lastActive = Date.now();
                this.storage.setItem('devices', devices, { secure: true });
            }
        }
    }

    /**
     * 速率限制器
     */
    class RateLimiter {
        constructor(maxAttempts = SECURITY_CONFIG.RATE_LIMIT_ATTEMPTS, 
                    windowMs = SECURITY_CONFIG.RATE_LIMIT_WINDOW * 1000) {
            this.maxAttempts = maxAttempts;
            this.windowMs = windowMs;
            this.attempts = new Map();
        }

        // 检查是否允许
        check(key) {
            const now = Date.now();
            const attempts = this.attempts.get(key) || [];

            // 清理过期记录
            const validAttempts = attempts.filter(t => now - t < this.windowMs);

            if (validAttempts.length >= this.maxAttempts) {
                const oldestAttempt = validAttempts[0];
                const retryAfter = Math.ceil((this.windowMs - (now - oldestAttempt)) / 1000);
                return { allowed: false, retryAfter };
            }

            return { allowed: true, remaining: this.maxAttempts - validAttempts.length };
        }

        // 记录尝试
        record(key) {
            const now = Date.now();
            const attempts = this.attempts.get(key) || [];
            attempts.push(now);
            this.attempts.set(key, attempts);
        }

        // 重置
        reset(key) {
            this.attempts.delete(key);
        }
    }

    /**
     * 增强版JWT Token管理器
     */
    class EnhancedJWTTokenManager {
        constructor(options = {}) {
            this.storage = new SecureStorage(options.storagePrefix);
            this.deviceManager = new DeviceManager(this.storage, options.maxDevices);
            this.rateLimiter = new RateLimiter();

            this.tokenKey = 'auth_token';
            this.refreshKey = 'refresh_token';
            this.tokenBlacklist = new Set();

            this.accessToken = null;
            this.refreshToken = null;
            this.expiresAt = null;
            this.user = null;

            this.refreshPromise = null;
            this.eventListeners = new Map();

            // 初始化
            this.init();
        }

        // 初始化
        init() {
            // 从存储恢复
            this.restoreFromStorage();

            // 启动Token过期检查
            this.startTokenExpiryCheck();

            // 页面可见性变化处理
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) {
                    this.checkTokenValidity();
                }
            });
        }

        // 从存储恢复
        restoreFromStorage() {
            const token = this.storage.getItem(this.tokenKey);
            const refreshToken = this.storage.getItem(this.refreshKey);

            if (token && refreshToken) {
                this.setToken(token, refreshToken, false);
            }
        }

        // 登录
        async login(credentials, options = {}) {
            const identifier = credentials.email || credentials.username || 'unknown';

            // 速率限制检查
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
                        'X-Device-ID': this.deviceManager.deviceId,
                        'X-CSRF-Token': this.getCSRFToken()
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

                // 检查设备限制
                if (data.deviceLimitReached) {
                    this.emit(AUTH_EVENTS.DEVICE_LIMIT, {
                        devices: data.devices,
                        message: '设备数量已达上限'
                    });
                    throw new Error('DEVICE_LIMIT_EXCEEDED');
                }

                // 设置Token
                this.setToken(data.access_token, data.refresh_token);
                this.user = data.user;

                // 注册设备
                await this.deviceManager.registerDevice(data.access_token);

                // 重置速率限制
                this.rateLimiter.reset(`login:${identifier}`);

                // 触发事件
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

        // 登出
        async logout(options = {}) {
            const token = this.accessToken;

            // 通知服务器
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
                    console.warn('[EnhancedJWTTokenManager] 服务器登出通知失败:', error);
                }
            }

            // 加入黑名单
            if (token) {
                this.tokenBlacklist.add(token);
            }

            // 清理本地状态
            this.clearToken();
            this.deviceManager.removeDevice(this.deviceManager.deviceId);

            this.emit(AUTH_EVENTS.LOGOUT, { user: this.user });
            this.user = null;
        }

        // 设置Token
        setToken(accessToken, refreshToken, persist = true) {
            this.accessToken = accessToken;
            this.refreshToken = refreshToken;

            // 解析Token
            const payload = this.decodeToken(accessToken);
            if (payload) {
                this.expiresAt = payload.exp * 1000;
                this.user = payload.user || null;
            }

            // 持久化
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

        // 清理Token
        clearToken() {
            this.accessToken = null;
            this.refreshToken = null;
            this.expiresAt = null;
            this.storage.removeItem(this.tokenKey);
            this.storage.removeItem(this.refreshKey);
        }

        // 刷新Token（带并发控制）
        async refreshAccessToken() {
            // 如果正在刷新，等待结果
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

        // 执行刷新
        async doRefresh() {
            if (!this.refreshToken) {
                throw new Error('No refresh token available');
            }

            // 检查Token是否在黑名单
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
                console.error('[EnhancedJWTTokenManager] Token刷新失败:', error);
                throw error;
            }
        }

        // 检查Token有效性
        checkTokenValidity() {
            if (!this.accessToken) return false;
            if (this.tokenBlacklist.has(this.accessToken)) return false;
            if (!this.expiresAt) return false;

            // 提前5分钟认为过期
            return Date.now() < this.expiresAt - 300000;
        }

        // 检查是否需要刷新
        shouldRefresh() {
            if (!this.expiresAt) return false;
            return Date.now() > this.expiresAt - (SECURITY_CONFIG.TOKEN_REFRESH_WINDOW * 1000);
        }

        // 启动Token过期检查
        startTokenExpiryCheck() {
            setInterval(() => {
                if (this.shouldRefresh()) {
                    this.refreshAccessToken().catch(error => {
                        console.warn('[EnhancedJWTTokenManager] 自动刷新失败:', error);
                    });
                }
            }, 60000); // 每分钟检查
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
                return JSON.parse(jsonPayload);
            } catch (error) {
                return null;
            }
        }

        // 获取CSRF Token
        getCSRFToken() {
            return document.querySelector('meta[name="csrf-token"]')?.content || '';
        }

        // 事件监听
        on(event, callback) {
            if (!this.eventListeners.has(event)) {
                this.eventListeners.set(event, []);
            }
            this.eventListeners.get(event).push(callback);
        }

        // 触发事件
        emit(event, data) {
            const listeners = this.eventListeners.get(event) || [];
            listeners.forEach(cb => {
                try {
                    cb(data);
                } catch (error) {
                    console.error(`[EnhancedJWTTokenManager] 事件处理错误 [${event}]:`, error);
                }
            });

            // 同时触发全局事件
            window.dispatchEvent(new CustomEvent(event, { detail: data }));
        }

        // 获取当前状态
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

    // 导出
    window.EnhancedWebSocketAuth = {
        EnhancedJWTTokenManager,
        SecureStorage,
        DeviceManager,
        RateLimiter,
        AUTH_EVENTS,
        SECURITY_CONFIG
    };

    console.log('[EnhancedWebSocketAuth] 增强版认证模块已加载');
})();
