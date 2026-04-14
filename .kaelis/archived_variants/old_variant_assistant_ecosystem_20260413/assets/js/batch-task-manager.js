/**
 * Kaelis Batch Task Manager
 * 批量任务管理 - 支持并行/串行执行
 */

(function() {
    'use strict';

    // 批量执行模式
    const BATCH_MODE = {
        PARALLEL: 'parallel',     // 并行执行
        SEQUENTIAL: 'sequential', // 串行执行
        PIPELINE: 'pipeline'      // 流水线
    };

    // 批量任务状态
    const BATCH_STATUS = {
        PENDING: 'pending',
        RUNNING: 'running',
        PAUSED: 'paused',
        COMPLETED: 'completed',
        PARTIAL: 'partial',       // 部分完成
        FAILED: 'failed',
        CANCELLED: 'cancelled'
    };

    // 任务依赖关系
    const DEPENDENCY_TYPE = {
        ALL: 'all',           // 所有前置任务完成
        ANY: 'any',           // 任一前置任务完成
        SUCCESS: 'success',   // 前置任务成功
        FAILURE: 'failure'    // 前置任务失败
    };

    /**
     * 批量任务定义
     */
    class BatchTask {
        constructor(config) {
            this.id = config.id || `batch_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            this.name = config.name || 'Unnamed Batch';
            this.userId = config.userId;
            
            this.mode = config.mode || BATCH_MODE.PARALLEL;
            this.maxConcurrency = config.maxConcurrency || 5; // 最大并行数
            
            this.tasks = new Map();           // 所有任务
            this.taskOrder = [];              // 任务执行顺序
            this.dependencies = new Map();    // 任务依赖关系
            
            this.status = BATCH_STATUS.PENDING;
            this.progress = 0;
            
            this.results = new Map();
            this.errors = new Map();
            
            this.createdAt = Date.now();
            this.startedAt = null;
            this.completedAt = null;
            
            this.metadata = config.metadata || {};
            this.billingInfo = config.billingInfo || null;
        }

        // 添加任务
        addTask(taskConfig, options = {}) {
            const taskId = taskConfig.id || `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            const task = {
                id: taskId,
                name: taskConfig.name || `Task ${this.tasks.size + 1}`,
                config: taskConfig,
                status: 'pending',
                progress: 0,
                dependencies: options.dependencies || [],
                dependType: options.dependType || DEPENDENCY_TYPE.ALL,
                priority: options.priority || 0,
                createdAt: Date.now()
            };

            this.tasks.set(taskId, task);
            this.dependencies.set(taskId, task.dependencies);
            
            return taskId;
        }

        // 设置任务依赖
        setDependency(taskId, dependencies, dependType = DEPENDENCY_TYPE.ALL) {
            const task = this.tasks.get(taskId);
            if (task) {
                task.dependencies = dependencies;
                task.dependType = dependType;
                this.dependencies.set(taskId, dependencies);
            }
        }

        // 计算执行顺序
        computeExecutionOrder() {
            const visited = new Set();
            const visiting = new Set();
            const order = [];

            const visit = (taskId) => {
                if (visiting.has(taskId)) {
                    throw new Error(`Circular dependency detected at task: ${taskId}`);
                }
                if (visited.has(taskId)) return;

                visiting.add(taskId);
                
                const deps = this.dependencies.get(taskId) || [];
                for (const depId of deps) {
                    if (this.tasks.has(depId)) {
                        visit(depId);
                    }
                }

                visiting.delete(taskId);
                visited.add(taskId);
                order.push(taskId);
            };

            for (const taskId of this.tasks.keys()) {
                visit(taskId);
            }

            this.taskOrder = order;
            return order;
        }

        // 检查任务是否可以执行
        canExecute(taskId) {
            const task = this.tasks.get(taskId);
            if (!task) return false;
            if (task.status !== 'pending') return false;

            const deps = this.dependencies.get(taskId) || [];
            if (deps.length === 0) return true;

            const depStatuses = deps.map(depId => {
                const dep = this.tasks.get(depId);
                return dep ? dep.status : 'unknown';
            });

            switch (task.dependType) {
                case DEPENDENCY_TYPE.ALL:
                    return depStatuses.every(s => s === 'completed');
                case DEPENDENCY_TYPE.ANY:
                    return depStatuses.some(s => s === 'completed');
                case DEPENDENCY_TYPE.SUCCESS:
                    return depStatuses.every(s => s === 'completed');
                case DEPENDENCY_TYPE.FAILURE:
                    return depStatuses.some(s => s === 'failed');
                default:
                    return false;
            }
        }

        // 获取可执行任务
        getExecutableTasks() {
            return Array.from(this.tasks.values())
                .filter(t => this.canExecute(t.id));
        }

        // 更新任务状态
        updateTaskStatus(taskId, status, result = null, error = null) {
            const task = this.tasks.get(taskId);
            if (!task) return;

            task.status = status;
            
            if (status === 'completed') {
                task.completedAt = Date.now();
                if (result) this.results.set(taskId, result);
            } else if (status === 'failed') {
                task.failedAt = Date.now();
                if (error) this.errors.set(taskId, error);
            }

            this.updateOverallProgress();
        }

        // 更新整体进度
        updateOverallProgress() {
            const total = this.tasks.size;
            if (total === 0) {
                this.progress = 0;
                return;
            }

            let completedProgress = 0;
            for (const task of this.tasks.values()) {
                if (task.status === 'completed') {
                    completedProgress += 100;
                } else if (task.status === 'running') {
                    completedProgress += task.progress;
                }
            }

            this.progress = Math.round(completedProgress / total);

            // 更新批量任务状态
            const completed = Array.from(this.tasks.values()).filter(t => t.status === 'completed').length;
            const failed = Array.from(this.tasks.values()).filter(t => t.status === 'failed').length;
            const running = Array.from(this.tasks.values()).filter(t => t.status === 'running').length;

            if (running > 0) {
                this.status = BATCH_STATUS.RUNNING;
            } else if (completed === total) {
                this.status = BATCH_STATUS.COMPLETED;
                this.completedAt = Date.now();
            } else if (completed + failed === total) {
                this.status = failed === total ? BATCH_STATUS.FAILED : BATCH_STATUS.PARTIAL;
                this.completedAt = Date.now();
            }
        }

        // 获取统计
        getStats() {
            const statuses = Array.from(this.tasks.values()).map(t => t.status);
            return {
                total: this.tasks.size,
                pending: statuses.filter(s => s === 'pending').length,
                running: statuses.filter(s => s === 'running').length,
                completed: statuses.filter(s => s === 'completed').length,
                failed: statuses.filter(s => s === 'failed').length,
                cancelled: statuses.filter(s => s === 'cancelled').length,
                progress: this.progress
            };
        }

        // 序列化
        toJSON() {
            return {
                id: this.id,
                name: this.name,
                mode: this.mode,
                status: this.status,
                progress: this.progress,
                stats: this.getStats(),
                createdAt: this.createdAt,
                startedAt: this.startedAt,
                completedAt: this.completedAt,
                tasks: Array.from(this.tasks.values())
            };
        }
    }

    /**
     * 批量任务执行器
     */
    class BatchTaskExecutor {
        constructor(options = {}) {
            this.wsClient = options.wsClient;
            this.persistence = window.persistenceManager;
            
            this.activeBatches = new Map();
            this.runningTasks = new Map();
            
            this.callbacks = {
                onBatchStart: [],
                onBatchProgress: [],
                onBatchComplete: [],
                onTaskStart: [],
                onTaskComplete: [],
                onTaskFail: []
            };
        }

        // 提交批量任务
        async submitBatch(batchConfig) {
            const batch = new BatchTask(batchConfig);
            
            // 计算执行顺序
            batch.computeExecutionOrder();
            
            this.activeBatches.set(batch.id, batch);
            
            // 保存到持久化存储
            await this.persistence.saveTask({
                id: batch.id,
                type: 'batch',
                userId: batch.userId,
                status: 'pending',
                config: batchConfig
            });

            this.trigger('onBatchStart', batch.toJSON());

            // 开始执行
            this.executeBatch(batch);

            return batch.id;
        }

        // 执行批量任务
        async executeBatch(batch) {
            batch.status = BATCH_STATUS.RUNNING;
            batch.startedAt = Date.now();

            switch (batch.mode) {
                case BATCH_MODE.PARALLEL:
                    await this.executeParallel(batch);
                    break;
                case BATCH_MODE.SEQUENTIAL:
                    await this.executeSequential(batch);
                    break;
                case BATCH_MODE.PIPELINE:
                    await this.executePipeline(batch);
                    break;
            }
        }

        // 并行执行
        async executeParallel(batch) {
            const semaphore = new Semaphore(batch.maxConcurrency);
            const promises = [];

            for (const taskId of batch.taskOrder) {
                const promise = semaphore.acquire().then(async () => {
                    try {
                        await this.executeSingleTask(batch, taskId);
                    } finally {
                        semaphore.release();
                    }
                });
                promises.push(promise);
            }

            await Promise.all(promises);
        }

        // 串行执行
        async executeSequential(batch) {
            for (const taskId of batch.taskOrder) {
                if (batch.status === BATCH_STATUS.CANCELLED) break;
                
                // 等待依赖完成
                while (!batch.canExecute(taskId) && batch.status !== BATCH_STATUS.CANCELLED) {
                    await sleep(100);
                }

                if (batch.canExecute(taskId)) {
                    await this.executeSingleTask(batch, taskId);
                }
            }
        }

        // 流水线执行
        async executePipeline(batch) {
            const pipelineStages = this.groupByStage(batch);
            
            for (const stage of pipelineStages) {
                if (batch.status === BATCH_STATUS.CANCELLED) break;
                
                // 并行执行当前阶段
                await Promise.all(
                    stage.map(taskId => this.executeSingleTask(batch, taskId))
                );
            }
        }

        // 按阶段分组
        groupByStage(batch) {
            const stages = [];
            const executed = new Set();
            
            while (executed.size < batch.tasks.size) {
                const stage = [];
                
                for (const taskId of batch.taskOrder) {
                    if (executed.has(taskId)) continue;
                    
                    const deps = batch.dependencies.get(taskId) || [];
                    const allDepsExecuted = deps.every(d => executed.has(d));
                    
                    if (allDepsExecuted) {
                        stage.push(taskId);
                    }
                }
                
                if (stage.length === 0) break;
                
                stages.push(stage);
                stage.forEach(id => executed.add(id));
            }
            
            return stages;
        }

        // 执行单个任务
        async executeSingleTask(batch, taskId) {
            const task = batch.tasks.get(taskId);
            if (!task || task.status !== 'pending') return;

            task.status = 'running';
            this.runningTasks.set(taskId, { batchId: batch.id, taskId });
            
            this.trigger('onTaskStart', { batchId: batch.id, taskId, task: task.config });

            try {
                // 通过WebSocket发送任务
                const result = await this.sendTaskToExecutor(batch, task);
                
                batch.updateTaskStatus(taskId, 'completed', result);
                this.trigger('onTaskComplete', { batchId: batch.id, taskId, result });

            } catch (error) {
                batch.updateTaskStatus(taskId, 'failed', null, error.message);
                this.trigger('onTaskFail', { batchId: batch.id, taskId, error: error.message });
            } finally {
                this.runningTasks.delete(taskId);
            }

            // 更新批量任务进度
            this.trigger('onBatchProgress', batch.toJSON());

            // 检查是否完成
            if (batch.status === BATCH_STATUS.COMPLETED || 
                batch.status === BATCH_STATUS.PARTIAL ||
                batch.status === BATCH_STATUS.FAILED) {
                this.trigger('onBatchComplete', batch.toJSON());
            }
        }

        // 发送任务到执行端
        async sendTaskToExecutor(batch, task) {
            return new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('Task execution timeout'));
                }, task.config.timeout || 300000); // 默认5分钟超时

                // 监听任务结果
                const resultHandler = (message) => {
                    if (message.payload && message.payload.taskId === task.id) {
                        clearTimeout(timeout);
                        this.wsClient.off('task_result', resultHandler);
                        
                        if (message.payload.success) {
                            resolve(message.payload.result);
                        } else {
                            reject(new Error(message.payload.error || 'Task failed'));
                        }
                    }
                };

                this.wsClient.on('task_result', resultHandler);

                // 发送任务
                this.wsClient.send({
                    type: 'submit_task',
                    payload: {
                        batchId: batch.id,
                        taskId: task.id,
                        config: task.config,
                        userId: batch.userId,
                        billingInfo: batch.billingInfo
                    }
                });
            });
        }

        // 取消批量任务
        cancelBatch(batchId) {
            const batch = this.activeBatches.get(batchId);
            if (!batch) return false;

            batch.status = BATCH_STATUS.CANCELLED;

            // 取消所有运行中的任务
            for (const task of batch.tasks.values()) {
                if (task.status === 'running') {
                    this.wsClient.send({
                        type: 'cancel_task',
                        payload: { taskId: task.id }
                    });
                    task.status = 'cancelled';
                } else if (task.status === 'pending') {
                    task.status = 'cancelled';
                }
            }

            return true;
        }

        // 暂停批量任务
        pauseBatch(batchId) {
            const batch = this.activeBatches.get(batchId);
            if (!batch || batch.status !== BATCH_STATUS.RUNNING) return false;

            batch.status = BATCH_STATUS.PAUSED;
            return true;
        }

        // 恢复批量任务
        resumeBatch(batchId) {
            const batch = this.activeBatches.get(batchId);
            if (!batch || batch.status !== BATCH_STATUS.PAUSED) return false;

            batch.status = BATCH_STATUS.RUNNING;
            this.executeBatch(batch);
            return true;
        }

        // 获取批量任务状态
        getBatchStatus(batchId) {
            const batch = this.activeBatches.get(batchId);
            return batch ? batch.toJSON() : null;
        }

        // 获取所有批量任务
        getAllBatches() {
            return Array.from(this.activeBatches.values()).map(b => b.toJSON());
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
                        console.error('[BatchTaskExecutor] 回调错误:', error);
                    }
                });
            }
        }
    }

    /**
     * 信号量（用于控制并发）
     */
    class Semaphore {
        constructor(max) {
            this.max = max;
            this.current = 0;
            this.queue = [];
        }

        acquire() {
            return new Promise(resolve => {
                if (this.current < this.max) {
                    this.current++;
                    resolve();
                } else {
                    this.queue.push(resolve);
                }
            });
        }

        release() {
            if (this.queue.length > 0) {
                const next = this.queue.shift();
                next();
            } else {
                this.current--;
            }
        }
    }

    // 辅助函数
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // 导出 - UMD格式
    const exports = {
        BatchTask,
        BatchTaskExecutor,
        BATCH_MODE,
        BATCH_STATUS,
        DEPENDENCY_TYPE
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.BatchTaskManager = exports;
        // 保持向后兼容
        window.BatchTaskManager = exports;
    }

    console.log('[BatchTaskManager] 批量任务管理器已加载');
})();
