/**
 * Kaelis Performance Monitor
 * 性能监控模块 - 参考Web Vitals、Lighthouse最佳实践
 * 增加：Core Web Vitals、资源加载监控、长任务检测、性能预算
 */

(function() {
    'use strict';

    // 性能指标阈值（基于Google Web Vitals）
    const PERFORMANCE_THRESHOLDS = {
        LCP: { good: 2500, needsImprovement: 4000 }, // Largest Contentful Paint
        FID: { good: 100, needsImprovement: 300 },   // First Input Delay
        CLS: { good: 0.1, needsImprovement: 0.25 },  // Cumulative Layout Shift
        FCP: { good: 1800, needsImprovement: 3000 }, // First Contentful Paint
        TTFB: { good: 800, needsImprovement: 1800 }, // Time to First Byte
        INP: { good: 200, needsImprovement: 500 }    // Interaction to Next Paint
    };

    // 性能预算
    const PERFORMANCE_BUDGET = {
        javascript: 300 * 1024,      // 300KB JS
        images: 1000 * 1024,         // 1MB images
        css: 50 * 1024,              // 50KB CSS
        fonts: 100 * 1024,           // 100KB fonts
        total: 2000 * 1024,          // 2MB total
        requests: 50,                // 50 requests
        thirdParty: 10               // 10 third-party requests
    };

    /**
     * Web Vitals收集器
     */
    class WebVitalsCollector {
        constructor() {
            this.metrics = {};
            this.observers = [];
        }

        // 收集LCP
        observeLCP(callback) {
            if (!('PerformanceObserver' in window)) return;

            const observer = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];
                
                this.metrics.LCP = {
                    value: lastEntry.startTime,
                    element: lastEntry.element?.tagName,
                    url: lastEntry.url,
                    rating: this.getRating('LCP', lastEntry.startTime)
                };

                callback(this.metrics.LCP);
            });

            observer.observe({ entryTypes: ['largest-contentful-paint'] });
            this.observers.push(observer);
        }

        // 收集FID
        observeFID(callback) {
            if (!('PerformanceObserver' in window)) return;

            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'first-input') {
                        const delay = entry.processingStart - entry.startTime;
                        
                        this.metrics.FID = {
                            value: delay,
                            target: entry.target?.tagName,
                            rating: this.getRating('FID', delay)
                        };

                        callback(this.metrics.FID);
                    }
                }
            });

            observer.observe({ entryTypes: ['first-input'] });
            this.observers.push(observer);
        }

        // 收集CLS
        observeCLS(callback) {
            if (!('PerformanceObserver' in window)) return;

            let clsValue = 0;
            let clsEntries = [];

            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) {
                        clsValue += entry.value;
                        clsEntries.push(entry);
                    }
                }

                this.metrics.CLS = {
                    value: clsValue,
                    entries: clsEntries.length,
                    rating: this.getRating('CLS', clsValue)
                };

                callback(this.metrics.CLS);
            });

            observer.observe({ entryTypes: ['layout-shift'] });
            this.observers.push(observer);
        }

        // 收集FCP
        observeFCP(callback) {
            if (!('PerformanceObserver' in window)) return;

            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.name === 'first-contentful-paint') {
                        this.metrics.FCP = {
                            value: entry.startTime,
                            rating: this.getRating('FCP', entry.startTime)
                        };

                        callback(this.metrics.FCP);
                    }
                }
            });

            observer.observe({ entryTypes: ['paint'] });
            this.observers.push(observer);
        }

        // 收集TTFB
        observeTTFB(callback) {
            const navigation = performance.getEntriesByType('navigation')[0];
            if (navigation) {
                const ttfb = navigation.responseStart - navigation.startTime;
                
                this.metrics.TTFB = {
                    value: ttfb,
                    rating: this.getRating('TTFB', ttfb)
                };

                callback(this.metrics.TTFB);
            }
        }

        // 收集INP
        observeINP(callback) {
            if (!('PerformanceObserver' in window)) return;

            let maxDuration = 0;
            let slowEntries = [];

            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'event') {
                        const duration = entry.processingEnd - entry.startTime;
                        
                        if (duration > maxDuration) {
                            maxDuration = duration;
                        }

                        if (duration > 50) {
                            slowEntries.push({
                                name: entry.name,
                                duration,
                                target: entry.target?.tagName
                            });
                        }
                    }
                }

                this.metrics.INP = {
                    value: maxDuration,
                    slowInteractions: slowEntries.length,
                    rating: this.getRating('INP', maxDuration)
                };

                callback(this.metrics.INP);
            });

            observer.observe({ entryTypes: ['event'] });
            this.observers.push(observer);
        }

        // 获取评级
        getRating(metric, value) {
            const thresholds = PERFORMANCE_THRESHOLDS[metric];
            if (!thresholds) return 'unknown';

            if (value <= thresholds.good) return 'good';
            if (value <= thresholds.needsImprovement) return 'needs-improvement';
            return 'poor';
        }

        // 断开所有观察器
        disconnect() {
            this.observers.forEach(observer => observer.disconnect());
            this.observers = [];
        }

        // 获取所有指标
        getAllMetrics() {
            return { ...this.metrics };
        }
    }

    /**
     * 资源加载监控器
     */
    class ResourceMonitor {
        constructor() {
            this.resources = [];
            this.budget = PERFORMANCE_BUDGET;
        }

        // 开始监控
        start() {
            if (!('PerformanceObserver' in window)) return;

            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'resource') {
                        this.analyzeResource(entry);
                    }
                }
            });

            observer.observe({ entryTypes: ['resource'] });

            // 分析已有资源
            performance.getEntriesByType('resource').forEach(r => this.analyzeResource(r));
        }

        // 分析资源
        analyzeResource(entry) {
            const resource = {
                name: entry.name,
                type: this.getResourceType(entry),
                size: entry.transferSize,
                duration: entry.duration,
                startTime: entry.startTime,
                dns: entry.domainLookupEnd - entry.domainLookupStart,
                tcp: entry.connectEnd - entry.connectStart,
                ttfb: entry.responseStart - entry.requestStart,
                download: entry.responseEnd - entry.responseStart,
                isThirdParty: this.isThirdParty(entry.name)
            };

            this.resources.push(resource);
        }

        // 获取资源类型
        getResourceType(entry) {
            const initiator = entry.initiatorType;
            if (initiator) return initiator;

            const url = entry.name;
            if (url.match(/\.(js)$/)) return 'script';
            if (url.match(/\.(css)$/)) return 'stylesheet';
            if (url.match(/\.(png|jpg|jpeg|gif|webp|svg)$/)) return 'image';
            if (url.match(/\.(woff|woff2|ttf|otf)$/)) return 'font';
            if (url.match(/\.(json)$/)) return 'fetch';

            return 'other';
        }

        // 判断是否第三方
        isThirdParty(url) {
            try {
                const urlHost = new URL(url).hostname;
                const pageHost = window.location.hostname;
                return urlHost !== pageHost && !urlHost.endsWith('.' + pageHost);
            } catch (e) {
                return false;
            }
        }

        // 检查性能预算
        checkBudget() {
            const stats = this.getStats();
            const violations = [];

            // 检查总大小
            const totalSize = Object.values(stats.byType).reduce((a, b) => a + b.size, 0);
            if (totalSize > this.budget.total) {
                violations.push({
                    type: 'total-size',
                    actual: totalSize,
                    budget: this.budget.total,
                    message: `Total size ${(totalSize / 1024 / 1024).toFixed(2)}MB exceeds budget ${(this.budget.total / 1024 / 1024).toFixed(2)}MB`
                });
            }

            // 检查各类型
            for (const [type, budget] of Object.entries(this.budget)) {
                if (type === 'total' || type === 'requests' || type === 'thirdParty') continue;
                
                const actual = stats.byType[type]?.size || 0;
                if (actual > budget) {
                    violations.push({
                        type: `${type}-size`,
                        actual,
                        budget,
                        message: `${type} size ${(actual / 1024).toFixed(2)}KB exceeds budget ${(budget / 1024).toFixed(2)}KB`
                    });
                }
            }

            // 检查请求数
            if (stats.total > this.budget.requests) {
                violations.push({
                    type: 'requests',
                    actual: stats.total,
                    budget: this.budget.requests,
                    message: `${stats.total} requests exceeds budget ${this.budget.requests}`
                });
            }

            // 检查第三方
            if (stats.thirdParty > this.budget.thirdParty) {
                violations.push({
                    type: 'third-party',
                    actual: stats.thirdParty,
                    budget: this.budget.thirdParty,
                    message: `${stats.thirdParty} third-party requests exceeds budget ${this.budget.thirdParty}`
                });
            }

            return violations;
        }

        // 获取统计
        getStats() {
            const byType = {};
            let thirdParty = 0;

            for (const resource of this.resources) {
                if (!byType[resource.type]) {
                    byType[resource.type] = { count: 0, size: 0, duration: 0 };
                }
                
                byType[resource.type].count++;
                byType[resource.type].size += resource.size;
                byType[resource.type].duration += resource.duration;

                if (resource.isThirdParty) {
                    thirdParty++;
                }
            }

            return {
                total: this.resources.length,
                thirdParty,
                byType,
                slowest: this.resources
                    .filter(r => r.duration > 1000)
                    .sort((a, b) => b.duration - a.duration)
                    .slice(0, 10)
            };
        }
    }

    /**
     * 长任务检测器
     */
    class LongTaskDetector {
        constructor(callback) {
            this.callback = callback;
            this.longTasks = [];
            this.observer = null;
        }

        start() {
            if (!('PerformanceObserver' in window)) return;

            this.observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'longtask') {
                        const task = {
                            duration: entry.duration,
                            startTime: entry.startTime,
                            attribution: entry.attribution.map(a => ({
                                name: a.name,
                                type: a.entryType,
                                container: a.container?.tagName
                            }))
                        };

                        this.longTasks.push(task);
                        this.callback(task);
                    }
                }
            });

            this.observer.observe({ entryTypes: ['longtask'] });
        }

        stop() {
            if (this.observer) {
                this.observer.disconnect();
            }
        }

        getLongTasks() {
            return [...this.longTasks];
        }
    }

    /**
     * 性能监控器主类
     */
    class PerformanceMonitor {
        constructor(options = {}) {
            this.options = {
                endpoint: options.endpoint || '/api/performance',
                sampleRate: options.sampleRate || 1.0,
                enableWebVitals: options.enableWebVitals !== false,
                enableResourceMonitoring: options.enableResourceMonitoring !== false,
                enableLongTaskDetection: options.enableLongTaskDetection !== false,
                ...options
            };

            this.webVitals = new WebVitalsCollector();
            this.resourceMonitor = new ResourceMonitor();
            this.longTaskDetector = null;
            
            this.metrics = {};
            this.callbacks = [];
        }

        // 开始监控
        start() {
            // Web Vitals
            if (this.options.enableWebVitals) {
                this.webVitals.observeLCP(m => this.onMetric('LCP', m));
                this.webVitals.observeFID(m => this.onMetric('FID', m));
                this.webVitals.observeCLS(m => this.onMetric('CLS', m));
                this.webVitals.observeFCP(m => this.onMetric('FCP', m));
                this.webVitals.observeTTFB(m => this.onMetric('TTFB', m));
            }

            // 资源监控
            if (this.options.enableResourceMonitoring) {
                this.resourceMonitor.start();
            }

            // 长任务检测
            if (this.options.enableLongTaskDetection) {
                this.longTaskDetector = new LongTaskDetector((task) => {
                    this.onMetric('longtask', task);
                });
                this.longTaskDetector.start();
            }

            // 页面卸载时上报
            window.addEventListener('beforeunload', () => {
                this.sendMetrics();
            });
        }

        // 指标回调
        onMetric(name, metric) {
            this.metrics[name] = metric;

            // 触发回调
            this.callbacks.forEach(cb => {
                try {
                    cb(name, metric);
                } catch (e) {
                    console.error(e);
                }
            });

            // 检查预算违规
            if (name === 'resource') {
                const violations = this.resourceMonitor.checkBudget();
                if (violations.length > 0) {
                    this.onMetric('budget-violation', violations);
                }
            }
        }

        // 添加回调
        onMetricCollected(callback) {
            this.callbacks.push(callback);
        }

        // 发送指标
        async sendMetrics() {
            if (Math.random() > this.options.sampleRate) return;

            const payload = {
                url: window.location.href,
                timestamp: Date.now(),
                webVitals: this.webVitals.getAllMetrics(),
                resources: this.resourceMonitor.getStats(),
                budgetViolations: this.resourceMonitor.checkBudget(),
                longTasks: this.longTaskDetector?.getLongTasks().length || 0
            };

            try {
                await fetch(this.options.endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    keepalive: true
                });
            } catch (error) {
                console.error('[PerformanceMonitor] 发送失败:', error);
            }
        }

        // 获取报告
        getReport() {
            return {
                webVitals: this.webVitals.getAllMetrics(),
                resources: this.resourceMonitor.getStats(),
                budgetViolations: this.resourceMonitor.checkBudget()
            };
        }

        // 停止监控
        stop() {
            this.webVitals.disconnect();
            this.longTaskDetector?.stop();
        }
    }

    // 导出 - UMD格式
    const exports = {
        PerformanceMonitor,
        WebVitalsCollector,
        ResourceMonitor,
        LongTaskDetector,
        PERFORMANCE_THRESHOLDS,
        PERFORMANCE_BUDGET
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.PerformanceMonitor = exports;
        // 保持向后兼容
        window.PerformanceMonitor = exports;
    }

    console.log('[PerformanceMonitor] 性能监控模块已加载');
})();
