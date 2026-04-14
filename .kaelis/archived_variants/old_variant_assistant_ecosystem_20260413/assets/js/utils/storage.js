/**
 * Kaelis Storage Utils
 * 统一存储工具 - 安全存储封装
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.Storage = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';

    const PREFIX = 'kaelis_';
    const DEFAULT_EXPIRY = 3600; // 1小时

    /**
     * 安全存储类
     */
    class SecureStorage {
        constructor(options = {}) {
            this.prefix = options.prefix || PREFIX;
            this.memoryCache = new Map();
            this.fallbackToMemory = false;
        }

        /**
         * 检查存储可用性
         */
        isAvailable(type = 'localStorage') {
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

        /**
         * 设置存储项
         * @param {string} key - 键名
         * @param {*} value - 值
         * @param {Object} options - 选项
         * @param {number} options.expires - 过期时间（秒）
         * @param {boolean} options.secure - 是否仅内存存储
         */
        set(key, value, options = {}) {
            const fullKey = this.prefix + key;
            const data = {
                value: value,
                timestamp: Date.now(),
                expires: options.expires ? Date.now() + options.expires * 1000 : null
            };

            // 敏感数据仅内存存储
            if (options.secure || this.fallbackToMemory) {
                this.memoryCache.set(fullKey, data);
                return true;
            }

            // 尝试localStorage
            if (this.isAvailable('localStorage')) {
                try {
                    localStorage.setItem(fullKey, JSON.stringify(data));
                    return true;
                } catch (e) {
                    // 存储已满，切换到内存
                    this.fallbackToMemory = true;
                    this.memoryCache.set(fullKey, data);
                    console.warn('[SecureStorage] Fallback to memory storage');
                    return true;
                }
            }

            // 使用内存存储
            this.memoryCache.set(fullKey, data);
            return true;
        }

        /**
         * 获取存储项
         * @param {string} key - 键名
         * @returns {*} 存储的值
         */
        get(key) {
            const fullKey = this.prefix + key;

            // 优先从内存获取
            if (this.memoryCache.has(fullKey)) {
                const data = this.memoryCache.get(fullKey);
                if (this.isExpired(data)) {
                    this.memoryCache.delete(fullKey);
                    return null;
                }
                return data.value;
            }

            // 从localStorage获取
            if (this.isAvailable('localStorage')) {
                try {
                    const item = localStorage.getItem(fullKey);
                    if (!item) return null;

                    const data = JSON.parse(item);
                    if (this.isExpired(data)) {
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

        /**
         * 删除存储项
         * @param {string} key - 键名
         */
        remove(key) {
            const fullKey = this.prefix + key;
            this.memoryCache.delete(fullKey);

            if (this.isAvailable('localStorage')) {
                localStorage.removeItem(fullKey);
            }
        }

        /**
         * 清空所有存储
         */
        clear() {
            this.memoryCache.clear();

            if (this.isAvailable('localStorage')) {
                for (let i = localStorage.length - 1; i >= 0; i--) {
                    const key = localStorage.key(i);
                    if (key && key.startsWith(this.prefix)) {
                        localStorage.removeItem(key);
                    }
                }
            }
        }

        /**
         * 检查是否过期
         * @private
         */
        isExpired(data) {
            if (!data || !data.expires) return false;
            return Date.now() > data.expires;
        }

        /**
         * 获取所有键
         * @returns {string[]}
         */
        keys() {
            const keys = [];
            
            // 内存中的键
            for (const key of this.memoryCache.keys()) {
                if (key.startsWith(this.prefix)) {
                    keys.push(key.slice(this.prefix.length));
                }
            }

            // localStorage中的键
            if (this.isAvailable('localStorage')) {
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    if (key && key.startsWith(this.prefix)) {
                        const shortKey = key.slice(this.prefix.length);
                        if (!keys.includes(shortKey)) {
                            keys.push(shortKey);
                        }
                    }
                }
            }

            return keys;
        }

        /**
         * 获取存储大小
         * @returns {number}
         */
        size() {
            return this.keys().length;
        }
    }

    // 创建默认实例
    const defaultStorage = new SecureStorage();

    // 导出
    return {
        SecureStorage,
        storage: defaultStorage,
        
        // 便捷方法
        get: (key) => defaultStorage.get(key),
        set: (key, value, options) => defaultStorage.set(key, value, options),
        remove: (key) => defaultStorage.remove(key),
        clear: () => defaultStorage.clear()
    };
}));
