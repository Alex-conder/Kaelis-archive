/**
 * Kaelis Main JavaScript
 * 统一的交互逻辑和组件行为
 */

// ========== DOM Ready ==========
document.addEventListener('DOMContentLoaded', function() {
    initNavigation();
    initToggles();
    initForms();
    initTooltips();
});

// ========== 导航逻辑 ==========
function initNavigation() {
    // 高亮当前页面导航
    const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href === currentPage || (currentPage === '' && href === 'dashboard.html')) {
            link.classList.add('active');
        }
    });
    
    // 移动端菜单切换
    const mobileMenuBtn = document.querySelector('.nav-mobile-toggle');
    const mobileMenu = document.querySelector('.nav-mobile-menu');
    
    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('active');
            mobileMenuBtn.classList.toggle('active');
        });
    }
}

// ========== 开关组件逻辑 ==========
function initToggles() {
    const toggles = document.querySelectorAll('.toggle');
    
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            this.classList.toggle('active');
            const isActive = this.classList.contains('active');
            
            // 触发自定义事件
            this.dispatchEvent(new CustomEvent('toggle', { 
                detail: { active: isActive } 
            }));
        });
    });
}

// ========== 表单验证逻辑 ==========
function initForms() {
    const forms = document.querySelectorAll('form[data-validate]');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (validateForm(this)) {
                // 提交表单
                const submitBtn = this.querySelector('[type="submit"]');
                if (submitBtn) {
                    setLoading(submitBtn, true);
                    
                    // 模拟提交
                    setTimeout(() => {
                        setLoading(submitBtn, false);
                        showToast('操作成功', 'success');
                    }, 1500);
                }
            }
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    
    inputs.forEach(input => {
        const formGroup = input.closest('.form-group');
        const errorMsg = formGroup?.querySelector('.form-error-message');
        
        if (!input.value.trim()) {
            isValid = false;
            input.classList.add('form-error');
            if (errorMsg) errorMsg.style.display = 'block';
        } else {
            input.classList.remove('form-error');
            if (errorMsg) errorMsg.style.display = 'none';
        }
    });
    
    return isValid;
}

// ========== 加载状态 ==========
function setLoading(element, isLoading) {
    if (isLoading) {
        element.classList.add('loading');
        element.disabled = true;
    } else {
        element.classList.remove('loading');
        element.disabled = false;
    }
}

// ========== Toast 提示 ==========
function showToast(message, type = 'info', duration = 3000) {
    // 移除已存在的 toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    // 创建新 toast - 使用textContent防止XSS
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // 创建图标元素
    const iconSpan = document.createElement('span');
    iconSpan.className = 'toast-icon';
    iconSpan.textContent = getToastIcon(type);
    
    // 创建消息元素
    const messageSpan = document.createElement('span');
    messageSpan.className = 'toast-message';
    messageSpan.textContent = message; // 使用textContent防止XSS
    
    toast.appendChild(iconSpan);
    toast.appendChild(messageSpan);
    
    // 样式
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 24px;
        background: ${getToastColor(type)};
        color: white;
        border-radius: 12px;
        font-weight: 500;
        z-index: 9999;
        transform: translateX(150%);
        transition: transform 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    `;
    
    document.body.appendChild(toast);
    
    // 显示动画
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(0)';
    });
    
    // 自动隐藏
    setTimeout(() => {
        toast.style.transform = 'translateX(150%)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function getToastIcon(type) {
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    return icons[type] || icons.info;
}

function getToastColor(type) {
    const colors = {
        success: '#22C55E',
        error: '#EF4444',
        warning: '#F59E0B',
        info: '#3B82F6'
    };
    return colors[type] || colors.info;
}

// ========== 工具提示 ==========
function initTooltips() {
    const tooltipTriggers = document.querySelectorAll('[data-tooltip]');
    
    tooltipTriggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', function(e) {
            const text = this.getAttribute('data-tooltip');
            showTooltip(e, text);
        });
        
        trigger.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(e, text) {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = text;
    tooltip.style.cssText = `
        position: fixed;
        padding: 8px 12px;
        background: rgba(0,0,0,0.9);
        color: white;
        font-size: 12px;
        border-radius: 6px;
        white-space: nowrap;
        z-index: 9999;
        pointer-events: none;
    `;
    
    document.body.appendChild(tooltip);
    
    const rect = e.target.getBoundingClientRect();
    tooltip.style.left = `${rect.left + rect.width/2 - tooltip.offsetWidth/2}px`;
    tooltip.style.top = `${rect.top - tooltip.offsetHeight - 8}px`;
}

function hideTooltip() {
    const tooltip = document.querySelector('.tooltip');
    if (tooltip) tooltip.remove();
}

// ========== 模态框 ==========
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// ========== 确认对话框 ==========
function confirmDialog(message, onConfirm, onCancel) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    `;
    
    // 创建对话框内容 - 使用DOM API防止XSS
    const dialog = document.createElement('div');
    dialog.style.cssText = `
        background: var(--bg-card, #171717);
        border: 1px solid var(--border-color, rgba(255,255,255,0.1));
        border-radius: 16px;
        padding: 32px;
        max-width: 400px;
        text-align: center;
    `;
    
    // 警告图标
    const iconDiv = document.createElement('div');
    iconDiv.style.cssText = 'font-size: 48px; margin-bottom: 16px;';
    iconDiv.textContent = '⚠️';
    
    // 消息文本 - 使用textContent防止XSS
    const messageP = document.createElement('p');
    messageP.style.cssText = 'margin-bottom: 24px; color: var(--text-primary, #fff);';
    messageP.textContent = message;
    
    // 按钮容器
    const btnContainer = document.createElement('div');
    btnContainer.style.cssText = 'display: flex; gap: 12px; justify-content: center;';
    
    // 取消按钮
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-secondary';
    cancelBtn.textContent = '取消';
    cancelBtn.addEventListener('click', () => {
        overlay.remove();
        if (onCancel) onCancel();
    });
    
    // 确认按钮
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'btn btn-primary';
    confirmBtn.textContent = '确认';
    confirmBtn.addEventListener('click', () => {
        overlay.remove();
        if (onConfirm) onConfirm();
    });
    
    btnContainer.appendChild(cancelBtn);
    btnContainer.appendChild(confirmBtn);
    
    dialog.appendChild(iconDiv);
    dialog.appendChild(messageP);
    dialog.appendChild(btnContainer);
    overlay.appendChild(dialog);
    
    document.body.appendChild(overlay);
    
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.remove();
            if (onCancel) onCancel();
        }
    });
}

// ========== 统一模块导出 (UMD格式) ==========
(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        Object.assign(root.Kaelis, factory());
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';
    
    return {
        showToast,
        setLoading,
        openModal,
        closeModal,
        confirmDialog,
        validateForm,
        initNavigation,
        initToggles,
        initForms,
        initTooltips,
        showTooltip,
        hideTooltip
    };
}));
