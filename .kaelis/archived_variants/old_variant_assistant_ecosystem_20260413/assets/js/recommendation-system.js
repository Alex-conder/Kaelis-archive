/**
 * Kaelis Recommendation System
 * 个性化推荐系统
 */

(function() {
    'use strict';

    // 推荐类型
    const RECOMMENDATION_TYPES = {
        PLUGIN: 'plugin',
        CONTENT: 'content',
        WORKFLOW: 'workflow',
        KNOWLEDGE: 'knowledge'
    };

    // 协同过滤引擎
    class CollaborativeFiltering {
        constructor() {
            this.userItemMatrix = new Map();
            this.itemUserMatrix = new Map();
            this.userSimilarities = new Map();
        }

        // 记录用户行为
        recordInteraction(userId, itemId, rating = 1) {
            if (!this.userItemMatrix.has(userId)) {
                this.userItemMatrix.set(userId, new Map());
            }
            this.userItemMatrix.get(userId).set(itemId, rating);

            if (!this.itemUserMatrix.has(itemId)) {
                this.itemUserMatrix.set(itemId, new Map());
            }
            this.itemUserMatrix.get(itemId).set(userId, rating);
        }

        // 计算用户相似度（余弦相似度）
        calculateUserSimilarity(userId1, userId2) {
            const items1 = this.userItemMatrix.get(userId1);
            const items2 = this.userItemMatrix.get(userId2);

            if (!items1 || !items2) return 0;

            const commonItems = [];
            for (const item of items1.keys()) {
                if (items2.has(item)) {
                    commonItems.push(item);
                }
            }

            if (commonItems.length === 0) return 0;

            let dotProduct = 0;
            let norm1 = 0;
            let norm2 = 0;

            for (const item of commonItems) {
                const r1 = items1.get(item);
                const r2 = items2.get(item);
                dotProduct += r1 * r2;
            }

            for (const rating of items1.values()) {
                norm1 += rating * rating;
            }

            for (const rating of items2.values()) {
                norm2 += rating * rating;
            }

            return dotProduct / (Math.sqrt(norm1) * Math.sqrt(norm2));
        }

        // 获取相似用户
        getSimilarUsers(userId, k = 5) {
            const similarities = [];

            for (const otherUserId of this.userItemMatrix.keys()) {
                if (otherUserId !== userId) {
                    const similarity = this.calculateUserSimilarity(userId, otherUserId);
                    if (similarity > 0) {
                        similarities.push({ userId: otherUserId, similarity });
                    }
                }
            }

            similarities.sort((a, b) => b.similarity - a.similarity);
            return similarities.slice(0, k);
        }

        // 推荐物品
        recommend(userId, n = 5) {
            const userItems = this.userItemMatrix.get(userId);
            if (!userItems) return [];

            const similarUsers = this.getSimilarUsers(userId, 10);
            const recommendations = new Map();

            for (const { userId: similarUserId, similarity } of similarUsers) {
                const similarUserItems = this.userItemMatrix.get(similarUserId);

                for (const [itemId, rating] of similarUserItems) {
                    if (!userItems.has(itemId)) {
                        const currentScore = recommendations.get(itemId) || 0;
                        recommendations.set(itemId, currentScore + similarity * rating);
                    }
                }
            }

            const sorted = Array.from(recommendations.entries())
                .sort((a, b) => b[1] - a[1])
                .slice(0, n);

            return sorted.map(([itemId, score]) => ({ itemId, score }));
        }
    }

    // 内容推荐引擎
    class ContentBasedFiltering {
        constructor() {
            this.itemFeatures = new Map();
            this.userProfiles = new Map();
        }

        // 设置物品特征
        setItemFeatures(itemId, features) {
            this.itemFeatures.set(itemId, features);
        }

        // 更新用户画像
        updateUserProfile(userId, itemId, interaction = 1) {
            const itemFeatures = this.itemFeatures.get(itemId);
            if (!itemFeatures) return;

            if (!this.userProfiles.has(userId)) {
                this.userProfiles.set(userId, {});
            }

            const profile = this.userProfiles.get(userId);

            for (const [feature, value] of Object.entries(itemFeatures)) {
                if (!profile[feature]) {
                    profile[feature] = 0;
                }
                profile[feature] += value * interaction;
            }
        }

        // 计算物品与用户画像的相似度
        calculateSimilarity(userId, itemId) {
            const userProfile = this.userProfiles.get(userId);
            const itemFeatures = this.itemFeatures.get(itemId);

            if (!userProfile || !itemFeatures) return 0;

            let dotProduct = 0;
            let userNorm = 0;
            let itemNorm = 0;

            for (const [feature, userValue] of Object.entries(userProfile)) {
                const itemValue = itemFeatures[feature] || 0;
                dotProduct += userValue * itemValue;
                userNorm += userValue * userValue;
            }

            for (const value of Object.values(itemFeatures)) {
                itemNorm += value * value;
            }

            return dotProduct / (Math.sqrt(userNorm) * Math.sqrt(itemNorm) + 1e-10);
        }

        // 基于内容的推荐
        recommend(userId, n = 5) {
            const recommendations = [];

            for (const itemId of this.itemFeatures.keys()) {
                const similarity = this.calculateSimilarity(userId, itemId);
                if (similarity > 0) {
                    recommendations.push({ itemId, score: similarity });
                }
            }

            recommendations.sort((a, b) => b.score - a.score);
            return recommendations.slice(0, n);
        }
    }

    // 知识图谱推荐
    class KnowledgeGraphRecommendation {
        constructor() {
            this.graph = new Map();
            this.entityTypes = new Map();
        }

        // 添加实体
        addEntity(entityId, type, properties = {}) {
            this.entityTypes.set(entityId, type);
            if (!this.graph.has(entityId)) {
                this.graph.set(entityId, new Map());
            }
            this.graph.get(entityId).set('_properties', properties);
        }

        // 添加关系
        addRelation(entityId1, relation, entityId2, weight = 1) {
            if (!this.graph.has(entityId1)) {
                this.graph.set(entityId1, new Map());
            }
            if (!this.graph.has(entityId2)) {
                this.graph.set(entityId2, new Map());
            }

            this.graph.get(entityId1).set(`${relation}:${entityId2}`, weight);
        }

        // 基于路径的推荐
        recommendByPath(userId, targetType, maxDepth = 3) {
            const visited = new Set();
            const paths = [];

            const dfs = (currentId, path, depth) => {
                if (depth > maxDepth) return;

                const entityType = this.entityTypes.get(currentId);
                if (entityType === targetType && currentId !== userId) {
                    paths.push([...path, currentId]);
                    return;
                }

                visited.add(currentId);

                const neighbors = this.graph.get(currentId);
                if (neighbors) {
                    for (const [key, weight] of neighbors) {
                        if (key === '_properties') continue;

                        const [, neighborId] = key.split(':');
                        if (!visited.has(neighborId)) {
                            dfs(neighborId, [...path, { id: currentId, relation: key.split(':')[0], weight }], depth + 1);
                        }
                    }
                }

                visited.delete(currentId);
            };

            dfs(userId, [], 0);

            // 按路径权重排序
            paths.sort((a, b) => {
                const weightA = a.reduce((sum, node) => sum + (node.weight || 0), 0);
                const weightB = b.reduce((sum, node) => sum + (node.weight || 0), 0);
                return weightB - weightA;
            });

            return paths.slice(0, 10).map(path => ({
                path: path.filter(p => typeof p === 'object'),
                target: path[path.length - 1]
            }));
        }
    }

    // 上下文感知推荐
    class ContextAwareRecommendation {
        constructor() {
            this.contextWeights = {
                time: 0.2,
                location: 0.15,
                device: 0.1,
                task: 0.3,
                history: 0.25
            };
        }

        // 获取当前上下文
        getCurrentContext() {
            const hour = new Date().getHours();
            let timeContext = 'morning';
            if (hour >= 12 && hour < 18) timeContext = 'afternoon';
            else if (hour >= 18) timeContext = 'evening';

            return {
                time: timeContext,
                dayOfWeek: new Date().getDay(),
                device: this.detectDevice(),
                recentTasks: this.getRecentTasks(),
                activePlugins: this.getActivePlugins()
            };
        }

        detectDevice() {
            const width = window.innerWidth;
            if (width < 768) return 'mobile';
            if (width < 1024) return 'tablet';
            return 'desktop';
        }

        getRecentTasks() {
            // 从本地存储获取最近任务
            const tasks = localStorage.getItem('kaelis_recent_tasks');
            return tasks ? JSON.parse(tasks) : [];
        }

        getActivePlugins() {
            const plugins = localStorage.getItem('kaelis_active_plugins');
            return plugins ? JSON.parse(plugins) : [];
        }

        // 计算上下文匹配分数
        calculateContextScore(item, context) {
            let score = 0;

            // 时间匹配
            if (item.timeContexts && item.timeContexts.includes(context.time)) {
                score += this.contextWeights.time;
            }

            // 设备匹配
            if (item.supportedDevices && item.supportedDevices.includes(context.device)) {
                score += this.contextWeights.device;
            }

            // 任务匹配
            if (item.relatedTasks) {
                const taskMatch = context.recentTasks.some(task =>
                    item.relatedTasks.includes(task)
                );
                if (taskMatch) score += this.contextWeights.task;
            }

            // 插件关联
            if (item.requiredPlugins) {
                const pluginMatch = context.activePlugins.some(plugin =>
                    item.requiredPlugins.includes(plugin)
                );
                if (pluginMatch) score += this.contextWeights.task * 0.5;
            }

            return score;
        }
    }

    // 推荐引擎主类
    class RecommendationEngine {
        constructor() {
            this.collaborative = new CollaborativeFiltering();
            this.contentBased = new ContentBasedFiltering();
            this.knowledgeGraph = new KnowledgeGraphRecommendation();
            this.contextAware = new ContextAwareRecommendation();

            this.weights = {
                collaborative: 0.3,
                contentBased: 0.3,
                knowledgeGraph: 0.2,
                contextAware: 0.2
            };

            this.cache = new Map();
            this.cacheExpiry = 5 * 60 * 1000; // 5分钟
        }

        // 记录用户交互
        recordInteraction(userId, itemId, type, rating = 1) {
            this.collaborative.recordInteraction(userId, itemId, rating);

            // 更新内容画像
            const itemFeatures = this.getItemFeatures(itemId, type);
            this.contentBased.setItemFeatures(itemId, itemFeatures);
            this.contentBased.updateUserProfile(userId, itemId, rating);

            // 更新知识图谱
            this.updateKnowledgeGraph(userId, itemId, type);

            // 清除缓存
            this.clearCache(userId);
        }

        // 获取物品特征
        getItemFeatures(itemId, type) {
            const features = {
                type: type === RECOMMENDATION_TYPES.PLUGIN ? 1 : 0,
                content: type === RECOMMENDATION_TYPES.CONTENT ? 1 : 0,
                workflow: type === RECOMMENDATION_TYPES.WORKFLOW ? 1 : 0
            };

            // 从本地存储获取更多特征
            const itemData = localStorage.getItem(`kaelis_item_${itemId}`);
            if (itemData) {
                const data = JSON.parse(itemData);
                Object.assign(features, data.features || {});
            }

            return features;
        }

        // 更新知识图谱
        updateKnowledgeGraph(userId, itemId, type) {
            this.knowledgeGraph.addEntity(userId, 'user');
            this.knowledgeGraph.addEntity(itemId, type);
            this.knowledgeGraph.addRelation(userId, 'interacted', itemId, 1);
        }

        // 生成推荐
        async recommend(userId, options = {}) {
            const { type = null, limit = 10, context = null } = options;

            // 检查缓存
            const cacheKey = `${userId}_${type}_${limit}`;
            const cached = this.getCached(cacheKey);
            if (cached) return cached;

            const recommendations = new Map();

            // 1. 协同过滤推荐
            const cfResults = this.collaborative.recommend(userId, limit * 2);
            for (const { itemId, score } of cfResults) {
                recommendations.set(itemId, (recommendations.get(itemId) || 0) + score * this.weights.collaborative);
            }

            // 2. 基于内容的推荐
            const cbResults = this.contentBased.recommend(userId, limit * 2);
            for (const { itemId, score } of cbResults) {
                recommendations.set(itemId, (recommendations.get(itemId) || 0) + score * this.weights.contentBased);
            }

            // 3. 知识图谱推荐
            const kgResults = this.knowledgeGraph.recommendByPath(userId, type || 'plugin', 3);
            for (const result of kgResults) {
                const itemId = result.target;
                const score = result.path.reduce((sum, p) => sum + p.weight, 0) / result.path.length;
                recommendations.set(itemId, (recommendations.get(itemId) || 0) + score * this.weights.knowledgeGraph);
            }

            // 4. 上下文感知推荐
            const currentContext = context || this.contextAware.getCurrentContext();
            for (const [itemId, baseScore] of recommendations) {
                const item = this.getItemData(itemId);
                const contextScore = this.contextAware.calculateContextScore(item, currentContext);
                recommendations.set(itemId, baseScore + contextScore * this.weights.contextAware);
            }

            // 排序并返回
            let results = Array.from(recommendations.entries())
                .map(([itemId, score]) => ({
                    itemId,
                    score,
                    data: this.getItemData(itemId)
                }))
                .sort((a, b) => b.score - a.score);

            // 按类型过滤
            if (type) {
                results = results.filter(r => r.data && r.data.type === type);
            }

            results = results.slice(0, limit);

            // 缓存结果
            this.setCache(cacheKey, results);

            return results;
        }

        // 获取物品数据
        getItemData(itemId) {
            const data = localStorage.getItem(`kaelis_item_${itemId}`);
            return data ? JSON.parse(data) : null;
        }

        // 缓存操作
        getCached(key) {
            const cached = this.cache.get(key);
            if (cached && Date.now() - cached.timestamp < this.cacheExpiry) {
                return cached.data;
            }
            return null;
        }

        setCache(key, data) {
            this.cache.set(key, { data, timestamp: Date.now() });
        }

        clearCache(userId) {
            for (const key of this.cache.keys()) {
                if (key.startsWith(userId)) {
                    this.cache.delete(key);
                }
            }
        }

        // 解释推荐原因
        explainRecommendation(userId, itemId) {
            const explanations = [];

            // 协同过滤解释
            const similarUsers = this.collaborative.getSimilarUsers(userId, 3);
            if (similarUsers.length > 0) {
                explanations.push({
                    type: 'collaborative',
                    reason: `与您兴趣相似的用户也喜欢此项目`,
                    confidence: similarUsers[0].similarity
                });
            }

            // 内容解释
            const userProfile = this.contentBased.userProfiles.get(userId);
            const itemFeatures = this.contentBased.itemFeatures.get(itemId);
            if (userProfile && itemFeatures) {
                const matchingFeatures = [];
                for (const feature of Object.keys(userProfile)) {
                    if (itemFeatures[feature]) {
                        matchingFeatures.push(feature);
                    }
                }
                if (matchingFeatures.length > 0) {
                    explanations.push({
                        type: 'content',
                        reason: `符合您的兴趣偏好: ${matchingFeatures.join(', ')}`,
                        features: matchingFeatures
                    });
                }
            }

            // 上下文解释
            const context = this.contextAware.getCurrentContext();
            explanations.push({
                type: 'context',
                reason: `适合您当前的${context.time === 'morning' ? '上午' : context.time === 'afternoon' ? '下午' : '晚上'}使用场景`,
                context
            });

            return explanations;
        }
    }

    // 推荐管理器
    class RecommendationManager {
        constructor() {
            this.engine = new RecommendationEngine();
            this.userHistory = new Map();
        }

        // 初始化用户
        initUser(userId) {
            if (!this.userHistory.has(userId)) {
                this.userHistory.set(userId, []);
            }
        }

        // 记录行为
        track(userId, action, itemId, metadata = {}) {
            this.initUser(userId);

            const history = this.userHistory.get(userId);
            history.push({
                action,
                itemId,
                timestamp: Date.now(),
                ...metadata
            });

            // 限制历史长度
            if (history.length > 1000) {
                history.shift();
            }

            // 更新推荐引擎
            const rating = this.actionToRating(action);
            this.engine.recordInteraction(userId, itemId, metadata.type, rating);
        }

        actionToRating(action) {
            const ratings = {
                view: 1,
                click: 2,
                install: 5,
                use: 4,
                favorite: 5,
                share: 4,
                dismiss: -1
            };
            return ratings[action] || 1;
        }

        // 获取推荐
        async getRecommendations(userId, options = {}) {
            this.initUser(userId);
            return await this.engine.recommend(userId, options);
        }

        // 获取个性化首页内容
        async getPersonalizedFeed(userId) {
            const [plugins, workflows, knowledge] = await Promise.all([
                this.getRecommendations(userId, { type: RECOMMENDATION_TYPES.PLUGIN, limit: 6 }),
                this.getRecommendations(userId, { type: RECOMMENDATION_TYPES.WORKFLOW, limit: 4 }),
                this.getRecommendations(userId, { type: RECOMMENDATION_TYPES.KNOWLEDGE, limit: 4 })
            ]);

            return {
                plugins,
                workflows,
                knowledge,
                trending: await this.getTrending(),
                forYou: await this.getRecommendations(userId, { limit: 8 })
            };
        }

        // 获取热门内容
        async getTrending() {
            // 基于所有用户行为统计
            const trending = [];
            for (const [userId, history] of this.userHistory) {
                const recent = history.filter(h => Date.now() - h.timestamp < 7 * 24 * 60 * 60 * 1000);
                for (const h of recent) {
                    const existing = trending.find(t => t.itemId === h.itemId);
                    if (existing) {
                        existing.score += this.actionToRating(h.action);
                    } else {
                        trending.push({
                            itemId: h.itemId,
                            score: this.actionToRating(h.action),
                            data: this.engine.getItemData(h.itemId)
                        });
                    }
                }
            }

            return trending.sort((a, b) => b.score - a.score).slice(0, 10);
        }

        // 获取推荐理由
        getExplanation(userId, itemId) {
            return this.engine.explainRecommendation(userId, itemId);
        }
    }

    // 导出 - UMD格式
    const exports = {
        RecommendationEngine,
        RecommendationManager,
        CollaborativeFiltering,
        ContentBasedFiltering,
        KnowledgeGraphRecommendation,
        ContextAwareRecommendation,
        RECOMMENDATION_TYPES
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.RecommendationSystem = exports;
        // 保持向后兼容
        window.RecommendationSystem = exports;
        window.recommendationManager = new RecommendationManager();
    }

    console.log('[RecommendationSystem] 个性化推荐系统已加载');
})();
