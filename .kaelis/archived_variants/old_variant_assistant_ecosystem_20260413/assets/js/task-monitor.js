/**
 * Kaelis Task Monitor
 * 任务流监控体系
 * 架构: WebSocket + Celery + Redis
 */

(function() {
    'use strict';

    // 任务状态
    const TASK_STATUS = {
        PENDING: 'pending',           // 等待中
        QUEUED: 'queued',             // 已入队
        RUNNING: 'running',           // 运行中
        PAUSED: 'paused',             // 已暂停
        RETRYING: 'retrying',         // 重试中
        SUCCESS: 'success',           // 成功
        FAILED: 'failed',             // 失败
        CANCELLED: 'cancelled',       // 已取消
        TIMEOUT: 'timeout'            // 超时
    };

    // 任务类型
    const TASK_TYPES = {
        COMPUTATION: 'computation',   // 计算任务
        DATA_PROCESS: 'data_process', // 数据处理
        MODEL_TRAIN: 'model_train',   // 模型训练
        API_CALL: 'api_call',         // API调用
        FILE_TRANSFER: 'file_transfer', // 文件传输
        CUSTOM: 'custom'              // 自定义
    };

    // 任务优先级
    const TASK_PRIORITY = {
        CRITICAL: 0,  // 紧急
        HIGH: 1,      // 高
        NORMAL: 2,    // 普通
        LOW: 3,       // 低
        BACKGROUND: 4 // 后台
    };

    /**
     * 任务定义
     */
    class Task {
        constructor(config) {
            this.id = config.id || `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            this.name = config.name || 'Unnamed Task';
            this.type = config.type || TASK_TYPES.CUSTOM;
            this.priority = config.priority ?? TASK_PRIORITY.NORMAL;
            
            this.status = TASK_STATUS.PENDING;
            this.progress = 0;
            this.result = null;
            this.error = null;
            
            this.createdAt = Date.now();
            this.startedAt = null;
            this.completedAt = null;
            this.estimatedDuration = config.estimatedDuration || null;
            
            this.config = config.config || {};
            this.metadata = config.metadata || {};
            
            this.instanceId = null;
            this.userId = config.userId || null;
            this.billingInfo = config.billingInfo || null;
            
            this.retryCount = 0;
            this.maxRetries = config.maxRetries || 3;
            
            this.logs = [];
            this.events = [];
        }

        // 更新状态
        updateStatus(newStatus, details = {}) {
            const oldStatus = this.status;
            this.status = newStatus;
            
            this.addEvent('status_change', {
                from: oldStatus,
                to: newStatus,
                ...details
            });

            if (newStatus === TASK_STATUS.RUNNING && !this.startedAt) {
                this.startedAt = Date.now();
            }

            if ([TASK_STATUS.SUCCESS, TASK_STATUS.FAILED, TASK_STATUS.CANCELLED, TASK_STATUS.TIMEOUT].includes(newStatus)) {
                this.completedAt = Date.now();
            }
        }

        // 更新进度
        updateProgress(progress, message = '') {
            this.progress = Math.max(0, Math.min(100, progress));
            this.addEvent('progress', { progress: this.progress, message });
        }

        // 添加日志
        addLog(level, message, metadata = {}) {
            this.logs.push({
                level,
                message,
                metadata,
                timestamp: Date.now()
            });
            
            // 限制日志数量
            if (this.logs.length > 1000) {
                this.logs.shift();
            }
        }

        // 添加事件
        addEvent(type, data = {}) {
            this.events.push({
                type,
                data,
                timestamp: Date.now()
            });
        }

        // 获取运行时长
        getDuration() {
            if (!this.startedAt) return 0;
            const endTime = this.completedAt || Date.now();
            return endTime - this.startedAt;
        }

        // 序列化
        toJSON() {
            return {
                id: this.id,
                name: this.name,
                type: this.type,
                priority: this.priority,
                status: this.status,
                progress: this.progress,
                createdAt: this.createdAt,
                startedAt: this.startedAt,
                completedAt: this.completedAt,
                duration: this.getDuration(),
                instanceId: this.instanceId,
                userId: this.userId,
                retryCount: this.retryCount,
                config: this.config
            };
        }
    }

    /**
     * 任务队列管理器
     */
    class TaskQueue {
        constructor() {
            this.queues = new Map();
            this.processing = new Map();
            this.completed = new Map();
            
            // 初始化各优先级队列
            Object.keys(TASK_PRIORITY).forEach(key => {
                this.queues.set(TASK_PRIORITY[key], []);
            });
        }

        // 添加任务
        enqueue(task) {
            const queue = this.queues.get(task.priority);
            if (queue) {
                queue.push(task);
                // 按创建时间排序
                queue.sort((a, b) => a.createdAt - b.createdAt);
            }
        }

        // 取出任务
        dequeue() {
            // 按优先级取任务
            const priorities = Object.values(TASK_PRIORITY).sort((a, b) => a - b);
            
            for (const priority of priorities) {
                const queue = this.queues.get(priority);
                if (queue && queue.length > 0) {
                    const task = queue.shift();
                    this.processing.set(task.id, task);
                    task.updateStatus(TASK_STATUS.RUNNING);
                    return task;
                }
            }
            
            return null;
        }

        // 获取队列统计
        getStats() {
            const stats = {
                pending: 0,
                processing: this.processing.size,
                completed: this.completed.size
            };

            for (const [priority, queue] of this.queues) {
                stats.pending += queue.length;
            }

            return stats;
        }

        // 获取任务
        getTask(taskId) {
            // 在队列中查找
            for (const queue of this.queues.values()) {
                const task = queue.find(t => t.id === taskId);
                if (task) return task;
            }
            
            // 在处理中查找
            if (this.processing.has(taskId)) {
                return this.processing.get(taskId);
            }
            
            // 在已完成中查找
            if (this.completed.has(taskId)) {
                return this.completed.get(taskId);
            }
            
            return null;
        }

        // 完成任务
        completeTask(taskId, result) {
            const task = this.processing.get(taskId);
            if (task) {
                task.result = result;
                task.updateStatus(TASK_STATUS.SUCCESS);
                this.processing.delete(taskId);
                this.completed.set(taskId, task);
            }
        }

        // 失败任务
        failTask(taskId, error) {
            const task = this.processing.get(taskId);
            if (task) {
                task.error = error;
                
                if (task.retryCount < task.maxRetries) {
                    task.retryCount++;
                    task.updateStatus(TASK_STATUS.RETRYING, { retryCount: task.retryCount });
                    this.enqueue(task);
                } else {
                    task.updateStatus(TASK_STATUS.FAILED);
                    this.processing.delete(taskId);
                    this.completed.set(taskId, task);
                }
            }
        }

        // 取消任务
        cancelTask(taskId) {
            // 从队列中移除
            for (const queue of this.queues.values()) {
                const index = queue.findIndex(t => t.id === taskId);
                if (index > -1) {
                    const task = queue.splice(index, 1)[0];
                    task.updateStatus(TASK_STATUS.CANCELLED);
                    this.completed.set(taskId, task);
                    return true;
                }
            }
            
            // 从处理中移除
            if (this.processing.has(taskId)) {
                const task = this.processing.get(taskId);
                task.updateStatus(TASK_STATUS.CANCELLED);
                this.processing.delete(taskId);
                this.completed.set(taskId, task);
                return true;
            }
            
            return false;
        }
    }

    /**
     * 任务流监控器
     */
    class TaskFlowMonitor {
        constructor() {
            this.taskQueue = new TaskQueue();
            this.workers = new Map();
            this.maxWorkers = 4;
            this.running = false;
            
            this.callbacks = {
                onTaskStart: [],
                onTaskProgress: [],
                onTaskComplete: [],
                onTaskFail: [],
                onTaskCancel: [],
                onQueueUpdate: []
            };
            
            this.metrics = {
                totalTasks: 0,
                successfulTasks: 0,
                failedTasks: 0,
                cancelledTasks: 0,
                averageDuration: 0
            };
        }

        // 启动监控器
        start() {
            this.running = true;
            this.scheduleProcess();
            console.log('[TaskFlowMonitor] 任务流监控器已启动');
        }

        // 停止监控器
        stop() {
            this.running = false;
            console.log('[TaskFlowMonitor] 任务流监控器已停止');
        }

        // 提交任务
        submitTask(config) {
            const task = new Task(config);
            task.updateStatus(TASK_STATUS.QUEUED);
            this.taskQueue.enqueue(task);
            this.metrics.totalTasks++;
            
            this.triggerCallback('onQueueUpdate', this.taskQueue.getStats());
            
            return task;
        }

        // 取消任务
        cancelTask(taskId) {
            const result = this.taskQueue.cancelTask(taskId);
            if (result) {
                this.metrics.cancelledTasks++;
                this.triggerCallback('onTaskCancel', { taskId });
                this.triggerCallback('onQueueUpdate', this.taskQueue.getStats());
            }
            return result;
        }

        // 获取任务状态
        getTaskStatus(taskId) {
            const task = this.taskQueue.getTask(taskId);
            return task ? task.toJSON() : null;
        }

        // 获取所有任务
        getAllTasks(filters = {}) {
            const tasks = [];
            
            // 收集所有任务
            for (const queue of this.taskQueue.queues.values()) {
                tasks.push(...queue);
            }
            
            for (const task of this.taskQueue.processing.values()) {
                tasks.push(task);
            }
            
            for (const task of this.taskQueue.completed.values()) {
                tasks.push(task);
            }
            
            // 应用过滤
            return tasks.filter(task => {
                if (filters.status && task.status !== filters.status) return false;
                if (filters.type && task.type !== filters.type) return false;
                if (filters.userId && task.userId !== filters.userId) return false;
                return true;
            }).map(t => t.toJSON());
        }

        // 调度处理
        scheduleProcess() {
            if (!this.running) return;
            
            // 检查是否有可用工作槽
            if (this.workers.size < this.maxWorkers) {
                const task = this.taskQueue.dequeue();
                if (task) {
                    this.processTask(task);
                }
            }
            
            // 继续调度
            setTimeout(() => this.scheduleProcess(), 100);
        }

        // 处理任务
        async processTask(task) {
            this.workers.set(task.id, task);
            this.triggerCallback('onTaskStart', task.toJSON());
            
            try {
                // 模拟任务执行
                await this.executeTask(task);
                
                this.taskQueue.completeTask(task.id, task.result);
                this.metrics.successfulTasks++;
                this.updateAverageDuration(task.getDuration());
                this.triggerCallback('onTaskComplete', task.toJSON());
                
            } catch (error) {
                this.taskQueue.failTask(task.id, error.message);
                this.metrics.failedTasks++;
                this.triggerCallback('onTaskFail', { taskId: task.id, error: error.message });
            } finally {
                this.workers.delete(task.id);
                this.triggerCallback('onQueueUpdate', this.taskQueue.getStats());
            }
        }

        // 执行任务
        async executeTask(task) {
            // 这里应该调用实际的执行逻辑
            // 目前使用模拟实现
            return new Promise((resolve, reject) => {
                const steps = 10;
                let currentStep = 0;
                
                const interval = setInterval(() => {
                    currentStep++;
                    const progress = (currentStep / steps) * 100;
                    task.updateProgress(progress, `Step ${currentStep}/${steps}`);
                    task.addLog('info', `Executing step ${currentStep}`);
                    this.triggerCallback('onTaskProgress', task.toJSON());
                    
                    if (currentStep >= steps) {
                        clearInterval(interval);
                        task.result = { message: 'Task completed successfully' };
                        resolve();
                    }
                }, 500);
            });
        }

        // 更新平均时长
        updateAverageDuration(duration) {
            const total = this.metrics.successfulTasks + this.metrics.failedTasks;
            this.metrics.averageDuration = 
                (this.metrics.averageDuration * (total - 1) + duration) / total;
        }

        // 获取统计
        getMetrics() {
            return {
                ...this.metrics,
                queueStats: this.taskQueue.getStats(),
                activeWorkers: this.workers.size
            };
        }

        // 事件监听
        on(event, callback) {
            if (this.callbacks[event]) {
                this.callbacks[event].push(callback);
            }
            return this;
        }

        // 触发回调
        triggerCallback(event, data) {
            if (this.callbacks[event]) {
                this.callbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error(`[TaskFlowMonitor] 回调错误:`, error);
                    }
                });
            }
        }
    }

    /**
     * 任务监控面板 UI
     */
    class TaskMonitorPanel {
        constructor(containerId, taskMonitor) {
            this.container = document.getElementById(containerId);
            this.taskMonitor = taskMonitor;
            this.tasks = new Map();
            
            this.init();
        }

        init() {
            this.render();
            this.bindEvents();
        }

        render() {
            if (!this.container) return;
            
            this.container.innerHTML = `
                <div class="task-monitor-panel">
                    <div class="panel-header">
                        <h3>任务流监控</h3>
                        <div class="stats">
                            <span class="stat pending">等待: <span id="pending-count">0</span></span>
                            <span class="stat running">运行: <span id="running-count">0</span></span>
                            <span class="stat completed">完成: <span id="completed-count">0</span></span>
                        </div>
                    </div>
                    <div class="panel-body">
                        <div class="task-list" id="task-list"></div>
                    </div>
                </div>
            `;
        }

        bindEvents() {
            this.taskMonitor
                .on('onTaskStart', (task) => this.updateTask(task))
                .on('onTaskProgress', (task) => this.updateTask(task))
                .on('onTaskComplete', (task) => this.updateTask(task))
                .on('onTaskFail', ({ taskId }) => this.markTaskFailed(taskId))
                .on('onQueueUpdate', (stats) => this.updateStats(stats));
        }

        updateTask(task) {
            this.tasks.set(task.id, task);
            this.renderTaskList();
        }

        markTaskFailed(taskId) {
            const task = this.tasks.get(taskId);
            if (task) {
                task.status = TASK_STATUS.FAILED;
                this.renderTaskList();
            }
        }

        updateStats(stats) {
            const pendingEl = document.getElementById('pending-count');
            const runningEl = document.getElementById('running-count');
            const completedEl = document.getElementById('completed-count');
            
            if (pendingEl) pendingEl.textContent = stats.pending;
            if (runningEl) runningEl.textContent = stats.processing;
            if (completedEl) completedEl.textContent = stats.completed;
        }

        renderTaskList() {
            const listEl = document.getElementById('task-list');
            if (!listEl) return;
            
            const sortedTasks = Array.from(this.tasks.values())
                .sort((a, b) => b.createdAt - a.createdAt)
                .slice(0, 50); // 只显示最近50个
            
            listEl.innerHTML = sortedTasks.map(task => `
                <div class="task-item ${task.status}" data-task-id="${task.id}">
                    <div class="task-info">
                        <span class="task-name">${task.name}</span>
                        <span class="task-type">${task.type}</span>
                    </div>
                    <div class="task-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${task.progress}%"></div>
                        </div>
                        <span class="progress-text">${task.progress.toFixed(1)}%</span>
                    </div>
                    <div class="task-status">
                        <span class="status-badge ${task.status}">${task.status}</span>
                    </div>
                </div>
            `).join('');
        }
    }

    // 导出 - UMD格式
    const exports = {
        Task,
        TaskQueue,
        TaskFlowMonitor,
        TaskMonitorPanel,
        TASK_STATUS,
        TASK_TYPES,
        TASK_PRIORITY
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.TaskMonitor = exports;
        // 保持向后兼容
        window.TaskMonitor = exports;
        window.taskFlowMonitor = new TaskFlowMonitor();
    }

    console.log('[TaskMonitor] 任务流监控体系已加载');
})();
