/**
 * Kaelis Multi-Platform Plugin Integration System
 * 多平台插件集成架构 - GitHub/GitLab/Gitee/Bitbucket
 */

(function() {
    'use strict';

    // 平台配置
    const PLATFORMS = {
        github: {
            name: 'GitHub',
            icon: '💻',
            apiBase: 'https://api.github.com',
            authType: 'oauth2',
            scopes: ['repo', 'user', 'read:org'],
            features: ['repo', 'code', 'issues', 'pulls', 'search']
        },
        gitlab: {
            name: 'GitLab',
            icon: '🦊',
            apiBase: 'https://gitlab.com/api/v4',
            authType: 'oauth2',
            scopes: ['api', 'read_user', 'read_repository'],
            features: ['repo', 'code', 'issues', 'merge_requests', 'search']
        },
        gitee: {
            name: 'Gitee',
            icon: '🇨🇳',
            apiBase: 'https://gitee.com/api/v5',
            authType: 'oauth2',
            scopes: ['projects', 'pull_requests', 'issues', 'user_info'],
            features: ['repo', 'code', 'issues', 'pulls', 'search']
        },
        bitbucket: {
            name: 'Bitbucket',
            icon: '🪣',
            apiBase: 'https://api.bitbucket.org/2.0',
            authType: 'oauth2',
            scopes: ['repository', 'pullrequest', 'issue:read'],
            features: ['repo', 'code', 'issues', 'pulls']
        }
    };

    // 插件管理器
    class PlatformPluginManager {
        constructor() {
            this.plugins = new Map();
            this.activePlugins = new Set();
            this.cache = new Map();
            this.rateLimits = new Map();
        }

        // 注册插件
        register(platform, config) {
            if (!PLATFORMS[platform]) {
                throw new Error(`不支持的平台: ${platform}`);
            }
            
            this.plugins.set(platform, {
                ...PLATFORMS[platform],
                ...config,
                isAuthenticated: false,
                token: null,
                rateLimit: null
            });
            
            console.log(`[PlatformPlugin] 已注册 ${platform} 插件`);
        }

        // 认证流程
        async authenticate(platform) {
            const plugin = this.plugins.get(platform);
            if (!plugin) {
                throw new Error(`插件未注册: ${platform}`);
            }

            try {
                // OAuth2 认证流程
                const authUrl = this.buildAuthUrl(platform);
                const popup = window.open(authUrl, `${platform}_auth`, 'width=600,height=600');
                
                return new Promise((resolve, reject) => {
                    const checkAuth = setInterval(() => {
                        if (popup.closed) {
                            clearInterval(checkAuth);
                            reject(new Error('用户取消了认证'));
                        }
                    }, 1000);

                    window.addEventListener('message', (event) => {
                        if (event.data.type === `${platform}_auth_success`) {
                            clearInterval(checkAuth);
                            popup.close();
                            this.handleAuthSuccess(platform, event.data.token);
                            resolve(true);
                        }
                    });
                });
            } catch (error) {
                console.error(`[PlatformPlugin] ${platform} 认证失败:`, error);
                throw error;
            }
        }

        // 构建认证URL
        buildAuthUrl(platform) {
            const plugin = this.plugins.get(platform);
            const redirectUri = encodeURIComponent(`${window.location.origin}/auth/callback/${platform}`);
            
            const authUrls = {
                github: `https://github.com/login/oauth/authorize?client_id=${plugin.clientId}&redirect_uri=${redirectUri}&scope=${plugin.scopes.join(',')}`,
                gitlab: `https://gitlab.com/oauth/authorize?client_id=${plugin.clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${plugin.scopes.join(',')}`,
                gitee: `https://gitee.com/oauth/authorize?client_id=${plugin.clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${plugin.scopes.join(',')}`,
                bitbucket: `https://bitbucket.org/site/oauth2/authorize?client_id=${plugin.clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${plugin.scopes.join(',')}`
            };
            
            return authUrls[platform];
        }

        // 处理认证成功
        handleAuthSuccess(platform, token) {
            const plugin = this.plugins.get(platform);
            plugin.token = token;
            plugin.isAuthenticated = true;
            this.activePlugins.add(platform);
            
            // 保存到本地存储
            localStorage.setItem(`kaelis_${platform}_token`, JSON.stringify({
                token,
                timestamp: Date.now()
            }));
            
            console.log(`[PlatformPlugin] ${platform} 认证成功`);
        }

        // API调用封装
        async callApi(platform, endpoint, options = {}) {
            const plugin = this.plugins.get(platform);
            if (!plugin || !plugin.isAuthenticated) {
                throw new Error(`${platform} 未认证`);
            }

            // 检查速率限制
            if (this.isRateLimited(platform)) {
                throw new Error(`${platform} API 速率限制，请稍后重试`);
            }

            const url = `${plugin.apiBase}${endpoint}`;
            const headers = {
                'Authorization': `Bearer ${plugin.token}`,
                'Accept': 'application/json',
                'User-Agent': 'Kaelis-Platform-Plugin/1.0'
            };

            try {
                const response = await fetch(url, {
                    ...options,
                    headers: {
                        ...headers,
                        ...options.headers
                    }
                });

                // 更新速率限制信息
                this.updateRateLimit(platform, response.headers);

                if (!response.ok) {
                    throw new Error(`${platform} API 错误: ${response.status}`);
                }

                return await response.json();
            } catch (error) {
                console.error(`[PlatformPlugin] ${platform} API 调用失败:`, error);
                throw error;
            }
        }

        // 检查速率限制
        isRateLimited(platform) {
            const limit = this.rateLimits.get(platform);
            if (!limit) return false;
            
            return limit.remaining <= 0 && Date.now() < limit.resetTime;
        }

        // 更新速率限制
        updateRateLimit(platform, headers) {
            const remaining = headers.get('X-RateLimit-Remaining');
            const reset = headers.get('X-RateLimit-Reset');
            
            if (remaining && reset) {
                this.rateLimits.set(platform, {
                    remaining: parseInt(remaining),
                    resetTime: parseInt(reset) * 1000
                });
            }
        }

        // 搜索仓库
        async searchRepos(platform, query, options = {}) {
            const endpoints = {
                github: `/search/repositories?q=${encodeURIComponent(query)}&sort=${options.sort || 'stars'}&order=${options.order || 'desc'}`,
                gitlab: `/projects?search=${encodeURIComponent(query)}&order_by=${options.sort || 'stars'}&sort=${options.order || 'desc'}`,
                gitee: `/search/repositories?q=${encodeURIComponent(query)}&sort=${options.sort || 'stars_count'}&order=${options.order || 'desc'}`,
                bitbucket: `/repositories/${encodeURIComponent(query)}?sort=${options.sort || '-updated_on'}`
            };

            const data = await this.callApi(platform, endpoints[platform]);
            return this.normalizeRepoData(platform, data);
        }

        // 标准化仓库数据
        normalizeRepoData(platform, data) {
            const normalizers = {
                github: (items) => items.items.map(item => ({
                    id: item.id,
                    name: item.name,
                    fullName: item.full_name,
                    description: item.description,
                    url: item.html_url,
                    stars: item.stargazers_count,
                    forks: item.forks_count,
                    language: item.language,
                    updatedAt: item.updated_at,
                    platform: 'github'
                })),
                gitlab: (data) => data.map(item => ({
                    id: item.id,
                    name: item.name,
                    fullName: item.path_with_namespace,
                    description: item.description,
                    url: item.web_url,
                    stars: item.star_count,
                    forks: item.forks_count,
                    language: null,
                    updatedAt: item.last_activity_at,
                    platform: 'gitlab'
                })),
                gitee: (data) => data.repositories.map(item => ({
                    id: item.id,
                    name: item.name,
                    fullName: item.full_name,
                    description: item.description,
                    url: item.html_url,
                    stars: item.stargazers_count,
                    forks: item.forks_count,
                    language: item.language,
                    updatedAt: item.updated_at,
                    platform: 'gitee'
                })),
                bitbucket: (data) => data.values.map(item => ({
                    id: item.uuid,
                    name: item.name,
                    fullName: item.full_name,
                    description: item.description,
                    url: item.links.html.href,
                    stars: 0,
                    forks: 0,
                    language: item.language,
                    updatedAt: item.updated_on,
                    platform: 'bitbucket'
                }))
            };

            return normalizers[platform](data);
        }

        // 获取代码内容
        async getCode(platform, owner, repo, path, ref = 'main') {
            const endpoints = {
                github: `/repos/${owner}/${repo}/contents/${path}?ref=${ref}`,
                gitlab: `/projects/${encodeURIComponent(`${owner}/${repo}`)}/repository/files/${encodeURIComponent(path)}?ref=${ref}`,
                gitee: `/repos/${owner}/${repo}/contents/${path}?ref=${ref}`,
                bitbucket: `/repositories/${owner}/${repo}/src/${ref}/${path}`
            };

            return await this.callApi(platform, endpoints[platform]);
        }

        // 获取Issue列表
        async getIssues(platform, owner, repo, state = 'open') {
            const endpoints = {
                github: `/repos/${owner}/${repo}/issues?state=${state}`,
                gitlab: `/projects/${encodeURIComponent(`${owner}/${repo}`)}/issues?state=${state}`,
                gitee: `/repos/${owner}/${repo}/issues?state=${state}`,
                bitbucket: `/repositories/${owner}/${repo}/issues?state=${state}`
            };

            return await this.callApi(platform, endpoints[platform]);
        }

        // 多平台统一搜索
        async searchAllPlatforms(query, options = {}) {
            const promises = [];
            
            for (const platform of this.activePlugins) {
                promises.push(
                    this.searchRepos(platform, query, options)
                        .then(results => ({ platform, results, success: true }))
                        .catch(error => ({ platform, error: error.message, success: false }))
                );
            }

            const results = await Promise.allSettled(promises);
            
            return results.reduce((acc, result) => {
                if (result.status === 'fulfilled') {
                    acc[result.value.platform] = result.value;
                }
                return acc;
            }, {});
        }

        // 获取已认证的平台列表
        getAuthenticatedPlatforms() {
            return Array.from(this.activePlugins).map(platform => ({
                platform,
                ...this.plugins.get(platform),
                token: undefined // 不暴露token
            }));
        }

        // 注销平台
        logout(platform) {
            const plugin = this.plugins.get(platform);
            if (plugin) {
                plugin.token = null;
                plugin.isAuthenticated = false;
                this.activePlugins.delete(platform);
                localStorage.removeItem(`kaelis_${platform}_token`);
                console.log(`[PlatformPlugin] ${platform} 已注销`);
            }
        }
    }

    // 导出 - UMD格式
    const exports = {
        PlatformPluginManager,
        PLATFORMS,
        AUTH_SCOPES
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.PlatformPlugins = exports;
        // 保持向后兼容
        window.PlatformPluginManager = PlatformPluginManager;
        window.platformPlugins = new PlatformPluginManager();
    }

    console.log('[PlatformPlugin] 多平台插件系统已加载');
})();
