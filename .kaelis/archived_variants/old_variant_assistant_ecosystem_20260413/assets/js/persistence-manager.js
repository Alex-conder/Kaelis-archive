/**
 * Kaelis Persistence Manager
 * 消息持久化模块 - PostgreSQL + Redis 双存储
 */

(function() {
    'use strict';

    // 存储类型
    const STORAGE_TYPE = {
        REDIS: 'redis',
        POSTGRESQL: 'postgresql'
    };

    // 数据类型
    const DATA_TYPE = {
        TASK: 'task',
        TASK_LOG: 'task_log',
        TASK_RESULT: 'task_result',
        TASK_METRIC: 'task_metric',
        SYSTEM_EVENT: 'system_event'
    };

    /**
     * PostgreSQL 持久化客户端
     */
    class PostgreSQLClient {
        constructor(config = {}) {
            this.apiEndpoint = config.apiEndpoint || '/api/persistence';
            this.batchSize = config.batchSize || 100;
            this.pendingWrites = [];
            this.flushInterval = config.flushInterval || 5000;
            
            this.startAutoFlush();
        }

        // 写入任务
        async writeTask(taskData) {
            const record = {
                type: DATA_TYPE.TASK,
                data: taskData,
                timestamp: Date.now()
            };
            
            return this.insert(record);
        }

        // 写入任务日志
        async writeTaskLog(taskId, logEntry) {
            const record = {
                type: DATA_TYPE.TASK_LOG,
                data: {
                    task_id: taskId,
                    level: logEntry.level,
                    message: logEntry.message,
                    metadata: logEntry.metadata,
                    created_at: logEntry.timestamp || Date.now()
                },
                timestamp: Date.now()
            };
            
            return this.insert(record);
        }

        // 写入任务结果
        async writeTaskResult(taskId, result) {
            const record = {
                type: DATA_TYPE.TASK_RESULT,
                data: {
                    task_id: taskId,
                    result: this.serializeResult(result),
                    result_type: result.type || 'json',
                    created_at: Date.now()
                },
                timestamp: Date.now()
            };
            
            return this.insert(record);
        }

        // 序列化结果（处理二进制数据）
        serializeResult(result) {
            if (result.type === 'binary' || result.type === 'file') {
                return {
                    type: result.type,
                    mime_type: result.mimeType,
                    filename: result.filename,
                    size: result.data ? result.data.length : 0,
                    data: result.data // Base64编码的数据
                };
            }
            return result;
        }

        // 插入数据
        async insert(record) {
            this.pendingWrites.push(record);
            
            if (this.pendingWrites.length >= this.batchSize) {
                await this.flush();
            }
            
            return { success: true, queued: true };
        }

        // 批量写入
        async flush() {
            if (this.pendingWrites.length === 0) return;

            const batch = this.pendingWrites.splice(0, this.batchSize);
            
            try {
                const response = await fetch(`${this.apiEndpoint}/batch`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.getAuthToken()}`
                    },
                    body: JSON.stringify({ records: batch })
                });

                if (!response.ok) {
                    throw new Error(`Flush failed: ${response.status}`);
                }

                return await response.json();
            } catch (error) {
                console.error('[PostgreSQLClient] 批量写入失败:', error);
                // 失败时重新加入队列
                this.pendingWrites.unshift(...batch);
                throw error;
            }
        }

        // 自动刷新
        startAutoFlush() {
            setInterval(() => {
                this.flush();
            }, this.flushInterval);
        }

        // 查询任务历史
        async queryTaskHistory(userId, options = {}) {
            const { startDate, endDate, status, limit = 100, offset = 0 } = options;
            
            const params = new URLSearchParams({
                user_id: userId,
                limit: limit.toString(),
                offset: offset.toString()
            });
            
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);
            if (status) params.append('status', status);

            const response = await fetch(`${this.apiEndpoint}/tasks?${params}`, {
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });

            if (!response.ok) {
                throw new Error('Query failed');
            }

            return await response.json();
        }

        // 查询任务日志
        async queryTaskLogs(taskId, options = {}) {
            const { limit = 100, offset = 0 } = options;
            
            const params = new URLSearchParams({
                limit: limit.toString(),
                offset: offset.toString()
            });

            const response = await fetch(`${this.apiEndpoint}/tasks/${taskId}/logs?${params}`, {
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });

            if (!response.ok) {
                throw new Error('Query failed');
            }

            return await response.json();
        }

        // 查询任务结果
        async queryTaskResult(taskId) {
            const response = await fetch(`${this.apiEndpoint}/tasks/${taskId}/result`, {
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });

            if (response.status === 404) {
                return null;
            }

            if (!response.ok) {
                throw new Error('Query failed');
            }

            return await response.json();
        }

        // 获取任务统计
        async getTaskStatistics(userId, period = '30d') {
            const response = await fetch(`${this.apiEndpoint}/statistics?user_id=${userId}&period=${period}`, {
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });

            if (!response.ok) {
                throw new Error('Query failed');
            }

            return await response.json();
        }

        // 获取认证Token
        getAuthToken() {
            return localStorage.getItem('kaelis_auth_token') || 
                   localStorage.getItem('access_token') ||
                   '';
        }
    }

    /**
     * 持久化管理器
     */
    class PersistenceManager {
        constructor(config = {}) {
            this.pgClient = new PostgreSQLClient(config.postgresql);
            this.redis = window.redisStateManager;
            
            this.writeStrategies = {
                [DATA_TYPE.TASK]: { redis: true, pg: true },
                [DATA_TYPE.TASK_LOG]: { redis: true, pg: true },
                [DATA_TYPE.TASK_RESULT]: { redis: false, pg: true },
                [DATA_TYPE.TASK_METRIC]: { redis: true, pg: false }
            };
        }

        // 保存任务
        async saveTask(taskData) {
            const results = {};

            // 写入Redis（实时状态）
            if (this.writeStrategies[DATA_TYPE.TASK].redis) {
                this.redis.saveTaskState(taskData.id, taskData);
                results.redis = true;
            }

            // 写入PostgreSQL（持久化）
            if (this.writeStrategies[DATA_TYPE.TASK].pg) {
                results.pg = await this.pgClient.writeTask(taskData);
            }

            return results;
        }

        // 保存任务日志
        async saveTaskLog(taskId, logEntry) {
            const results = {};

            // 写入Redis（最近日志）
            if (this.writeStrategies[DATA_TYPE.TASK_LOG].redis) {
                const key = `task:${taskId}:logs`;
                this.redis.store.rpush(key, JSON.stringify(logEntry));
                // 限制日志数量
                this.redis.store.lrange(key, 0, -1).then(logs => {
                    if (logs.length > 1000) {
                        // 只保留最近1000条
                        this.redis.store.lrange(key, -1000, -1).then(recentLogs => {
                            this.redis.store.set(key, JSON.stringify(recentLogs));
                        });
                    }
                });
                results.redis = true;
            }

            // 写入PostgreSQL（完整日志）
            if (this.writeStrategies[DATA_TYPE.TASK_LOG].pg) {
                results.pg = await this.pgClient.writeTaskLog(taskId, logEntry);
            }

            return results;
        }

        // 保存任务结果
        async saveTaskResult(taskId, result) {
            const results = {};

            // 小结果写入Redis
            if (this.writeStrategies[DATA_TYPE.TASK_RESULT].redis && 
                JSON.stringify(result).length < 10000) {
                this.redis.saveTaskState(taskId, { result });
                results.redis = true;
            }

            // 写入PostgreSQL
            if (this.writeStrategies[DATA_TYPE.TASK_RESULT].pg) {
                results.pg = await this.pgClient.writeTaskResult(taskId, result);
            }

            return results;
        }

        // 获取任务（优先Redis，无则查PG）
        async getTask(taskId) {
            // 先查Redis
            let task = this.redis.getTaskState(taskId);
            
            if (!task) {
                // 查PostgreSQL
                try {
                    const result = await this.pgClient.queryTaskHistory(null, { 
                        task_id: taskId,
                        limit: 1 
                    });
                    if (result && result.tasks && result.tasks.length > 0) {
                        task = result.tasks[0];
                        // 回填Redis
                        this.redis.saveTaskState(taskId, task);
                    }
                } catch (error) {
                    console.error('[PersistenceManager] 查询任务失败:', error);
                }
            }

            return task;
        }

        // 获取任务日志
        async getTaskLogs(taskId, options = {}) {
            const { source = 'both', limit = 100 } = options;
            
            let logs = [];

            if (source === 'redis' || source === 'both') {
                const key = `task:${taskId}:logs`;
                const redisLogs = this.redis.store.lrange(key, -limit, -1);
                if (redisLogs) {
                    logs = redisLogs.map(l => JSON.parse(l));
                }
            }

            if ((source === 'pg' || source === 'both') && logs.length < limit) {
                try {
                    const pgLogs = await this.pgClient.queryTaskLogs(taskId, { 
                        limit: limit - logs.length 
                    });
                    if (pgLogs && pgLogs.logs) {
                        logs = [...logs, ...pgLogs.logs];
                    }
                } catch (error) {
                    console.error('[PersistenceManager] 查询日志失败:', error);
                }
            }

            return logs;
        }

        // 获取任务结果
        async getTaskResult(taskId) {
            // 先查PostgreSQL（完整结果）
            try {
                const result = await this.pgClient.queryTaskResult(taskId);
                if (result) {
                    return this.deserializeResult(result);
                }
            } catch (error) {
                console.error('[PersistenceManager] 查询结果失败:', error);
            }

            return null;
        }

        // 反序列化结果
        deserializeResult(result) {
            if (result.result_type === 'binary' || result.result_type === 'file') {
                return {
                    type: result.result_type,
                    mimeType: result.data.mime_type,
                    filename: result.data.filename,
                    size: result.data.size,
                    data: result.data.data // Base64
                };
            }
            return result.data;
        }

        // 获取用户任务历史
        async getUserTaskHistory(userId, options = {}) {
            return this.pgClient.queryTaskHistory(userId, options);
        }

        // 获取未完成任务（用于断线重连恢复）
        async getIncompleteTasks(userId) {
            // 从Redis获取
            const redisTasks = this.redis.getUserTasks(userId)
                .filter(t => ['pending', 'running', 'queued'].includes(t.status));

            // 从PostgreSQL获取（作为备份）
            try {
                const pgTasks = await this.pgClient.queryTaskHistory(userId, {
                    status: 'running',
                    limit: 100
                });
                
                // 合并去重
                const taskMap = new Map();
                redisTasks.forEach(t => taskMap.set(t.id, t));
                if (pgTasks && pgTasks.tasks) {
                    pgTasks.tasks.forEach(t => {
                        if (!taskMap.has(t.id)) {
                            taskMap.set(t.id, t);
                        }
                    });
                }

                return Array.from(taskMap.values());
            } catch (error) {
                console.error('[PersistenceManager] 获取未完成任务失败:', error);
                return redisTasks;
            }
        }

        // 归档旧数据
        async archiveOldData(days = 30) {
            const cutoffDate = Date.now() - (days * 24 * 60 * 60 * 1000);
            
            try {
                const response = await fetch('/api/persistence/archive', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.pgClient.getAuthToken()}`
                    },
                    body: JSON.stringify({ cutoff_date: cutoffDate })
                });

                return await response.json();
            } catch (error) {
                console.error('[PersistenceManager] 归档失败:', error);
                throw error;
            }
        }
    }

    // 导出 - UMD格式
    const exports = {
        PostgreSQLClient,
        PersistenceManager,
        DATA_TYPE,
        STORAGE_TYPE
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.PersistenceManager = exports;
        // 保持向后兼容
        window.PersistenceManager = exports;
        window.persistenceManager = new PersistenceManager();
    }

    console.log('[PersistenceManager] 持久化管理器已加载');
})();
