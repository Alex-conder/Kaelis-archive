/**
 * Kaelis Validator Utils
 * 输入验证工具 - XSS防护、数据验证
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.Validator = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';

    // HTML转义映射
    const HTML_ESCAPE_MAP = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;',
        '`': '&#x60;',
        '=': '&#x3D;'
    };

    // 正则表达式集合
    const REGEX = {
        email: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
        url: /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/,
        phone: /^1[3-9]\d{9}$/,
        uuid: /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
        ip: /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
        hexColor: /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/
    };

    /**
     * 验证器类
     */
    class Validator {
        constructor() {
            this.errors = [];
        }

        /**
         * HTML转义 - 防止XSS
         * @param {string} str - 输入字符串
         * @returns {string} 转义后的字符串
         */
        escapeHTML(str) {
            if (typeof str !== 'string') return '';
            return str.replace(/[&<>"'`=\/]/g, (s) => HTML_ESCAPE_MAP[s] || s);
        }

        /**
         * 反转义HTML
         * @param {string} str - 转义字符串
         * @returns {string} 原始字符串
         */
        unescapeHTML(str) {
            if (typeof str !== 'string') return '';
            const unescapeMap = Object.fromEntries(
                Object.entries(HTML_ESCAPE_MAP).map(([k, v]) => [v, k])
            );
            return str.replace(/&[^;]+;/g, (s) => unescapeMap[s] || s);
        }

        /**
         * 清理HTML标签
         * @param {string} str - 输入字符串
         * @param {string[]} allowedTags - 允许的标签
         * @returns {string} 清理后的字符串
         */
        sanitizeHTML(str, allowedTags = []) {
            if (typeof str !== 'string') return '';
            
            if (allowedTags.length === 0) {
                // 移除所有标签
                return str.replace(/<[^>]*>/g, '');
            }

            // 只允许指定标签
            const tagPattern = new RegExp(
                `<(?!\\/?(?:${allowedTags.join('|')})\\b)[^>]*>`,
                'gi'
            );
            return str.replace(tagPattern, '');
        }

        /**
         * 验证邮箱
         * @param {string} email - 邮箱地址
         * @returns {boolean}
         */
        isEmail(email) {
            return REGEX.email.test(String(email).toLowerCase());
        }

        /**
         * 验证URL
         * @param {string} url - URL地址
         * @returns {boolean}
         */
        isURL(url) {
            return REGEX.url.test(String(url));
        }

        /**
         * 验证手机号
         * @param {string} phone - 手机号
         * @returns {boolean}
         */
        isPhone(phone) {
            return REGEX.phone.test(String(phone));
        }

        /**
         * 验证UUID
         * @param {string} uuid - UUID
         * @returns {boolean}
         */
        isUUID(uuid) {
            return REGEX.uuid.test(String(uuid));
        }

        /**
         * 验证IP地址
         * @param {string} ip - IP地址
         * @returns {boolean}
         */
        isIP(ip) {
            return REGEX.ip.test(String(ip));
        }

        /**
         * 验证长度
         * @param {string} str - 字符串
         * @param {Object} options - 选项
         * @param {number} options.min - 最小长度
         * @param {number} options.max - 最大长度
         * @returns {boolean}
         */
        isLength(str, options = {}) {
            const len = String(str).length;
            if (options.min !== undefined && len < options.min) return false;
            if (options.max !== undefined && len > options.max) return false;
            return true;
        }

        /**
         * 验证非空
         * @param {*} value - 值
         * @returns {boolean}
         */
        isRequired(value) {
            if (value === null || value === undefined) return false;
            if (typeof value === 'string' && value.trim() === '') return false;
            if (Array.isArray(value) && value.length === 0) return false;
            return true;
        }

        /**
         * 验证数值范围
         * @param {number} num - 数值
         * @param {Object} options - 选项
         * @param {number} options.min - 最小值
         * @param {number} options.max - 最大值
         * @returns {boolean}
         */
        isNumberRange(num, options = {}) {
            const n = Number(num);
            if (isNaN(n)) return false;
            if (options.min !== undefined && n < options.min) return false;
            if (options.max !== undefined && n > options.max) return false;
            return true;
        }

        /**
         * 验证正则
         * @param {string} str - 字符串
         * @param {RegExp} regex - 正则表达式
         * @returns {boolean}
         */
        matches(str, regex) {
            return regex.test(String(str));
        }

        /**
         * 验证对象结构
         * @param {Object} obj - 对象
         * @param {Object} schema - 验证模式
         * @returns {Object} 验证结果
         */
        validateObject(obj, schema) {
            this.errors = [];
            const result = {};

            for (const [key, rules] of Object.entries(schema)) {
                const value = obj[key];
                const fieldResult = this.validateField(key, value, rules);
                
                if (!fieldResult.valid) {
                    this.errors.push(...fieldResult.errors);
                }
                
                result[key] = fieldResult.value;
            }

            return {
                valid: this.errors.length === 0,
                errors: this.errors,
                data: result
            };
        }

        /**
         * 验证单个字段
         * @private
         */
        validateField(key, value, rules) {
            const errors = [];
            let processedValue = value;

            // 必填检查
            if (rules.required && !this.isRequired(value)) {
                errors.push({ field: key, message: `${key} is required` });
                return { valid: false, errors, value: null };
            }

            // 如果非必填且为空，跳过其他验证
            if (!rules.required && !this.isRequired(value)) {
                return { valid: true, errors: [], value: null };
            }

            // 类型转换和验证
            if (rules.type) {
                const typeResult = this.validateType(key, value, rules.type);
                if (!typeResult.valid) {
                    errors.push(typeResult.error);
                } else {
                    processedValue = typeResult.value;
                }
            }

            // 长度验证
            if (rules.length) {
                if (!this.isLength(processedValue, rules.length)) {
                    errors.push({ 
                        field: key, 
                        message: `${key} length must be between ${rules.length.min} and ${rules.length.max}` 
                    });
                }
            }

            // 自定义验证
            if (rules.validator && typeof rules.validator === 'function') {
                const customResult = rules.validator(processedValue);
                if (customResult !== true) {
                    errors.push({ 
                        field: key, 
                        message: customResult || `${key} validation failed` 
                    });
                }
            }

            // XSS防护 - 自动转义字符串
            if (rules.escape !== false && typeof processedValue === 'string') {
                processedValue = this.escapeHTML(processedValue);
            }

            return {
                valid: errors.length === 0,
                errors,
                value: processedValue
            };
        }

        /**
         * 验证类型
         * @private
         */
        validateType(key, value, type) {
            switch (type) {
                case 'string':
                    return { valid: true, value: String(value) };
                case 'number':
                    const num = Number(value);
                    if (isNaN(num)) {
                        return { valid: false, error: { field: key, message: `${key} must be a number` } };
                    }
                    return { valid: true, value: num };
                case 'boolean':
                    return { valid: true, value: Boolean(value) };
                case 'email':
                    if (!this.isEmail(value)) {
                        return { valid: false, error: { field: key, message: `${key} must be a valid email` } };
                    }
                    return { valid: true, value: String(value) };
                case 'url':
                    if (!this.isURL(value)) {
                        return { valid: false, error: { field: key, message: `${key} must be a valid URL` } };
                    }
                    return { valid: true, value: String(value) };
                default:
                    return { valid: true, value };
            }
        }

        /**
         * 获取错误信息
         * @returns {string[]}
         */
        getErrors() {
            return this.errors;
        }

        /**
         * 清除错误
         */
        clearErrors() {
            this.errors = [];
        }
    }

    // 创建默认实例
    const defaultValidator = new Validator();

    // 导出
    return {
        Validator,
        validator: defaultValidator,
        
        // 便捷方法
        escapeHTML: (str) => defaultValidator.escapeHTML(str),
        sanitizeHTML: (str, allowed) => defaultValidator.sanitizeHTML(str, allowed),
        isEmail: (email) => defaultValidator.isEmail(email),
        isURL: (url) => defaultValidator.isURL(url),
        isRequired: (value) => defaultValidator.isRequired(value),
        validateObject: (obj, schema) => defaultValidator.validateObject(obj, schema)
    };
}));
