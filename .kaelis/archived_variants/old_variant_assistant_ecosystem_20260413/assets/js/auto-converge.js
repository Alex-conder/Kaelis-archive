/**
 * Kaelis Auto-Converge Script
 * 自动收敛脚本 - 应用到所有页面
 */
(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';
    
    function init() {
        // 统一导航高亮
        const currentPage = location.pathname.split('/').pop() || 'dashboard.html';
        document.querySelectorAll('nav a').forEach(link => {
            if (link.getAttribute('href') === currentPage) {
                link.classList.add('active');
            }
        });
        
        // 统一按钮样式
        document.querySelectorAll('button:not([class])').forEach(btn => {
            btn.classList.add('btn', 'btn-secondary');
        });
        
        // 统一卡片样式
        document.querySelectorAll('div[style*="background"]').forEach(card => {
            if (card.style.background.includes('23, 23, 23') || card.style.background.includes('card')) {
                card.classList.add('card');
            }
        });
        
        console.log('[Kaelis] 自动收敛脚本已执行');
    }
    
    // 自动执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    return { init };
}));
