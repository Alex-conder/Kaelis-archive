/**
 * Kaelis User Role Inference System
 * 用户角色推断系统
 */

(function() {
    'use strict';

    // 用户角色定义
    const USER_ROLES = {
        STUDENT: {
            id: 'student',
            name: '学生',
            description: '在校学生，关注学习、作业、考试等',
            characteristics: ['学习', '作业', '考试', '论文', '课程', '老师', '同学'],
            priority: 1
        },
        DEVELOPER: {
            id: 'developer',
            name: '开发者',
            description: '软件开发者，关注代码、技术、项目等',
            characteristics: ['代码', '编程', '开发', 'bug', 'git', 'API', '框架', '部署'],
            priority: 2
        },
        RESEARCHER: {
            id: 'researcher',
            name: '研究人员',
            description: '科研人员，关注论文、实验、数据等',
            characteristics: ['研究', '论文', '实验', '数据', '分析', '文献', '发表', '期刊'],
            priority: 3
        },
        PRODUCT_MANAGER: {
            id: 'product_manager',
            name: '产品经理',
            description: '产品经理，关注需求、用户、规划等',
            characteristics: ['产品', '需求', '用户', '规划', '设计', '迭代', 'PRD', '原型'],
            priority: 4
        },
        DESIGNER: {
            id: 'designer',
            name: '设计师',
            description: '设计师，关注UI、UX、视觉等',
            characteristics: ['设计', 'UI', 'UX', '视觉', '配色', '布局', 'Figma', 'Sketch'],
            priority: 5
        },
        BUSINESS_USER: {
            id: 'business_user',
            name: '商务用户',
            description: '商务人士，关注报告、数据、决策等',
            characteristics: ['报告', '数据', '分析', '决策', '市场', '客户', '销售', 'KPI'],
            priority: 6
        },
        GENERAL_USER: {
            id: 'general_user',
            name: '普通用户',
            description: '一般用户，无特定专业背景',
            characteristics: ['帮助', '问题', '使用', '功能', '设置'],
            priority: 7
        }
    };

    // 规则引擎
    class RuleEngine {
        constructor() {
            this.rules = [];
            this.initRules();
        }

        initRules() {
            // 基于关键词的规则
            this.rules.push({
                name: 'student_keywords',
                type: 'keyword',
                condition: (input) => {
                    const keywords = ['作业', '考试', '论文', '课程', '学分', '绩点', '导师'];
                    return keywords.some(k => input.includes(k));
                },
                action: () => ({ role: 'student', confidence: 0.85 })
            });

            this.rules.push({
                name: 'developer_keywords',
                type: 'keyword',
                condition: (input) => {
                    const keywords = ['代码', '编程', 'git', 'github', 'api', 'bug', 'debug', '部署'];
                    return keywords.some(k => input.includes(k));
                },
                action: () => ({ role: 'developer', confidence: 0.9 })
            });

            this.rules.push({
                name: 'researcher_keywords',
                type: 'keyword',
                condition: (input) => {
                    const keywords = ['论文', '研究', '实验', '数据', '文献', '期刊', '引用'];
                    return keywords.some(k => input.includes(k));
                },
                action: () => ({ role: 'researcher', confidence: 0.85 })
            });

            this.rules.push({
                name: 'product_manager_keywords',
                type: 'keyword',
                condition: (input) => {
                    const keywords = ['产品', '需求', 'PRD', '原型', '迭代', '用户调研'];
                    return keywords.some(k => input.includes(k));
                },
                action: () => ({ role: 'product_manager', confidence: 0.8 })
            });

            this.rules.push({
                name: 'designer_keywords',
                type: 'keyword',
                condition: (input) => {
                    const keywords = ['设计', 'UI', 'UX', 'Figma', '配色', '布局', '视觉'];
                    return keywords.some(k => input.includes(k));
                },
                action: () => ({ role: 'designer', confidence: 0.8 })
            });

            // 基于行为的规则
            this.rules.push({
                name: 'frequent_code_search',
                type: 'behavior',
                condition: (behavior) => behavior.codeSearchCount > 5,
                action: () => ({ role: 'developer', confidence: 0.75 })
            });

            this.rules.push({
                name: 'frequent_document_reading',
                type: 'behavior',
                condition: (behavior) => behavior.docReadCount > 10,
                action: () => ({ role: 'researcher', confidence: 0.7 })
            });

            // 基于上下文的规则
            this.rules.push({
                name: 'project_context',
                type: 'context',
                condition: (context) => context.currentProject === 'academic',
                action: () => ({ role: 'student', confidence: 0.7 })
            });
        }

        evaluate(input, behavior = {}, context = {}) {
            const results = [];

            for (const rule of this.rules) {
                let matched = false;
                let result = null;

                switch (rule.type) {
                    case 'keyword':
                        matched = rule.condition(input);
                        break;
                    case 'behavior':
                        matched = rule.condition(behavior);
                        break;
                    case 'context':
                        matched = rule.condition(context);
                        break;
                }

                if (matched) {
                    result = rule.action();
                    results.push({
                        rule: rule.name,
                        type: rule.type,
                        ...result
                    });
                }
            }

            return results;
        }
    }

    // 机器学习推断器（简化版）
    class MLInference {
        constructor() {
            this.model = null;
            this.featureExtractor = new FeatureExtractor();
        }

        async predict(input, history = []) {
            // 特征提取
            const features = this.featureExtractor.extract(input, history);
            
            // 简化的分类逻辑（实际应使用训练好的模型）
            const scores = this.calculateScores(features);
            
            // 返回最高分的角色
            let maxRole = 'general_user';
            let maxScore = 0;
            
            for (const [role, score] of Object.entries(scores)) {
                if (score > maxScore) {
                    maxScore = score;
                    maxRole = role;
                }
            }

            return {
                role: maxRole,
                confidence: Math.min(maxScore, 1.0),
                scores
            };
        }

        calculateScores(features) {
            const scores = {};
            
            for (const [roleId, role] of Object.entries(USER_ROLES)) {
                let score = 0.3; // 基础分
                
                // 关键词匹配
                for (const char of role.characteristics) {
                    if (features.keywords.includes(char)) {
                        score += 0.15;
                    }
                }
                
                // 行为特征匹配
                if (role.id === 'developer' && features.codeRelated) {
                    score += 0.2;
                }
                if (role.id === 'student' && features.academicRelated) {
                    score += 0.2;
                }
                
                scores[role.id] = Math.min(score, 1.0);
            }
            
            return scores;
        }
    }

    // 特征提取器
    class FeatureExtractor {
        extract(input, history = []) {
            const features = {
                keywords: [],
                codeRelated: false,
                academicRelated: false,
                businessRelated: false,
                queryLength: input.length,
                historyLength: history.length
            };

            // 提取关键词
            const allKeywords = [
                ...USER_ROLES.STUDENT.characteristics,
                ...USER_ROLES.DEVELOPER.characteristics,
                ...USER_ROLES.RESEARCHER.characteristics,
                ...USER_ROLES.PRODUCT_MANAGER.characteristics,
                ...USER_ROLES.DESIGNER.characteristics,
                ...USER_ROLES.BUSINESS_USER.characteristics
            ];

            for (const keyword of allKeywords) {
                if (input.includes(keyword)) {
                    features.keywords.push(keyword);
                }
            }

            // 检测代码相关
            const codePatterns = [
                /function\s+\w+/, /const\s+\w+/, /let\s+\w+/,
                /import\s+.*from/, /class\s+\w+/, /=>\s*{/,
                /git\s+\w+/, /npm\s+\w+/, /pip\s+\w+/
            ];
            features.codeRelated = codePatterns.some(p => p.test(input));

            // 检测学术相关
            const academicPatterns = [
                /\d{4}\s*年/, /第\s*\d+\s*卷/, /DOI[:\s]/i,
                /et\s+al\./i, /参考文献/, /摘要/
            ];
            features.academicRelated = academicPatterns.some(p => p.test(input));

            // 检测商务相关
            const businessPatterns = [
                /报告/, /数据/, /KPI/, /ROI/, /Q\d/, /FY\d{4}/
            ];
            features.businessRelated = businessPatterns.some(p => p.test(input));

            return features;
        }
    }

    // 角色推断引擎
    class RoleInferenceEngine {
        constructor() {
            this.ruleEngine = new RuleEngine();
            this.mlInference = new MLInference();
            this.inferenceHistory = [];
            this.roleConfidence = new Map();
        }

        async infer(input, options = {}) {
            const { behavior = {}, context = {}, history = [] } = options;
            
            // 1. 规则引擎推断
            const ruleResults = this.ruleEngine.evaluate(input, behavior, context);
            
            // 2. ML 推断
            const mlResult = await this.mlInference.predict(input, history);
            
            // 3. 融合结果
            const fusedResult = this.fuseResults(ruleResults, mlResult);
            
            // 4. 更新历史
            this.inferenceHistory.push({
                input: input.substring(0, 100),
                result: fusedResult,
                timestamp: Date.now()
            });

            // 5. 限制历史长度
            if (this.inferenceHistory.length > 100) {
                this.inferenceHistory.shift();
            }

            return fusedResult;
        }

        fuseResults(ruleResults, mlResult) {
            // 初始化角色分数
            const roleScores = {};
            for (const roleId of Object.keys(USER_ROLES)) {
                roleScores[roleId] = 0;
            }

            // 规则引擎结果加权
            for (const result of ruleResults) {
                const weight = result.type === 'keyword' ? 0.4 : 0.3;
                roleScores[result.role] += result.confidence * weight;
            }

            // ML 结果加权
            for (const [role, score] of Object.entries(mlResult.scores)) {
                roleScores[role] += score * 0.3;
            }

            // 归一化并找出最高分
            let maxRole = 'general_user';
            let maxScore = 0;
            let totalScore = 0;

            for (const [role, score] of Object.entries(roleScores)) {
                totalScore += score;
                if (score > maxScore) {
                    maxScore = score;
                    maxRole = role;
                }
            }

            // 计算置信度
            const confidence = totalScore > 0 ? maxScore / totalScore : 0;

            // 构建角色分布
            const distribution = {};
            for (const [role, score] of Object.entries(roleScores)) {
                distribution[role] = totalScore > 0 ? score / totalScore : 0;
            }

            return {
                role: maxRole,
                roleInfo: USER_ROLES[maxRole.toUpperCase()],
                confidence: Math.min(confidence * 1.5, 1.0), // 调整置信度
                distribution,
                ruleMatches: ruleResults.length,
                mlConfidence: mlResult.confidence
            };
        }

        // 获取角色特定的响应风格
        getResponseStyle(role) {
            const styles = {
                student: {
                    tone: 'friendly',
                    formality: 'casual',
                    examples: true,
                    stepByStep: true
                },
                developer: {
                    tone: 'technical',
                    formality: 'neutral',
                    codeExamples: true,
                    concise: true
                },
                researcher: {
                    tone: 'academic',
                    formality: 'formal',
                    citations: true,
                    detailed: true
                },
                product_manager: {
                    tone: 'business',
                    formality: 'professional',
                    metrics: true,
                    actionable: true
                },
                designer: {
                    tone: 'creative',
                    formality: 'casual',
                    visual: true,
                    inspirational: true
                },
                business_user: {
                    tone: 'professional',
                    formality: 'formal',
                    dataDriven: true,
                    executive: true
                },
                general_user: {
                    tone: 'helpful',
                    formality: 'neutral',
                    simple: true
                }
            };

            return styles[role] || styles.general_user;
        }

        // 获取推断历史
        getHistory(limit = 10) {
            return this.inferenceHistory.slice(-limit);
        }

        // 获取最可能的角色（基于历史）
        getDominantRole() {
            if (this.inferenceHistory.length === 0) {
                return { role: 'general_user', confidence: 1.0 };
            }

            const roleCounts = {};
            for (const record of this.inferenceHistory) {
                const role = record.result.role;
                roleCounts[role] = (roleCounts[role] || 0) + 1;
            }

            let maxRole = 'general_user';
            let maxCount = 0;
            const total = this.inferenceHistory.length;

            for (const [role, count] of Object.entries(roleCounts)) {
                if (count > maxCount) {
                    maxCount = count;
                    maxRole = role;
                }
            }

            return {
                role: maxRole,
                confidence: maxCount / total,
                distribution: roleCounts
            };
        }
    }

    // 用户画像管理器
    class UserProfileManager {
        constructor() {
            this.profiles = new Map();
            this.inferenceEngine = new RoleInferenceEngine();
        }

        async createProfile(userId, initialData = {}) {
            const profile = {
                userId,
                createdAt: Date.now(),
                updatedAt: Date.now(),
                inferredRole: 'general_user',
                roleConfidence: 0,
                roleHistory: [],
                preferences: {},
                behaviorStats: {
                    totalQueries: 0,
                    codeQueries: 0,
                    academicQueries: 0,
                    businessQueries: 0
                },
                ...initialData
            };

            this.profiles.set(userId, profile);
            return profile;
        }

        async updateProfile(userId, input, context = {}) {
            let profile = this.profiles.get(userId);
            if (!profile) {
                profile = await this.createProfile(userId);
            }

            // 推断角色
            const inference = await this.inferenceEngine.infer(input, {
                behavior: profile.behaviorStats,
                context,
                history: profile.roleHistory
            });

            // 更新角色
            profile.inferredRole = inference.role;
            profile.roleConfidence = inference.confidence;
            profile.roleHistory.push({
                role: inference.role,
                confidence: inference.confidence,
                timestamp: Date.now()
            });

            // 限制历史长度
            if (profile.roleHistory.length > 50) {
                profile.roleHistory.shift();
            }

            // 更新行为统计
            profile.behaviorStats.totalQueries++;
            if (inference.role === 'developer') {
                profile.behaviorStats.codeQueries++;
            } else if (inference.role === 'student' || inference.role === 'researcher') {
                profile.behaviorStats.academicQueries++;
            } else if (inference.role === 'business_user' || inference.role === 'product_manager') {
                profile.behaviorStats.businessQueries++;
            }

            profile.updatedAt = Date.now();

            return {
                profile,
                inference
            };
        }

        getProfile(userId) {
            return this.profiles.get(userId);
        }

        getResponseStyle(userId) {
            const profile = this.profiles.get(userId);
            if (!profile) {
                return this.inferenceEngine.getResponseStyle('general_user');
            }
            return this.inferenceEngine.getResponseStyle(profile.inferredRole);
        }
    }

    // 导出 - UMD格式
    const exports = {
        USER_ROLES,
        RoleInferenceEngine,
        UserProfileManager,
        RuleEngine,
        MLInference
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.UserRoleInference = exports;
        // 保持向后兼容
        window.UserRoleInference = exports;
        window.roleInferenceEngine = new RoleInferenceEngine();
        window.userProfileManager = new UserProfileManager();
    }

    console.log('[UserRoleInference] 用户角色推断系统已加载');
})();
