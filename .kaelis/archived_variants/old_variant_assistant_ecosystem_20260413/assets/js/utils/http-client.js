/**
 * Kaelis HTTP Client
 * HTTP请求客户端 - 统一请求处理、拦截器、错误处理
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.HttpClient = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';

    // 默认配置
    const DEFAULT_CONFIG = {
        baseURL: '',
        timeout: 30000,
        headers: {
            'Content-Type': 'application/json'
        },
        retry: 0,
        retryDelay: 1000
    };

    /**
     * HTTP错误类
     */
    class HttpError extends Error {
        constructor(message, status, data, response) {
            super(message);
            this.name = 'HttpError';
            this.status = status;
            this.data = data;
            this.response = response;
        }
    }

    /**
     * HTTP客户端类
     */
    class HttpClient {
        constructor(config = {}) {
            this.config = { ...DEFAULT_CONFIG, ...config };
            this.interceptors = {
                request: [],
                response: []
            };
        }

        /**
         * 设置配置
         * @param {Object} config - 配置对象
         */
        setConfig(config) {
            this.config = { ...this.config, ...config };
        }

        /**
         * 添加请求拦截器
         * @param {Function} onFulfilled - 成功回调
         * @param {Function} onRejected - 失败回调
         * @returns {number} 拦截器ID
         */
        addRequestInterceptor(onFulfilled, onRejected) {
            const id = this.interceptors.request.length;
            this.interceptors.request.push({ onFulfilled, onRejected });
            return id;
        }

        /**
         * 添加响应拦截器
         * @param {Function} onFulfilled - 成功回调
         * @param {Function} onRejected - 失败回调
         * @returns {number} 拦截器ID
         */
        addResponseInterceptor(onFulfilled, onRejected) {
            const id = this.interceptors.response.length;
            this.interceptors.response.push({ onFulfilled, onRejected });
            return id;
        }

        /**
         * 移除请求拦截器
         * @param {number} id - 拦截器ID
         */
        removeRequestInterceptor(id) {
            this.interceptors.request[id] = null;
        }

        /**
         * 移除响应拦截器
         * @param {number} id - 拦截器ID
         */
        removeResponseInterceptor(id) {
            this.interceptors.response[id] = null;
        }

        /**
         * 执行请求拦截器
         * @private
         */
        async runRequestInterceptors(config) {
            let result = config;
            for (const interceptor of this.interceptors.request) {
                if (!interceptor) continue;
                try {
                    result = await interceptor.onFulfilled(result);
                } catch (error) {
                    if (interceptor.onRejected) {
                        result = await interceptor.onRejected(error);
                    } else {
                        throw error;
                    }
                }
            }
            return result;
        }

        /**
         * 执行响应拦截器
         * @private
         */
        async runResponseInterceptors(response) {
            let result = response;
            for (const interceptor of this.interceptors.response) {
                if (!interceptor) continue;
                try {
                    result = await interceptor.onFulfilled(result);
                } catch (error) {
                    if (interceptor.onRejected) {
                        result = await interceptor.onRejected(error);
                    } else {
                        throw error;
                    }
                }
            }
            return result;
        }

        /**
         * 构建完整URL
         * @private
         */
        buildURL(url) {
            if (url.startsWith('http://') || url.startsWith('https://')) {
                return url;
            }
            const baseURL = this.config.baseURL.replace(/\/$/, '');
            const path = url.startsWith('/') ? url : `/${url}`;
            return baseURL + path;
        }

        /**
         * 构建请求头
         * @private
         */
        buildHeaders(customHeaders = {}) {
            return {
                ...this.config.headers,
                ...customHeaders
            };
        }

        /**
         * 发送请求
         * @param {string} method - HTTP方法
         * @param {string} url - URL
         * @param {Object} options - 选项
         * @returns {Promise<any>}
         */
        async request(method, url, options = {}) {
            const config = {
                method: method.toUpperCase(),
                url,
                headers: this.buildHeaders(options.headers),
                timeout: options.timeout || this.config.timeout,
                retry: options.retry !== undefined ? options.retry : this.config.retry,
                retryDelay: options.retryDelay || this.config.retryDelay,
                data: options.data,
                params: options.params
            };

            // 执行请求拦截器
            const finalConfig = await this.runRequestInterceptors(config);

            // 构建URL
            let fullURL = this.buildURL(finalConfig.url);
            
            // 添加查询参数
            if (finalConfig.params) {
                const params = new URLSearchParams(finalConfig.params);
                fullURL += `?${params.toString()}`;
            }

            // 发送请求
            return this.sendRequest(fullURL, finalConfig);
        }

        /**
         * 实际发送请求
         * @private
         */
        async sendRequest(url, config, attempt = 0) {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), config.timeout);

            try {
                const fetchConfig = {
                    method: config.method,
                    headers: config.headers,
                    signal: controller.signal
                };

                // 处理请求体
                if (config.data) {
                    if (config.data instanceof FormData) {
                        delete fetchConfig.headers['Content-Type'];
                        fetchConfig.body = config.data;
                    } else if (typeof config.data === 'object') {
                        fetchConfig.body = JSON.stringify(config.data);
                    } else {
                        fetchConfig.body = config.data;
                    }
                }

                const response = await fetch(url, fetchConfig);
                clearTimeout(timeoutId);

                // 处理响应
                const result = await this.handleResponse(response);
                
                // 执行响应拦截器
                return await this.runResponseInterceptors(result);

            } catch (error) {
                clearTimeout(timeoutId);

                // 重试逻辑
                if (attempt < config.retry && this.shouldRetry(error)) {
                    await this.delay(config.retryDelay * (attempt + 1));
                    return this.sendRequest(url, config, attempt + 1);
                }

                throw this.handleError(error);
            }
        }

        /**
         * 处理响应
         * @private
         */
        async handleResponse(response) {
            const contentType = response.headers.get('content-type') || '';
            let data;

            if (contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            if (!response.ok) {
                throw new HttpError(
                    data.message || `HTTP ${response.status}`,
                    response.status,
                    data,
                    response
                );
            }

            return {
                data,
                status: response.status,
                headers: response.headers,
                response
            };
        }

        /**
         * 处理错误
         * @private
         */
        handleError(error) {
            if (error.name === 'AbortError') {
                return new HttpError('Request timeout', 408, null, null);
            }
            if (error instanceof HttpError) {
                return error;
            }
            return new HttpError(error.message || 'Network error', 0, null, null);
        }

        /**
         * 判断是否重试
         * @private
         */
        shouldRetry(error) {
            if (error instanceof HttpError) {
                // 5xx错误或网络错误时重试
                return error.status >= 500 || error.status === 0;
            }
            return false;
        }

        /**
         * 延迟
         * @private
         */
        delay(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }

        // HTTP方法快捷方式
        get(url, options = {}) {
            return this.request('GET', url, options);
        }

        post(url, data, options = {}) {
            return this.request('POST', url, { ...options, data });
        }

        put(url, data, options = {}) {
            return this.request('PUT', url, { ...options, data });
        }

        patch(url, data, options = {}) {
            return this.request('PATCH', url, { ...options, data });
        }

        delete(url, options = {}) {
            return this.request('DELETE', url, options);
        }

        /**
         * 上传文件
         * @param {string} url - URL
         * @param {File|Blob} file - 文件
         * @param {Object} options - 选项
         * @returns {Promise<any>}
         */
        upload(url, file, options = {}) {
            const formData = new FormData();
            formData.append(options.fieldName || 'file', file);

            // 添加额外字段
            if (options.data) {
                for (const [key, value] of Object.entries(options.data)) {
                    formData.append(key, value);
                }
            }

            return this.post(url, formData, {
                ...options,
                headers: {
                    ...options.headers,
                    'Content-Type': undefined // 让浏览器自动设置
                }
            });
        }
    }

    // 创建默认实例
    const defaultClient = new HttpClient();

    // 导出
    return {
        HttpClient,
        HttpError,
        http: defaultClient,
        
        // 便捷方法
        get: (url, options) => defaultClient.get(url, options),
        post: (url, data, options) => defaultClient.post(url, data, options),
        put: (url, data, options) => defaultClient.put(url, data, options),
        patch: (url, data, options) => defaultClient.patch(url, data, options),
        delete: (url, options) => defaultClient.delete(url, options),
        upload: (url, file, options) => defaultClient.upload(url, file, options)
    };
}));
