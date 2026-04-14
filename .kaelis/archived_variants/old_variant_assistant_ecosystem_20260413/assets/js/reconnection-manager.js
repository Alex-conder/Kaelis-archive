/**
 * Kaelis Reconnection Manager
 * 断线重连与任务状态恢复
 */

(function() {
    'use strict';

    // 连接状态
    const CONNECTION_STATE = {
        DISCONNECTED: 'disconnected',
        CONNECTING: 'connecting',
        CONNECTED: 'connected',
        AUTHENTICATING: 'authenticating',
        AUTHENTICATED: 'authenticated',
        RECOVERING: 'recovering',
        ERROR: 'error'
    };

    // 重连策略
    const RECONNECT_STRATEGY = {
        IMMEDIATE: 'immediate',       // 立即重连
        LINEAR: 'linear',             // 线性退避
        EXPONENTIAL: 'exponential',   // 指数退避
        FIXED: 'fixed'                // 固定间隔
    };

    /**
     * 重连管理器
     */
    class ReconnectionManager {
        constructor(options = {}) {
            this.strategy = options.strategy || RECONNECT_STRATEGY.EXPONENTIAL;
            this.baseDelay = options.baseDelay || 1000;
            this.maxDelay = options.maxDelay || 30000;
            this.maxAttempts = options.maxAttempts || 10;
            this.resetTimeout = options.resetTimeout || 60000; // 1分钟后重置重连计数

            this.attempts = 0;
            this.lastAttemptTime = null;
            this.reconnectTimer = null;
            this.isReconnecting = false;

            this.callbacks = {
                onReconnectAttempt: [],
                onReconnectSuccess: [],
                onReconnectFailure: [],
                onStateChange: []
            };
        }

        // 计算重连延迟
        calculateDelay() {
            // 检查是否需要重置计数
            if (this.lastAttemptTime && 
                Date.now() - this.lastAttemptTime > this.resetTimeout) {
                this.attempts = 0;
            }

            this.attempts++;
            this.lastAttemptTime = Date.now();

            switch (this.strategy) {
                case RECONNECT_STRATEGY.IMMEDIATE:
                    return 0;
                case RECONNECT_STRATEGY.LINEAR:
                    return Math.min(this.baseDelay * this.attempts, this.maxDelay);
                case RECONNECT_STRATEGY.EXPONENTIAL:
                    return Math.min(this.baseDelay * Math.pow(2, this.attempts - 1), this.maxDelay);
                case RECONNECT_STRATEGY.FIXED:
                    return this.baseDelay;
                default:
                    return this.baseDelay;
            }
        }

        // 开始重连
        async reconnect(connectFn) {
            if (this.isReconnecting) {
                return { success: false, reason: 'already_reconnecting' };
            }

            if (this.attempts >= this.maxAttempts) {
                this.trigger('onReconnectFailure', { 
                    reason: 'max_attempts_reached',
                    attempts: this.attempts 
                });
                return { success: false, reason: 'max_attempts_reached' };
            }

            this.isReconnecting = true;
            const delay = this.calculateDelay();

            this.trigger('onReconnectAttempt', {
                attempt: this.attempts,
                maxAttempts: this.maxAttempts,
                delay: delay
            });

            return new Promise((resolve) => {
                this.reconnectTimer = setTimeout(async () => {
                    try {
                        const result = await connectFn();
                        this.isReconnecting = false;
                        this.attempts = 0;
                        this.trigger('onReconnectSuccess', { attempt: this.attempts });
                        resolve({ success: true, result });
                    } catch (error) {
                        this.isReconnecting = false;
                        this.trigger('onReconnectFailure', { 
                            attempt: this.attempts,
                            error: error.message 
                        });
                        resolve({ success: false, error: error.message });
                    }
                }, delay);
            });
        }

        // 取消重连
        cancel() {
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
            this.isReconnecting = false;
        }

        // 重置
        reset() {
            this.cancel();
            this.attempts = 0;
            this.lastAttemptTime = null;
        }

        // 事件监听
        on(event, callback) {
            if (this.callbacks[event]) {
                this.callbacks[event].push(callback);
            }
            return this;
        }

        trigger(event, data) {
            if (this.callbacks[event]) {
                this.callbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error('[ReconnectionManager] 回调错误:', error);
                    }
                });
            }
        }

        // 获取状态
        getState() {
            return {
                isReconnecting: this.isReconnecting,
                attempts: this.attempts,
                maxAttempts: this.maxAttempts,
                strategy: this.strategy
            };
        }
    }

    /**
     * 状态恢复管理器
     */
    class StateRecoveryManager {
        constructor(options = {}) {
            this.persistence = window.persistenceManager;
            this.redis = window.redisStateManager;
            
            this.recoveryCallbacks = {
                onTaskRecovered: [],
                onRecoveryComplete: [],
                onRecoveryFailed: []
            };

            this.recoveredTasks = new Set();
            this.pendingSubscriptions = new Map();
        }

        // 恢复连接后的状态
        async recoverState(userId, wsClient) {
            console.log('[StateRecoveryManager] 开始恢复状态...');

            try {
                // 1. 获取未完成任务
                const incompleteTasks = await this.persistence.getIncompleteTasks(userId);
                console.log(`[StateRecoveryManager] 发现 ${incompleteTasks.length} 个未完成任务`);

                // 2. 恢复任务订阅
                for (const task of incompleteTasks) {
                    await this.recoverTask(task, wsClient);
                }

                // 3. 恢复用户级订阅
                await this.recoverUserSubscriptions(userId, wsClient);

                this.trigger('onRecoveryComplete', {
                    recoveredTasks: incompleteTasks.length,
                    taskIds: incompleteTasks.map(t => t.id)
                });

                return {
                    success: true,
                    recoveredTasks: incompleteTasks
                };

            } catch (error) {
                console.error('[StateRecoveryManager] 状态恢复失败:', error);
                this.trigger('onRecoveryFailed', { error: error.message });
                return {
                    success: false,
                    error: error.message
                };
            }
        }

        // 恢复单个任务
        async recoverTask(task, wsClient) {
            if (this.recoveredTasks.has(task.id)) {
                return;
            }

            console.log(`[StateRecoveryManager] 恢复任务: ${task.id}`);

            // 重新订阅任务更新
            wsClient.send({
                type: 'subscribe_task',
                payload: { taskId: task.id }
            });

            // 查询最新状态
            wsClient.send({
                type: 'query_task',
                payload: { taskId: task.id }
            });

            this.recoveredTasks.add(task.id);
            this.trigger('onTaskRecovered', { task });
        }

        // 恢复用户级订阅
        async recoverUserSubscriptions(userId, wsClient) {
            // 订阅用户任务列表更新
            wsClient.send({
                type: 'subscribe_user_tasks',
                payload: { userId }
            });

            // 订阅计费更新
            wsClient.send({
                type: 'subscribe_billing',
                payload: { userId }
            });
        }

        // 保存待恢复状态（断开前调用）
        saveStateForRecovery(userId, state) {
            const recoveryState = {
                userId,
                timestamp: Date.now(),
                activeTasks: state.activeTasks || [],
                subscriptions: state.subscriptions || [],
                clientState: state.clientState || {}
            };

            localStorage.setItem('kaelis_recovery_state', JSON.stringify(recoveryState));
        }

        // 加载恢复状态
        loadStateForRecovery() {
            const saved = localStorage.getItem('kaelis_recovery_state');
            if (!saved) return null;

            try {
                const state = JSON.parse(saved);
                
                // 检查状态是否过期（5分钟内有效）
                if (Date.now() - state.timestamp > 5 * 60 * 1000) {
                    localStorage.removeItem('kaelis_recovery_state');
                    return null;
                }

                return state;
            } catch (error) {
                return null;
            }
        }

        // 清除恢复状态
        clearRecoveryState() {
            localStorage.removeItem('kaelis_recovery_state');
            this.recoveredTasks.clear();
        }

        // 事件监听
        on(event, callback) {
            if (this.recoveryCallbacks[event]) {
                this.recoveryCallbacks[event].push(callback);
            }
            return this;
        }

        trigger(event, data) {
            if (this.recoveryCallbacks[event]) {
                this.recoveryCallbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error('[StateRecoveryManager] 回调错误:', error);
                    }
                });
            }
        }
    }

    /**
     * 增强版WebSocket客户端（带重连和恢复）
     */
    class ResilientWebSocketClient {
        constructor(options = {}) {
            this.url = options.url;
            this.userId = options.userId;
            this.role = options.role || 'control';
            
            this.ws = null;
            this.state = CONNECTION_STATE.DISCONNECTED;
            this.authenticated = false;

            this.reconnectionManager = new ReconnectionManager(options.reconnect);
            this.stateRecoveryManager = new StateRecoveryManager();
            this.persistence = window.persistenceManager;

            this.messageHandlers = new Map();
            this.eventCallbacks = {
                onConnect: [],
                onDisconnect: [],
                onAuthSuccess: [],
                onAuthFailure: [],
                onStateChange: [],
                onRecoveryStart: [],
                onRecoveryComplete: []
            };

            this.activeTasks = new Set();
            this.setupEventHandlers();
        }

        setupEventHandlers() {
            // 重连事件
            this.reconnectionManager
                .on('onReconnectAttempt', (data) => {
                    console.log(`[ResilientWebSocketClient] 重连尝试 ${data.attempt}/${data.maxAttempts}，延迟 ${data.delay}ms`);
                    this.setState(CONNECTION_STATE.CONNECTING);
                })
                .on('onReconnectSuccess', () => {
                    console.log('[ResilientWebSocketClient] 重连成功');
                })
                .on('onReconnectFailure', (data) => {
                    console.error('[ResilientWebSocketClient] 重连失败:', data.reason);
                    this.setState(CONNECTION_STATE.ERROR);
                });

            // 恢复事件
            this.stateRecoveryManager
                .on('onTaskRecovered', (data) => {
                    this.activeTasks.add(data.task.id);
                })
                .on('onRecoveryComplete', (data) => {
                    console.log(`[ResilientWebSocketClient] 状态恢复完成，恢复 ${data.recoveredTasks} 个任务`);
                    this.trigger('onRecoveryComplete', data);
                });
        }

        // 连接
        async connect() {
            if (this.state === CONNECTION_STATE.CONNECTED || 
                this.state === CONNECTION_STATE.CONNECTING) {
                return;
            }

            this.setState(CONNECTION_STATE.CONNECTING);

            try {
                // 使用认证客户端连接
                const authClient = new window.AuthenticatedWebSocketClient({
                    url: this.url,
                    role: this.role
                });

                authClient
                    .addEventListener('onOpen', () => {
                        this.setState(CONNECTION_STATE.AUTHENTICATING);
                    })
                    .addEventListener('onAuthSuccess', async (payload) => {
                        this.authenticated = true;
                        this.setState(CONNECTION_STATE.AUTHENTICATED);
                        this.reconnectionManager.reset();
                        
                        // 恢复状态
                        this.setState(CONNECTION_STATE.RECOVERING);
                        this.trigger('onRecoveryStart');
                        await this.stateRecoveryManager.recoverState(this.userId, authClient);
                        
                        this.setState(CONNECTION_STATE.CONNECTED);
                        this.trigger('onConnect', payload);
                    })
                    .addEventListener('onAuthFailure', (error) => {
                        this.setState(CONNECTION_STATE.ERROR);
                        this.trigger('onAuthFailure', error);
                    })
                    .addEventListener('onClose', (event) => {
                        this.handleDisconnect(event);
                    })
                    .addEventListener('onMessage', (event) => {
                        this.handleMessage(JSON.parse(event.data));
                    });

                this.ws = authClient;
                await authClient.connect();

            } catch (error) {
                this.handleDisconnect({ wasClean: false });
                throw error;
            }
        }

        // 处理断开
        handleDisconnect(event) {
            this.authenticated = false;
            this.setState(CONNECTION_STATE.DISCONNECTED);
            this.trigger('onDisconnect', event);

            // 保存状态以便恢复
            this.stateRecoveryManager.saveStateForRecovery(this.userId, {
                activeTasks: Array.from(this.activeTasks),
                subscriptions: [],
                clientState: {}
            });

            // 尝试重连
            if (!event.wasClean) {
                this.attemptReconnect();
            }
        }

        // 尝试重连
        async attemptReconnect() {
            const result = await this.reconnectionManager.reconnect(() => this.connect());
            
            if (!result.success && result.reason === 'max_attempts_reached') {
                this.trigger('onReconnectFailed');
            }
        }

        // 处理消息
        handleMessage(message) {
            // 更新任务状态
            if (message.type === 'task_update' && message.payload) {
                if (message.payload.status === 'completed' || message.payload.status === 'failed') {
                    this.activeTasks.delete(message.payload.id);
                } else {
                    this.activeTasks.add(message.payload.id);
                }
            }

            // 调用注册的处理器
            const handler = this.messageHandlers.get(message.type);
            if (handler) {
                handler(message);
            }
        }

        // 发送消息
        send(message) {
            if (this.ws && this.state === CONNECTION_STATE.CONNECTED) {
                this.ws.send(message);
            }
        }

        // 设置状态
        setState(newState) {
            const oldState = this.state;
            this.state = newState;
            
            if (oldState !== newState) {
                this.trigger('onStateChange', { from: oldState, to: newState });
            }
        }

        // 事件监听
        on(event, callback) {
            if (this.eventCallbacks[event]) {
                this.eventCallbacks[event].push(callback);
            }
            return this;
        }

        trigger(event, data) {
            if (this.eventCallbacks[event]) {
                this.eventCallbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error('[ResilientWebSocketClient] 回调错误:', error);
                    }
                });
            }
        }

        // 断开连接
        disconnect() {
            this.reconnectionManager.cancel();
            this.stateRecoveryManager.clearRecoveryState();
            
            if (this.ws) {
                this.ws.disconnect();
            }
        }

        // 获取状态
        getState() {
            return {
                connectionState: this.state,
                authenticated: this.authenticated,
                reconnectState: this.reconnectionManager.getState(),
                activeTasks: this.activeTasks.size
            };
        }
    }

    // 导出 - UMD格式
    const exports = {
        ReconnectionManager,
        StateRecoveryManager,
        ResilientWebSocketClient,
        CONNECTION_STATE,
        RECONNECT_STRATEGY
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.ReconnectionManager = exports;
        // 保持向后兼容
        window.ReconnectionManager = exports;
    }

    console.log('[ReconnectionManager] 断线重连管理器已加载');
})();
