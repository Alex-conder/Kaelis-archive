/**
 * Kaelis Billing System
 * 收费体系与主账号管理
 * 支持多种计费模式：按量计费、包月/包年、预付费/后付费
 */

(function() {
    'use strict';

    // 计费模式
    const BILLING_MODES = {
        PAY_AS_YOU_GO: 'pay_as_you_go',  // 按量计费
        SUBSCRIPTION: 'subscription',     // 订阅制（包月/包年）
        PREPAID: 'prepaid',               // 预付费
        POSTPAID: 'postpaid'              // 后付费
    };

    // 资源类型
    const RESOURCE_TYPES = {
        COMPUTE: 'compute',           // 计算资源
        STORAGE: 'storage',           // 存储资源
        BANDWIDTH: 'bandwidth',       // 带宽资源
        API_CALL: 'api_call',         // API调用
        TASK_EXECUTION: 'task_execution', // 任务执行
        AI_MODEL: 'ai_model',         // AI模型调用
        PLUGIN: 'plugin'              // 插件使用
    };

    // 套餐类型
    const PLAN_TYPES = {
        FREE: {
            id: 'free',
            name: '免费版',
            price: 0,
            billingMode: BILLING_MODES.SUBSCRIPTION,
            quotas: {
                [RESOURCE_TYPES.COMPUTE]: { limit: 100, unit: 'hours/month' },
                [RESOURCE_TYPES.STORAGE]: { limit: 1, unit: 'GB' },
                [RESOURCE_TYPES.API_CALL]: { limit: 1000, unit: 'calls/month' },
                [RESOURCE_TYPES.TASK_EXECUTION]: { limit: 100, unit: 'tasks/month' }
            },
            features: ['基础功能', '社区支持']
        },
        BASIC: {
            id: 'basic',
            name: '基础版',
            price: 99,
            billingMode: BILLING_MODES.SUBSCRIPTION,
            period: 'month',
            quotas: {
                [RESOURCE_TYPES.COMPUTE]: { limit: 500, unit: 'hours/month' },
                [RESOURCE_TYPES.STORAGE]: { limit: 10, unit: 'GB' },
                [RESOURCE_TYPES.API_CALL]: { limit: 10000, unit: 'calls/month' },
                [RESOURCE_TYPES.TASK_EXECUTION]: { limit: 1000, unit: 'tasks/month' },
                [RESOURCE_TYPES.AI_MODEL]: { limit: 5000, unit: 'calls/month' }
            },
            features: ['全部基础功能', '邮件支持', '5个子账号']
        },
        PRO: {
            id: 'pro',
            name: '专业版',
            price: 299,
            billingMode: BILLING_MODES.SUBSCRIPTION,
            period: 'month',
            quotas: {
                [RESOURCE_TYPES.COMPUTE]: { limit: 2000, unit: 'hours/month' },
                [RESOURCE_TYPES.STORAGE]: { limit: 100, unit: 'GB' },
                [RESOURCE_TYPES.API_CALL]: { limit: 100000, unit: 'calls/month' },
                [RESOURCE_TYPES.TASK_EXECUTION]: { limit: 10000, unit: 'tasks/month' },
                [RESOURCE_TYPES.AI_MODEL]: { limit: 50000, unit: 'calls/month' },
                [RESOURCE_TYPES.PLUGIN]: { limit: 50, unit: 'plugins' }
            },
            features: ['全部专业功能', '优先支持', '20个子账号', 'API访问']
        },
        ENTERPRISE: {
            id: 'enterprise',
            name: '企业版',
            price: null, // 定制价格
            billingMode: BILLING_MODES.SUBSCRIPTION,
            period: 'year',
            quotas: {
                [RESOURCE_TYPES.COMPUTE]: { limit: Infinity, unit: 'hours/month' },
                [RESOURCE_TYPES.STORAGE]: { limit: Infinity, unit: 'GB' },
                [RESOURCE_TYPES.API_CALL]: { limit: Infinity, unit: 'calls/month' },
                [RESOURCE_TYPES.TASK_EXECUTION]: { limit: Infinity, unit: 'tasks/month' },
                [RESOURCE_TYPES.AI_MODEL]: { limit: Infinity, unit: 'calls/month' },
                [RESOURCE_TYPES.PLUGIN]: { limit: Infinity, unit: 'plugins' }
            },
            features: ['全部企业功能', '专属客服', '无限子账号', 'SLA保障', '私有化部署']
        }
    };

    // 单价配置（按量计费）
    const UNIT_PRICES = {
        [RESOURCE_TYPES.COMPUTE]: { price: 0.05, unit: 'hour', currency: 'CNY' },
        [RESOURCE_TYPES.STORAGE]: { price: 0.1, unit: 'GB/month', currency: 'CNY' },
        [RESOURCE_TYPES.BANDWIDTH]: { price: 0.5, unit: 'GB', currency: 'CNY' },
        [RESOURCE_TYPES.API_CALL]: { price: 0.001, unit: 'call', currency: 'CNY' },
        [RESOURCE_TYPES.TASK_EXECUTION]: { price: 0.1, unit: 'task', currency: 'CNY' },
        [RESOURCE_TYPES.AI_MODEL]: { price: 0.02, unit: 'call', currency: 'CNY' },
        [RESOURCE_TYPES.PLUGIN]: { price: 9.9, unit: 'plugin/month', currency: 'CNY' }
    };

    /**
     * 主账号
     */
    class MasterAccount {
        constructor(config) {
            this.id = config.id || `acc_${Date.now()}`;
            this.name = config.name || 'Unnamed Account';
            this.email = config.email;
            this.phone = config.phone;
            
            this.plan = config.plan || PLAN_TYPES.FREE;
            this.billingMode = this.plan.billingMode;
            
            this.balance = config.balance || 0;  // 余额（预付费）
            this.creditLimit = config.creditLimit || 0;  // 信用额度（后付费）
            this.currentUsage = 0;  // 当前周期已使用金额
            
            this.subAccounts = new Map();
            this.apiKeys = new Map();
            
            this.createdAt = config.createdAt || Date.now();
            this.expiresAt = this.calculateExpiry();
            
            this.status = 'active'; // active, suspended, cancelled
            this.autoRenew = config.autoRenew !== false;
            
            this.usage = this.initUsage();
            this.billingHistory = [];
        }

        calculateExpiry() {
            if (this.plan.id === 'free') return null;
            
            const now = Date.now();
            const period = this.plan.period === 'year' ? 365 : 30;
            return now + period * 24 * 60 * 60 * 1000;
        }

        initUsage() {
            const usage = {};
            for (const [resource, quota] of Object.entries(this.plan.quotas)) {
                usage[resource] = {
                    used: 0,
                    limit: quota.limit,
                    unit: quota.unit
                };
            }
            return usage;
        }

        // 检查资源使用
        checkResourceLimit(resourceType, amount = 1) {
            const resource = this.usage[resourceType];
            if (!resource) return { allowed: true };
            
            if (resource.limit === Infinity) {
                return { allowed: true };
            }
            
            const remaining = resource.limit - resource.used;
            const allowed = remaining >= amount;
            
            return {
                allowed,
                remaining,
                willExceed: !allowed,
                usagePercent: (resource.used / resource.limit) * 100
            };
        }

        // 记录资源使用
        recordUsage(resourceType, amount = 1, metadata = {}) {
            const check = this.checkResourceLimit(resourceType, amount);
            
            if (!check.allowed && this.billingMode !== BILLING_MODES.PAY_AS_YOU_GO) {
                return {
                    success: false,
                    error: 'Resource quota exceeded',
                    check
                };
            }

            // 更新使用量
            if (this.usage[resourceType]) {
                this.usage[resourceType].used += amount;
            }

            // 计算费用
            const cost = this.calculateCost(resourceType, amount);
            this.currentUsage += cost;

            // 检查余额（预付费）
            if (this.billingMode === BILLING_MODES.PREPAID) {
                if (this.balance < this.currentUsage) {
                    return {
                        success: false,
                        error: 'Insufficient balance',
                        required: this.currentUsage - this.balance
                    };
                }
            }

            // 记录账单明细
            this.billingHistory.push({
                resourceType,
                amount,
                cost,
                timestamp: Date.now(),
                metadata
            });

            return {
                success: true,
                cost,
                check,
                remaining: this.balance - this.currentUsage
            };
        }

        // 计算费用
        calculateCost(resourceType, amount) {
            const unitPrice = UNIT_PRICES[resourceType];
            if (!unitPrice) return 0;
            
            return amount * unitPrice.price;
        }

        // 充值
        recharge(amount) {
            if (amount <= 0) return { success: false, error: 'Invalid amount' };
            
            this.balance += amount;
            
            this.billingHistory.push({
                type: 'recharge',
                amount,
                balance: this.balance,
                timestamp: Date.now()
            });

            return { success: true, balance: this.balance };
        }

        // 创建子账号
        createSubAccount(config) {
            const subAccountLimit = this.plan.features.find(f => f.includes('子账号'));
            const maxSubAccounts = subAccountLimit ? parseInt(subAccountLimit.match(/\d+/)[0]) : 0;
            
            if (this.subAccounts.size >= maxSubAccounts) {
                return { success: false, error: 'Sub-account limit reached' };
            }

            const subAccount = new SubAccount({
                masterAccountId: this.id,
                ...config
            });

            this.subAccounts.set(subAccount.id, subAccount);
            return { success: true, subAccount };
        }

        // 生成API密钥
        generateApiKey(name, permissions = []) {
            const key = `kaelis_${this.id}_${Date.now()}_${Math.random().toString(36).substr(2, 16)}`;
            
            const apiKey = {
                id: `key_${Date.now()}`,
                name,
                key,
                permissions,
                createdAt: Date.now(),
                lastUsed: null,
                usageCount: 0
            };

            this.apiKeys.set(apiKey.id, apiKey);
            return { success: true, apiKey };
        }

        // 获取账单摘要
        getBillingSummary() {
            const now = Date.now();
            const currentMonth = new Date(now).getMonth();
            const currentYear = new Date(now).getFullYear();

            const monthlyUsage = this.billingHistory
                .filter(h => {
                    const date = new Date(h.timestamp);
                    return date.getMonth() === currentMonth && date.getFullYear() === currentYear;
                })
                .reduce((sum, h) => sum + (h.cost || 0), 0);

            return {
                plan: this.plan,
                balance: this.balance,
                currentUsage: this.currentUsage,
                monthlyUsage,
                usage: this.usage,
                expiresAt: this.expiresAt,
                subAccountCount: this.subAccounts.size,
                apiKeyCount: this.apiKeys.size
            };
        }
    }

    /**
     * 子账号
     */
    class SubAccount {
        constructor(config) {
            this.id = config.id || `sub_${Date.now()}`;
            this.masterAccountId = config.masterAccountId;
            this.name = config.name;
            this.email = config.email;
            
            this.permissions = config.permissions || [];
            this.quotas = config.quotas || {};
            this.usage = {};
            
            this.status = 'active';
            this.createdAt = Date.now();
        }

        hasPermission(permission) {
            return this.permissions.includes(permission) || this.permissions.includes('admin');
        }

        checkQuota(resourceType, amount = 1) {
            const quota = this.quotas[resourceType];
            if (!quota) return { allowed: true };
            
            const used = this.usage[resourceType] || 0;
            return {
                allowed: used + amount <= quota,
                remaining: quota - used,
                used
            };
        }
    }

    /**
     * 账单管理器
     */
    class BillingManager {
        constructor() {
            this.accounts = new Map();
            this.transactions = [];
            this.invoices = [];
            
            this.callbacks = {
                onPayment: [],
                onQuotaExceeded: [],
                onInvoiceGenerated: []
            };
        }

        // 创建主账号
        createAccount(config) {
            const account = new MasterAccount(config);
            this.accounts.set(account.id, account);
            return account;
        }

        // 获取账号
        getAccount(accountId) {
            return this.accounts.get(accountId);
        }

        // 处理资源使用
        processUsage(accountId, resourceType, amount, metadata = {}) {
            const account = this.accounts.get(accountId);
            if (!account) {
                return { success: false, error: 'Account not found' };
            }

            const result = account.recordUsage(resourceType, amount, metadata);
            
            if (!result.success && result.check?.willExceed) {
                this.triggerCallback('onQuotaExceeded', {
                    accountId,
                    resourceType,
                    ...result
                });
            }

            return result;
        }

        // 生成发票
        generateInvoice(accountId, period = 'monthly') {
            const account = this.accounts.get(accountId);
            if (!account) return null;

            const now = Date.now();
            const invoice = {
                id: `inv_${Date.now()}`,
                accountId,
                period,
                items: account.billingHistory.filter(h => h.cost && !h.invoiced),
                subtotal: 0,
                tax: 0,
                total: 0,
                status: 'pending',
                createdAt: now,
                dueDate: now + 7 * 24 * 60 * 60 * 1000 // 7天付款期
            };

            invoice.subtotal = invoice.items.reduce((sum, item) => sum + item.cost, 0);
            invoice.tax = invoice.subtotal * 0.06; // 6% 税
            invoice.total = invoice.subtotal + invoice.tax;

            // 标记为已开票
            invoice.items.forEach(item => item.invoiced = true);
            
            this.invoices.push(invoice);
            this.triggerCallback('onInvoiceGenerated', invoice);

            return invoice;
        }

        // 处理付款
        processPayment(invoiceId, paymentMethod, amount) {
            const invoice = this.invoices.find(i => i.id === invoiceId);
            if (!invoice) return { success: false, error: 'Invoice not found' };

            const account = this.accounts.get(invoice.accountId);
            if (!account) return { success: false, error: 'Account not found' };

            // 如果是预付费账号，从余额扣款
            if (account.billingMode === BILLING_MODES.PREPAID) {
                if (account.balance < amount) {
                    return { success: false, error: 'Insufficient balance' };
                }
                account.balance -= amount;
            }

            invoice.status = 'paid';
            invoice.paidAt = Date.now();
            invoice.paymentMethod = paymentMethod;

            this.transactions.push({
                id: `txn_${Date.now()}`,
                invoiceId,
                accountId: invoice.accountId,
                amount,
                paymentMethod,
                timestamp: Date.now()
            });

            this.triggerCallback('onPayment', { invoice, account });

            return { success: true, invoice };
        }

        // 获取使用统计
        getUsageStats(accountId, startDate, endDate) {
            const account = this.accounts.get(accountId);
            if (!account) return null;

            const history = account.billingHistory.filter(h => {
                return h.timestamp >= startDate && h.timestamp <= endDate;
            });

            const stats = {};
            for (const item of history) {
                if (!stats[item.resourceType]) {
                    stats[item.resourceType] = { count: 0, amount: 0, cost: 0 };
                }
                stats[item.resourceType].count++;
                stats[item.resourceType].amount += item.amount || 0;
                stats[item.resourceType].cost += item.cost || 0;
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

        triggerCallback(event, data) {
            if (this.callbacks[event]) {
                this.callbacks[event].forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        console.error(`[BillingManager] 回调错误:`, error);
                    }
                });
            }
        }
    }

    // 导出 - UMD格式
    const exports = {
        MasterAccount,
        SubAccount,
        BillingManager,
        PLAN_TYPES,
        RESOURCE_TYPES,
        BILLING_MODES,
        UNIT_PRICES
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.BillingSystem = exports;
        // 保持向后兼容
        window.BillingSystem = exports;
        window.billingManager = new BillingManager();
    }

    console.log('[BillingSystem] 收费体系已加载');
})();
