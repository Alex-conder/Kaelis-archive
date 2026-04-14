/**
 * Kaelis Error Handler Enhanced
 * 增强版错误处理模块 - 参考Sentry、Bugsnag最佳实践
 * 增加：错误分类、自动上报、用户反馈、错误恢复
 */

(function() {
    'use strict';

    // 错误级别
    const ERROR_LEVEL = {
        FATAL: 'fatal',
        ERROR: 'error',
        WARNING: 'warning',
        INFO: 'info',
        DEBUG: 'debug'
    };

    // 错误类型
    const ERROR_TYPE = {
        JAVASCRIPT: 'javascript',
        NETWORK: 'network',
        AUTH: 'authentication',
        VALIDATION: 'validation',
        BUSINESS: 'business',
        RESOURCE: 'resource',
        TIMEOUT: 'timeout',
        UNKNOWN: 'unknown'
    };

    /**
     * 错误分类器
     */
    class ErrorClassifier {
        constructor() {
            this.patterns = {
                [ERROR_TYPE.NETWORK]: [
                    /network error/i,
                    /failed to fetch/i,
                    /network request failed/i,
                    /timeout/i,
                    /abort/i
                ],
                [ERROR_TYPE.AUTH]: [
                    /unauthorized/i,
                    /forbidden/i,
                    /token expired/i,
                    /authentication failed/i,
                    /401|403/
                ],
                [ERROR_TYPE.VALIDATION]: [
                    /validation failed/i,
                    /invalid input/i,
                    /required field/i,
                    /bad request/i,
                    /400/
                ],
                [ERROR_TYPE.RESOURCE]: [
                    /not found/i,
                    /404/i,
                    /resource unavailable/i
                ]
            };
        }

        classify(error) {
            const message = error.message || error.toString();
            
            for (const [type, patterns] of Object.entries(this.patterns)) {
                for (const pattern of patterns) {
                    if (pattern.test(message)) {
                        return type;
                    }
                }
            }

            // 根据错误对象类型判断
            if (error instanceof TypeError || error instanceof ReferenceError) {
                return ERROR_TYPE.JAVASCRIPT;
            }

            if (error instanceof NetworkError || error.name === 'NetworkError') {
                return ERROR_TYPE.NETWORK;
            }

            return ERROR_TYPE.UNKNOWN;
        }

        getLevel(error, type) {
            if (type === ERROR_TYPE.FATAL || error.fatal) {
                return ERROR_LEVEL.FATAL;
            }
            
            if (type === ERROR_TYPE.NETWORK) {
                return ERROR_LEVEL.WARNING;
            }

            if (type === ERROR_TYPE.AUTH) {
                return ERROR_LEVEL.WARNING;
            }

            if (type === ERROR_TYPE.JAVASCRIPT) {
                return ERROR_LEVEL.ERROR;
            }

            return ERROR_LEVEL.ERROR;
        }
    }

    /**
     * 错误上下文收集器
     */
    class ErrorContextCollector {
        collect() {
            return {
                url: window.location.href,
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                screen: {
                    width: screen.width,
                    height: screen.height,
                    colorDepth: screen.colorDepth
                },
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                timestamp: Date.now(),
                performance: this.getPerformanceData(),
                memory: this.getMemoryData(),
                storage: this.getStorageData()
            };
        }

        getPerformanceData() {
            if (!window.performance || !performance.timing) {
                return null;
            }

            const timing = performance.timing;
            return {
                loadTime: timing.loadEventEnd - timing.navigationStart,
                domReady: timing.domContentLoadedEventEnd - timing.navigationStart,
                resources: performance.getEntriesByType('resource').slice(-10).map(r => ({
                    name: r.name,
                    duration: r.duration,
                    size: r.transferSize
                }))
            };
        }

        getMemoryData() {
            if (performance.memory) {
                return {
                    usedJSHeapSize: performance.memory.usedJSHeapSize,
                    totalJSHeapSize: performance.memory.totalJSHeapSize,
                    jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
                };
            }
            return null;
        }

        getStorageData() {
            try {
                return {
                    localStorage: Object.keys(localStorage).length,
                    sessionStorage: Object.keys(sessionStorage).length
                };
            } catch (e) {
                return null;
            }
        }
    }

    /**
     * 增强版错误处理器
     */
    class EnhancedErrorHandler {
        constructor(options = {}) {
            this.options = {
                endpoint: options.endpoint || '/api/errors',
                apiKey: options.apiKey,
                environment: options.environment || 'production',
                release: options.release,
                maxBreadcrumbs: options.maxBreadcrumbs || 100,
                sampleRate: options.sampleRate || 1.0,
                beforeSend: options.beforeSend,
                ...options
            };

            this.classifier = new ErrorClassifier();
            this.contextCollector = new ErrorContextCollector();
            this.breadcrumbs = [];
            this.user = null;
            this.tags = new Map();
            
            this.errorQueue = [];
            this.isProcessing = false;

            this.init();
        }

        init() {
            // 全局错误捕获
            window.addEventListener('error', (event) => {
                this.handleError(event.error || event, {
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno
                });
            });

            // 未处理的Promise拒绝
            window.addEventListener('unhandledrejection', (event) => {
                this.handleError(event.reason, {
                    type: 'unhandledrejection'
                });
            });

            // 网络错误监控
            this.monitorNetworkErrors();

            // 控制台错误捕获
            this.captureConsoleErrors();
        }

        // 处理错误
        handleError(error, context = {}) {
            // 采样
            if (Math.random() > this.options.sampleRate) {
                return;
            }

            const errorType = this.classifier.classify(error);
            const level = this.classifier.getLevel(error, errorType);

            const errorEvent = {
                eventId: this.generateEventId(),
                timestamp: Date.now(),
                level,
                type: errorType,
                message: error.message || String(error),
                stack: error.stack,
                context: {
                    ...this.contextCollector.collect(),
                    ...context
                },
                breadcrumbs: [...this.breadcrumbs],
                user: this.user,
                tags: Object.fromEntries(this.tags),
                environment: this.options.environment,
                release: this.options.release
            };

            // 调用beforeSend钩子
            if (this.options.beforeSend) {
                const result = this.options.beforeSend(errorEvent);
                if (result === null) return; // 取消发送
                Object.assign(errorEvent, result);
            }

            // 加入队列
            this.errorQueue.push(errorEvent);
            this.processQueue();

            // 触发本地事件
            this.emit('error', errorEvent);

            return errorEvent;
        }

        // 处理队列
        async processQueue() {
            if (this.isProcessing || this.errorQueue.length === 0) {
                return;
            }

            this.isProcessing = true;

            const batch = this.errorQueue.splice(0, 10);

            try {
                await this.sendErrors(batch);
            } catch (error) {
                // 发送失败，重新加入队列
                this.errorQueue.unshift(...batch);
                console.error('[EnhancedErrorHandler] 错误上报失败:', error);
            } finally {
                this.isProcessing = false;
                
                // 继续处理剩余
                if (this.errorQueue.length > 0) {
                    setTimeout(() => this.processQueue(), 1000);
                }
            }
        }

        // 发送错误
        async sendErrors(errors) {
            const response = await fetch(this.options.endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': this.options.apiKey
                },
                body: JSON.stringify({ errors })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
        }

        // 添加面包屑
        addBreadcrumb(category, message, data = {}) {
            const crumb = {
                timestamp: Date.now(),
                category,
                message,
                data
            };

            this.breadcrumbs.push(crumb);

            // 限制数量
            if (this.breadcrumbs.length > this.options.maxBreadcrumbs) {
                this.breadcrumbs.shift();
            }
        }

        // 设置用户
        setUser(user) {
            this.user = user;
        }

        // 设置标签
        setTag(key, value) {
            this.tags.set(key, value);
        }

        // 监控网络错误
        monitorNetworkErrors() {
            const originalFetch = window.fetch;
            
            window.fetch = async (...args) => {
                const startTime = Date.now();
                
                try {
                    const response = await originalFetch.apply(window, args);
                    
                    // 记录慢请求
                    const duration = Date.now() - startTime;
                    if (duration > 5000) {
                        this.addBreadcrumb('http', 'Slow request', {
                            url: args[0],
                            duration,
                            status: response.status
                        });
                    }

                    // 记录错误状态
                    if (!response.ok && response.status >= 500) {
                        this.addBreadcrumb('http', 'Server error', {
                            url: args[0],
                            status: response.status,
                            statusText: response.statusText
                        });
                    }

                    return response;
                } catch (error) {
                    this.addBreadcrumb('http', 'Network error', {
                        url: args[0],
                        error: error.message
                    });
                    throw error;
                }
            };
        }

        // 捕获控制台错误
        captureConsoleErrors() {
            const levels = ['error', 'warn'];
            
            levels.forEach(level => {
                const original = console[level];
                console[level] = (...args) => {
                    // 记录面包屑
                    this.addBreadcrumb('console', args.join(' '), { level });
                    
                    // 调用原始方法
                    original.apply(console, args);
                };
            });
        }

        // 生成事件ID
        generateEventId() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }

        // 事件发射
        emit(event, data) {
            window.dispatchEvent(new CustomEvent(`kaelis:error:${event}`, { detail: data }));
        }

        // 包装函数
        wrap(fn, options = {}) {
            return (...args) => {
                try {
                    return fn.apply(this, args);
                } catch (error) {
                    this.handleError(error, {
                        function: fn.name || 'anonymous',
                        arguments: args,
                        ...options
                    });
                    throw error;
                }
            };
        }

        // 异步包装
        wrapAsync(fn, options = {}) {
            return async (...args) => {
                try {
                    return await fn.apply(this, args);
                } catch (error) {
                    this.handleError(error, {
                        function: fn.name || 'anonymous',
                        arguments: args,
                        async: true,
                        ...options
                    });
                    throw error;
                }
            };
        }
    }

    // 导出 - UMD格式
    const exports = {
        EnhancedErrorHandler,
        ErrorClassifier,
        ErrorContextCollector,
        ERROR_LEVEL,
        ERROR_TYPE
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.ErrorHandler = exports;
        // 保持向后兼容
        window.EnhancedErrorHandler = exports;
    }

    console.log('[EnhancedErrorHandler] 增强版错误处理模块已加载');
})();
