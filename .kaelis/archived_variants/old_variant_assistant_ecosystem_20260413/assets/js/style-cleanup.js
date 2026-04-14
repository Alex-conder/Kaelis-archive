/**
 * Kaelis Style Cleanup Script
 * 自动清理冗余内联样式
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
    
    function cleanup() {
        // 清理重复的基础reset样式
        const styleTags = document.querySelectorAll('style');
        styleTags.forEach(style => {
            let css = style.textContent;
            
            // 移除与variables.css重复的:root定义
            css = css.replace(/:root\s*\{[^}]*\}/g, '');
            
            // 移除重复的基础reset（如果已加载variables.css）
            if (document.querySelector('link[href*="variables.css"]')) {
                css = css.replace(/\*\s*\{\s*margin:\s*0;\s*padding:\s*0;\s*box-sizing:\s*border-box;\s*\}/g, '');
                css = css.replace(/body\s*\{\s*font-family:[^}]*\}/g, '');
            }
            
            // 清理空样式标签
            style.textContent = css.trim();
            if (!style.textContent) {
                style.remove();
            }
        });
        
        console.log('[Kaelis] 样式清理完成');
    }
    
    // 自动执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', cleanup);
    } else {
        cleanup();
    }
    
    return { cleanup };
}));
