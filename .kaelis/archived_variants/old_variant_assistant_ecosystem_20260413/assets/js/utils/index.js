/**
 * Kaelis Utils Index
 * 工具库统一入口
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define(['./storage', './validator', './event-bus', './http-client'], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory(
            require('./storage'),
            require('./validator'),
            require('./event-bus'),
            require('./http-client')
        );
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.Utils = factory(
            root.Kaelis.Storage,
            root.Kaelis.Validator,
            root.Kaelis.EventBus,
            root.Kaelis.HttpClient
        );
    }
}(typeof self !== 'undefined' ? self : this, function(Storage, Validator, EventBus, HttpClient) {
    'use strict';

    /**
     * 工具库命名空间
     */
    const Utils = {
        // 子模块
        Storage: Storage,
        Validator: Validator,
        EventBus: EventBus,
        HttpClient: HttpClient,

        // 便捷访问
        storage: Storage ? Storage.storage : null,
        validator: Validator ? Validator.validator : null,
        eventBus: EventBus ? EventBus.eventBus : null,
        http: HttpClient ? HttpClient.http : null,

        /**
         * 初始化所有工具
         * @param {Object} config - 配置对象
         */
        init(config = {}) {
            // 配置存储
            if (this.storage && config.storage) {
                // 存储配置已应用到实例
            }

            // 配置HTTP客户端
            if (this.http && config.http) {
                this.http.setConfig(config.http);
            }

            // 配置验证器
            if (this.validator && config.validator) {
                // 验证器配置
            }

            console.log('[Kaelis Utils] Initialized');
        },

        /**
         * 版本信息
         */
        version: '1.0.0',

        /**
         * 检查模块是否可用
         * @param {string} moduleName - 模块名称
         * @returns {boolean}
         */
        has(moduleName) {
            const modules = {
                storage: !!this.storage,
                validator: !!this.validator,
                eventBus: !!this.eventBus,
                http: !!this.http
            };
            return modules[moduleName] || false;
        }
    };

    return Utils;
}));
