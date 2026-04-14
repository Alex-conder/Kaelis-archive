/**
 * Kaelis Chat Engine
 * AI对话引擎 - 处理消息、流式响应、上下文管理
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.ChatEngine = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';

    // 消息类型
    const MESSAGE_TYPES = {
        USER: 'user',
        ASSISTANT: 'assistant',
        SYSTEM: 'system',
        ERROR: 'error',
        TYPING: 'typing'
    };

    // 对话状态
    const CHAT_STATES = {
        IDLE: 'idle',
        CONNECTING: 'connecting',
        STREAMING: 'streaming',
        ERROR: 'error'
    };

    /**
     * 消息类
     */
    class Message {
        constructor(options = {}) {
            this.id = options.id || this.generateId();
            this.type = options.type || MESSAGE_TYPES.USER;
            this.content = options.content || '';
            this.timestamp = options.timestamp || Date.now();
            this.metadata = options.metadata || {};
            this.status = options.status || 'sent';
        }

        generateId() {
            return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        }

        toJSON() {
            return {
                id: this.id,
                type: this.type,
                content: this.content,
                timestamp: this.timestamp,
                metadata: this.metadata,
                status: this.status
            };
        }
    }

    /**
     * 对话会话类
     */
    class ChatSession {
        constructor(options = {}) {
            this.id = options.id || this.generateId();
            this.title = options.title || '新对话';
            this.messages = [];
            this.createdAt = options.createdAt || Date.now();
            this.updatedAt = options.updatedAt || Date.now();
            this.metadata = options.metadata || {};
            this.maxContextLength = options.maxContextLength || 10;
        }

        generateId() {
            return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        }

        addMessage(message) {
            this.messages.push(message);
            this.updatedAt = Date.now();
            this.trimContext();
        }

        trimContext() {
            if (this.messages.length > this.maxContextLength * 2) {
                // 保留系统消息和最近的对话
                const systemMessages = this.messages.filter(m => m.type === MESSAGE_TYPES.SYSTEM);
                const recentMessages = this.messages.slice(-this.maxContextLength * 2);
                this.messages = [...systemMessages, ...recentMessages];
            }
        }

        getContext() {
            return this.messages.map(m => ({
                role: m.type === MESSAGE_TYPES.USER ? 'user' : 'assistant',
                content: m.content
            }));
        }

        clear() {
            this.messages = [];
            this.updatedAt = Date.now();
        }

        toJSON() {
            return {
                id: this.id,
                title: this.title,
                messages: this.messages.map(m => m.toJSON()),
                createdAt: this.createdAt,
                updatedAt: this.updatedAt,
                metadata: this.metadata
            };
        }
    }

    /**
     * 流式响应处理器
     */
    class StreamHandler {
        constructor(options = {}) {
            this.onChunk = options.onChunk || (() => {});
            this.onComplete = options.onComplete || (() => {});
            this.onError = options.onError || (() => {});
            this.accumulatedContent = '';
        }

        processChunk(chunk) {
            try {
                // 处理 SSE 格式数据
                if (chunk.startsWith('data: ')) {
                    const data = chunk.slice(6);
                    if (data === '[DONE]') {
                        this.onComplete(this.accumulatedContent);
                        return;
                    }
                    
                    const parsed = JSON.parse(data);
                    const content = parsed.choices?.[0]?.delta?.content || '';
                    
                    if (content) {
                        this.accumulatedContent += content;
                        this.onChunk(content, this.accumulatedContent);
                    }
                }
            } catch (error) {
                this.onError(error);
            }
        }
    }

    /**
     * 对话引擎主类
     */
    class ChatEngine {
        constructor(options = {}) {
            this.apiEndpoint = options.apiEndpoint || '/api/chat';
            this.apiKey = options.apiKey || '';
            this.model = options.model || 'default';
            this.sessions = new Map();
            this.currentSession = null;
            this.state = CHAT_STATES.IDLE;
            this.eventListeners = new Map();
            
            // 初始化默认会话
            this.createSession();
        }

        // 创建新会话
        createSession(options = {}) {
            const session = new ChatSession(options);
            this.sessions.set(session.id, session);
            this.currentSession = session;
            this.emit('sessionCreated', session);
            return session;
        }

        // 切换会话
        switchSession(sessionId) {
            const session = this.sessions.get(sessionId);
            if (session) {
                this.currentSession = session;
                this.emit('sessionSwitched', session);
                return true;
            }
            return false;
        }

        // 删除会话
        deleteSession(sessionId) {
            if (this.sessions.has(sessionId)) {
                this.sessions.delete(sessionId);
                if (this.currentSession?.id === sessionId) {
                    this.currentSession = this.sessions.values().next().value || null;
                }
                this.emit('sessionDeleted', sessionId);
                return true;
            }
            return false;
        }

        // 获取所有会话
        getSessions() {
            return Array.from(this.sessions.values());
        }

        // 发送消息
        async sendMessage(content, options = {}) {
            if (!this.currentSession) {
                throw new Error('No active session');
            }

            if (this.state === CHAT_STATES.STREAMING) {
                throw new Error('Already streaming');
            }

            // 创建用户消息
            const userMessage = new Message({
                type: MESSAGE_TYPES.USER,
                content: content
            });

            this.currentSession.addMessage(userMessage);
            this.emit('messageSent', userMessage);

            // 创建助手消息占位
            const assistantMessage = new Message({
                type: MESSAGE_TYPES.ASSISTANT,
                content: '',
                status: 'streaming'
            });

            this.currentSession.addMessage(assistantMessage);
            this.emit('messageReceived', assistantMessage);

            // 开始流式请求
            try {
                this.state = CHAT_STATES.STREAMING;
                this.emit('stateChange', this.state);

                await this.streamResponse(content, assistantMessage, options);

            } catch (error) {
                this.state = CHAT_STATES.ERROR;
                this.emit('stateChange', this.state);
                this.emit('error', error);
                
                assistantMessage.status = 'error';
                assistantMessage.metadata.error = error.message;
            }

            return assistantMessage;
        }

        // 流式响应
        async streamResponse(content, assistantMessage, options) {
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.apiKey}`
                },
                body: JSON.stringify({
                    model: options.model || this.model,
                    messages: [
                        ...this.currentSession.getContext(),
                        { role: 'user', content: content }
                    ],
                    stream: true
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            const streamHandler = new StreamHandler({
                onChunk: (chunk, accumulated) => {
                    assistantMessage.content = accumulated;
                    this.emit('streamChunk', { chunk, accumulated, message: assistantMessage });
                },
                onComplete: (finalContent) => {
                    assistantMessage.content = finalContent;
                    assistantMessage.status = 'complete';
                    this.state = CHAT_STATES.IDLE;
                    this.emit('stateChange', this.state);
                    this.emit('messageComplete', assistantMessage);
                },
                onError: (error) => {
                    throw error;
                }
            });

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.trim()) {
                        streamHandler.processChunk(line);
                    }
                }
            }
        }

        // 停止生成
        stopGeneration() {
            if (this.state === CHAT_STATES.STREAMING) {
                // 实现停止逻辑
                this.state = CHAT_STATES.IDLE;
                this.emit('stateChange', this.state);
                this.emit('generationStopped');
            }
        }

        // 重新生成
        async regenerate(messageId) {
            if (!this.currentSession) return;

            const messageIndex = this.currentSession.messages.findIndex(m => m.id === messageId);
            if (messageIndex === -1) return;

            // 找到对应的用户消息
            let userMessageIndex = messageIndex - 1;
            while (userMessageIndex >= 0 && 
                   this.currentSession.messages[userMessageIndex].type !== MESSAGE_TYPES.USER) {
                userMessageIndex--;
            }

            if (userMessageIndex >= 0) {
                const userMessage = this.currentSession.messages[userMessageIndex];
                
                // 删除当前助手消息及之后的消息
                this.currentSession.messages = this.currentSession.messages.slice(0, messageIndex);
                
                // 重新发送
                return this.sendMessage(userMessage.content);
            }
        }

        // 事件监听
        on(event, callback) {
            if (!this.eventListeners.has(event)) {
                this.eventListeners.set(event, []);
            }
            this.eventListeners.get(event).push(callback);
        }

        off(event, callback) {
            if (this.eventListeners.has(event)) {
                const listeners = this.eventListeners.get(event);
                const index = listeners.indexOf(callback);
                if (index > -1) {
                    listeners.splice(index, 1);
                }
            }
        }

        emit(event, data) {
            if (this.eventListeners.has(event)) {
                this.eventListeners.get(event).forEach(callback => {
                    try {
                        callback(data);
                    } catch (error) {
                        console.error(`[ChatEngine] Event handler error:`, error);
                    }
                });
            }
        }

        // 导出会话
        exportSession(sessionId) {
            const session = this.sessions.get(sessionId);
            if (session) {
                return JSON.stringify(session.toJSON(), null, 2);
            }
            return null;
        }

        // 导入会话
        importSession(json) {
            try {
                const data = JSON.parse(json);
                const session = new ChatSession(data);
                
                // 恢复消息对象
                if (data.messages) {
                    session.messages = data.messages.map(m => new Message(m));
                }

                this.sessions.set(session.id, session);
                this.emit('sessionImported', session);
                return session;
            } catch (error) {
                console.error('[ChatEngine] Import failed:', error);
                return null;
            }
        }
    }

    // 导出
    return {
        ChatEngine,
        ChatSession,
        Message,
        StreamHandler,
        MESSAGE_TYPES,
        CHAT_STATES
    };
}));
