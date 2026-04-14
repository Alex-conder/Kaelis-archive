/**
 * Kaelis Alert System Advanced
 * 监控告警高级功能 - 规则引擎、告警抑制、聚合、可视化面板
 */

(function() {
    'use strict';

    // 告警操作
    const ALERT_ACTION = {
        NOTIFY: 'notify',
        SUPPRESS: 'suppress',
        ESCALATE: 'escalate',
        AUTO_RESOLVE: 'auto_resolve',
        WEBHOOK: 'webhook'
    };

    // 抑制策略
    const SUPPRESSION_POLICY = {
        TIME_BASED: 'time_based',       // 时间窗口抑制
        COUNT_BASED: 'count_based',     // 计数抑制
        SIMILARITY: 'similarity',       // 相似性抑制
        UPSTREAM: 'upstream'            // 上游抑制
    };

    // 聚合策略
    const AGGREGATION_POLICY = {
        GROUP_BY: 'group_by',           // 按字段分组
        TIME_WINDOW: 'time_window',     // 时间窗口聚合
        TOP_N: 'top_n',                 // Top N聚合
        PATTERN: 'pattern'              // 模式匹配聚合
    };

    /**
     * 告警规则引擎
     */
    class AlertRuleEngine {
        constructor() {
            this.rules = [];
            this.operators = this.initOperators();
        }

        // 初始化操作符
        initOperators() {
            return {
                // 比较操作符
                eq: (a, b) => a === b,
                ne: (a, b) => a !== b,
                gt: (a, b) => a > b,
                gte: (a, b) => a >= b,
                lt: (a, b) => a < b,
                lte: (a, b) => a <= b,
                
                // 范围操作符
                between: (a, [min, max]) => a >= min && a <= max,
                in: (a, arr) => arr.includes(a),
                not_in: (a, arr) => !arr.includes(a),
                
                // 字符串操作符
                contains: (a, b) => String(a).includes(b),
                starts_with: (a, b) => String(a).startsWith(b),
                ends_with: (a, b) => String(a).endsWith(b),
                matches: (a, regex) => new RegExp(regex).test(String(a)),
                
                // 存在性操作符
                exists: (a) => a !== undefined && a !== null,
                not_exists: (a) => a === undefined || a === null,
                
                // 逻辑操作符
                and: (...conditions) => conditions.every(c => c),
                or: (...conditions) => conditions.some(c => c),
                not: (condition) => !condition
            };
        }

        // 添加规则
        addRule(rule) {
            this.rules.push({
                id: rule.id || `rule_${Date.now()}`,
                name: rule.name,
                description: rule.description,
                condition: rule.condition,
                actions: rule.actions || [ALERT_ACTION.NOTIFY],
                priority: rule.priority || 0,
                enabled: rule.enabled !== false,
                createdAt: Date.now()
            });
            
            // 按优先级排序
            this.rules.sort((a, b) => b.priority - a.priority);
        }

        // 评估规则
        evaluate(data) {
            const triggered = [];
            
            for (const rule of this.rules) {
                if (!rule.enabled) continue;
                
                try {
                    const result = this.evaluateCondition(rule.condition, data);
                    if (result) {
                        triggered.push({
                            rule: rule,
                            data: data,
                            timestamp: Date.now()
                        });
                    }
                } catch (error) {
                    console.error(`[AlertRuleEngine] 规则评估失败 [${rule.id}]:`, error);
                }
            }
            
            return triggered;
        }

        // 评估条件
        evaluateCondition(condition, data) {
            if (typeof condition === 'function') {
                return condition(data);
            }

            if (typeof condition === 'object') {
                const { operator, field, value, conditions } = condition;
                
                // 复合条件
                if (operator === 'and' || operator === 'or') {
                    const results = conditions.map(c => this.evaluateCondition(c, data));
                    return operator === 'and' ? 
                        results.every(r => r) : 
                        results.some(r => r);
                }

                if (operator === 'not') {
                    return !this.evaluateCondition(conditions[0], data);
                }

                // 字段条件
                const fieldValue = this.getFieldValue(data, field);
                const op = this.operators[operator];
                
                if (op) {
                    return op(fieldValue, value);
                }
            }

            return false;
        }

        // 获取字段值（支持嵌套路径）
        getFieldValue(data, path) {
            return path.split('.').reduce((obj, key) => obj?.[key], data);
        }

        // 删除规则
        removeRule(ruleId) {
            const index = this.rules.findIndex(r => r.id === ruleId);
            if (index > -1) {
                this.rules.splice(index, 1);
                return true;
            }
            return false;
        }

        // 启用/禁用规则
        toggleRule(ruleId, enabled) {
            const rule = this.rules.find(r => r.id === ruleId);
            if (rule) {
                rule.enabled = enabled;
                return true;
            }
            return false;
        }
    }

    /**
     * 告警抑制管理器
     */
    class AlertSuppressionManager {
        constructor() {
            this.suppressions = new Map();
            this.policies = new Map();
        }

        // 添加抑制策略
        addPolicy(policy) {
            this.policies.set(policy.id, {
                id: policy.id,
                name: policy.name,
                type: policy.type,
                config: policy.config,
                enabled: policy.enabled !== false
            });
        }

        // 检查是否应该抑制告警
        shouldSuppress(alert) {
            for (const policy of this.policies.values()) {
                if (!policy.enabled) continue;
                
                if (this.checkSuppression(policy, alert)) {
                    return {
                        suppressed: true,
                        policy: policy,
                        reason: this.getSuppressionReason(policy)
                    };
                }
            }
            
            return { suppressed: false };
        }

        // 检查抑制条件
        checkSuppression(policy, alert) {
            const key = this.getSuppressionKey(policy, alert);
            
            switch (policy.type) {
                case SUPPRESSION_POLICY.TIME_BASED:
                    return this.checkTimeBasedSuppression(key, policy.config);
                    
                case SUPPRESSION_POLICY.COUNT_BASED:
                    return this.checkCountBasedSuppression(key, policy.config);
                    
                case SUPPRESSION_POLICY.SIMILARITY:
                    return this.checkSimilaritySuppression(alert, policy.config);
                    
                case SUPPRESSION_POLICY.UPSTREAM:
                    return this.checkUpstreamSuppression(alert, policy.config);
                    
                default:
                    return false;
            }
        }

        // 时间窗口抑制
        checkTimeBasedSuppression(key, config) {
            const now = Date.now();
            const window = config.window * 1000; // 转换为毫秒
            
            const lastAlert = this.suppressions.get(key);
            if (lastAlert && (now - lastAlert.timestamp) < window) {
                return true;
            }
            
            this.suppressions.set(key, { timestamp: now, count: 1 });
            return false;
        }

        // 计数抑制
        checkCountBasedSuppression(key, config) {
            const now = Date.now();
            const window = config.window * 1000;
            const maxCount = config.maxCount;
            
            let suppression = this.suppressions.get(key);
            
            if (!suppression || (now - suppression.timestamp) > window) {
                suppression = { timestamp: now, count: 1 };
                this.suppressions.set(key, suppression);
                return false;
            }
            
            suppression.count++;
            
            if (suppression.count > maxCount) {
                return true;
            }
            
            return false;
        }

        // 相似性抑制
        checkSimilaritySuppression(alert, config) {
            const threshold = config.threshold || 0.8;
            const fields = config.fields || ['type', 'source'];
            
            for (const [key, suppressed] of this.suppressions) {
                if (suppressed.type === 'similarity') {
                    const similarity = this.calculateSimilarity(alert, suppressed.alert, fields);
                    if (similarity >= threshold) {
                        return true;
                    }
                }
            }
            
            return false;
        }

        // 计算相似度
        calculateSimilarity(alert1, alert2, fields) {
            let matches = 0;
            for (const field of fields) {
                if (alert1[field] === alert2[field]) {
                    matches++;
                }
            }
            return matches / fields.length;
        }

        // 上游抑制
        checkUpstreamSuppression(alert, config) {
            // 检查上游组件是否已有告警
            const upstreamKey = `upstream_${alert.source}`;
            const upstreamAlert = this.suppressions.get(upstreamKey);
            
            if (upstreamAlert && 
                (Date.now() - upstreamAlert.timestamp) < config.window * 1000) {
                return true;
            }
            
            return false;
        }

        // 获取抑制键
        getSuppressionKey(policy, alert) {
            const parts = [policy.id];
            
            if (policy.config.groupBy) {
                for (const field of policy.config.groupBy) {
                    parts.push(alert[field]);
                }
            }
            
            return parts.join('_');
        }

        // 获取抑制原因
        getSuppressionReason(policy) {
            const reasons = {
                [SUPPRESSION_POLICY.TIME_BASED]: '时间窗口内重复告警',
                [SUPPRESSION_POLICY.COUNT_BASED]: '超过告警计数阈值',
                [SUPPRESSION_POLICY.SIMILARITY]: '相似告警已存在',
                [SUPPRESSION_POLICY.UPSTREAM]: '上游告警抑制'
            };
            return reasons[policy.type] || '未知原因';
        }

        // 清理过期抑制记录
        cleanup(maxAge = 3600000) { // 默认1小时
            const now = Date.now();
            for (const [key, suppression] of this.suppressions) {
                if (now - suppression.timestamp > maxAge) {
                    this.suppressions.delete(key);
                }
            }
        }
    }

    /**
     * 告警聚合管理器
     */
    class AlertAggregationManager {
        constructor() {
            this.aggregations = new Map();
            this.buckets = new Map();
        }

        // 创建聚合配置
        createAggregation(config) {
            const aggId = `agg_${Date.now()}`;
            
            this.aggregations.set(aggId, {
                id: aggId,
                name: config.name,
                policy: config.policy,
                config: config.config,
                window: config.window || 300, // 5分钟
                enabled: config.enabled !== false
            });
            
            return aggId;
        }

        // 添加告警到聚合
        addAlert(alert) {
            for (const aggregation of this.aggregations.values()) {
                if (!aggregation.enabled) continue;
                
                const bucketKey = this.getBucketKey(aggregation, alert);
                
                if (!this.buckets.has(bucketKey)) {
                    this.buckets.set(bucketKey, {
                        alerts: [],
                        createdAt: Date.now(),
                        aggregation: aggregation
                    });
                    
                    // 设置定时器发送聚合告警
                    setTimeout(() => {
                        this.flushBucket(bucketKey);
                    }, aggregation.window * 1000);
                }
                
                const bucket = this.buckets.get(bucketKey);
                bucket.alerts.push(alert);
            }
        }

        // 获取分桶键
        getBucketKey(aggregation, alert) {
            const parts = [aggregation.id];
            
            switch (aggregation.policy) {
                case AGGREGATION_POLICY.GROUP_BY:
                    for (const field of aggregation.config.fields) {
                        parts.push(alert[field]);
                    }
                    break;
                    
                case AGGREGATION_POLICY.TIME_WINDOW:
                    const window = Math.floor(Date.now() / (aggregation.window * 1000));
                    parts.push(window);
                    break;
                    
                case AGGREGATION_POLICY.PATTERN:
                    const pattern = this.extractPattern(alert, aggregation.config.pattern);
                    parts.push(pattern);
                    break;
            }
            
            return parts.join('_');
        }

        // 提取模式
        extractPattern(alert, pattern) {
            // 简单的模式提取，实际应用可使用正则
            return pattern.replace(/\{(\w+)\}/g, (match, field) => alert[field] || 'unknown');
        }

        // 刷新分桶
        flushBucket(bucketKey) {
            const bucket = this.buckets.get(bucketKey);
            if (!bucket || bucket.alerts.length === 0) return;
            
            const aggregatedAlert = this.createAggregatedAlert(bucket);
            
            this.buckets.delete(bucketKey);
            
            return aggregatedAlert;
        }

        // 创建聚合告警
        createAggregatedAlert(bucket) {
            const { alerts, aggregation } = bucket;
            
            const severityCounts = {};
            const sourceCounts = {};
            
            for (const alert of alerts) {
                severityCounts[alert.severity] = (severityCounts[alert.severity] || 0) + 1;
                sourceCounts[alert.source] = (sourceCounts[alert.source] || 0) + 1;
            }
            
            return {
                type: 'aggregated',
                name: aggregation.name,
                count: alerts.length,
                severityCounts,
                sourceCounts,
                alerts: alerts.slice(0, 10), // 只保留前10个详情
                timeRange: {
                    start: Math.min(...alerts.map(a => a.timestamp)),
                    end: Math.max(...alerts.map(a => a.timestamp))
                },
                timestamp: Date.now()
            };
        }

        // 获取所有待发送的聚合告警
        flushAll() {
            const results = [];
            for (const bucketKey of this.buckets.keys()) {
                const result = this.flushBucket(bucketKey);
                if (result) results.push(result);
            }
            return results;
        }
    }

    /**
     * 告警可视化面板
     */
    class AlertDashboard {
        constructor(containerId, alertManager) {
            this.container = document.getElementById(containerId);
            this.alertManager = alertManager;
            this.alerts = [];
            this.filters = {
                severity: null,
                source: null,
                timeRange: null
            };
            
            this.init();
        }

        init() {
            this.render();
            this.bindEvents();
            this.startAutoRefresh();
        }

        render() {
            if (!this.container) return;
            
            this.container.innerHTML = `
                <div class="alert-dashboard">
                    <div class="dashboard-header">
                        <h3>告警监控面板</h3>
                        <div class="alert-stats">
                            <span class="stat critical" data-severity="critical">严重: 0</span>
                            <span class="stat high" data-severity="high">高: 0</span>
                            <span class="stat medium" data-severity="medium">中: 0</span>
                            <span class="stat low" data-severity="low">低: 0</span>
                        </div>
                    </div>
                    <div class="dashboard-filters">
                        <select id="severity-filter">
                            <option value="">全部级别</option>
                            <option value="critical">严重</option>
                            <option value="high">高</option>
                            <option value="medium">中</option>
                            <option value="low">低</option>
                        </select>
                        <select id="source-filter">
                            <option value="">全部来源</option>
                        </select>
                        <input type="text" id="search-filter" placeholder="搜索告警...">
                    </div>
                    <div class="alert-timeline" id="alert-timeline"></div>
                    <div class="alert-list" id="alert-list"></div>
                </div>
            `;
        }

        bindEvents() {
            // 级别过滤
            const severityFilter = this.container.querySelector('#severity-filter');
            if (severityFilter) {
                severityFilter.addEventListener('change', (e) => {
                    this.filters.severity = e.target.value || null;
                    this.refresh();
                });
            }

            // 搜索过滤
            const searchFilter = this.container.querySelector('#search-filter');
            if (searchFilter) {
                searchFilter.addEventListener('input', (e) => {
                    this.searchTerm = e.target.value;
                    this.refresh();
                });
            }

            // 统计点击
            const stats = this.container.querySelectorAll('.stat');
            stats.forEach(stat => {
                stat.addEventListener('click', () => {
                    const severity = stat.dataset.severity;
                    this.filters.severity = severity;
                    
                    const filter = this.container.querySelector('#severity-filter');
                    if (filter) filter.value = severity;
                    
                    this.refresh();
                });
            });
        }

        updateAlerts(alerts) {
            this.alerts = alerts;
            this.updateStats();
            this.renderAlerts();
            this.renderTimeline();
        }

        updateStats() {
            const counts = {
                critical: 0,
                high: 0,
                medium: 0,
                low: 0
            };

            for (const alert of this.alerts) {
                if (counts[alert.severity] !== undefined) {
                    counts[alert.severity]++;
                }
            }

            for (const [severity, count] of Object.entries(counts)) {
                const stat = this.container.querySelector(`.stat.${severity}`);
                if (stat) {
                    stat.textContent = `${this.getSeverityLabel(severity)}: ${count}`;
                }
            }
        }

        getSeverityLabel(severity) {
            const labels = {
                critical: '严重',
                high: '高',
                medium: '中',
                low: '低'
            };
            return labels[severity] || severity;
        }

        renderAlerts() {
            const listEl = this.container.querySelector('#alert-list');
            if (!listEl) return;

            let filtered = this.alerts;

            // 应用过滤
            if (this.filters.severity) {
                filtered = filtered.filter(a => a.severity === this.filters.severity);
            }

            if (this.searchTerm) {
                const term = this.searchTerm.toLowerCase();
                filtered = filtered.filter(a => 
                    a.message?.toLowerCase().includes(term) ||
                    a.source?.toLowerCase().includes(term)
                );
            }

            // 按时间倒序
            filtered.sort((a, b) => b.timestamp - a.timestamp);

            listEl.innerHTML = filtered.map(alert => `
                <div class="alert-item ${alert.severity}" data-alert-id="${alert.id}">
                    <div class="alert-icon">${this.getSeverityIcon(alert.severity)}</div>
                    <div class="alert-content">
                        <div class="alert-header">
                            <span class="alert-source">${alert.source}</span>
                            <span class="alert-time">${this.formatTime(alert.timestamp)}</span>
                        </div>
                        <div class="alert-message">${alert.message}</div>
                        <div class="alert-meta">
                            <span class="alert-type">${alert.type}</span>
                            ${alert.acknowledged ? '<span class="ack-badge">已确认</span>' : ''}
                        </div>
                    </div>
                    <div class="alert-actions">
                        <button class="btn-ack" data-id="${alert.id}">确认</button>
                        <button class="btn-detail" data-id="${alert.id}">详情</button>
                    </div>
                </div>
            `).join('');

            // 绑定操作按钮
            listEl.querySelectorAll('.btn-ack').forEach(btn => {
                btn.addEventListener('click', () => this.acknowledgeAlert(btn.dataset.id));
            });
        }

        renderTimeline() {
            const timelineEl = this.container.querySelector('#alert-timeline');
            if (!timelineEl) return;

            // 按小时分组
            const hourly = {};
            const now = Date.now();
            const hours = 24;

            for (let i = 0; i < hours; i++) {
                const hour = new Date(now - i * 3600000).getHours();
                hourly[hour] = { critical: 0, high: 0, medium: 0, low: 0 };
            }

            for (const alert of this.alerts) {
                const hour = new Date(alert.timestamp).getHours();
                if (hourly[hour] && hourly[hour][alert.severity] !== undefined) {
                    hourly[hour][alert.severity]++;
                }
            }

            // 渲染时间线
            const maxCount = Math.max(...Object.values(hourly).map(h => 
                Object.values(h).reduce((a, b) => a + b, 0)
            )) || 1;

            timelineEl.innerHTML = Object.entries(hourly).map(([hour, counts]) => {
                const total = Object.values(counts).reduce((a, b) => a + b, 0);
                const height = maxCount > 0 ? (total / maxCount * 100) : 0;
                
                return `
                    <div class="timeline-bar" style="height: ${height}%" title="${hour}:00 - ${total}个告警">
                        ${counts.critical > 0 ? `<div class="bar-critical" style="height: ${counts.critical/total*100}%"></div>` : ''}
                        ${counts.high > 0 ? `<div class="bar-high" style="height: ${counts.high/total*100}%"></div>` : ''}
                        ${counts.medium > 0 ? `<div class="bar-medium" style="height: ${counts.medium/total*100}%"></div>` : ''}
                        ${counts.low > 0 ? `<div class="bar-low" style="height: ${counts.low/total*100}%"></div>` : ''}
                    </div>
                `;
            }).reverse().join('');
        }

        getSeverityIcon(severity) {
            const icons = {
                critical: '🚨',
                high: '⚠️',
                medium: '⚡',
                low: 'ℹ️'
            };
            return icons[severity] || '📋';
        }

        formatTime(timestamp) {
            const date = new Date(timestamp);
            const now = Date.now();
            const diff = now - timestamp;

            if (diff < 60000) return '刚刚';
            if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
            if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
            
            return date.toLocaleDateString();
        }

        acknowledgeAlert(alertId) {
            // 发送确认请求
            if (this.alertManager) {
                this.alertManager.acknowledgeAlert(alertId);
            }
            
            // 更新UI
            const alert = this.alerts.find(a => a.id === alertId);
            if (alert) {
                alert.acknowledged = true;
                this.renderAlerts();
            }
        }

        refresh() {
            this.renderAlerts();
        }

        startAutoRefresh() {
            setInterval(() => {
                if (this.alertManager) {
                    const alerts = this.alertManager.getAlertHistory();
                    this.updateAlerts(alerts);
                }
            }, 30000); // 30秒刷新
        }
    }

    /**
     * 高级告警系统
     */
    class AdvancedAlertSystem {
        constructor(options = {}) {
            this.ruleEngine = new AlertRuleEngine();
            this.suppressionManager = new AlertSuppressionManager();
            this.aggregationManager = new AlertAggregationManager();
            
            this.alertManager = options.alertManager;
            this.callbacks = {
                onAlert: [],
                onSuppressed: [],
                onAggregated: []
            };
        }

        // 处理告警
        async processAlert(alert) {
            // 1. 规则引擎评估
            const triggered = this.ruleEngine.evaluate(alert);
            
            if (triggered.length === 0) return;

            // 2. 抑制检查
            const suppression = this.suppressionManager.shouldSuppress(alert);
            if (suppression.suppressed) {
                this.trigger('onSuppressed', { alert, suppression });
                return;
            }

            // 3. 聚合
            this.aggregationManager.addAlert(alert);

            // 4. 发送到告警管理器
            if (this.alertManager) {
                await this.alertManager.processAlert(alert);
            }

            this.trigger('onAlert', alert);
        }

        // 获取聚合告警
        getAggregatedAlerts() {
            return this.aggregationManager.flushAll();
        }

        // 创建可视化面板
        createDashboard(containerId) {
            return new AlertDashboard(containerId, this.alertManager);
        }

        // 事件监听
        on(event, callback) {
            if (this.callbacks[event]) {
                this.callbacks[event].push(callback);
            }
        }

        trigger(event, data) {
            if (this.callbacks[event]) {
                this.callbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error('[AdvancedAlertSystem] 回调错误:', error);
                    }
                });
            }
        }
    }

    // 导出 - UMD格式
    const exports = {
        AlertRuleEngine,
        AlertSuppressionManager,
        AlertAggregationManager,
        AlertDashboard,
        AdvancedAlertSystem,
        ALERT_ACTION,
        SUPPRESSION_POLICY,
        AGGREGATION_POLICY
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.AlertSystem = exports;
        // 保持向后兼容
        window.AlertSystemAdvanced = exports;
    }

    console.log('[AlertSystemAdvanced] 高级告警系统已加载');
})();
