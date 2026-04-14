/**
 * Kaelis Unified Loader
 * 统一加载器 - 按需加载Kaelis模块
 * 
 * 使用方法:
 * <script src="assets/js/kaelis-loader.js" data-modules="core,auth,utils"></script>
 * 或
 * <script src="assets/js/kaelis-loader.js"></script>
 * <script>
 *   KaelisLoader.load(['core', 'auth', 'utils']).then(() => {
 *     // 模块加载完成
 *   });
 * </script>
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KaelisLoader = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';

    // 模块配置
    const MODULE_CONFIG = {
        // 核心模块
        'core': {
            files: ['kaelis-core.js'],
            deps: [],
            priority: 1
        },
        'init': {
            files: ['kaelis-init.js'],
            deps: ['core'],
            priority: 2
        },
        'core-loader': {
            files: ['kaelis-core-loader.js'],
            deps: [],
            priority: 1
        },
        
        // 工具模块
        'utils': {
            files: ['utils/storage.js', 'utils/validator.js', 'utils/event-bus.js', 'utils/http-client.js', 'utils/index.js'],
            deps: [],
            priority: 1
        },
        'main': {
            files: ['main.js'],
            deps: [],
            priority: 1
        },
        'nav': {
            files: ['nav-component.js'],
            deps: ['main'],
            priority: 2
        },
        'animations': {
            files: ['animations.js'],
            deps: [],
            priority: 1
        },
        
        // 认证与通信
        'auth': {
            files: ['websocket-auth-unified.js'],
            deps: [],
            priority: 1
        },
        'websocket': {
            files: ['websocket-client.js'],
            deps: [],
            priority: 1
        },
        'reconnection': {
            files: ['reconnection-manager.js'],
            deps: ['websocket'],
            priority: 2
        },
        
        // 功能模块
        'opensource': {
            files: ['open-source-matcher-enhanced.js'],
            deps: [],
            priority: 1
        },
        'license': {
            files: ['license-compliance-ui.js'],
            deps: ['opensource'],
            priority: 2
        },
        'alerts': {
            files: ['alert-system-advanced.js'],
            deps: [],
            priority: 1
        },
        'alert-monitor': {
            files: ['alert-monitor.js'],
            deps: ['alerts'],
            priority: 2
        },
        'binary': {
            files: ['binary-transfer-advanced.js'],
            deps: [],
            priority: 1
        },
        'binary-result': {
            files: ['binary-result-handler.js'],
            deps: ['binary'],
            priority: 2
        },
        
        // 监控与错误处理
        'error-handler': {
            files: ['error-handler-enhanced.js'],
            deps: [],
            priority: 1
        },
        'performance': {
            files: ['performance-monitor.js'],
            deps: [],
            priority: 1
        },
        
        // 任务管理
        'batch': {
            files: ['batch-task-manager.js'],
            deps: [],
            priority: 1
        },
        'task-monitor': {
            files: ['task-monitor.js'],
            deps: ['batch'],
            priority: 2
        },
        
        // 数据管理
        'persistence': {
            files: ['persistence-manager.js'],
            deps: [],
            priority: 1
        },
        'context': {
            files: ['context-manager.js'],
            deps: [],
            priority: 1
        },
        'redis': {
            files: ['redis-state-manager.js'],
            deps: [],
            priority: 1
        },
        
        // 架构
        'distributed': {
            files: ['distributed-architecture.js'],
            deps: [],
            priority: 1
        },
        'dialogue': {
            files: ['dialogue-state-machine.js'],
            deps: [],
            priority: 1
        },
        
        // 用户与计费
        'user': {
            files: ['user-role-inference.js'],
            deps: [],
            priority: 1
        },
        'billing': {
            files: ['billing-system.js'],
            deps: [],
            priority: 1
        },
        'recommendation': {
            files: ['recommendation-system.js'],
            deps: [],
            priority: 1
        },
        'plugins': {
            files: ['platform-plugins.js'],
            deps: [],
            priority: 1
        },
        
        // 其他
        'converge': {
            files: ['auto-converge-v2.js'],
            deps: ['main'],
            priority: 2
        },
        'style-cleanup': {
            files: ['style-cleanup.js'],
            deps: [],
            priority: 1
        }
    };

    // 预定义的模块组合
    const MODULE_BUNDLES = {
        'minimal': ['main', 'nav'],
        'basic': ['main', 'nav', 'animations', 'converge'],
        'standard': ['main', 'nav', 'animations', 'utils', 'auth', 'converge'],
        'full': ['main', 'nav', 'animations', 'utils', 'auth', 'websocket', 'alerts', 'performance', 'error-handler', 'converge'],
        'dashboard': ['main', 'nav', 'animations', 'utils', 'auth', 'performance', 'alerts', 'converge'],
        'chat': ['main', 'nav', 'animations', 'utils', 'auth', 'websocket', 'context', 'dialogue', 'converge'],
        'admin': ['main', 'nav', 'animations', 'utils', 'auth', 'websocket', 'alerts', 'performance', 'error-handler', 'billing', 'user', 'converge']
    };

    // 加载器类
    class KaelisLoader {
        constructor(options = {}) {
            this.basePath = options.basePath || this.detectBasePath();
            this.loadedModules = new Set();
            this.loadingPromises = new Map();
            this.options = {
                async: true,
                cache: true,
                ...options
            };
        }

        // 自动检测基础路径
        detectBasePath() {
            const currentScript = document.currentScript;
            if (currentScript) {
                const src = currentScript.src;
                const match = src.match(/(.*?)assets\/js\/kaelis-loader\.js/);
                if (match) {
                    return match[1] + 'assets/js/';
                }
            }
            return '/assets/js/';
        }

        // 加载单个脚本
        loadScript(url) {
            // 检查是否已加载
            if (document.querySelector(`script[src="${url}"]`)) {
                return Promise.resolve();
            }

            // 检查是否正在加载
            if (this.loadingPromises.has(url)) {
                return this.loadingPromises.get(url);
            }

            const promise = new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = url;
                script.async = this.options.async;
                
                if (!this.options.cache) {
                    script.src += '?t=' + Date.now();
                }

                script.onload = () => {
                    this.loadingPromises.delete(url);
                    resolve();
                };

                script.onerror = () => {
                    this.loadingPromises.delete(url);
                    reject(new Error(`Failed to load: ${url}`));
                };

                document.head.appendChild(script);
            });

            this.loadingPromises.set(url, promise);
            return promise;
        }

        // 解析模块列表
        resolveModules(modules) {
            const resolved = new Set();
            const queue = [...modules];

            while (queue.length > 0) {
                const name = queue.shift();
                
                // 检查是否是预定义组合
                if (MODULE_BUNDLES[name]) {
                    queue.unshift(...MODULE_BUNDLES[name]);
                    continue;
                }

                // 检查模块配置
                const config = MODULE_CONFIG[name];
                if (!config) {
                    console.warn(`[KaelisLoader] Unknown module: ${name}`);
                    continue;
                }

                if (resolved.has(name)) {
                    continue;
                }

                // 先添加依赖
                for (const dep of config.deps) {
                    if (!resolved.has(dep)) {
                        queue.unshift(dep);
                    }
                }

                resolved.add(name);
            }

            // 按优先级排序
            return Array.from(resolved).sort((a, b) => {
                const priorityA = MODULE_CONFIG[a]?.priority || 0;
                const priorityB = MODULE_CONFIG[b]?.priority || 0;
                return priorityA - priorityB;
            });
        }

        // 加载模块
        async load(modules) {
            if (typeof modules === 'string') {
                modules = modules.split(',').map(m => m.trim());
            }

            const resolved = this.resolveModules(modules);
            const results = {};

            for (const name of resolved) {
                if (this.loadedModules.has(name)) {
                    results[name] = { status: 'already-loaded' };
                    continue;
                }

                const config = MODULE_CONFIG[name];
                
                try {
                    // 加载所有文件
                    for (const file of config.files) {
                        const url = this.basePath + file;
                        await this.loadScript(url);
                    }

                    this.loadedModules.add(name);
                    results[name] = { status: 'loaded' };
                    
                    // 触发自定义事件
                    window.dispatchEvent(new CustomEvent('kaelis:module-loaded', {
                        detail: { module: name }
                    }));

                } catch (error) {
                    results[name] = { status: 'error', error: error.message };
                    console.error(`[KaelisLoader] Failed to load module: ${name}`, error);
                }
            }

            return results;
        }

        // 预加载模块
        preload(modules) {
            if (typeof modules === 'string') {
                modules = modules.split(',').map(m => m.trim());
            }

            // 使用 requestIdleCallback 或 setTimeout 延迟加载
            const loadFn = () => this.load(modules);
            
            if ('requestIdleCallback' in window) {
                requestIdleCallback(loadFn, { timeout: 2000 });
            } else {
                setTimeout(loadFn, 100);
            }
        }

        // 检查模块是否已加载
        isLoaded(name) {
            return this.loadedModules.has(name);
        }

        // 获取已加载的模块列表
        getLoadedModules() {
            return Array.from(this.loadedModules);
        }
    }

    // 创建全局实例
    const loader = new KaelisLoader();

    // 自动加载（如果配置了data-modules）
    function autoLoad() {
        const currentScript = document.currentScript;
        if (!currentScript) return;

        const modules = currentScript.getAttribute('data-modules');
        if (modules) {
            loader.load(modules).then(results => {
                console.log('[KaelisLoader] Auto-load complete:', results);
            });
        }
    }

    // 如果DOM已加载，立即执行自动加载
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoLoad);
    } else {
        autoLoad();
    }

    // 导出
    return {
        KaelisLoader,
        loader,
        load: (modules) => loader.load(modules),
        preload: (modules) => loader.preload(modules),
        isLoaded: (name) => loader.isLoaded(name),
        getLoadedModules: () => loader.getLoadedModules(),
        MODULE_CONFIG,
        MODULE_BUNDLES
    };
}));
