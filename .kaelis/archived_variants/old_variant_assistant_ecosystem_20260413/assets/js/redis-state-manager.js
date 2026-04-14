/**
 * Kaelis Redis State Manager
 * Redis 状态存储管理（客户端模拟实现）
 * 服务端实际使用 Redis 数据库
 */

(function() {
    'use strict';

    // 状态键前缀
    const KEY_PREFIXES = {
        TASK: 'task:',
        INSTANCE: 'instance:',
        USER: 'user:',
        SESSION: 'session:',
        BILLING: 'billing:',
        METRICS: 'metrics:',
        LOCK: 'lock:',
        QUEUE: 'queue:',
        CACHE: 'cache:'
    };

    // 过期时间（秒）
    const EXPIRY = {
        TASK: 7 * 24 * 60 * 60,      // 7天
        SESSION: 24 * 60 * 60,       // 1天
        INSTANCE: 60,                // 60秒（心跳间隔）
        CACHE: 60 * 60,              // 1小时
        LOCK: 30                     // 30秒
    };

    /**
     * 内存存储（模拟 Redis）
     */
    class MemoryStore {
        constructor() {
            this.data = new Map();
            this.timers = new Map();
        }

        // 设置值
        set(key, value, expiry = null) {
            this.data.set(key, {
                value,
                createdAt: Date.now()
            });

            // 设置过期
            if (expiry) {
                this.setExpiry(key, expiry);
            }

            return true;
        }

        // 获取值
        get(key) {
            const item = this.data.get(key);
            if (!item) return null;
            return item.value;
        }

        // 删除值
        del(key) {
            this.clearExpiry(key);
            return this.data.delete(key);
        }

        // 设置过期时间
        setExpiry(key, seconds) {
            this.clearExpiry(key);
            
            const timer = setTimeout(() => {
                this.data.delete(key);
                this.timers.delete(key);
            }, seconds * 1000);

            this.timers.set(key, timer);
        }

        // 清除过期定时器
        clearExpiry(key) {
            const timer = this.timers.get(key);
            if (timer) {
                clearTimeout(timer);
                this.timers.delete(key);
            }
        }

        // 检查是否存在
        exists(key) {
            return this.data.has(key);
        }

        // 设置哈希字段
        hset(key, field, value) {
            let hash = this.data.get(key);
            if (!hash) {
                hash = { value: {} };
                this.data.set(key, hash);
            }
            hash.value[field] = value;
            return true;
        }

        // 获取哈希字段
        hget(key, field) {
            const hash = this.data.get(key);
            if (!hash) return null;
            return hash.value[field];
        }

        // 获取所有哈希字段
        hgetall(key) {
            const hash = this.data.get(key);
            if (!hash) return {};
            return { ...hash.value };
        }

        // 列表操作 - 右侧推入
        rpush(key, value) {
            let list = this.data.get(key);
            if (!list) {
                list = { value: [] };
                this.data.set(key, list);
            }
            list.value.push(value);
            return list.value.length;
        }

        // 列表操作 - 左侧弹出
        lpop(key) {
            const list = this.data.get(key);
            if (!list || list.value.length === 0) return null;
            return list.value.shift();
        }

        // 列表操作 - 获取范围
        lrange(key, start, end) {
            const list = this.data.get(key);
            if (!list) return [];
            
            const actualEnd = end === -1 ? list.value.length : end + 1;
            return list.value.slice(start, actualEnd);
        }

        // 集合操作 - 添加成员
        sadd(key, member) {
            let set = this.data.get(key);
            if (!set) {
                set = { value: new Set() };
                this.data.set(key, set);
            }
            set.value.add(member);
            return set.value.size;
        }

        // 集合操作 - 获取所有成员
        smembers(key) {
            const set = this.data.get(key);
            if (!set) return [];
            return Array.from(set.value);
        }

        // 有序集合操作 - 添加成员
        zadd(key, score, member) {
            let zset = this.data.get(key);
            if (!zset) {
                zset = { value: new Map() };
                this.data.set(key, zset);
            }
            zset.value.set(member, score);
            return true;
        }

        // 有序集合操作 - 按分数范围获取
        zrangebyscore(key, min, max, withScores = false) {
            const zset = this.data.get(key);
            if (!zset) return [];

            const result = [];
            for (const [member, score] of zset.value) {
                if (score >= min && score <= max) {
                    if (withScores) {
                        result.push({ member, score });
                    } else {
                        result.push(member);
                    }
                }
            }

            return result.sort((a, b) => {
                const scoreA = typeof a === 'object' ? a.score : 0;
                const scoreB = typeof b === 'object' ? b.score : 0;
                return scoreA - scoreB;
            });
        }

        // 发布订阅 - 发布
        publish(channel, message) {
            // 触发订阅者
            const subscribers = this.getSubscribers(channel);
            subscribers.forEach(callback => {
                try {
                    callback(channel, message);
                } catch (error) {
                    console.error('[MemoryStore] 订阅回调错误:', error);
                }
            });
            return subscribers.length;
        }

        // 获取订阅者
        getSubscribers(channel) {
            if (!this.subscribers) {
                this.subscribers = new Map();
            }
            return this.subscribers.get(channel) || [];
        }

        // 订阅
        subscribe(channel, callback) {
            if (!this.subscribers) {
                this.subscribers = new Map();
            }
            
            let subscribers = this.subscribers.get(channel);
            if (!subscribers) {
                subscribers = [];
                this.subscribers.set(channel, subscribers);
            }
            
            subscribers.push(callback);
            
            // 返回取消订阅函数
            return () => {
                const index = subscribers.indexOf(callback);
                if (index > -1) {
                    subscribers.splice(index, 1);
                }
            };
        }

        // 扫描键
        scan(pattern) {
            const keys = [];
            for (const key of this.data.keys()) {
                if (this.matchPattern(key, pattern)) {
                    keys.push(key);
                }
            }
            return keys;
        }

        // 模式匹配
        matchPattern(key, pattern) {
            const regex = pattern
                .replace(/\*/g, '.*')
                .replace(/\?/g, '.');
            return new RegExp('^' + regex + '$').test(key);
        }

        // 清空
        flushall() {
            this.data.clear();
            for (const timer of this.timers.values()) {
                clearTimeout(timer);
            }
            this.timers.clear();
        }

        // 获取统计
        info() {
            return {
                keys: this.data.size,
                memory: JSON.stringify(this.data).length
            };
        }
    }

    /**
     * Redis 状态管理器
     */
    class RedisStateManager {
        constructor() {
            this.store = new MemoryStore();
            this.pubsub = new MemoryStore();
        }

        // ========== 任务状态管理 ==========

        // 保存任务状态
        saveTaskState(taskId, state) {
            const key = `${KEY_PREFIXES.TASK}${taskId}`;
            this.store.set(key, JSON.stringify(state), EXPIRY.TASK);
            
            // 同时保存到用户任务列表
            if (state.userId) {
                this.store.sadd(`${KEY_PREFIXES.USER}${state.userId}:tasks`, taskId);
            }
            
            // 发布状态更新
            this.publish('task:status', { taskId, state });
            
            return true;
        }

        // 获取任务状态
        getTaskState(taskId) {
            const key = `${KEY_PREFIXES.TASK}${taskId}`;
            const data = this.store.get(key);
            return data ? JSON.parse(data) : null;
        }

        // 更新任务进度
        updateTaskProgress(taskId, progress) {
            const key = `${KEY_PREFIXES.TASK}${taskId}`;
            const state = this.getTaskState(taskId);
            if (state) {
                state.progress = progress;
                state.updatedAt = Date.now();
                this.store.set(key, JSON.stringify(state), EXPIRY.TASK);
                this.publish('task:progress', { taskId, progress });
            }
        }

        // 获取用户任务列表
        getUserTasks(userId) {
            const taskIds = this.store.smembers(`${KEY_PREFIXES.USER}${userId}:tasks`);
            return taskIds.map(id => this.getTaskState(id)).filter(Boolean);
        }

        // ========== 实例状态管理 ==========

        // 注册实例
        registerInstance(instanceId, info) {
            const key = `${KEY_PREFIXES.INSTANCE}${instanceId}`;
            this.store.set(key, JSON.stringify({
                ...info,
                registeredAt: Date.now(),
                lastHeartbeat: Date.now()
            }), EXPIRY.INSTANCE);
            
            // 添加到活跃实例集合
            this.store.sadd(`${KEY_PREFIXES.INSTANCE}active`, instanceId);
            
            this.publish('instance:register', { instanceId, info });
        }

        // 更新实例心跳
        updateInstanceHeartbeat(instanceId) {
            const key = `${KEY_PREFIXES.INSTANCE}${instanceId}`;
            const data = this.store.get(key);
            if (data) {
                const info = JSON.parse(data);
                info.lastHeartbeat = Date.now();
                this.store.set(key, JSON.stringify(info), EXPIRY.INSTANCE);
            }
        }

        // 获取活跃实例
        getActiveInstances() {
            const instanceIds = this.store.smembers(`${KEY_PREFIXES.INSTANCE}active`);
            return instanceIds.map(id => {
                const data = this.store.get(`${KEY_PREFIXES.INSTANCE}${id}`);
                return data ? JSON.parse(data) : null;
            }).filter(Boolean);
        }

        // ========== 会话状态管理 ==========

        // 创建会话
        createSession(sessionId, data) {
            const key = `${KEY_PREFIXES.SESSION}${sessionId}`;
            this.store.set(key, JSON.stringify({
                ...data,
                createdAt: Date.now()
            }), EXPIRY.SESSION);
        }

        // 获取会话
        getSession(sessionId) {
            const key = `${KEY_PREFIXES.SESSION}${sessionId}`;
            const data = this.store.get(key);
            return data ? JSON.parse(data) : null;
        }

        // 更新会话
        updateSession(sessionId, updates) {
            const session = this.getSession(sessionId);
            if (session) {
                Object.assign(session, updates, { updatedAt: Date.now() });
                this.createSession(sessionId, session);
            }
        }

        // ========== 计费状态管理 ==========

        // 记录资源使用
        recordUsage(accountId, resourceType, amount, cost) {
            const timestamp = Date.now();
            const key = `${KEY_PREFIXES.BILLING}${accountId}:${new Date().toISOString().slice(0, 7)}`;
            
            // 使用哈希存储各类资源使用
            this.store.hset(key, `${resourceType}:${timestamp}`, JSON.stringify({
                amount,
                cost,
                timestamp
            }));
            
            // 更新累计使用
            const totalKey = `${KEY_PREFIXES.BILLING}${accountId}:total`;
            const current = parseFloat(this.store.hget(totalKey, resourceType) || '0');
            this.store.hset(totalKey, resourceType, (current + cost).toString());
        }

        // 获取计费统计
        getBillingStats(accountId, period) {
            const key = `${KEY_PREFIXES.BILLING}${accountId}:${period}`;
            return this.store.hgetall(key);
        }

        // ========== 队列管理 ==========

        // 入队
        enqueue(queueName, item) {
            const key = `${KEY_PREFIXES.QUEUE}${queueName}`;
            return this.store.rpush(key, JSON.stringify(item));
        }

        // 出队
        dequeue(queueName) {
            const key = `${KEY_PREFIXES.QUEUE}${queueName}`;
            const data = this.store.lpop(key);
            return data ? JSON.parse(data) : null;
        }

        // 查看队列
        peekQueue(queueName, count = 10) {
            const key = `${KEY_PREFIXES.QUEUE}${queueName}`;
            const items = this.store.lrange(key, 0, count - 1);
            return items.map(item => JSON.parse(item));
        }

        // ========== 缓存管理 ==========

        // 设置缓存
        setCache(key, value, expiry = EXPIRY.CACHE) {
            const cacheKey = `${KEY_PREFIXES.CACHE}${key}`;
            this.store.set(cacheKey, JSON.stringify(value), expiry);
        }

        // 获取缓存
        getCache(key) {
            const cacheKey = `${KEY_PREFIXES.CACHE}${key}`;
            const data = this.store.get(cacheKey);
            return data ? JSON.parse(data) : null;
        }

        // 删除缓存
        deleteCache(key) {
            const cacheKey = `${KEY_PREFIXES.CACHE}${key}`;
            return this.store.del(cacheKey);
        }

        // ========== 分布式锁 ==========

        // 获取锁
        acquireLock(lockName, ttl = EXPIRY.LOCK) {
            const key = `${KEY_PREFIXES.LOCK}${lockName}`;
            if (this.store.exists(key)) {
                return false;
            }
            this.store.set(key, JSON.stringify({
                acquiredAt: Date.now(),
                owner: this.generateLockId()
            }), ttl);
            return true;
        }

        // 释放锁
        releaseLock(lockName) {
            const key = `${KEY_PREFIXES.LOCK}${lockName}`;
            return this.store.del(key);
        }

        generateLockId() {
            return `lock_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        }

        // ========== 发布订阅 ==========

        // 发布消息
        publish(channel, message) {
            return this.pubsub.publish(channel, message);
        }

        // 订阅频道
        subscribe(channel, callback) {
            return this.pubsub.subscribe(channel, callback);
        }

        // ========== 指标收集 ==========

        // 记录指标
        recordMetric(metricName, value, tags = {}) {
            const timestamp = Date.now();
            const key = `${KEY_PREFIXES.METRICS}${metricName}`;
            
            // 使用有序集合存储时间序列数据
            this.store.zadd(key, timestamp, JSON.stringify({
                value,
                tags,
                timestamp
            }));
        }

        // 查询指标
        queryMetrics(metricName, startTime, endTime) {
            const key = `${KEY_PREFIXES.METRICS}${metricName}`;
            return this.store.zrangebyscore(key, startTime, endTime, true);
        }

        // ========== 工具方法 ==========

        // 清理过期数据
        cleanup() {
            // 清理离线实例
            const activeInstances = this.store.smembers(`${KEY_PREFIXES.INSTANCE}active`);
            const now = Date.now();
            
            for (const instanceId of activeInstances) {
                const data = this.getInstanceState(instanceId);
                if (data && now - data.lastHeartbeat > EXPIRY.INSTANCE * 1000) {
                    this.store.del(`${KEY_PREFIXES.INSTANCE}${instanceId}`);
                }
            }
        }

        getInstanceState(instanceId) {
            const data = this.store.get(`${KEY_PREFIXES.INSTANCE}${instanceId}`);
            return data ? JSON.parse(data) : null;
        }

        // 获取统计信息
        getStats() {
            return {
                store: this.store.info(),
                tasks: this.store.scan(`${KEY_PREFIXES.TASK}*`).length,
                instances: this.store.scan(`${KEY_PREFIXES.INSTANCE}*`).length,
                sessions: this.store.scan(`${KEY_PREFIXES.SESSION}*`).length
            };
        }

        // 清空所有数据
        flushall() {
            this.store.flushall();
        }
    }

    // 导出 - UMD格式
    const exports = {
        RedisStateManager,
        RedisStore,
        KEY_PREFIXES,
        EXPIRY
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.RedisStateManager = exports;
        // 保持向后兼容
        window.RedisStateManager = RedisStateManager;
        window.redisStateManager = new RedisStateManager();
        window.KEY_PREFIXES = KEY_PREFIXES;
        window.EXPIRY = EXPIRY;
    }

    console.log('[RedisStateManager] Redis状态管理器已加载');
})();
