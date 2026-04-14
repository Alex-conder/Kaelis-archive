/**
 * Kaelis Initialization
 * 系统初始化入口 - 统一初始化所有模块
 */

(function() {
    'use strict';

    // Kaelis 全局命名空间
    window.Kaelis = window.Kaelis || {};
    
    // 导出为UMD格式
    if (typeof module === 'object' && module.exports) {
        module.exports = { KaelisInitializer };
    }

    /**
     * Kaelis 初始化器
     */
    class KaelisInitializer {
        constructor(config = {}) {
            this.config = {
                apiBaseUrl: config.apiBaseUrl || '/api',
                wsUrl: config.wsUrl || null,
                enableAuth: config.enableAuth !== false,
                enableMonitoring: config.enableMonitoring !== false,
                enableOpenSource: config.enableOpenSource !== false,
                debug: config.debug || false
            };

            this.modules = {};
            this.initialized = false;
            this.initTime = null;
        }

        // 初始化
        async init() {
            if (this.initialized) {
                console.warn('[Kaelis] Already initialized');
                return;
            }

            this.initTime = Date.now();
            console.log('[Kaelis] Initializing...');

            try {
                // 1. 初始化认证模块
                if (this.config.enableAuth) {
                    await this.initAuth();
                }

                // 2. 初始化开源合规模块
                if (this.config.enableOpenSource) {
                    await this.initOpenSource();
                }

                // 3. 初始化监控模块
                if (this.config.enableMonitoring) {
                    await this.initMonitoring();
                }

                // 4. 初始化WebSocket
                await this.initWebSocket();

                this.initialized = true;
                const duration = Date.now() - this.initTime;
                console.log(`[Kaelis] Initialized in ${duration}ms`);

                // 触发初始化完成事件
                window.dispatchEvent(new CustomEvent('kaelis:ready', {
                    detail: { modules: Object.keys(this.modules) }
                }));

            } catch (error) {
                console.error('[Kaelis] Initialization failed:', error);
                throw error;
            }
        }

        // 初始化认证
        async initAuth() {
            const wsAuth = window.Kaelis && window.Kaelis.WebSocketAuth;
            if (!wsAuth) {
                console.warn('[Kaelis] WebSocketAuth module not available');
                return;
            }

            const { JWTTokenManager } = wsAuth;
            
            this.modules.auth = new JWTTokenManager({
                maxDevices: 5
            });

            // 监听认证事件
            this.modules.auth.on('auth:login:success', (data) => {
                console.log('[Kaelis] User logged in:', data.user?.email);
            });

            this.modules.auth.on('auth:logout', () => {
                console.log('[Kaelis] User logged out');
            });

            // 尝试恢复会话
            const state = this.modules.auth.getState();
            if (state.isAuthenticated && state.isTokenValid) {
                console.log('[Kaelis] Session restored');
            }
        }

        // 初始化开源合规
        async initOpenSource() {
            const osm = (window.Kaelis && window.Kaelis.OpenSourceMatcher) || window.EnhancedOpenSourceMatcher;
            if (!osm) {
                console.warn('[Kaelis] Open source module not available');
                return;
            }

            const { 
                EnhancedLicenseDetector, 
                EnhancedSBOMGenerator,
                DependencyTreeAnalyzer 
            } = osm;

            this.modules.licenseDetector = new EnhancedLicenseDetector();
            this.modules.sbomGenerator = new EnhancedSBOMGenerator();
            this.modules.dependencyAnalyzer = new DependencyTreeAnalyzer();

            console.log('[Kaelis] Open source compliance modules ready');
        }

        // 初始化监控
        async initMonitoring() {
            const alertSys = (window.Kaelis && window.Kaelis.AlertSystem) || window.AlertSystemAdvanced;
            if (!alertSys) {
                console.warn('[Kaelis] Alert system not available');
                return;
            }

            const { AdvancedAlertSystem } = alertSys;
            
            this.modules.alerts = new AdvancedAlertSystem();

            // 添加默认规则
            this.modules.alerts.ruleEngine.addRule({
                name: 'System Error Alert',
                condition: (data) => data.level === 'error',
                actions: ['notify'],
                priority: 10
            });

            console.log('[Kaelis] Monitoring modules ready');
        }

        // 初始化WebSocket
        async initWebSocket() {
            if (!window.ResilientWebSocketClient) {
                console.warn('[Kaelis] WebSocket client not available');
                return;
            }

            // WebSocket将在需要时延迟初始化
            this.modules.ws = null;
        }

        // 获取模块
        getModule(name) {
            return this.modules[name];
        }

        // 检查是否已初始化
        isReady() {
            return this.initialized;
        }

        // 获取状态
        getStatus() {
            return {
                initialized: this.initialized,
                initTime: this.initTime,
                modules: Object.keys(this.modules),
                config: this.config
            };
        }
    }

    // 创建全局实例
    Kaelis.init = async function(config) {
        if (!Kaelis.instance) {
            Kaelis.instance = new KaelisInitializer(config);
        }
        return Kaelis.instance.init();
    };

    Kaelis.getInstance = function() {
        return Kaelis.instance;
    };

    // 自动初始化（DOM加载完成后）
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            Kaelis.init();
        });
    } else {
        // DOM已加载
        setTimeout(() => Kaelis.init(), 0);
    }

    console.log('[Kaelis] Initialization system loaded');
})();
