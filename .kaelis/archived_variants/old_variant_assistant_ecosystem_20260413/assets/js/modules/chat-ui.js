/**
 * Kaelis Chat UI
 * AI对话UI组件 - 消息渲染、输入处理、界面交互
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.ChatUI = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';

    /**
     * 消息渲染器
     */
    class MessageRenderer {
        constructor(container) {
            this.container = container;
            this.templates = {
                user: this.createUserTemplate(),
                assistant: this.createAssistantTemplate(),
                system: this.createSystemTemplate(),
                typing: this.createTypingTemplate()
            };
        }

        createUserTemplate() {
            return (message) => `
                <div class="message message-user" data-message-id="${message.id}">
                    <div class="message-content">
                        <div class="message-text">${this.escapeHtml(message.content)}</div>
                        <div class="message-time">${this.formatTime(message.timestamp)}</div>
                    </div>
                    <div class="message-avatar user-avatar">我</div>
                </div>
            `;
        }

        createAssistantTemplate() {
            return (message) => `
                <div class="message message-assistant" data-message-id="${message.id}">
                    <div class="message-avatar ai-avatar">
                        <img src="../assets/images/ai-avatar.svg" alt="AI">
                    </div>
                    <div class="message-content">
                        <div class="message-text">${this.formatContent(message.content)}</div>
                        ${message.status === 'streaming' ? '<span class="typing-cursor">|</span>' : ''}
                        <div class="message-actions">
                            <button class="btn-icon" data-action="copy" title="复制">📋</button>
                            <button class="btn-icon" data-action="regenerate" title="重新生成">🔄</button>
                            ${message.status === 'streaming' ? 
                                '<button class="btn-icon" data-action="stop" title="停止">⏹️</button>' : ''}
                        </div>
                        <div class="message-time">${this.formatTime(message.timestamp)}</div>
                    </div>
                </div>
            `;
        }

        createSystemTemplate() {
            return (message) => `
                <div class="message message-system" data-message-id="${message.id}">
                    <div class="message-content">
                        <div class="message-text">${this.escapeHtml(message.content)}</div>
                    </div>
                </div>
            `;
        }

        createTypingTemplate() {
            return () => `
                <div class="message message-typing">
                    <div class="message-avatar ai-avatar">
                        <img src="../assets/images/ai-avatar.svg" alt="AI">
                    </div>
                    <div class="message-content">
                        <div class="typing-indicator">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </div>
                </div>
            `;
        }

        render(message) {
            const template = this.templates[message.type] || this.templates.system;
            const html = template(message);
            const wrapper = document.createElement('div');
            wrapper.innerHTML = html;
            return wrapper.firstElementChild;
        }

        update(messageId, content) {
            const messageEl = this.container.querySelector(`[data-message-id="${messageId}"]`);
            if (messageEl) {
                const textEl = messageEl.querySelector('.message-text');
                if (textEl) {
                    textEl.innerHTML = this.formatContent(content);
                }
            }
        }

        remove(messageId) {
            const messageEl = this.container.querySelector(`[data-message-id="${messageId}"]`);
            if (messageEl) {
                messageEl.remove();
            }
        }

        clear() {
            this.container.innerHTML = '';
        }

        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        formatContent(content) {
            // 简单的 Markdown 格式化
            return content
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
                .replace(/\*([^*]+)\*/g, '<em>$1</em>')
                .replace(/\n/g, '<br>');
        }

        formatTime(timestamp) {
            const date = new Date(timestamp);
            return date.toLocaleTimeString('zh-CN', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        }
    }

    /**
     * 输入处理器
     */
    class InputHandler {
        constructor(inputElement, options = {}) {
            this.input = inputElement;
            this.onSubmit = options.onSubmit || (() => {});
            this.onTyping = options.onTyping || (() => {});
            this.maxLength = options.maxLength || 4000;
            
            this.init();
        }

        init() {
            // 自动调整高度
            this.input.addEventListener('input', () => {
                this.autoResize();
                this.onTyping(this.input.value);
            });

            // 键盘事件
            this.input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.submit();
                }
            });

            // 粘贴处理
            this.input.addEventListener('paste', (e) => {
                this.handlePaste(e);
            });
        }

        autoResize() {
            this.input.style.height = 'auto';
            this.input.style.height = Math.min(this.input.scrollHeight, 200) + 'px';
        }

        submit() {
            const content = this.input.value.trim();
            if (content && content.length <= this.maxLength) {
                this.onSubmit(content);
                this.clear();
            }
        }

        clear() {
            this.input.value = '';
            this.input.style.height = 'auto';
        }

        handlePaste(e) {
            // 处理粘贴的图片或文件
            const items = e.clipboardData.items;
            for (let item of items) {
                if (item.type.indexOf('image') !== -1) {
                    e.preventDefault();
                    const file = item.getAsFile();
                    this.handleImagePaste(file);
                }
            }
        }

        handleImagePaste(file) {
            // 触发图片粘贴事件
            const event = new CustomEvent('imagePasted', { detail: { file } });
            this.input.dispatchEvent(event);
        }

        focus() {
            this.input.focus();
        }

        setPlaceholder(text) {
            this.input.placeholder = text;
        }

        disable() {
            this.input.disabled = true;
        }

        enable() {
            this.input.disabled = false;
            this.focus();
        }
    }

    /**
     * 会话列表UI
     */
    class SessionListUI {
        constructor(container, options = {}) {
            this.container = container;
            this.onSelect = options.onSelect || (() => {});
            this.onDelete = options.onDelete || (() => {});
            this.onRename = options.onRename || (() => {});
        }

        render(sessions) {
            this.container.innerHTML = sessions.map(session => `
                <div class="session-item ${session.id === this.activeSessionId ? 'active' : ''}" 
                     data-session-id="${session.id}">
                    <div class="session-icon">💬</div>
                    <div class="session-info">
                        <div class="session-title">${this.escapeHtml(session.title)}</div>
                        <div class="session-preview">${this.getPreview(session)}</div>
                    </div>
                    <div class="session-actions">
                        <button class="btn-icon btn-rename" title="重命名">✏️</button>
                        <button class="btn-icon btn-delete" title="删除">🗑️</button>
                    </div>
                </div>
            `).join('');

            this.bindEvents();
        }

        bindEvents() {
            this.container.querySelectorAll('.session-item').forEach(item => {
                const sessionId = item.dataset.sessionId;

                item.addEventListener('click', (e) => {
                    if (!e.target.closest('.session-actions')) {
                        this.onSelect(sessionId);
                    }
                });

                const renameBtn = item.querySelector('.btn-rename');
                if (renameBtn) {
                    renameBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.onRename(sessionId);
                    });
                }

                const deleteBtn = item.querySelector('.btn-delete');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.onDelete(sessionId);
                    });
                }
            });
        }

        setActive(sessionId) {
            this.activeSessionId = sessionId;
            this.container.querySelectorAll('.session-item').forEach(item => {
                item.classList.toggle('active', item.dataset.sessionId === sessionId);
            });
        }

        getPreview(session) {
            const lastMessage = session.messages[session.messages.length - 1];
            if (lastMessage) {
                return this.escapeHtml(lastMessage.content.substring(0, 50) + '...');
            }
            return '无消息';
        }

        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    }

    /**
     * 主UI类
     */
    class ChatUI {
        constructor(container, options = {}) {
            this.container = container;
            this.options = options;
            
            this.elements = {
                messages: null,
                input: null,
                sendBtn: null,
                sessionList: null,
                newSessionBtn: null
            };

            this.renderer = null;
            this.inputHandler = null;
            this.sessionListUI = null;

            this.init();
        }

        init() {
            this.createLayout();
            this.initComponents();
        }

        createLayout() {
            this.container.innerHTML = `
                <div class="chat-container">
                    <aside class="chat-sidebar">
                        <button class="btn btn-primary btn-new-session">
                            <span>+</span> 新对话
                        </button>
                        <div class="session-list"></div>
                    </aside>
                    <main class="chat-main">
                        <div class="messages-container"></div>
                        <div class="input-container">
                            <div class="input-wrapper">
                                <textarea 
                                    class="chat-input" 
                                    placeholder="输入消息... (Shift+Enter换行)"
                                    rows="1"
                                ></textarea>
                                <button class="btn btn-primary btn-send">
                                    <svg viewBox="0 0 24 24" width="20" height="20">
                                        <path fill="currentColor" d="M2 21l21-9L2 3v7l15 2-15 2v7z"/>
                                    </svg>
                                </button>
                            </div>
                            <div class="input-hints">
                                <span>Shift + Enter 换行</span>
                                <span class="char-count">0/4000</span>
                            </div>
                        </div>
                    </main>
                </div>
            `;

            this.elements.messages = this.container.querySelector('.messages-container');
            this.elements.input = this.container.querySelector('.chat-input');
            this.elements.sendBtn = this.container.querySelector('.btn-send');
            this.elements.sessionList = this.container.querySelector('.session-list');
            this.elements.newSessionBtn = this.container.querySelector('.btn-new-session');
        }

        initComponents() {
            // 消息渲染器
            this.renderer = new MessageRenderer(this.elements.messages);

            // 输入处理器
            this.inputHandler = new InputHandler(this.elements.input, {
                onSubmit: (content) => this.emit('submit', content),
                onTyping: (content) => this.updateCharCount(content.length)
            });

            // 发送按钮
            this.elements.sendBtn.addEventListener('click', () => {
                this.inputHandler.submit();
            });

            // 会话列表
            this.sessionListUI = new SessionListUI(this.elements.sessionList, {
                onSelect: (sessionId) => this.emit('selectSession', sessionId),
                onDelete: (sessionId) => this.emit('deleteSession', sessionId),
                onRename: (sessionId) => this.emit('renameSession', sessionId)
            });

            // 新建会话按钮
            this.elements.newSessionBtn.addEventListener('click', () => {
                this.emit('newSession');
            });
        }

        updateCharCount(count) {
            const counter = this.container.querySelector('.char-count');
            if (counter) {
                counter.textContent = `${count}/4000`;
                counter.classList.toggle('warning', count > 3500);
            }
        }

        addMessage(message) {
            const el = this.renderer.render(message);
            this.elements.messages.appendChild(el);
            this.scrollToBottom();
            return el;
        }

        updateMessage(messageId, content) {
            this.renderer.update(messageId, content);
        }

        removeMessage(messageId) {
            this.renderer.remove(messageId);
        }

        clearMessages() {
            this.renderer.clear();
        }

        scrollToBottom() {
            this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
        }

        showTyping() {
            this.hideTyping();
            const el = this.renderer.render({ type: 'typing' });
            el.classList.add('typing-indicator-container');
            this.elements.messages.appendChild(el);
            this.scrollToBottom();
        }

        hideTyping() {
            const typing = this.container.querySelector('.typing-indicator-container');
            if (typing) {
                typing.remove();
            }
        }

        renderSessions(sessions) {
            this.sessionListUI.render(sessions);
        }

        setActiveSession(sessionId) {
            this.sessionListUI.setActive(sessionId);
        }

        disableInput() {
            this.inputHandler.disable();
            this.elements.sendBtn.disabled = true;
        }

        enableInput() {
            this.inputHandler.enable();
            this.elements.sendBtn.disabled = false;
        }

        // 事件系统
        emit(event, data) {
            if (this.options[`on${event.charAt(0).toUpperCase() + event.slice(1)}`]) {
                this.options[`on${event.charAt(0).toUpperCase() + event.slice(1)}`](data);
            }
        }
    }

    // 导出
    return {
        ChatUI,
        MessageRenderer,
        InputHandler,
        SessionListUI
    };
}));
