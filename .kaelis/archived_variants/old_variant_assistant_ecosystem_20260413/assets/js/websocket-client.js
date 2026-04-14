/**
 * Kaelis WebSocket Client
 * 双向实时通信客户端 - 控制端/执行端通用
 * 架构: 控制端 ↔ 服务端 ↔ 执行端
 */

(function() {
    'use strict';

    // WebSocket 连接状态
    const WS_STATE = {
        CONNECTING: 0,
        OPEN: 1,
        CLOSING: 2,
        CLOSED: 3
    };

    // 消息类型定义
    const MESSAGE_TYPES = {
        // 控制端 -> 服务端 -> 执行端
        TASK_SUBMIT: 'task_submit',           // 提交任务
        TASK_CANCEL: 'task_cancel',           // 取消任务
        TASK_QUERY: 'task_query',             // 查询任务状态
        INSTANCE_COMMAND: 'instance_command', // 实例控制命令
        
        // 执行端 -> 服务端 -> 控制端
        TASK_STATUS: 'task_status',           // 任务状态更新
        TASK_PROGRESS: 'task_progress',       // 任务进度
        TASK_RESULT: 'task_result',           // 任务结果
        TASK_LOG: 'task_log',                 // 任务日志
        INSTANCE_HEARTBEAT: 'instance_heartbeat', // 实例心跳
        INSTANCE_METRICS: 'instance_metrics', // 实例指标
        
        // 服务端广播
        SYSTEM_NOTICE: 'system_notice',       // 系统通知
        BILLING_UPDATE: 'billing_update',     // 计费更新
        
        // 认证相关
        AUTH_REQUEST: 'auth_request',         // 认证请求
        AUTH_RESPONSE: 'auth_response',       // 认证响应
        
        // 心跳
        PING: 'ping',
        PONG: 'pong'
    };

    // 客户端角色
    const CLIENT_ROLES = {
        CONTROL: 'control',     // 控制端
        EXECUTOR: 'executor',   // 执行端
        SERVICE: 'service'      // 服务端（内部）
    };

    /**
     * WebSocket 客户端基类
     */
    class WebSocketClient {
        constructor(options = {}) {
            this.url = options.url || this.getWebSocketUrl();
            this.role = options.role || CLIENT_ROLES.CONTROL;
            this.clientId = options.clientId || this.generateClientId();
            this.token = options.token || null;
            
            this.ws = null;
            this.state = WS_STATE.CLOSED;
            this.reconnectAttempts = 0;
            this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
            this.reconnectInterval = options.reconnectInterval || 3000;
            
            this.messageHandlers = new Map();
            this.pendingMessages = [];
            this.heartbeatInterval = null;
            this.heartbeatIntervalTime = options.heartbeatInterval || 30000;
            
            this.eventCallbacks = {
                onOpen: [],
                onClose: [],
                onError: [],
                onMessage: [],
                onReconnect: []
            };
        }

        getWebSocketUrl() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            return `${protocol}//${window.location.host}/ws`;
        }

        generateClientId() {
            return `${this.role}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        }

        // 连接 WebSocket
        connect() {
            return new Promise((resolve, reject) => {
                try {
                    this.ws = new WebSocket(this.url);
                    this.state = WS_STATE.CONNECTING;

                    this.ws.onopen = (event) => {
                        this.state = WS_STATE.OPEN;
                        this.reconnectAttempts = 0;
                        this.triggerEvent('onOpen', event);
                        
                        // 发送认证请求
                        this.authenticate();
                        
                        // 启动心跳
                        this.startHeartbeat();
                        
                        // 发送待处理消息
                        this.flushPendingMessages();
                        
                        resolve(event);
                    };

                    this.ws.onmessage = (event) => {
                        this.handleMessage(event.data);
                        this.triggerEvent('onMessage', event);
                    };

                    this.ws.onclose = (event) => {
                        this.state = WS_STATE.CLOSED;
                        this.stopHeartbeat();
                        this.triggerEvent('onClose', event);
                        
                        // 自动重连
                        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
                            this.scheduleReconnect();
                        }
                    };

                    this.ws.onerror = (error) => {
                        this.triggerEvent('onError', error);
                        reject(error);
                    };

                } catch (error) {
                    reject(error);
                }
            });
        }

        // 认证
        authenticate() {
            this.send({
                type: MESSAGE_TYPES.AUTH_REQUEST,
                payload: {
                    clientId: this.clientId,
                    role: this.role,
                    token: this.token,
                    timestamp: Date.now()
                }
            });
        }

        // 发送消息
        send(message) {
            const data = typeof message === 'string' ? message : JSON.stringify(message);
            
            if (this.state === WS_STATE.OPEN) {
                this.ws.send(data);
            } else {
                this.pendingMessages.push(data);
            }
        }

        // 刷新待处理消息
        flushPendingMessages() {
            while (this.pendingMessages.length > 0 && this.state === WS_STATE.OPEN) {
                const message = this.pendingMessages.shift();
                this.ws.send(message);
            }
        }

        // 处理接收消息
        handleMessage(data) {
            try {
                const message = JSON.parse(data);
                
                // 处理心跳
                if (message.type === MESSAGE_TYPES.PING) {
                    this.send({ type: MESSAGE_TYPES.PONG, timestamp: Date.now() });
                    return;
                }
                
                if (message.type === MESSAGE_TYPES.PONG) {
                    this.lastPongTime = Date.now();
                    return;
                }

                // 调用注册的消息处理器
                const handler = this.messageHandlers.get(message.type);
                if (handler) {
                    handler(message);
                }

            } catch (error) {
                console.error('[WebSocketClient] 消息解析失败:', error);
            }
        }

        // 注册消息处理器
        on(messageType, handler) {
            this.messageHandlers.set(messageType, handler);
            return this;
        }

        // 取消注册
        off(messageType) {
            this.messageHandlers.delete(messageType);
            return this;
        }

        // 事件监听
        addEventListener(event, callback) {
            if (this.eventCallbacks[event]) {
                this.eventCallbacks[event].push(callback);
            }
            return this;
        }

        removeEventListener(event, callback) {
            if (this.eventCallbacks[event]) {
                const index = this.eventCallbacks[event].indexOf(callback);
                if (index > -1) {
                    this.eventCallbacks[event].splice(index, 1);
                }
            }
            return this;
        }

        triggerEvent(event, data) {
            if (this.eventCallbacks[event]) {
                this.eventCallbacks[event].forEach(callback => {
                    try {
                        callback(data);
                    } catch (error) {
                        console.error(`[WebSocketClient] 事件处理错误:`, error);
                    }
                });
            }
        }

        // 启动心跳
        startHeartbeat() {
            this.heartbeatInterval = setInterval(() => {
                if (this.state === WS_STATE.OPEN) {
                    this.send({
                        type: MESSAGE_TYPES.PING,
                        timestamp: Date.now()
                    });
                }
            }, this.heartbeatIntervalTime);
        }

        // 停止心跳
        stopHeartbeat() {
            if (this.heartbeatInterval) {
                clearInterval(this.heartbeatInterval);
                this.heartbeatInterval = null;
            }
        }

        // 计划重连
        scheduleReconnect() {
            this.reconnectAttempts++;
            const delay = Math.min(this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1), 30000);
            
            console.log(`[WebSocketClient] ${delay}ms后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.triggerEvent('onReconnect', { attempt: this.reconnectAttempts });
                this.connect();
            }, delay);
        }

        // 断开连接
        disconnect() {
            this.stopHeartbeat();
            if (this.ws) {
                this.ws.close(1000, 'Client disconnect');
            }
        }

        // 获取连接状态
        getState() {
            return {
                state: this.state,
                connected: this.state === WS_STATE.OPEN,
                clientId: this.clientId,
                role: this.role,
                pendingMessages: this.pendingMessages.length
            };
        }
    }

    /**
     * 控制端客户端
     */
    class ControlClient extends WebSocketClient {
        constructor(options = {}) {
            super({ ...options, role: CLIENT_ROLES.CONTROL });
            this.taskCallbacks = new Map();
        }

        // 提交任务到执行端
        submitTask(taskConfig) {
            const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            this.send({
                type: MESSAGE_TYPES.TASK_SUBMIT,
                payload: {
                    taskId,
                    ...taskConfig,
                    submittedAt: Date.now()
                }
            });

            return taskId;
        }

        // 取消任务
        cancelTask(taskId) {
            this.send({
                type: MESSAGE_TYPES.TASK_CANCEL,
                payload: { taskId, cancelledAt: Date.now() }
            });
        }

        // 查询任务状态
        queryTask(taskId) {
            this.send({
                type: MESSAGE_TYPES.TASK_QUERY,
                payload: { taskId, queriedAt: Date.now() }
            });
        }

        // 发送实例命令
        sendInstanceCommand(instanceId, command, params = {}) {
            this.send({
                type: MESSAGE_TYPES.INSTANCE_COMMAND,
                payload: {
                    instanceId,
                    command,
                    params,
                    sentAt: Date.now()
                }
            });
        }

        // 监听任务状态
        onTaskStatus(callback) {
            this.on(MESSAGE_TYPES.TASK_STATUS, (message) => {
                callback(message.payload);
            });
            return this;
        }

        // 监听任务进度
        onTaskProgress(callback) {
            this.on(MESSAGE_TYPES.TASK_PROGRESS, (message) => {
                callback(message.payload);
            });
            return this;
        }

        // 监听任务结果
        onTaskResult(callback) {
            this.on(MESSAGE_TYPES.TASK_RESULT, (message) => {
                callback(message.payload);
            });
            return this;
        }

        // 监听任务日志
        onTaskLog(callback) {
            this.on(MESSAGE_TYPES.TASK_LOG, (message) => {
                callback(message.payload);
            });
            return this;
        }

        // 监听实例指标
        onInstanceMetrics(callback) {
            this.on(MESSAGE_TYPES.INSTANCE_METRICS, (message) => {
                callback(message.payload);
            });
            return this;
        }

        // 监听计费更新
        onBillingUpdate(callback) {
            this.on(MESSAGE_TYPES.BILLING_UPDATE, (message) => {
                callback(message.payload);
            });
            return this;
        }
    }

    /**
     * 执行端客户端
     */
    class ExecutorClient extends WebSocketClient {
        constructor(options = {}) {
            super({ ...options, role: CLIENT_ROLES.EXECUTOR });
            this.instanceId = options.instanceId || this.generateClientId();
            this.capabilities = options.capabilities || [];
        }

        // 报告任务状态
        reportTaskStatus(taskId, status, details = {}) {
            this.send({
                type: MESSAGE_TYPES.TASK_STATUS,
                payload: {
                    taskId,
                    instanceId: this.instanceId,
                    status,
                    details,
                    reportedAt: Date.now()
                }
            });
        }

        // 报告任务进度
        reportTaskProgress(taskId, progress, message = '') {
            this.send({
                type: MESSAGE_TYPES.TASK_PROGRESS,
                payload: {
                    taskId,
                    instanceId: this.instanceId,
                    progress: Math.max(0, Math.min(100, progress)),
                    message,
                    reportedAt: Date.now()
                }
            });
        }

        // 报告任务结果
        reportTaskResult(taskId, result, success = true) {
            this.send({
                type: MESSAGE_TYPES.TASK_RESULT,
                payload: {
                    taskId,
                    instanceId: this.instanceId,
                    success,
                    result,
                    completedAt: Date.now()
                }
            });
        }

        // 发送任务日志
        sendTaskLog(taskId, level, message, metadata = {}) {
            this.send({
                type: MESSAGE_TYPES.TASK_LOG,
                payload: {
                    taskId,
                    instanceId: this.instanceId,
                    level, // info, warn, error, debug
                    message,
                    metadata,
                    timestamp: Date.now()
                }
            });
        }

        // 发送心跳
        sendHeartbeat() {
            this.send({
                type: MESSAGE_TYPES.INSTANCE_HEARTBEAT,
                payload: {
                    instanceId: this.instanceId,
                    timestamp: Date.now(),
                    capabilities: this.capabilities
                }
            });
        }

        // 发送实例指标
        sendMetrics(metrics) {
            this.send({
                type: MESSAGE_TYPES.INSTANCE_METRICS,
                payload: {
                    instanceId: this.instanceId,
                    metrics,
                    reportedAt: Date.now()
                }
            });
        }

        // 监听任务提交
        onTaskSubmit(callback) {
            this.on(MESSAGE_TYPES.TASK_SUBMIT, (message) => {
                callback(message.payload);
            });
            return this;
        }

        // 监听任务取消
        onTaskCancel(callback) {
            this.on(MESSAGE_TYPES.TASK_CANCEL, (message) => {
                callback(message.payload);
            });
            return this;
        }

        // 监听实例命令
        onInstanceCommand(callback) {
            this.on(MESSAGE_TYPES.INSTANCE_COMMAND, (message) => {
                callback(message.payload);
            });
            return this;
        }
    }

    // 导出 - UMD格式
    const exports = {
        WebSocketClient,
        ControlClient,
        ExecutorClient,
        MESSAGE_TYPES,
        CLIENT_ROLES,
        WS_STATE
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.WebSocketClient = exports;
        // 保持向后兼容
        window.WebSocketClient = WebSocketClient;
        window.ControlClient = ControlClient;
        window.ExecutorClient = ExecutorClient;
        window.WS_MESSAGE_TYPES = MESSAGE_TYPES;
        window.WS_CLIENT_ROLES = CLIENT_ROLES;
    }

    console.log('[WebSocketClient] WebSocket客户端已加载');
})();
