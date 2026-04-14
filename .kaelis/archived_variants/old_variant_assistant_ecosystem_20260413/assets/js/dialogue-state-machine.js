/**
 * Kaelis Dialogue State Machine
 * 状态机与对话流程控制系统
 */

(function() {
    'use strict';

    // 状态定义
    const STATES = {
        // 顶层状态
        IDLE: {
            id: 'idle',
            name: '空闲',
            description: '等待用户输入',
            transitions: ['chat', 'task', 'error']
        },
        
        // 闲聊模式
        CHAT: {
            id: 'chat',
            name: '闲聊模式',
            description: '自由对话',
            parent: null,
            children: ['CHAT_GENERAL', 'CHAT_PERSONAL']
        },
        CHAT_GENERAL: {
            id: 'chat_general',
            name: '一般闲聊',
            parent: 'CHAT',
            transitions: ['chat_personal', 'task']
        },
        CHAT_PERSONAL: {
            id: 'chat_personal',
            name: '个人话题',
            parent: 'CHAT',
            transitions: ['chat_general', 'task']
        },
        
        // 任务模式
        TASK: {
            id: 'task',
            name: '任务模式',
            description: '执行具体任务',
            parent: null,
            children: ['TASK_INFO', 'TASK_EXEC', 'TASK_FEEDBACK']
        },
        TASK_INFO: {
            id: 'task_info',
            name: '信息收集',
            parent: 'TASK',
            children: ['TASK_INFO_REQUIRED', 'TASK_INFO_OPTIONAL']
        },
        TASK_INFO_REQUIRED: {
            id: 'task_info_required',
            name: '必填项收集',
            parent: 'TASK_INFO',
            transitions: ['task_info_optional', 'task_exec']
        },
        TASK_INFO_OPTIONAL: {
            id: 'task_info_optional',
            name: '可选项收集',
            parent: 'TASK_INFO',
            transitions: ['task_exec']
        },
        TASK_EXEC: {
            id: 'task_exec',
            name: '任务执行',
            parent: 'TASK',
            transitions: ['task_feedback', 'error']
        },
        TASK_FEEDBACK: {
            id: 'task_feedback',
            name: '结果反馈',
            parent: 'TASK',
            transitions: ['idle', 'task_exec']
        },
        
        // 异常处理模式
        ERROR: {
            id: 'error',
            name: '异常处理',
            description: '处理错误或异常',
            parent: null,
            children: ['ERROR_RECOVER', 'ERROR_ESCALATE']
        },
        ERROR_RECOVER: {
            id: 'error_recover',
            name: '错误恢复',
            parent: 'ERROR',
            transitions: ['idle', 'chat']
        },
        ERROR_ESCALATE: {
            id: 'error_escalate',
            name: '升级处理',
            parent: 'ERROR',
            transitions: ['idle']
        }
    };

    // 意图分类器
    class IntentClassifier {
        constructor() {
            this.intentPatterns = {
                // 闲聊意图
                greeting: {
                    patterns: ['你好', '嗨', 'hello', 'hi', '在吗'],
                    confidence: 0.9
                },
                personal: {
                    patterns: ['你觉得', '你喜欢', '你的', '私人的', '个人的'],
                    confidence: 0.8
                },
                
                // 任务意图
                search_repo: {
                    patterns: ['搜索', '查找', '找一下', '推荐', 'GitHub', '项目'],
                    confidence: 0.85
                },
                code_review: {
                    patterns: ['代码', 'review', '审查', '优化', 'bug'],
                    confidence: 0.85
                },
                info_query: {
                    patterns: ['查询', '获取', '查看', '显示', '列表'],
                    confidence: 0.8
                },
                
                // 控制意图
                confirm: {
                    patterns: ['确认', '是的', '对', '没错', 'ok', '好的'],
                    confidence: 0.95
                },
                cancel: {
                    patterns: ['取消', '放弃', '不', '算了', '退出'],
                    confidence: 0.95
                },
                back: {
                    patterns: ['返回', '回去', '上一步', '重来'],
                    confidence: 0.9
                },
                
                // 异常意图
                error: {
                    patterns: ['错误', '失败', '异常', 'bug', '问题'],
                    confidence: 0.85
                },
                help: {
                    patterns: ['帮助', '怎么用', '指南', '说明', '教教我'],
                    confidence: 0.9
                }
            };
        }

        classify(input) {
            const results = [];
            const lowerInput = input.toLowerCase();
            
            for (const [intent, config] of Object.entries(this.intentPatterns)) {
                let matched = false;
                let matchScore = 0;
                
                for (const pattern of config.patterns) {
                    if (lowerInput.includes(pattern.toLowerCase())) {
                        matched = true;
                        matchScore += 1;
                    }
                }
                
                if (matched) {
                    results.push({
                        intent,
                        confidence: Math.min(config.confidence * (matchScore / config.patterns.length), 1.0)
                    });
                }
            }
            
            // 按置信度排序
            results.sort((a, b) => b.confidence - a.confidence);
            
            return results.length > 0 ? results[0] : { intent: 'unknown', confidence: 0.5 };
        }
    }

    // POMDP 信念状态管理
    class BeliefState {
        constructor() {
            this.beliefs = new Map();
            this.history = [];
        }

        update(observation, action) {
            // 基于观察更新信念分布
            this.history.push({ observation, action, timestamp: Date.now() });
            
            // 简化的信念更新
            const possibleStates = this.getPossibleStates(observation);
            const totalProb = possibleStates.reduce((sum, s) => sum + s.probability, 0);
            
            // 归一化
            possibleStates.forEach(s => {
                s.probability /= totalProb;
                this.beliefs.set(s.state, s.probability);
            });
        }

        getPossibleStates(observation) {
            // 根据观察推断可能的状态
            const states = [];
            
            if (observation.intent === 'search_repo') {
                states.push({ state: 'TASK_INFO_REQUIRED', probability: 0.6 });
                states.push({ state: 'CHAT_GENERAL', probability: 0.4 });
            } else if (observation.intent === 'greeting') {
                states.push({ state: 'CHAT_GENERAL', probability: 0.8 });
                states.push({ state: 'IDLE', probability: 0.2 });
            } else if (observation.intent === 'error') {
                states.push({ state: 'ERROR_RECOVER', probability: 0.7 });
                states.push({ state: 'ERROR_ESCALATE', probability: 0.3 });
            } else {
                states.push({ state: 'CHAT_GENERAL', probability: 0.5 });
                states.push({ state: 'IDLE', probability: 0.5 });
            }
            
            return states;
        }

        getMostLikelyState() {
            let maxProb = 0;
            let mostLikely = 'IDLE';
            
            for (const [state, prob] of this.beliefs) {
                if (prob > maxProb) {
                    maxProb = prob;
                    mostLikely = state;
                }
            }
            
            return { state: mostLikely, probability: maxProb };
        }
    }

    // 对话状态机
    class DialogueStateMachine {
        constructor() {
            this.currentState = STATES.IDLE;
            this.stateStack = []; // 用于回退
            this.intentClassifier = new IntentClassifier();
            this.beliefState = new BeliefState();
            this.context = {};
            this.sessionData = {};
        }

        // 处理用户输入
        async processInput(input, context = {}) {
            // 1. 意图识别
            const intent = this.intentClassifier.classify(input);
            
            // 2. 更新信念状态
            this.beliefState.update(intent, this.currentState.id);
            
            // 3. 确定转移
            const transition = this.determineTransition(intent);
            
            // 4. 执行状态转移
            if (transition) {
                await this.transitionTo(transition.targetState, transition.data);
            }
            
            // 5. 生成响应
            const response = await this.generateResponse(input, intent);
            
            return {
                state: this.currentState.id,
                intent: intent.intent,
                confidence: intent.confidence,
                response,
                context: this.context
            };
        }

        // 确定状态转移
        determineTransition(intent) {
            const current = this.currentState;
            const belief = this.beliefState.getMostLikelyState();
            
            // 特殊处理：返回上一步
            if (intent.intent === 'back' && this.stateStack.length > 0) {
                return {
                    targetState: STATES[this.stateStack.pop()],
                    data: { action: 'back' }
                };
            }
            
            // 特殊处理：取消
            if (intent.intent === 'cancel') {
                return {
                    targetState: STATES.IDLE,
                    data: { action: 'cancel' }
                };
            }

            // 基于当前状态和意图确定转移
            switch (current.id) {
                case 'idle':
                    if (intent.intent === 'greeting' || intent.intent === 'personal') {
                        return { targetState: STATES.CHAT_GENERAL };
                    } else if (intent.intent === 'search_repo' || intent.intent === 'code_review') {
                        return { targetState: STATES.TASK_INFO_REQUIRED };
                    }
                    break;
                    
                case 'chat_general':
                    if (intent.intent === 'search_repo' || intent.intent === 'code_review') {
                        return { targetState: STATES.TASK_INFO_REQUIRED };
                    } else if (intent.intent === 'personal') {
                        return { targetState: STATES.CHAT_PERSONAL };
                    }
                    break;
                    
                case 'task_info_required':
                    if (intent.intent === 'confirm') {
                        return { targetState: STATES.TASK_EXEC };
                    } else if (intent.intent === 'info_query') {
                        return { targetState: STATES.TASK_INFO_OPTIONAL };
                    }
                    break;
                    
                case 'task_exec':
                    if (intent.intent === 'confirm' || intent.intent === 'info_query') {
                        return { targetState: STATES.TASK_FEEDBACK };
                    } else if (intent.intent === 'error') {
                        return { targetState: STATES.ERROR_RECOVER };
                    }
                    break;
                    
                case 'error_recover':
                    if (intent.intent === 'confirm') {
                        return { targetState: STATES.IDLE };
                    }
                    break;
            }
            
            // 默认：保持在当前状态
            return null;
        }

        // 执行状态转移
        async transitionTo(newState, data = {}) {
            // 保存当前状态到栈
            if (this.currentState && data.action !== 'back') {
                this.stateStack.push(this.currentState.id);
            }
            
            // 执行退出动作
            await this.onExitState(this.currentState);
            
            // 更新状态
            this.currentState = newState;
            
            // 执行进入动作
            await this.onEnterState(newState, data);
            
            console.log(`[StateMachine] 状态转移: ${this.stateStack[this.stateStack.length - 1] || 'none'} -> ${newState.id}`);
        }

        // 进入状态回调
        async onEnterState(state, data) {
            switch (state.id) {
                case 'task_info_required':
                    this.context.taskStarted = true;
                    this.context.requiredInfo = [];
                    break;
                case 'task_exec':
                    this.context.taskExecuting = true;
                    break;
                case 'task_feedback':
                    this.context.taskCompleted = true;
                    break;
            }
        }

        // 退出状态回调
        async onExitState(state) {
            // 清理状态特定数据
            if (state && state.id === 'task_exec') {
                this.context.taskExecuting = false;
            }
        }

        // 生成响应
        async generateResponse(input, intent) {
            const state = this.currentState;
            
            // 基于状态和意图生成响应
            const responses = {
                'idle': {
                    'greeting': '你好！我是 Kaelis AI 助手。有什么可以帮助你的吗？',
                    'default': '请告诉我您需要什么帮助。'
                },
                'chat_general': {
                    'personal': '作为 AI，我没有个人情感，但我很乐意和你聊天！',
                    'default': '我明白了。还有其他想了解的吗？'
                },
                'task_info_required': {
                    'search_repo': '我来帮您搜索 GitHub 仓库。请告诉我您想搜索什么？',
                    'code_review': '我可以帮您审查代码。请提供代码或仓库链接。',
                    'default': '请提供更多信息，以便我更好地帮助您。'
                },
                'task_exec': {
                    'default': '正在处理您的请求，请稍候...'
                },
                'task_feedback': {
                    'default': '任务已完成！还有其他需要帮助的吗？'
                },
                'error_recover': {
                    'default': '抱歉遇到了问题。让我重新尝试，或者您可以换个方式描述需求。'
                }
            };
            
            const stateResponses = responses[state.id] || responses['idle'];
            return stateResponses[intent.intent] || stateResponses['default'];
        }

        // 获取当前状态信息
        getCurrentState() {
            return {
                ...this.currentState,
                belief: this.beliefState.getMostLikelyState(),
                canGoBack: this.stateStack.length > 0
            };
        }

        // 重置状态机
        reset() {
            this.currentState = STATES.IDLE;
            this.stateStack = [];
            this.beliefState = new BeliefState();
            this.context = {};
            this.sessionData = {};
        }

        // 获取状态历史
        getStateHistory() {
            return [...this.stateStack];
        }
    }

    // 对话流程控制器
    class DialogueFlowController {
        constructor() {
            this.stateMachine = new DialogueStateMachine();
            this.flows = new Map();
        }

        // 注册流程
        registerFlow(flowId, flowConfig) {
            this.flows.set(flowId, {
                id: flowId,
                states: flowConfig.states,
                transitions: flowConfig.transitions,
                onComplete: flowConfig.onComplete
            });
        }

        // 启动流程
        async startFlow(flowId, initialData = {}) {
            const flow = this.flows.get(flowId);
            if (!flow) {
                throw new Error(`流程未注册: ${flowId}`);
            }

            this.stateMachine.reset();
            this.stateMachine.sessionData = {
                flowId,
                ...initialData
            };

            return await this.stateMachine.processInput('start');
        }

        // 处理输入
        async handleInput(input, context = {}) {
            return await this.stateMachine.processInput(input, context);
        }

        // 获取状态
        getState() {
            return this.stateMachine.getCurrentState();
        }
    }

    // 导出 - UMD格式
    const exports = {
        DialogueStateMachine,
        DialogueFlowController,
        STATES,
        TRANSITIONS,
        INTENTS
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.Dialogue = exports;
        // 保持向后兼容
        window.DialogueStateMachine = DialogueStateMachine;
        window.DialogueFlowController = DialogueFlowController;
        window.dialogueController = new DialogueFlowController();
    }

    console.log('[DialogueStateMachine] 对话状态机已加载');
})();
