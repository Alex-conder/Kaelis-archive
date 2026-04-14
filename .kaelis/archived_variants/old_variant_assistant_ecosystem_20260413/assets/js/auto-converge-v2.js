/**
 * Kaelis Auto-Converge v2.0 - Intelligent Page Classification
 * 智能页面分类与自动化收敛系统
 */

(function() {
    'use strict';

    // 页面类型定义
    const PAGE_TYPES = {
        DASHBOARD: {
            keywords: ['dashboard', '仪表盘', '首页', 'overview', '概览'],
            styles: ['grid-layout', 'metrics', 'charts'],
            navItems: ['dashboard', 'chat', 'plugins', 'settings']
        },
        CHAT: {
            keywords: ['chat', '对话', 'message', '消息', 'conversation'],
            styles: ['flex-layout', 'messages', 'input-area'],
            navItems: ['dashboard', 'chat', 'plugins', 'settings']
        },
        FORM: {
            keywords: ['form', '表单', 'login', 'register', 'settings', '设置'],
            styles: ['form-layout', 'inputs', 'validation'],
            navItems: ['dashboard', 'chat', 'plugins', 'settings']
        },
        DATA: {
            keywords: ['data', '数据', 'table', 'list', 'grid', '表格'],
            styles: ['table-layout', 'filters', 'pagination'],
            navItems: ['dashboard', 'chat', 'plugins', 'settings']
        },
        VISUALIZATION: {
            keywords: ['visualization', '可视化', 'chart', 'graph', '3d', 'canvas'],
            styles: ['canvas-layout', 'charts', 'controls'],
            navItems: ['dashboard', 'chat', 'plugins', 'settings']
        },
        RESEARCH: {
            keywords: ['research', '科研', 'experiment', 'paper', 'docking', '分子'],
            styles: ['research-layout', 'scientific', 'data-view'],
            navItems: ['research-data', 'experiment-design', 'paper-management', 'settings']
        }
    };

    // 高频内联样式映射
    const STYLE_MAPPINGS = {
        // 基础reset - 如果已加载variables.css则移除
        reset: {
            pattern: /\*\s*\{\s*margin:\s*0;\s*padding:\s*0;\s*box-sizing:\s*border-box;\s*\}/g,
            replacement: '',
            condition: () => document.querySelector('link[href*="variables.css"]')
        },
        // body基础样式
        bodyBase: {
            pattern: /body\s*\{\s*font-family:\s*[^}]+;\s*background:\s*[^}]+;\s*color:\s*[^}]+;\s*\}/g,
            replacement: '',
            condition: () => document.querySelector('link[href*="variables.css"]')
        },
        // 卡片样式统一
        card: {
            pattern: /\.(?:card|panel|box)[^{]*\{\s*background:\s*rgba\(23,\s*23,\s*23[^}]+;\s*border:\s*1px\s+solid\s+rgba\(255,\s*255,\s*255,\s*0\.1\)[^}]*\}/g,
            replacement: '.converged-card { @extend .card; }',
            condition: () => true
        },
        // 按钮主色
        btnPrimary: {
            pattern: /\.(?:btn-primary|button-primary)[^{]*\{\s*background:\s*linear-gradient\(135deg,\s*#8848F9[^}]+\}/g,
            replacement: '.converged-btn-primary { @extend .btn-primary; }',
            condition: () => true
        }
    };

    // 检测页面类型
    function detectPageType() {
        const url = window.location.pathname.toLowerCase();
        const title = document.title.toLowerCase();
        const content = document.body.innerText.toLowerCase().slice(0, 5000);
        
        const scores = {};
        
        for (const [type, config] of Object.entries(PAGE_TYPES)) {
            scores[type] = 0;
            
            // URL匹配
            config.keywords.forEach(keyword => {
                if (url.includes(keyword.toLowerCase())) scores[type] += 3;
            });
            
            // 标题匹配
            config.keywords.forEach(keyword => {
                if (title.includes(keyword.toLowerCase())) scores[type] += 2;
            });
            
            // 内容匹配
            config.keywords.forEach(keyword => {
                const matches = content.split(keyword.toLowerCase()).length - 1;
                scores[type] += matches;
            });
        }
        
        // 返回得分最高的类型
        const detectedType = Object.entries(scores)
            .sort((a, b) => b[1] - a[1])[0];
        
        return detectedType[1] > 0 ? detectedType[0] : 'GENERIC';
    }

    // 应用页面类型特定样式
    function applyPageTypeStyles(pageType) {
        const body = document.body;
        body.setAttribute('data-page-type', pageType.toLowerCase());
        
        // 添加页面类型特定类
        body.classList.add(`page-${pageType.toLowerCase()}`);
        
        // 应用特定布局优化
        switch(pageType) {
            case 'DASHBOARD':
                optimizeDashboardLayout();
                break;
            case 'CHAT':
                optimizeChatLayout();
                break;
            case 'FORM':
                optimizeFormLayout();
                break;
            case 'DATA':
                optimizeDataLayout();
                break;
            case 'VISUALIZATION':
                optimizeVisualizationLayout();
                break;
            case 'RESEARCH':
                optimizeResearchLayout();
                break;
        }
    }

    // 优化仪表盘布局
    function optimizeDashboardLayout() {
        // 统一网格系统
        document.querySelectorAll('[class*="grid"]').forEach(el => {
            if (!el.classList.contains('converged-grid')) {
                el.classList.add('converged-grid');
                el.style.display = 'grid';
                el.style.gap = 'var(--space-lg)';
            }
        });
        
        // 统一指标卡片
        document.querySelectorAll('[class*="metric"], [class*="stat"]').forEach(el => {
            el.classList.add('card', 'card-hover');
        });
    }

    // 优化聊天布局
    function optimizeChatLayout() {
        // 统一消息区域
        document.querySelectorAll('[class*="message"]').forEach(el => {
            el.style.maxWidth = '80%';
            el.style.marginBottom = 'var(--space-md)';
        });
        
        // 统一输入区域
        document.querySelectorAll('[class*="input"], textarea').forEach(el => {
            el.classList.add('form-input');
        });
    }

    // 优化表单布局
    function optimizeFormLayout() {
        // 统一表单组
        document.querySelectorAll('input, select, textarea').forEach(el => {
            if (!el.classList.contains('form-input') && !el.classList.contains('btn')) {
                el.classList.add('form-input');
            }
        });
        
        // 统一标签
        document.querySelectorAll('label').forEach(el => {
            el.classList.add('form-label');
        });
        
        // 统一按钮
        document.querySelectorAll('button:not([class])').forEach(el => {
            el.classList.add('btn', 'btn-primary');
        });
    }

    // 优化数据布局
    function optimizeDataLayout() {
        // 统一表格
        document.querySelectorAll('table').forEach(el => {
            el.classList.add('table');
        });
        
        // 统一筛选器
        document.querySelectorAll('[class*="filter"]').forEach(el => {
            el.classList.add('card');
        });
    }

    // 优化可视化布局
    function optimizeVisualizationLayout() {
        // 统一画布容器
        document.querySelectorAll('canvas, svg').forEach(el => {
            el.style.maxWidth = '100%';
            el.style.height = 'auto';
        });
    }

    // 优化科研布局
    function optimizeResearchLayout() {
        // 科研页面保持原有结构，添加统一卡片样式
        document.querySelectorAll('[class*="panel"], [class*="section"]').forEach(el => {
            if (!el.classList.contains('card')) {
                el.classList.add('card');
            }
        });
    }

    // 清理和迁移内联样式
    function cleanupInlineStyles() {
        const styleTags = document.querySelectorAll('style:not([data-preserve])');
        let cleanedCount = 0;
        
        styleTags.forEach(style => {
            let css = style.textContent;
            let originalLength = css.length;
            
            // 应用样式映射
            for (const [name, mapping] of Object.entries(STYLE_MAPPINGS)) {
                if (mapping.condition()) {
                    css = css.replace(mapping.pattern, mapping.replacement);
                }
            }
            
            // 清理空规则
            css = css.replace(/[^{}]+\{\s*\}/g, '');
            
            // 如果样式大幅减少，标记为已清理
            if (css.length < originalLength * 0.5) {
                cleanedCount++;
                style.setAttribute('data-cleaned', 'true');
            }
            
            style.textContent = css;
        });
        
        console.log(`[Kaelis Converge] 清理了 ${cleanedCount} 个样式标签`);
    }

    // 统一交互元素
    function unifyInteractiveElements() {
        // 统一按钮
        document.querySelectorAll('button:not([class*="btn"])').forEach(btn => {
            const classes = ['btn'];
            
            // 根据上下文推断按钮类型
            if (btn.type === 'submit' || btn.textContent.includes('保存') || btn.textContent.includes('确认')) {
                classes.push('btn-primary');
            } else if (btn.textContent.includes('取消') || btn.textContent.includes('删除')) {
                classes.push('btn-secondary');
            } else {
                classes.push('btn-secondary');
            }
            
            btn.classList.add(...classes);
        });
        
        // 统一链接按钮
        document.querySelectorAll('a[role="button"]').forEach(link => {
            link.classList.add('btn', 'btn-secondary');
        });
    }

    // 添加页面收敛报告
    function generateConvergenceReport() {
        const report = {
            pageType: detectPageType(),
            url: window.location.pathname,
            elements: {
                buttons: document.querySelectorAll('button').length,
                cards: document.querySelectorAll('.card, [class*="card"]').length,
                forms: document.querySelectorAll('form').length,
                tables: document.querySelectorAll('table').length
            },
            styles: {
                inlineStyleTags: document.querySelectorAll('style').length,
                cleanedStyles: document.querySelectorAll('style[data-cleaned]').length
            }
        };
        
        console.log('[Kaelis Converge] 收敛报告:', report);
        return report;
    }

    // 主执行函数
    function init() {
        console.log('[Kaelis Converge v2.0] 启动...');
        
        // 1. 检测页面类型
        const pageType = detectPageType();
        console.log(`[Kaelis Converge] 检测到页面类型: ${pageType}`);
        
        // 2. 应用页面类型特定样式
        applyPageTypeStyles(pageType);
        
        // 3. 清理内联样式
        cleanupInlineStyles();
        
        // 4. 统一交互元素
        unifyInteractiveElements();
        
        // 5. 生成收敛报告
        generateConvergenceReport();
        
        console.log('[Kaelis Converge] 收敛完成');
    }

    // 页面加载完成后执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // 导出 - UMD格式
    const exports = {
        version: '2.0',
        detectPageType,
        applyPageTypeStyles,
        cleanupInlineStyles,
        generateConvergenceReport,
        PAGE_TYPES
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.Converge = exports;
        // 保持向后兼容
        window.KaelisConverge = exports;
    }
})();
