/**
 * Kaelis Unified Navigation Component
 * 统一导航组件 - 动态插入标准导航
 */

(function() {
    'use strict';

    // 导航配置
    const NAV_CONFIG = {
        brand: {
            logo: '🚀',
            name: 'Kaelis',
            href: 'dashboard.html'
        },
        links: [
            { text: '首页', href: 'dashboard.html' },
            { text: '对话', href: 'chat.html' },
            { text: '插件', href: 'plugins.html' },
            { text: '设置', href: 'settings.html' }
        ],
        actions: [
            { icon: '🔔', tooltip: '通知', href: '#' },
            { icon: '👤', tooltip: '用户', href: 'profile.html' }
        ]
    };

    // 创建导航HTML
    function createNavigation() {
        const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
        
        const nav = document.createElement('nav');
        nav.className = 'nav-main';
        nav.innerHTML = `
            <div class="nav-container">
                <a href="${NAV_CONFIG.brand.href}" class="nav-brand text-gradient">
                    ${NAV_CONFIG.brand.logo} ${NAV_CONFIG.brand.name}
                </a>
                <div class="nav-links">
                    ${NAV_CONFIG.links.map(link => `
                        <a href="${link.href}" class="nav-link ${link.href === currentPage ? 'active' : ''}">${link.text}</a>
                    `).join('')}
                </div>
                <div class="nav-actions">
                    ${NAV_CONFIG.actions.map(action => `
                        <a href="${action.href}" class="btn btn-ghost btn-sm" data-tooltip="${action.tooltip}">${action.icon}</a>
                    `).join('')}
                </div>
                <button class="nav-mobile-toggle" aria-label="菜单">☰</button>
            </div>
            <div class="nav-mobile-menu">
                ${NAV_CONFIG.links.map(link => `
                    <a href="${link.href}" class="nav-mobile-link ${link.href === currentPage ? 'active' : ''}">${link.text}</a>
                `).join('')}
            </div>
        `;

        // 添加移动端菜单切换
        const mobileToggle = nav.querySelector('.nav-mobile-toggle');
        const mobileMenu = nav.querySelector('.nav-mobile-menu');
        
        if (mobileToggle && mobileMenu) {
            mobileToggle.addEventListener('click', () => {
                mobileMenu.classList.toggle('active');
                mobileToggle.classList.toggle('active');
            });
        }

        return nav;
    }

    // 插入导航到页面
    function insertNavigation() {
        // 检查是否已存在导航
        if (document.querySelector('.nav-main')) {
            return;
        }

        // 检查是否是登录/注册页面（不需要导航）
        const currentPage = window.location.pathname.split('/').pop();
        if (['login.html', 'register.html', 'forgot-password.html'].includes(currentPage)) {
            return;
        }

        const nav = createNavigation();
        document.body.insertBefore(nav, document.body.firstChild);

        // 为页面内容添加顶部间距
        const main = document.querySelector('main') || document.querySelector('.container');
        if (main) {
            main.style.paddingTop = '80px';
        }
    }

    // 页面加载完成后插入导航
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', insertNavigation);
    } else {
        insertNavigation();
    }

    // 导出 - UMD格式
    const exports = {
        config: NAV_CONFIG,
        refresh: insertNavigation
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.Nav = exports;
        // 保持向后兼容
        window.KaelisNav = exports;
    }
})();
