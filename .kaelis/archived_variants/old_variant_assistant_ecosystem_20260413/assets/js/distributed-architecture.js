/**
 * Kaelis Distributed Architecture
 * 控制端-服务端-执行端 分布式架构
 * WebSocket + Celery + Redis 实现
 */

(function() {
    'use strict';

    // 节点类型
    const NODE_TYPES = {
        CONTROL: 'control',     // 控制端 - 用户交互界面
        SERVICE: 'service',     // 服务端 - 调度中心
        EXECUTOR: 'executor'    // 执行端 - 任务执行
    };

    // 消息路由
    const MESSAGE_ROUTES = {
        CONTROL_TO_SERVICE: 'c2s',
        SERVICE_TO_CONTROL: 's2c',
        SERVICE_TO_EXECUTOR: 's2e',
        EXECUTOR_TO_SERVICE: 'e2s',
        BROADCAST: 'broadcast'
    };

    /**
     * 控制端节点
     * 负责：用户交互、任务提交、状态监控
     */
    class ControlNode {
        constructor(config) {
            this.id = config.id || `control_${Date.now()}`;
            this.type = NODE_TYPES.CONTROL;
            this.serviceUrl = config.serviceUrl;
            this.userId = config.userId;
            
            this.ws = null;
            this.connected = false;
            this.subscriptions = new Map();
            
            this.callbacks = {
                onConnect: [],
                onDisconnect: [],
                onTaskUpdate: [],
                onInstanceUpdate: [],
                onBillingUpdate: []
            };
        }

        // 连接到服务端
        async connect() {
            return new Promise((resolve, reject) => {
                try {
                    this.ws = new WebSocket(`${this.serviceUrl}/ws/control`);
                    
                    this.ws.onopen = () => {
                        this.connected = true;
                        // 发送认证信息
                        this.send({
                            type: 'auth',
                            nodeType: this.type,
                            nodeId: this.id,
                            userId: this.userId
                        });
                        this.trigger('onConnect');
                        resolve();
                    };

                    this.ws.onmessage = (event) => {
                        this.handleMessage(JSON.parse(event.data));
                    };

                    this.ws.onclose = () => {
                        this.connected = false;
                        this.trigger('onDisconnect');
                    };

                    this.ws.onerror = (error) => {
                        reject(error);
                    };

                } catch (error) {
                    reject(error);
                }
            });
        }

        // 发送消息
        send(message) {
            if (this.connected && this.ws) {
                this.ws.send(JSON.stringify(message));
            }
        }

        // 处理消息
        handleMessage(message) {
            switch (message.type) {
                case 'task_update':
                    this.trigger('onTaskUpdate', message.payload);
                    break;
                case 'instance_update':
                    this.trigger('onInstanceUpdate', message.payload);
                    break;
                case 'billing_update':
                    this.trigger('onBillingUpdate', message.payload);
                    break;
                default:
                    const callback = this.subscriptions.get(message.type);
                    if (callback) callback(message);
            }
        }

        // 提交任务
        submitTask(taskConfig) {
            const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            this.send({
                route: MESSAGE_ROUTES.CONTROL_TO_SERVICE,
                type: 'submit_task',
                payload: {
                    taskId,
                    userId: this.userId,
                    config: taskConfig,
                    submittedAt: Date.now()
                }
            });

            return taskId;
        }

        // 取消任务
        cancelTask(taskId) {
            this.send({
                route: MESSAGE_ROUTES.CONTROL_TO_SERVICE,
                type: 'cancel_task',
                payload: { taskId, userId: this.userId }
            });
        }

        // 查询任务状态
        queryTask(taskId) {
            this.send({
                route: MESSAGE_ROUTES.CONTROL_TO_SERVICE,
                type: 'query_task',
                payload: { taskId, userId: this.userId }
            });
        }

        // 获取可用实例
        getAvailableInstances() {
            this.send({
                route: MESSAGE_ROUTES.CONTROL_TO_SERVICE,
                type: 'get_instances',
                payload: { userId: this.userId }
            });
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
                this.callbacks[event].forEach(cb => cb(data));
            }
        }

        disconnect() {
            if (this.ws) {
                this.ws.close();
            }
        }
    }

    /**
     * 服务端节点（调度中心）
     * 负责：任务调度、状态管理、消息路由
     */
    class ServiceNode {
        constructor(config) {
            this.id = config.id || `service_${Date.now()}`;
            this.type = NODE_TYPES.SERVICE;
            this.port = config.port || 8080;
            
            this.controlNodes = new Map();
            this.executorNodes = new Map();
            this.taskQueue = [];
            this.taskStates = new Map();
            
            this.redis = window.redisStateManager;
            this.billing = window.billingManager;
        }

        // 初始化
        init() {
            // 启动任务调度器
            this.startScheduler();
            
            // 启动状态同步
            this.startStateSync();
            
            console.log(`[ServiceNode] 服务端节点 ${this.id} 已启动`);
        }

        // 注册控制端
        registerControl(nodeId, connection) {
            this.controlNodes.set(nodeId, {
                id: nodeId,
                connection,
                registeredAt: Date.now()
            });
            console.log(`[ServiceNode] 控制端已注册: ${nodeId}`);
        }

        // 注册执行端
        registerExecutor(nodeId, connection, capabilities) {
            this.executorNodes.set(nodeId, {
                id: nodeId,
                connection,
                capabilities,
                status: 'available',
                currentTask: null,
                registeredAt: Date.now()
            });
            
            // 注册到Redis
            this.redis.registerInstance(nodeId, {
                capabilities,
                status: 'available'
            });
            
            console.log(`[ServiceNode] 执行端已注册: ${nodeId}`);
        }

        // 处理控制端消息
        handleControlMessage(nodeId, message) {
            switch (message.type) {
                case 'submit_task':
                    this.handleTaskSubmit(message.payload);
                    break;
                case 'cancel_task':
                    this.handleTaskCancel(message.payload);
                    break;
                case 'query_task':
                    this.handleTaskQuery(nodeId, message.payload);
                    break;
                case 'get_instances':
                    this.handleGetInstances(nodeId);
                    break;
            }
        }

        // 处理执行端消息
        handleExecutorMessage(nodeId, message) {
            switch (message.type) {
                case 'task_status':
                    this.handleTaskStatusUpdate(nodeId, message.payload);
                    break;
                case 'task_progress':
                    this.handleTaskProgress(nodeId, message.payload);
                    break;
                case 'task_result':
                    this.handleTaskResult(nodeId, message.payload);
                    break;
                case 'heartbeat':
                    this.handleExecutorHeartbeat(nodeId, message.payload);
                    break;
            }
        }

        // 处理任务提交
        handleTaskSubmit(payload) {
            const { taskId, userId, config } = payload;
            
            // 检查用户配额
            const account = this.billing.getAccount(userId);
            if (account) {
                const check = account.checkResourceLimit(config.resourceType);
                if (!check.allowed) {
                    this.notifyControl(userId, 'task_rejected', {
                        taskId,
                        reason: 'Resource quota exceeded'
                    });
                    return;
                }
            }

            // 创建任务状态
            const taskState = {
                taskId,
                userId,
                config,
                status: 'pending',
                progress: 0,
                assignedExecutor: null,
                createdAt: Date.now(),
                startedAt: null,
                completedAt: null
            };

            this.taskStates.set(taskId, taskState);
            this.redis.saveTaskState(taskId, taskState);
            
            // 加入任务队列
            this.taskQueue.push(taskState);
            
            // 通知控制端
            this.notifyControl(userId, 'task_accepted', { taskId, status: 'pending' });
        }

        // 处理任务取消
        handleTaskCancel(payload) {
            const { taskId } = payload;
            const task = this.taskStates.get(taskId);
            
            if (task) {
                task.status = 'cancelled';
                
                // 如果已分配给执行端，通知执行端取消
                if (task.assignedExecutor) {
                    this.notifyExecutor(task.assignedExecutor, 'cancel_task', { taskId });
                }
                
                this.redis.saveTaskState(taskId, task);
                this.notifyControl(task.userId, 'task_cancelled', { taskId });
            }
        }

        // 处理任务查询
        handleTaskQuery(nodeId, payload) {
            const { taskId } = payload;
            const task = this.taskStates.get(taskId) || this.redis.getTaskState(taskId);
            
            if (task) {
                this.sendToControl(nodeId, 'task_info', task);
            }
        }

        // 处理任务状态更新
        handleTaskStatusUpdate(executorId, payload) {
            const { taskId, status } = payload;
            const task = this.taskStates.get(taskId);
            
            if (task) {
                task.status = status;
                this.redis.saveTaskState(taskId, task);
                this.notifyControl(task.userId, 'task_update', task);
            }
        }

        // 处理任务进度
        handleTaskProgress(executorId, payload) {
            const { taskId, progress } = payload;
            const task = this.taskStates.get(taskId);
            
            if (task) {
                task.progress = progress;
                this.redis.updateTaskProgress(taskId, progress);
                this.notifyControl(task.userId, 'task_progress', { taskId, progress });
            }
        }

        // 处理任务结果
        handleTaskResult(executorId, payload) {
            const { taskId, result, success } = payload;
            const task = this.taskStates.get(taskId);
            
            if (task) {
                task.status = success ? 'completed' : 'failed';
                task.result = result;
                task.completedAt = Date.now();
                
                // 释放执行端
                const executor = this.executorNodes.get(executorId);
                if (executor) {
                    executor.status = 'available';
                    executor.currentTask = null;
                }
                
                // 记录计费
                if (success && this.billing) {
                    this.billing.processUsage(task.userId, task.config.resourceType, 1, {
                        taskId,
                        duration: task.completedAt - task.startedAt
                    });
                }
                
                this.redis.saveTaskState(taskId, task);
                this.notifyControl(task.userId, 'task_result', task);
            }
        }

        // 处理执行端心跳
        handleExecutorHeartbeat(executorId, payload) {
            this.redis.updateInstanceHeartbeat(executorId);
        }

        // 启动任务调度器
        startScheduler() {
            setInterval(() => {
                this.scheduleTasks();
            }, 1000);
        }

        // 任务调度
        scheduleTasks() {
            // 获取可用执行端
            const availableExecutors = Array.from(this.executorNodes.values())
                .filter(e => e.status === 'available');

            if (availableExecutors.length === 0) return;

            // 分配任务
            while (this.taskQueue.length > 0 && availableExecutors.length > 0) {
                const task = this.taskQueue.shift();
                
                if (task.status === 'cancelled') continue;

                // 选择执行端（简单轮询）
                const executor = availableExecutors.shift();
                
                task.status = 'running';
                task.assignedExecutor = executor.id;
                task.startedAt = Date.now();
                
                executor.status = 'busy';
                executor.currentTask = task.taskId;
                
                // 通知执行端
                this.notifyExecutor(executor.id, 'execute_task', {
                    taskId: task.taskId,
                    config: task.config
                });
                
                this.redis.saveTaskState(task.taskId, task);
                this.notifyControl(task.userId, 'task_started', task);
            }
        }

        // 启动状态同步
        startStateSync() {
            setInterval(() => {
                // 同步任务状态到Redis
                for (const [taskId, task] of this.taskStates) {
                    this.redis.saveTaskState(taskId, task);
                }
            }, 5000);
        }

        // 通知控制端
        notifyControl(userId, type, payload) {
            // 找到用户的控制端连接
            for (const [nodeId, node] of this.controlNodes) {
                // 这里应该根据userId找到对应的控制端
                // 简化实现：广播给所有控制端
                this.sendToControl(nodeId, type, payload);
            }
        }

        // 通知执行端
        notifyExecutor(executorId, type, payload) {
            const executor = this.executorNodes.get(executorId);
            if (executor && executor.connection) {
                executor.connection.send(JSON.stringify({ type, payload }));
            }
        }

        // 发送消息到控制端
        sendToControl(nodeId, type, payload) {
            const control = this.controlNodes.get(nodeId);
            if (control && control.connection) {
                control.connection.send(JSON.stringify({ type, payload }));
            }
        }

        // 获取可用实例列表
        handleGetInstances(nodeId) {
            const instances = this.redis.getActiveInstances();
            this.sendToControl(nodeId, 'instance_list', instances);
        }
    }

    /**
     * 执行端节点
     * 负责：任务执行、资源管理、状态上报
     */
    class ExecutorNode {
        constructor(config) {
            this.id = config.id || `executor_${Date.now()}`;
            this.type = NODE_TYPES.EXECUTOR;
            this.serviceUrl = config.serviceUrl;
            this.capabilities = config.capabilities || [];
            
            this.ws = null;
            this.connected = false;
            this.currentTask = null;
            this.taskHandlers = new Map();
        }

        // 连接到服务端
        async connect() {
            return new Promise((resolve, reject) => {
                try {
                    this.ws = new WebSocket(`${this.serviceUrl}/ws/executor`);
                    
                    this.ws.onopen = () => {
                        this.connected = true;
                        // 发送注册信息
                        this.send({
                            type: 'register',
                            nodeType: this.type,
                            nodeId: this.id,
                            capabilities: this.capabilities
                        });
                        
                        // 启动心跳
                        this.startHeartbeat();
                        resolve();
                    };

                    this.ws.onmessage = (event) => {
                        this.handleMessage(JSON.parse(event.data));
                    };

                    this.ws.onclose = () => {
                        this.connected = false;
                        this.stopHeartbeat();
                    };

                    this.ws.onerror = reject;

                } catch (error) {
                    reject(error);
                }
            });
        }

        // 发送消息
        send(message) {
            if (this.connected && this.ws) {
                this.ws.send(JSON.stringify(message));
            }
        }

        // 处理消息
        handleMessage(message) {
            switch (message.type) {
                case 'execute_task':
                    this.executeTask(message.payload);
                    break;
                case 'cancel_task':
                    this.cancelTask(message.payload);
                    break;
            }
        }

        // 执行任务
        async executeTask(payload) {
            const { taskId, config } = payload;
            this.currentTask = taskId;

            // 上报任务开始
            this.send({
                route: MESSAGE_ROUTES.EXECUTOR_TO_SERVICE,
                type: 'task_status',
                payload: { taskId, status: 'running' }
            });

            try {
                // 获取任务处理器
                const handler = this.taskHandlers.get(config.type);
                
                if (handler) {
                    const result = await handler(config, {
                        onProgress: (progress) => {
                            this.send({
                                route: MESSAGE_ROUTES.EXECUTOR_TO_SERVICE,
                                type: 'task_progress',
                                payload: { taskId, progress }
                            });
                        }
                    });

                    // 上报成功
                    this.send({
                        route: MESSAGE_ROUTES.EXECUTOR_TO_SERVICE,
                        type: 'task_result',
                        payload: { taskId, result, success: true }
                    });
                } else {
                    throw new Error(`Unknown task type: ${config.type}`);
                }

            } catch (error) {
                // 上报失败
                this.send({
                    route: MESSAGE_ROUTES.EXECUTOR_TO_SERVICE,
                    type: 'task_result',
                    payload: { taskId, result: error.message, success: false }
                });
            } finally {
                this.currentTask = null;
            }
        }

        // 取消任务
        cancelTask(payload) {
            const { taskId } = payload;
            if (this.currentTask === taskId) {
                // 中断任务执行
                // 实际实现需要更复杂的取消机制
                this.currentTask = null;
            }
        }

        // 注册任务处理器
        registerTaskHandler(taskType, handler) {
            this.taskHandlers.set(taskType, handler);
        }

        // 启动心跳
        startHeartbeat() {
            this.heartbeatInterval = setInterval(() => {
                this.send({
                    route: MESSAGE_ROUTES.EXECUTOR_TO_SERVICE,
                    type: 'heartbeat',
                    payload: {
                        nodeId: this.id,
                        timestamp: Date.now(),
                        status: this.currentTask ? 'busy' : 'available',
                        currentTask: this.currentTask
                    }
                });
            }, 30000);
        }

        // 停止心跳
        stopHeartbeat() {
            if (this.heartbeatInterval) {
                clearInterval(this.heartbeatInterval);
            }
        }

        disconnect() {
            this.stopHeartbeat();
            if (this.ws) {
                this.ws.close();
            }
        }
    }

    /**
     * 架构管理器
     */
    class DistributedArchitecture {
        constructor() {
            this.nodes = new Map();
            this.serviceNode = null;
        }

        // 创建控制端
        createControlNode(config) {
            const node = new ControlNode(config);
            this.nodes.set(node.id, node);
            return node;
        }

        // 创建服务端
        createServiceNode(config) {
            this.serviceNode = new ServiceNode(config);
            this.serviceNode.init();
            return this.serviceNode;
        }

        // 创建执行端
        createExecutorNode(config) {
            const node = new ExecutorNode(config);
            this.nodes.set(node.id, node);
            return node;
        }

        // 获取节点
        getNode(nodeId) {
            return this.nodes.get(nodeId);
        }

        // 获取所有节点
        getAllNodes() {
            return Array.from(this.nodes.values());
        }

        // 获取架构状态
        getStatus() {
            return {
                controlNodes: Array.from(this.nodes.values()).filter(n => n.type === NODE_TYPES.CONTROL).length,
                executorNodes: Array.from(this.nodes.values()).filter(n => n.type === NODE_TYPES.EXECUTOR).length,
                serviceNode: this.serviceNode ? 'running' : 'stopped'
            };
        }
    }

    // 导出 - UMD格式
    const exports = {
        ControlNode,
        ServiceNode,
        ExecutorNode,
        DistributedArchitecture,
        NODE_TYPES,
        MESSAGE_ROUTES
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.DistributedArchitecture = exports;
        // 保持向后兼容
        window.DistributedArchitecture = exports;
        window.distributedArchitecture = new DistributedArchitecture();
    }

    console.log('[DistributedArchitecture] 分布式架构已加载');
})();
