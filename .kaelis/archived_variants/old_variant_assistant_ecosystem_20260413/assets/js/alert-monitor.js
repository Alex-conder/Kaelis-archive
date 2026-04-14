/**
 * Kaelis Alert Monitor
 * 监控告警系统
 * 支持邮件/短信告警
 */

(function() {
    'use strict';

    // 告警级别
    const ALERT_LEVEL = {
        CRITICAL: 'critical',  // 严重
        HIGH: 'high',          // 高
        MEDIUM: 'medium',      // 中
        LOW: 'low',            // 低
        INFO: 'info'           // 信息
    };

    // 告警类型
    const ALERT_TYPE = {
        TASK_FAILED: 'task_failed',
        TASK_TIMEOUT: 'task_timeout',
        SYSTEM_ERROR: 'system_error',
        RESOURCE_EXHAUSTED: 'resource_exhausted',
        QUOTA_EXCEEDED: 'quota_exceeded',
        INSTANCE_OFFLINE: 'instance_offline',
        BILLING_ALERT: 'billing_alert',
        SECURITY_ALERT: 'security_alert'
    };

    // 通知渠道
    const NOTIFICATION_CHANNEL = {
        EMAIL: 'email',
        SMS: 'sms',
        WEBSOCKET: 'websocket',
        WEBHOOK: 'webhook',
        PUSH: 'push'
    };

    /**
     * 告警规则
     */
    class AlertRule {
        constructor(config) {
            this.id = config.id || `rule_${Date.now()}`;
            this.name = config.name;
            this.description = config.description;
            
            this.type = config.type;
            this.level = config.level || ALERT_LEVEL.MEDIUM;
            
            this.condition = config.condition; // 触发条件函数
            this.threshold = config.threshold;
            
            this.channels = config.channels || [NOTIFICATION_CHANNEL.EMAIL];
            this.cooldown = config.cooldown || 300; // 冷却时间（秒）
            
            this.enabled = config.enabled !== false;
            this.createdAt = Date.now();
            
            this.lastTriggered = null;
            this.triggerCount = 0;
        }

        // 检查是否触发
        check(data) {
            if (!this.enabled) return false;
            
            // 检查冷却时间
            if (this.lastTriggered && 
                (Date.now() - this.lastTriggered) < this.cooldown * 1000) {
                return false;
            }

            // 执行条件检查
            if (this.condition && typeof this.condition === 'function') {
                return this.condition(data, this.threshold);
            }

            return false;
        }

        // 触发
        trigger(data) {
            this.lastTriggered = Date.now();
            this.triggerCount++;
            
            return {
                ruleId: this.id,
                ruleName: this.name,
                level: this.level,
                type: this.type,
                channels: this.channels,
                data: data,
                timestamp: Date.now()
            };
        }
    }

    /**
     * 告警管理器
     */
    class AlertManager {
        constructor(options = {}) {
            this.apiEndpoint = options.apiEndpoint || '/api/alerts';
            this.rules = new Map();
            this.alertHistory = [];
            this.maxHistorySize = options.maxHistorySize || 1000;
            
            this.callbacks = {
                onAlert: [],
                onAlertSent: [],
                onAlertFailed: []
            };

            this.initDefaultRules();
        }

        // 初始化默认规则
        initDefaultRules() {
            // 任务失败告警
            this.addRule(new AlertRule({
                name: '任务失败告警',
                description: '当任务执行失败时触发',
                type: ALERT_TYPE.TASK_FAILED,
                level: ALERT_LEVEL.HIGH,
                condition: (data) => data.status === 'failed',
                channels: [NOTIFICATION_CHANNEL.EMAIL, NOTIFICATION_CHANNEL.WEBSOCKET]
            }));

            // 任务超时告警
            this.addRule(new AlertRule({
                name: '任务超时告警',
                description: '当任务执行超时时触发',
                type: ALERT_TYPE.TASK_TIMEOUT,
                level: ALERT_LEVEL.HIGH,
                condition: (data, threshold) => {
                    const duration = Date.now() - (data.startedAt || data.createdAt);
                    return duration > (threshold || 300000); // 默认5分钟
                },
                channels: [NOTIFICATION_CHANNEL.EMAIL, NOTIFICATION_CHANNEL.SMS]
            }));

            // 资源耗尽告警
            this.addRule(new AlertRule({
                name: '资源耗尽告警',
                description: '当系统资源不足时触发',
                type: ALERT_TYPE.RESOURCE_EXHAUSTED,
                level: ALERT_LEVEL.CRITICAL,
                condition: (data) => data.resourceUsage > 90,
                channels: [NOTIFICATION_CHANNEL.EMAIL, NOTIFICATION_CHANNEL.SMS, NOTIFICATION_CHANNEL.WEBSOCKET]
            }));

            // 配额超限告警
            this.addRule(new AlertRule({
                name: '配额超限告警',
                description: '当用户配额使用超过阈值时触发',
                type: ALERT_TYPE.QUOTA_EXCEEDED,
                level: ALERT_LEVEL.MEDIUM,
                condition: (data, threshold) => data.quotaUsage > (threshold || 80),
                channels: [NOTIFICATION_CHANNEL.EMAIL, NOTIFICATION_CHANNEL.WEBSOCKET]
            }));

            // 执行端离线告警
            this.addRule(new AlertRule({
                name: '执行端离线告警',
                description: '当执行端长时间未上报心跳时触发',
                type: ALERT_TYPE.INSTANCE_OFFLINE,
                level: ALERT_LEVEL.HIGH,
                condition: (data) => data.heartbeatAge > 120000, // 2分钟
                channels: [NOTIFICATION_CHANNEL.EMAIL, NOTIFICATION_CHANNEL.SMS]
            }));
        }

        // 添加规则
        addRule(rule) {
            this.rules.set(rule.id, rule);
        }

        // 删除规则
        removeRule(ruleId) {
            this.rules.delete(ruleId);
        }

        // 启用/禁用规则
        toggleRule(ruleId, enabled) {
            const rule = this.rules.get(ruleId);
            if (rule) {
                rule.enabled = enabled;
            }
        }

        // 检查告警
        checkAlerts(data) {
            const triggeredAlerts = [];

            for (const rule of this.rules.values()) {
                if (rule.check(data)) {
                    const alert = rule.trigger(data);
                    triggeredAlerts.push(alert);
                    this.processAlert(alert);
                }
            }

            return triggeredAlerts;
        }

        // 处理告警
        async processAlert(alert) {
            // 记录告警
            this.recordAlert(alert);
            
            this.trigger('onAlert', alert);

            // 发送到各渠道
            for (const channel of alert.channels) {
                try {
                    await this.sendToChannel(channel, alert);
                    this.trigger('onAlertSent', { alert, channel });
                } catch (error) {
                    console.error(`[AlertManager] 发送告警失败 [${channel}]:`, error);
                    this.trigger('onAlertFailed', { alert, channel, error });
                }
            }
        }

        // 记录告警
        recordAlert(alert) {
            this.alertHistory.push({
                ...alert,
                recordedAt: Date.now()
            });

            // 限制历史记录大小
            if (this.alertHistory.length > this.maxHistorySize) {
                this.alertHistory.shift();
            }
        }

        // 发送到指定渠道
        async sendToChannel(channel, alert) {
            switch (channel) {
                case NOTIFICATION_CHANNEL.EMAIL:
                    await this.sendEmail(alert);
                    break;
                case NOTIFICATION_CHANNEL.SMS:
                    await this.sendSMS(alert);
                    break;
                case NOTIFICATION_CHANNEL.WEBSOCKET:
                    await this.sendWebSocket(alert);
                    break;
                case NOTIFICATION_CHANNEL.WEBHOOK:
                    await this.sendWebhook(alert);
                    break;
                case NOTIFICATION_CHANNEL.PUSH:
                    await this.sendPush(alert);
                    break;
            }
        }

        // 发送邮件
        async sendEmail(alert) {
            const response = await fetch(`${this.apiEndpoint}/email`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getAuthToken()}`
                },
                body: JSON.stringify({
                    to: alert.data.userEmail,
                    subject: `[${alert.level.toUpperCase()}] ${alert.ruleName}`,
                    template: 'alert',
                    data: {
                        alertName: alert.ruleName,
                        alertLevel: alert.level,
                        alertType: alert.type,
                        message: this.formatAlertMessage(alert),
                        timestamp: new Date(alert.timestamp).toLocaleString(),
                        details: alert.data
                    }
                })
            });

            if (!response.ok) {
                throw new Error('Email sending failed');
            }
        }

        // 发送短信
        async sendSMS(alert) {
            // 只有高优先级告警才发送短信
            if (alert.level !== ALERT_LEVEL.CRITICAL && alert.level !== ALERT_LEVEL.HIGH) {
                return;
            }

            const response = await fetch(`${this.apiEndpoint}/sms`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getAuthToken()}`
                },
                body: JSON.stringify({
                    to: alert.data.userPhone,
                    template: 'alert',
                    data: {
                        alertName: alert.ruleName,
                        level: alert.level,
                        message: this.formatAlertMessage(alert, true) // 简短消息
                    }
                })
            });

            if (!response.ok) {
                throw new Error('SMS sending failed');
            }
        }

        // WebSocket通知
        async sendWebSocket(alert) {
            // 通过WebSocket发送实时通知
            if (window.wsClient && window.wsClient.connected) {
                window.wsClient.send({
                    type: 'alert',
                    payload: alert
                });
            }
        }

        // Webhook通知
        async sendWebhook(alert) {
            const webhookUrl = alert.data.webhookUrl;
            if (!webhookUrl) return;

            const response = await fetch(webhookUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Alert-Signature': this.generateSignature(alert)
                },
                body: JSON.stringify(alert)
            });

            if (!response.ok) {
                throw new Error('Webhook sending failed');
            }
        }

        // 推送通知
        async sendPush(alert) {
            if (!('Notification' in window)) return;

            const permission = await Notification.requestPermission();
            if (permission === 'granted') {
                new Notification(alert.ruleName, {
                    body: this.formatAlertMessage(alert, true),
                    icon: '/assets/icons/alert.png',
                    tag: alert.id,
                    requireInteraction: alert.level === ALERT_LEVEL.CRITICAL
                });
            }
        }

        // 格式化告警消息
        formatAlertMessage(alert, short = false) {
            const levelEmoji = {
                [ALERT_LEVEL.CRITICAL]: '🚨',
                [ALERT_LEVEL.HIGH]: '⚠️',
                [ALERT_LEVEL.MEDIUM]: '⚡',
                [ALERT_LEVEL.LOW]: 'ℹ️',
                [ALERT_LEVEL.INFO]: '📝'
            };

            if (short) {
                return `${levelEmoji[alert.level]} ${alert.ruleName}`;
            }

            return `
${levelEmoji[alert.level]} ${alert.ruleName}
级别: ${alert.level.toUpperCase()}
类型: ${alert.type}
时间: ${new Date(alert.timestamp).toLocaleString()}
详情: ${JSON.stringify(alert.data, null, 2)}
            `.trim();
        }

        // 生成签名
        generateSignature(alert) {
            // 实际实现应使用HMAC-SHA256
            return `sha256=${Date.now()}`;
        }

        // 获取认证Token
        getAuthToken() {
            return localStorage.getItem('kaelis_auth_token') || 
                   localStorage.getItem('access_token') ||
                   '';
        }

        // 获取告警历史
        getAlertHistory(filters = {}) {
            let history = [...this.alertHistory];

            if (filters.level) {
                history = history.filter(a => a.level === filters.level);
            }
            if (filters.type) {
                history = history.filter(a => a.type === filters.type);
            }
            if (filters.startTime) {
                history = history.filter(a => a.timestamp >= filters.startTime);
            }
            if (filters.endTime) {
                history = history.filter(a => a.timestamp <= filters.endTime);
            }

            return history.sort((a, b) => b.timestamp - a.timestamp);
        }

        // 获取统计
        getStats() {
            const stats = {
                total: this.alertHistory.length,
                byLevel: {},
                byType: {},
                byChannel: {}
            };

            for (const alert of this.alertHistory) {
                stats.byLevel[alert.level] = (stats.byLevel[alert.level] || 0) + 1;
                stats.byType[alert.type] = (stats.byType[alert.type] || 0) + 1;
                
                for (const channel of alert.channels) {
                    stats.byChannel[channel] = (stats.byChannel[channel] || 0) + 1;
                }
            }

            return stats;
        }

        // 事件监听
        on(event, callback) {
            if (this.callbacks[event]) {
                this.callbacks[event].push(callback);
            }
            return this;
        }

        trigger(event, data) {
            if (this.callbacks[event]) {
                this.callbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error('[AlertManager] 回调错误:', error);
                    }
                });
            }
        }

        // 手动触发告警
        async manualAlert(type, level, message, data = {}) {
            const alert = {
                ruleId: 'manual',
                ruleName: '手动告警',
                level,
                type,
                channels: [NOTIFICATION_CHANNEL.EMAIL, NOTIFICATION_CHANNEL.WEBSOCKET],
                data: { message, ...data },
                timestamp: Date.now()
            };

            await this.processAlert(alert);
            return alert;
        }
    }

    /**
     * 任务监控集成
     */
    class TaskAlertIntegration {
        constructor(alertManager, taskMonitor) {
            this.alertManager = alertManager;
            this.taskMonitor = taskMonitor;
            
            this.integrate();
        }

        integrate() {
            // 监听任务失败
            this.taskMonitor.on('onTaskFail', (data) => {
                this.alertManager.checkAlerts({
                    type: ALERT_TYPE.TASK_FAILED,
                    status: 'failed',
                    taskId: data.taskId,
                    error: data.error,
                    userEmail: data.userEmail,
                    userPhone: data.userPhone
                });
            });

            // 监听任务完成
            this.taskMonitor.on('onTaskComplete', (task) => {
                // 检查是否超时
                const duration = task.completedAt - task.startedAt;
                if (duration > 300000) { // 5分钟
                    this.alertManager.checkAlerts({
                        type: ALERT_TYPE.TASK_TIMEOUT,
                        duration,
                        taskId: task.id,
                        userEmail: task.userEmail
                    });
                }
            });
        }
    }

    // 导出 - UMD格式
    const exports = {
        AlertRule,
        AlertManager,
        TaskAlertIntegration,
        ALERT_LEVEL,
        ALERT_TYPE,
        NOTIFICATION_CHANNEL
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.AlertMonitor = exports;
        // 保持向后兼容
        window.AlertMonitor = exports;
        window.alertManager = new AlertManager();
    }

    console.log('[AlertMonitor] 监控告警系统已加载');
})();
