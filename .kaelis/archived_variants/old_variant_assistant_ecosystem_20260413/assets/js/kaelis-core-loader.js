/**
 * Kaelis Core Loader
 * 核心模块加载器 - 动态加载、依赖管理、错误恢复
 */

(function() {
    'use strict';

    // 模块注册表
    const MODULE_REGISTRY = {
        // 基础模块
        'websocket-auth': {
            file: 'websocket-auth-unified.js',
            deps: [],
            priority: 1,
            required: true
        },
        'open-source-matcher': {
            file: 'open-source-matcher-enhanced.js',
            deps: [],
            priority: 2,
            required: false
        },
        'license-compliance-ui': {
            file: 'license-compliance-ui.js',
            deps: ['open-source-matcher'],
            priority: 3,
            required: false
        },
        'binary-transfer': {
            file: 'binary-transfer-advanced.js',
            deps: [],
            priority: 2,
            required: false
        },
        'alert-system': {
            file: 'alert-system-advanced.js',
            deps: [],
            priority: 2,
            required: false
        }
    };

    // 模块状态
    const MODULE_STATUS = {
        PENDING: 'pending',
        LOADING: 'loading',
        LOADED: 'loaded',
        ERROR: 'error',
        DISABLED: 'disabled'
    };

    /**
     * 核心加载器
     */
    class KaelisCoreLoader {
        constructor(options = {}) {
            this.basePath = options.basePath || '/assets/js/';
            this.modules = new Map();
            this.status = new Map();
            this.errors = [];
            this.listeners = new Map();
            
            // 初始化状态
            for (const [name, config] of Object.entries(MODULE_REGISTRY)) {
                this.modules.set(name, { ...config, status: MODULE_STATUS.PENDING });
            }
        }

        // 加载单个模块
        async loadModule(name) {
            const module = this.modules.get(name);
            if (!module) {
                throw new Error(`Module not found: ${name}`);
            }

            // 检查是否已加载
            if (module.status === MODULE_STATUS.LOADED) {
                return true;
            }

            // 检查是否出错
            if (module.status === MODULE_STATUS.ERROR) {
                throw new Error(`Module ${name} previously failed to load`);
            }

            // 更新状态
            module.status = MODULE_STATUS.LOADING;
            this.emit('module:loading', { name });

            try {
                // 加载依赖
                for (const dep of module.deps) {
                    await this.loadModule(dep);
                }

                // 加载脚本
                await this.loadScript(this.basePath + module.file);

                // 验证模块
                if (!this.verifyModule(name)) {
                    throw new Error(`Module ${name} failed verification`);
                }

                module.status = MODULE_STATUS.LOADED;
                this.emit('module:loaded', { name });
                
                return true;

            } catch (error) {
                module.status = MODULE_STATUS.ERROR;
                module.error = error.message;
                this.errors.push({ module: name, error: error.message });
                
                this.emit('module:error', { name, error: error.message });
                
                if (module.required) {
                    throw error;
                }
                
                return false;
            }
        }

        // 加载脚本
        loadScript(src) {
            return new Promise((resolve, reject) => {
                // 检查是否已存在
                if (document.querySelector(`script[src="${src}"]`)) {
                    resolve();
                    return;
                }

                const script = document.createElement('script');
                script.src = src;
                script.async = true;
                
                script.onload = () => resolve();
                script.onerror = () => reject(new Error(`Failed to load ${src}`));
                
                document.head.appendChild(script);
            });
        }

        // 验证模块
        verifyModule(name) {
            const verifications = {
                'websocket-auth': () => !!(window.Kaelis && window.Kaelis.WebSocketAuth),
                'open-source-matcher': () => !!(window.Kaelis && window.Kaelis.OpenSourceMatcher) || !!window.EnhancedOpenSourceMatcher,
                'license-compliance-ui': () => !!(window.Kaelis && window.Kaelis.LicenseComplianceUI) || !!window.LicenseComplianceUI,
                'binary-transfer': () => !!(window.Kaelis && window.Kaelis.BinaryTransfer) || !!window.BinaryTransferAdvanced,
                'alert-system': () => !!(window.Kaelis && window.Kaelis.AlertSystem) || !!window.AlertSystemAdvanced
            };

            const verify = verifications[name];
            return verify ? verify() : true;
        }

        // 加载所有模块
        async loadAll() {
            const sorted = this.sortByPriority();
            const results = {};

            for (const name of sorted) {
                try {
                    results[name] = await this.loadModule(name);
                } catch (error) {
                    results[name] = false;
                    console.error(`[KaelisCoreLoader] Failed to load ${name}:`, error);
                }
            }

            this.emit('load:complete', { results });
            return results;
        }

        // 按优先级排序
        sortByPriority() {
            const entries = Array.from(this.modules.entries());
            entries.sort((a, b) => a[1].priority - b[1].priority);
            return entries.map(([name]) => name);
        }

        // 获取模块状态
        getStatus(name) {
            return this.modules.get(name)?.status || MODULE_STATUS.PENDING;
        }

        // 获取所有状态
        getAllStatus() {
            const status = {};
            for (const [name, module] of this.modules) {
                status[name] = {
                    status: module.status,
                    error: module.error || null
                };
            }
            return status;
        }

        // 事件监听
        on(event, callback) {
            if (!this.listeners.has(event)) {
                this.listeners.set(event, []);
            }
            this.listeners.get(event).push(callback);
        }

        // 触发事件
        emit(event, data) {
            const callbacks = this.listeners.get(event) || [];
            callbacks.forEach(cb => {
                try {
                    cb(data);
                } catch (error) {
                    console.error(`[KaelisCoreLoader] Event handler error:`, error);
                }
            });
        }
    }

    // 导出 - UMD格式
    if (typeof define === 'function' && define.amd) {
        define([], function() { return { KaelisCoreLoader }; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = { KaelisCoreLoader };
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.CoreLoader = KaelisCoreLoader;
        window.KaelisCoreLoader = KaelisCoreLoader;
        window.kaelisLoader = new KaelisCoreLoader();
    }

    console.log('[KaelisCoreLoader] 核心加载器已就绪');
})();
