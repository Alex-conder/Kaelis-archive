/**
 * Kaelis Context Management System
 * 上下文管理机制 - 即时/短期/长期记忆三层架构
 */

(function() {
    'use strict';

    // 配置
    const CONFIG = {
        // 即时上下文
        immediate: {
            maxRounds: 10,
            maxTokens: 4000
        },
        // 短期记忆
        shortTerm: {
            maxSessions: 100,
            ttl: 24 * 60 * 60 * 1000, // 24小时
            adaptiveFactor: 0.5
        },
        // 长期记忆
        longTerm: {
            maxDays: 90,
            importantDays: 365,
            complianceYears: 7
        }
    };

    // 环形缓冲区实现
    class CircularBuffer {
        constructor(capacity) {
            this.capacity = capacity;
            this.buffer = [];
            this.index = 0;
        }

        push(item) {
            if (this.buffer.length < this.capacity) {
                this.buffer.push(item);
            } else {
                this.buffer[this.index] = item;
                this.index = (this.index + 1) % this.capacity;
            }
        }

        getAll() {
            if (this.buffer.length < this.capacity) {
                return [...this.buffer];
            }
            return [
                ...this.buffer.slice(this.index),
                ...this.buffer.slice(0, this.index)
            ];
        }

        clear() {
            this.buffer = [];
            this.index = 0;
        }
    }

    // 即时上下文层
    class ImmediateContext {
        constructor() {
            this.buffer = new CircularBuffer(CONFIG.immediate.maxRounds);
            this.tokenCount = 0;
        }

        addMessage(role, content, metadata = {}) {
            const message = {
                role,
                content,
                timestamp: Date.now(),
                tokens: this.estimateTokens(content),
                metadata
            };

            this.buffer.push(message);
            this.tokenCount += message.tokens;

            // 如果超出token限制，压缩最早的对话
            while (this.tokenCount > CONFIG.immediate.maxTokens) {
                this.compressOldest();
            }
        }

        estimateTokens(text) {
            // 简化的token估算: 中文约1.5字符/token，英文约4字符/token
            const chinese = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
            const english = text.length - chinese;
            return Math.ceil(chinese / 1.5 + english / 4);
        }

        compressOldest() {
            const messages = this.buffer.getAll();
            if (messages.length < 2) return;

            // 压缩最早的非系统消息
            for (let i = 0; i < messages.length; i++) {
                if (messages[i].role !== 'system') {
                    const originalTokens = messages[i].tokens;
                    messages[i].content = this.summarize(messages[i].content);
                    messages[i].tokens = this.estimateTokens(messages[i].content);
                    messages[i].compressed = true;
                    this.tokenCount -= (originalTokens - messages[i].tokens);
                    break;
                }
            }
        }

        summarize(content) {
            // 简化摘要: 取前100字符 + "..."
            if (content.length <= 100) return content;
            return content.substring(0, 100) + '...(已压缩)';
        }

        getContext() {
            return this.buffer.getAll();
        }

        clear() {
            this.buffer.clear();
            this.tokenCount = 0;
        }
    }

    // 短期记忆层
    class ShortTermMemory {
        constructor() {
            this.sessions = new Map();
            this.activityScores = new Map();
        }

        createSession(sessionId, userId) {
            const session = {
                id: sessionId,
                userId,
                messages: [],
                createdAt: Date.now(),
                lastActivity: Date.now(),
                messageCount: 0,
                ttl: CONFIG.shortTerm.ttl
            };

            this.sessions.set(sessionId, session);
            this.activityScores.set(sessionId, 1);
            
            return session;
        }

        addToSession(sessionId, message) {
            const session = this.sessions.get(sessionId);
            if (!session) return;

            session.messages.push({
                ...message,
                timestamp: Date.now()
            });
            session.lastActivity = Date.now();
            session.messageCount++;

            // 更新活跃度分数
            this.updateActivityScore(sessionId);
        }

        updateActivityScore(sessionId) {
            const session = this.sessions.get(sessionId);
            if (!session) return;

            const duration = Date.now() - session.createdAt;
            const frequency = session.messageCount / (duration / 60000 + 1); // 消息/分钟
            
            // 活跃度分数 = 消息数 * 频率因子
            const score = session.messageCount * (1 + frequency);
            this.activityScores.set(sessionId, score);

            // 自适应TTL
            const adaptiveTTL = CONFIG.shortTerm.ttl * 
                (1 + CONFIG.shortTerm.adaptiveFactor * Math.log(score + 1));
            session.ttl = adaptiveTTL;
        }

        getSession(sessionId) {
            const session = this.sessions.get(sessionId);
            if (!session) return null;

            // 检查是否过期
            if (Date.now() - session.lastActivity > session.ttl) {
                this.sessions.delete(sessionId);
                this.activityScores.delete(sessionId);
                return null;
            }

            return session;
        }

        getUserSessions(userId) {
            const sessions = [];
            for (const [id, session] of this.sessions) {
                if (session.userId === userId) {
                    sessions.push(session);
                }
            }
            return sessions.sort((a, b) => b.lastActivity - a.lastActivity);
        }

        // 清理过期会话
        cleanup() {
            const now = Date.now();
            for (const [id, session] of this.sessions) {
                if (now - session.lastActivity > session.ttl) {
                    this.sessions.delete(id);
                    this.activityScores.delete(id);
                }
            }
        }
    }

    // 长期记忆层
    class LongTermMemory {
        constructor() {
            this.db = null; // 实际项目中使用IndexedDB或后端数据库
            this.initDB();
        }

        async initDB() {
            // 初始化IndexedDB
            return new Promise((resolve, reject) => {
                const request = indexedDB.open('KaelisLongTermMemory', 1);
                
                request.onerror = () => reject(request.error);
                request.onsuccess = () => {
                    this.db = request.result;
                    resolve();
                };
                
                request.onupgradeneeded = (event) => {
                    const db = event.target.result;
                    
                    // 对话存储
                    if (!db.objectStoreNames.contains('conversations')) {
                        const store = db.createObjectStore('conversations', { keyPath: 'id' });
                        store.createIndex('userId', 'userId', { unique: false });
                        store.createIndex('timestamp', 'timestamp', { unique: false });
                        store.createIndex('importance', 'importance', { unique: false });
                    }
                    
                    // 摘要存储
                    if (!db.objectStoreNames.contains('summaries')) {
                        const store = db.createObjectStore('summaries', { keyPath: 'id' });
                        store.createIndex('userId', 'userId', { unique: false });
                        store.createIndex('date', 'date', { unique: false });
                    }
                };
            });
        }

        async saveConversation(userId, messages, metadata = {}) {
            if (!this.db) await this.initDB();

            const conversation = {
                id: `${userId}_${Date.now()}`,
                userId,
                messages,
                timestamp: Date.now(),
                importance: metadata.importance || 'normal',
                tags: metadata.tags || [],
                summary: await this.generateSummary(messages)
            };

            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['conversations'], 'readwrite');
                const store = transaction.objectStore('conversations');
                const request = store.add(conversation);
                
                request.onsuccess = () => resolve(conversation.id);
                request.onerror = () => reject(request.error);
            });
        }

        async generateSummary(messages) {
            // 简化的摘要生成
            const userMessages = messages.filter(m => m.role === 'user');
            const assistantMessages = messages.filter(m => m.role === 'assistant');
            
            return {
                userQueryCount: userMessages.length,
                assistantResponseCount: assistantMessages.length,
                topics: this.extractTopics(messages),
                keyPoints: this.extractKeyPoints(messages)
            };
        }

        extractTopics(messages) {
            // 简化的主题提取
            const allText = messages.map(m => m.content).join(' ');
            const keywords = ['代码', '项目', 'GitHub', 'Python', 'JavaScript', 'API'];
            return keywords.filter(kw => allText.includes(kw));
        }

        extractKeyPoints(messages) {
            // 提取关键信息点
            return messages
                .filter(m => m.role === 'assistant' && m.content.length > 50)
                .slice(0, 3)
                .map(m => m.content.substring(0, 100) + '...');
        }

        async getConversations(userId, options = {}) {
            if (!this.db) await this.initDB();

            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['conversations'], 'readonly');
                const store = transaction.objectStore('conversations');
                const index = store.index('userId');
                const request = index.getAll(userId);
                
                request.onsuccess = () => {
                    let conversations = request.result;
                    
                    // 过滤
                    if (options.importance) {
                        conversations = conversations.filter(c => c.importance === options.importance);
                    }
                    
                    // 时间范围
                    if (options.startDate) {
                        conversations = conversations.filter(c => c.timestamp >= options.startDate);
                    }
                    if (options.endDate) {
                        conversations = conversations.filter(c => c.timestamp <= options.endDate);
                    }
                    
                    // 排序
                    conversations.sort((a, b) => b.timestamp - a.timestamp);
                    
                    // 限制数量
                    if (options.limit) {
                        conversations = conversations.slice(0, options.limit);
                    }
                    
                    resolve(conversations);
                };
                
                request.onerror = () => reject(request.error);
            });
        }

        // 数据生命周期管理
        async lifecycleManagement() {
            const now = Date.now();
            const normalLimit = now - CONFIG.longTerm.maxDays * 24 * 60 * 60 * 1000;
            const importantLimit = now - CONFIG.longTerm.importantDays * 24 * 60 * 60 * 1000;

            const conversations = await this.getAllConversations();
            
            for (const conv of conversations) {
                const age = now - conv.timestamp;
                
                if (conv.importance === 'compliance' && age > CONFIG.longTerm.complianceYears * 365 * 24 * 60 * 60 * 1000) {
                    // 合规数据超过7年，删除
                    await this.deleteConversation(conv.id);
                } else if (conv.importance === 'normal' && age > normalLimit) {
                    // 普通数据超过90天，降级为摘要
                    await this.degradeToSummary(conv);
                } else if (conv.importance === 'important' && age > importantLimit) {
                    // 重要数据超过1年，降级为摘要
                    await this.degradeToSummary(conv);
                }
            }
        }

        async degradeToSummary(conversation) {
            // 保存摘要
            await this.saveSummary(conversation);
            // 删除原始对话
            await this.deleteConversation(conversation.id);
        }

        async saveSummary(conversation) {
            const summary = {
                id: conversation.id,
                userId: conversation.userId,
                date: new Date(conversation.timestamp).toISOString().split('T')[0],
                summary: conversation.summary,
                messageCount: conversation.messages.length,
                tags: conversation.tags
            };

            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['summaries'], 'readwrite');
                const store = transaction.objectStore('summaries');
                const request = store.add(summary);
                
                request.onsuccess = () => resolve();
                request.onerror = () => reject(request.error);
            });
        }

        async getAllConversations() {
            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['conversations'], 'readonly');
                const store = transaction.objectStore('conversations');
                const request = store.getAll();
                
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
        }

        async deleteConversation(id) {
            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['conversations'], 'readwrite');
                const store = transaction.objectStore('conversations');
                const request = store.delete(id);
                
                request.onsuccess = () => resolve();
                request.onerror = () => reject(request.error);
            });
        }
    }

    // FlowKV 缓存管理
    class FlowKV {
        constructor() {
            this.cache = new Map();
            this.compressionLog = new Map();
        }

        set(key, value, round) {
            // 只压缩最新轮次的KV
            if (this.compressionLog.has(key)) {
                const lastRound = this.compressionLog.get(key);
                if (round > lastRound) {
                    // 新轮次，压缩旧数据
                    const compressed = this.compress(value);
                    this.cache.set(key, { value: compressed, round, compressed: true });
                } else {
                    this.cache.set(key, { value, round, compressed: false });
                }
            } else {
                this.cache.set(key, { value, round, compressed: false });
            }
            this.compressionLog.set(key, round);
        }

        get(key) {
            const entry = this.cache.get(key);
            if (!entry) return null;
            
            if (entry.compressed) {
                return this.decompress(entry.value);
            }
            return entry.value;
        }

        compress(value) {
            // 简化的压缩: 去除冗余空格，缩短长文本
            if (typeof value === 'string') {
                return value.replace(/\s+/g, ' ').trim();
            }
            return value;
        }

        decompress(value) {
            return value;
        }
    }

    // 上下文管理器主类
    class ContextManager {
        constructor() {
            this.immediate = new ImmediateContext();
            this.shortTerm = new ShortTermMemory();
            this.longTerm = new LongTermMemory();
            this.flowKV = new FlowKV();
            
            // 定期清理
            setInterval(() => this.shortTerm.cleanup(), 60000); // 每分钟
            setInterval(() => this.longTerm.lifecycleManagement(), 24 * 60 * 60 * 1000); // 每天
        }

        // 添加消息到上下文
        addMessage(sessionId, userId, role, content, metadata = {}) {
            // 即时上下文
            this.immediate.addMessage(role, content, metadata);
            
            // 短期记忆
            this.shortTerm.addToSession(sessionId, { role, content, metadata });
            
            // 检查是否需要保存到长期记忆
            const session = this.shortTerm.getSession(sessionId);
            if (session && session.messageCount % 20 === 0) { // 每20条消息保存一次
                this.saveToLongTerm(userId, session);
            }
        }

        // 保存到长期记忆
        async saveToLongTerm(userId, session) {
            const messages = session.messages;
            const metadata = {
                importance: this.calculateImportance(messages),
                tags: this.extractTags(messages)
            };
            
            await this.longTerm.saveConversation(userId, messages, metadata);
        }

        calculateImportance(messages) {
            // 根据内容判断重要性
            const importantKeywords = ['重要', '关键', '决策', '合同', '法律'];
            const text = messages.map(m => m.content).join(' ');
            
            if (importantKeywords.some(kw => text.includes(kw))) {
                return 'important';
            }
            return 'normal';
        }

        extractTags(messages) {
            const allText = messages.map(m => m.content).join(' ');
            const tags = [];
            
            if (allText.includes('GitHub') || allText.includes('代码')) tags.push('开发');
            if (allText.includes('问题') || allText.includes('bug')) tags.push('问题');
            if (allText.includes('学习') || allText.includes('教程')) tags.push('学习');
            
            return tags;
        }

        // 获取完整上下文
        async getFullContext(sessionId, userId) {
            const context = {
                immediate: this.immediate.getContext(),
                shortTerm: null,
                longTerm: null
            };

            // 短期记忆
            const session = this.shortTerm.getSession(sessionId);
            if (session) {
                context.shortTerm = session.messages.slice(-50); // 最近50条
            }

            // 长期记忆 (最近5个相关对话)
            try {
                context.longTerm = await this.longTerm.getConversations(userId, {
                    limit: 5,
                    startDate: Date.now() - 7 * 24 * 60 * 60 * 1000 // 最近7天
                });
            } catch (e) {
                console.error('获取长期记忆失败:', e);
            }

            return context;
        }

        // 创建新会话
        createSession(sessionId, userId) {
            this.immediate.clear();
            return this.shortTerm.createSession(sessionId, userId);
        }

        // 获取会话历史
        getSessionHistory(sessionId) {
            const session = this.shortTerm.getSession(sessionId);
            return session ? session.messages : [];
        }
    }

    // 导出 - UMD格式
    const exports = {
        ContextManager,
        ShortTermMemory,
        LongTermMemory,
        MessageBuffer,
        CONTEXT_TYPE,
        MEMORY_LEVEL
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.ContextManager = exports;
        // 保持向后兼容
        window.ContextManager = ContextManager;
        window.contextManager = new ContextManager();
    }

    console.log('[ContextManager] 上下文管理系统已加载');
})();
