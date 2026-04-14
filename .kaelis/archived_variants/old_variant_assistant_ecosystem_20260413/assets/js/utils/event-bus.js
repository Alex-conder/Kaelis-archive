/**
 * Kaelis Event Bus
 * 全局事件总线 - 解耦组件通信
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.EventBus = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';

    /**
     * 事件总线类
     */
    class EventBus {
        constructor() {
            this.events = new Map();
            this.onceEvents = new Map();
            this.maxListeners = 100;
        }

        /**
         * 订阅事件
         * @param {string} event - 事件名称
         * @param {Function} callback - 回调函数
         * @param {Object} options - 选项
         * @param {boolean} options.once - 是否只执行一次
         * @param {Object} options.context - 回调上下文
         * @param {number} options.priority - 优先级(数字越大越先执行)
         * @returns {Function} 取消订阅函数
         */
        on(event, callback, options = {}) {
            if (typeof callback !== 'function') {
                console.error('EventBus: callback must be a function');
                return () => {};
            }

            const listeners = this.events.get(event) || [];
            
            // 检查监听器数量限制
            if (listeners.length >= this.maxListeners) {
                console.warn(`EventBus: Max listeners (${this.maxListeners}) exceeded for event "${event}"`);
            }

            const listener = {
                callback,
                context: options.context || null,
                priority: options.priority || 0,
                once: options.once || false
            };

            listeners.push(listener);
            
            // 按优先级排序
            listeners.sort((a, b) => b.priority - a.priority);
            
            this.events.set(event, listeners);

            // 返回取消订阅函数
            return () => this.off(event, callback);
        }

        /**
         * 订阅一次性事件
         * @param {string} event - 事件名称
         * @param {Function} callback - 回调函数
         * @param {Object} options - 选项
         * @returns {Function} 取消订阅函数
         */
        once(event, callback, options = {}) {
            return this.on(event, callback, { ...options, once: true });
        }

        /**
         * 取消订阅
         * @param {string} event - 事件名称
         * @param {Function} callback - 回调函数(可选，不传则取消所有)
         */
        off(event, callback) {
            if (!event) {
                // 清除所有事件
                this.events.clear();
                this.onceEvents.clear();
                return;
            }

            const listeners = this.events.get(event);
            if (!listeners) return;

            if (!callback) {
                // 取消该事件的所有监听
                this.events.delete(event);
                return;
            }

            // 移除特定回调
            const filtered = listeners.filter(l => l.callback !== callback);
            if (filtered.length === 0) {
                this.events.delete(event);
            } else {
                this.events.set(event, filtered);
            }
        }

        /**
         * 触发事件
         * @param {string} event - 事件名称
         * @param {...any} args - 参数
         * @returns {Promise<any[]>} 所有监听器返回值的数组
         */
        async emit(event, ...args) {
            const listeners = this.events.get(event);
            if (!listeners || listeners.length === 0) {
                return [];
            }

            const results = [];
            const toRemove = [];

            for (const listener of listeners) {
                try {
                    const result = await this.executeListener(listener, args);
                    results.push(result);

                    if (listener.once) {
                        toRemove.push(listener);
                    }
                } catch (error) {
                    console.error(`EventBus: Error in listener for "${event}":`, error);
                    results.push(undefined);
                }
            }

            // 移除一次性监听器
            if (toRemove.length > 0) {
                const remaining = listeners.filter(l => !toRemove.includes(l));
                if (remaining.length === 0) {
                    this.events.delete(event);
                } else {
                    this.events.set(event, remaining);
                }
            }

            return results;
        }

        /**
         * 同步触发事件
         * @param {string} event - 事件名称
         * @param {...any} args - 参数
         * @returns {any[]}
         */
        emitSync(event, ...args) {
            const listeners = this.events.get(event);
            if (!listeners || listeners.length === 0) {
                return [];
            }

            const results = [];
            const toRemove = [];

            for (const listener of listeners) {
                try {
                    const result = listener.context 
                        ? listener.callback.call(listener.context, ...args)
                        : listener.callback(...args);
                    results.push(result);

                    if (listener.once) {
                        toRemove.push(listener);
                    }
                } catch (error) {
                    console.error(`EventBus: Error in listener for "${event}":`, error);
                    results.push(undefined);
                }
            }

            // 移除一次性监听器
            if (toRemove.length > 0) {
                const remaining = listeners.filter(l => !toRemove.includes(l));
                if (remaining.length === 0) {
                    this.events.delete(event);
                } else {
                    this.events.set(event, remaining);
                }
            }

            return results;
        }

        /**
         * 执行监听器
         * @private
         */
        async executeListener(listener, args) {
            if (listener.context) {
                return await listener.callback.call(listener.context, ...args);
            }
            return await listener.callback(...args);
        }

        /**
         * 获取事件监听器数量
         * @param {string} event - 事件名称(可选，不传则返回总数)
         * @returns {number}
         */
        listenerCount(event) {
            if (event) {
                const listeners = this.events.get(event);
                return listeners ? listeners.length : 0;
            }

            let count = 0;
            for (const listeners of this.events.values()) {
                count += listeners.length;
            }
            return count;
        }

        /**
         * 获取所有事件名称
         * @returns {string[]}
         */
        eventNames() {
            return Array.from(this.events.keys());
        }

        /**
         * 设置最大监听器数量
         * @param {number} n - 最大数量
         */
        setMaxListeners(n) {
            this.maxListeners = n;
        }

        /**
         * 清除所有事件
         */
        clear() {
            this.events.clear();
            this.onceEvents.clear();
        }

        /**
         * 销毁实例
         */
        destroy() {
            this.clear();
        }
    }

    // 创建全局实例
    const globalEventBus = new EventBus();

    // 导出
    return {
        EventBus,
        eventBus: globalEventBus,
        
        // 便捷方法
        on: (event, callback, options) => globalEventBus.on(event, callback, options),
        once: (event, callback, options) => globalEventBus.once(event, callback, options),
        off: (event, callback) => globalEventBus.off(event, callback),
        emit: (event, ...args) => globalEventBus.emit(event, ...args),
        emitSync: (event, ...args) => globalEventBus.emitSync(event, ...args)
    };
}));
