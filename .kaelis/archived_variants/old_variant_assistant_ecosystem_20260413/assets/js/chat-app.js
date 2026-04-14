/**
 * Kaelis Chat Application
 * AI对话应用 - 整合引擎和UI
 */

(function() {
    'use strict';

    // 等待模块加载完成
    function initChatApp() {
        // 检查依赖模块是否可用
        if (!window.Kaelis || !window.Kaelis.ChatEngine || !window.Kaelis.ChatUI) {
            console.warn('[ChatApp] 等待模块加载...');
            setTimeout(initChatApp, 100);
            return;
        }

        const { ChatEngine, ChatSession, Message } = window.Kaelis.ChatEngine;
        const { ChatUI } = window.Kaelis.ChatUI;

        // 创建聊天引擎实例
        const engine = new ChatEngine({
            apiEndpoint: '/api/chat/completions',
            model: 'deepseek-chat'
        });

        // 创建UI实例
        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) {
            console.error('[ChatApp] 找不到聊天容器元素');
            return;
        }

        const ui = new ChatUI(chatContainer, {
            onSubmit: handleSubmit,
            onNewSession: handleNewSession,
            onSelectSession: handleSelectSession,
            onDeleteSession: handleDeleteSession,
            onRenameSession: handleRenameSession
        });

        // 处理消息提交
        async function handleSubmit(content) {
            // 添加用户消息到UI
            const userMessage = new Message({
                type: 'user',
                content: content
            });
            ui.addMessage(userMessage);

            // 禁用输入
            ui.disableInput();
            ui.showTyping();

            try {
                // 发送到引擎
                await engine.sendMessage(content, {
                    onChunk: (chunk, accumulated) => {
                        // 更新消息内容
                        const messages = engine.currentSession.messages;
                        const lastMessage = messages[messages.length - 1];
                        if (lastMessage && lastMessage.type === 'assistant') {
                            ui.updateMessage(lastMessage.id, accumulated);
                        }
                    }
                });

            } catch (error) {
                console.error('[ChatApp] 发送消息失败:', error);
                
                // 显示错误消息
                const errorMessage = new Message({
                    type: 'error',
                    content: '发送失败: ' + error.message
                });
                ui.addMessage(errorMessage);

            } finally {
                ui.hideTyping();
                ui.enableInput();
                updateSessionList();
            }
        }

        // 处理新建会话
        function handleNewSession() {
            const session = engine.createSession({
                title: '新对话 ' + (engine.getSessions().length + 1)
            });
            ui.clearMessages();
            updateSessionList();
            ui.setActiveSession(session.id);
        }

        // 处理切换会话
        function handleSelectSession(sessionId) {
            if (engine.switchSession(sessionId)) {
                ui.clearMessages();
                
                // 重新渲染消息
                const session = engine.currentSession;
                session.messages.forEach(message => {
                    ui.addMessage(message);
                });

                ui.setActiveSession(sessionId);
            }
        }

        // 处理删除会话
        function handleDeleteSession(sessionId) {
            if (confirm('确定要删除这个会话吗？')) {
                engine.deleteSession(sessionId);
                ui.clearMessages();
                updateSessionList();

                // 如果有当前会话，显示其消息
                if (engine.currentSession) {
                    engine.currentSession.messages.forEach(message => {
                        ui.addMessage(message);
                    });
                    ui.setActiveSession(engine.currentSession.id);
                }
            }
        }

        // 处理重命名会话
        function handleRenameSession(sessionId) {
            const session = engine.sessions.get(sessionId);
            if (!session) return;

            const newTitle = prompt('输入新标题:', session.title);
            if (newTitle && newTitle.trim()) {
                session.title = newTitle.trim();
                updateSessionList();
            }
        }

        // 更新会话列表
        function updateSessionList() {
            ui.renderSessions(engine.getSessions());
            if (engine.currentSession) {
                ui.setActiveSession(engine.currentSession.id);
            }
        }

        // 监听引擎事件
        engine.on('messageComplete', (message) => {
            updateSessionList();
        });

        engine.on('error', (error) => {
            console.error('[ChatApp] 引擎错误:', error);
            ui.hideTyping();
            ui.enableInput();
        });

        // 初始化
        updateSessionList();
        
        // 如果有当前会话，显示其消息
        if (engine.currentSession) {
            engine.currentSession.messages.forEach(message => {
                ui.addMessage(message);
            });
            ui.setActiveSession(engine.currentSession.id);
        }

        console.log('[ChatApp] 聊天应用已初始化');
    }

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChatApp);
    } else {
        initChatApp();
    }
})();
