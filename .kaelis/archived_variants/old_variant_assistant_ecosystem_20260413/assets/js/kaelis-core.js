/**
 * Kaelis Core
 * 核心模块加载器 - 整合所有增强功能模块
 * 提供统一的初始化、配置管理和模块协调
 */

(function() {
    'use strict';

    // Kaelis版本
    const VERSION = '4.1.0';

    // 模块状态
    const MODULE_STATUS = {
        PENDING: 'pending',
        LOADING: 'loading',
        LOADED: 'loaded',
        ERROR: 'error'
    };

    /**
     * 模块管理器
     */
    class ModuleManager {
        constructor() {
            this.modules = new Map();
            this.dependencies = new Map();
        }

        // 注册模块
        register(name, factory, dependencies = []) {
            this.modules.set(name, {
                name,
                factory,
                dependencies,
                status: MODULE_STATUS.PENDING,
                instance: null,
                error: null
            });
        }

        // 加载模块
        async load(name) {
            const module = this.modules.get(name);
            if (!module) {
                throw new Error(`Module not found: ${name}`);
            }

            if (module.status === MODULE_STATUS.LOADED) {
                return module.instance;
            }

            if (module.status === MODULE_STATUS.LOADING) {
                // 等待加载完成
                return new Promise((resolve, reject) => {
                    const check = () => {
                        if (module.status === MODULE_STATUS.LOADED) {
                            resolve(module.instance);
                        } else if (module.status === MODULE_STATUS.ERROR) {
                            reject(module.error);
                        } else {
                            setTimeout(check, 10);
                        }
                    };
                    check();
                });
            }

            module.status = MODULE_STATUS.LOADING;

            try {
                // 加载依赖
                const deps = {};
                for (const depName of module.dependencies) {
                    deps[depName] = await this.load(depName);
                }

                // 实例化
                module.instance = await module.factory(deps);
                module.status = MODULE_STATUS.LOADED;

                console.log(`[ModuleManager] 模块加载成功: ${name}`);
                return module.instance;

            } catch (error) {
                module.status = MODULE_STATUS.ERROR;
                module.error = error;
                console.error(`[ModuleManager] 模块加载失败: ${name}`, error);
                throw error;
            }
        }

        // 批量加载
        async loadAll(names) {
            const results = {};
            for (const name of names) {
                results[name] = await this.load(name);
            }
            return results;
        }

        // 获取模块
        get(name) {
            const module = this.modules.get(name);
            return module?.instance;
        }

        // 获取所有模块状态
        getStatus() {
            const status = {};
            for (const [name, module] of this.modules) {
                status[name] = module.status;
            }
            return status;
        }
    }

    /**
     * 配置管理器
     */
    class ConfigManager {
        constructor() {
            this.config = {
                environment: 'production',
                apiEndpoint: '/api',
                wsEndpoint: '/ws',
                features: {
                    auth: true,
                    websocket: true,
                    persistence: true,
                    monitoring: true,
                    errorTracking: true
                },
                security: {
                    maxRetries: 3,
                    tokenRefreshWindow: 300,
                    sessionTimeout: 3600
                },
                performance: {
                    sampleRate: 1.0,
                    enableWebVitals: true,
                    enableResourceMonitoring: true
                }
            };
        }

        // 设置配置
        set(key, value) {
            const keys = key.split('.');
            let target = this.config;
            
            for (let i = 0; i < keys.length - 1; i++) {
                if (!(keys[i] in target)) {
                    target[keys[i]] = {};
                }
                target = target[keys[i]];
            }
            
            target[keys[keys.length - 1]] = value;
        }

        // 获取配置
        get(key, defaultValue = null) {
            const keys = key.split('.');
            let target = this.config;
            
            for (const k of keys) {
                if (target === null || target === undefined) {
                    return defaultValue;
                }
                target = target[k];
            }
            
            return target !== undefined ? target : defaultValue;
        }

        // 合并配置
        merge(newConfig) {
            this.deepMerge(this.config, newConfig);
        }

        deepMerge(target, source) {
            for (const key in source) {
                if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                    if (!target[key]) target[key] = {};
                    this.deepMerge(target[key], source[key]);
                } else {
                    target[key] = source[key];
                }
            }
        }

        // 从环境变量加载
        loadFromEnvironment() {
            if (window.KAELIS_CONFIG) {
                this.merge(window.KAELIS_CONFIG);
            }
        }
    }

    /**
     * Kaelis核心类
     */
    class KaelisCore {
        constructor() {
            this.version = VERSION;
            this.moduleManager = new ModuleManager();
            this.config = new ConfigManager();
            this.initialized = false;
            this.hooks = {
                beforeInit: [],
                afterInit: [],
                onError: []
            };
        }

        // 初始化
        async init(options = {}) {
            if (this.initialized) {
                console.warn('[KaelisCore] 已经初始化');
                return this;
            }

            console.log(`[KaelisCore] 初始化 v${this.version}`);

            // 加载环境配置
            this.config.loadFromEnvironment();
            
            // 合并用户配置
            if (options.config) {
                this.config.merge(options.config);
            }

            // 执行beforeInit钩子
            for (const hook of this.hooks.beforeInit) {
                await hook(this);
            }

            // 注册核心模块
            this.registerCoreModules();

            // 加载启用的模块
            const modulesToLoad = [];
            
            if (this.config.get('features.auth')) {
                modulesToLoad.push('auth');
            }
            
            if (this.config.get('features.websocket')) {
                modulesToLoad.push('websocket');
            }
            
            if (this.config.get('features.monitoring')) {
                modulesToLoad.push('performance');
            }
            
            if (this.config.get('features.errorTracking')) {
                modulesToLoad.push('errorHandler');
            }

            try {
                await this.moduleManager.loadAll(modulesToLoad);
                this.initialized = true;

                // 执行afterInit钩子
                for (const hook of this.hooks.afterInit) {
                    await hook(this);
                }

                console.log('[KaelisCore] 初始化完成');
                
                // 触发全局事件
                window.dispatchEvent(new CustomEvent('kaelis:ready', { 
                    detail: { version: this.version } 
                }));

            } catch (error) {
                console.error('[KaelisCore] 初始化失败:', error);
                this.handleError(error);
                throw error;
            }

            return this;
        }

        // 注册核心模块
        registerCoreModules() {
            // 认证模块
            this.moduleManager.register('auth', async () => {
                const Auth = window.EnhancedWebSocketAuth?.EnhancedJWTTokenManager || 
                            window.JWTTokenManager;
                return new Auth({
                    maxDevices: this.config.get('security.maxDevices', 5)
                });
            });

            // WebSocket模块
            this.moduleManager.register('websocket', async (deps) => {
                const Client = window.ResilientWebSocketClient || 
                              window.AuthenticatedWebSocketClient;
                return new Client({
                    url: this.config.get('wsEndpoint'),
                    userId: deps.auth?.user?.id
                });
            }, ['auth']);

            // 性能监控模块
            this.moduleManager.register('performance', async () => {
                const Monitor = window.PerformanceMonitor?.PerformanceMonitor;
                if (!Monitor) return null;

                const monitor = new Monitor({
                    endpoint: `${this.config.get('apiEndpoint')}/performance`,
                    sampleRate: this.config.get('performance.sampleRate', 1.0)
                });
                monitor.start();
                return monitor;
            });

            // 错误处理模块
            this.moduleManager.register('errorHandler', async () => {
                const Handler = window.EnhancedErrorHandler?.EnhancedErrorHandler;
                if (!Handler) return null;

                return new Handler({
                    endpoint: `${this.config.get('apiEndpoint')}/errors`,
                    environment: this.config.get('environment'),
                    release: this.version
                });
            });
        }

        // 添加钩子
        hook(event, callback) {
            if (this.hooks[event]) {
                this.hooks[event].push(callback);
            }
        }

        // 获取模块
        getModule(name) {
            return this.moduleManager.get(name);
        }

        // 处理错误
        handleError(error) {
            // 调用错误钩子
            for (const hook of this.hooks.onError) {
                try {
                    hook(error);
                } catch (e) {
                    console.error(e);
                }
            }

            // 使用错误处理器
            const errorHandler = this.getModule('errorHandler');
            if (errorHandler) {
                errorHandler.handleError(error);
            }
        }

        // 获取状态
        getStatus() {
            return {
                version: this.version,
                initialized: this.initialized,
                modules: this.moduleManager.getStatus(),
                config: this.config.get('environment')
            };
        }
    }

    // 创建全局实例
    const kaelis = new KaelisCore();

    // 导出 - UMD格式
    const exports = {
        core: kaelis,
        version: VERSION,
        ModuleManager,
        ConfigManager,
        MODULE_STATUS,
        KaelisCore
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        Object.assign(window.Kaelis, exports);
    }

    // 自动初始化（如果配置了autoInit）
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            if (window.KAELIS_AUTO_INIT !== false) {
                kaelis.init().catch(console.error);
            }
        });
    } else {
        if (window.KAELIS_AUTO_INIT !== false) {
            kaelis.init().catch(console.error);
        }
    }

    console.log(`[KaelisCore] v${VERSION} 已加载`);
})();
