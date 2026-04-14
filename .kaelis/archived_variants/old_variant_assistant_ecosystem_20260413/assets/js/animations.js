/**
 * Kaelis Animation System v1.0
 * 适应性动画设计 - Adaptive Animation Design
 */

class KaelisAnimations {
    constructor() {
        this.observers = new Map();
        this.init();
    }

    init() {
        this.initScrollAnimations();
        this.initHoverEffects();
        this.initPageTransitions();
        this.initStaggerAnimations();
    }

    /* ============================================
       1. 滚动触发动画
       ============================================ */
    initScrollAnimations() {
        const scrollElements = document.querySelectorAll('.scroll-animate');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    // 可选：只触发一次
                    // observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });

        scrollElements.forEach(el => observer.observe(el));
    }

    /* ============================================
       2. 交错动画
       ============================================ */
    initStaggerAnimations() {
        const staggerContainers = document.querySelectorAll('.stagger-animate');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, {
            threshold: 0.1
        });

        staggerContainers.forEach(el => observer.observe(el));
    }

    /* ============================================
       3. 悬停效果增强
       ============================================ */
    initHoverEffects() {
        // 3D 倾斜效果
        const tiltElements = document.querySelectorAll('.tilt-hover');
        
        tiltElements.forEach(el => {
            el.addEventListener('mousemove', (e) => {
                const rect = el.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                
                const rotateX = (y - centerY) / 10;
                const rotateY = (centerX - x) / 10;
                
                el.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;
            });
            
            el.addEventListener('mouseleave', () => {
                el.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateZ(0)';
            });
        });

        // 磁性按钮效果
        const magneticElements = document.querySelectorAll('.magnetic-hover');
        
        magneticElements.forEach(el => {
            el.addEventListener('mousemove', (e) => {
                const rect = el.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;
                
                el.style.transform = `translate(${x * 0.3}px, ${y * 0.3}px)`;
            });
            
            el.addEventListener('mouseleave', () => {
                el.style.transform = 'translate(0, 0)';
            });
        });
    }

    /* ============================================
       4. 页面过渡动画
       ============================================ */
    initPageTransitions() {
        // 页面加载动画
        document.addEventListener('DOMContentLoaded', () => {
            document.body.classList.add('page-transition');
            
            // 为元素添加延迟动画
            const animatedElements = document.querySelectorAll('[data-animate]');
            animatedElements.forEach((el, index) => {
                const delay = el.dataset.delay || index * 0.1;
                el.style.animationDelay = `${delay}s`;
                el.classList.add(`animate-${el.dataset.animate}`);
            });
        });

        // 链接点击过渡
        document.querySelectorAll('a[href]').forEach(link => {
            link.addEventListener('click', (e) => {
                const href = link.getAttribute('href');
                if (href && !href.startsWith('#') && !href.startsWith('javascript:')) {
                    e.preventDefault();
                    document.body.classList.add('page-transition-out');
                    
                    setTimeout(() => {
                        window.location.href = href;
                    }, 200);
                }
            });
        });
    }

    /* ============================================
       5. 工具方法
       ============================================ */
    
    // 添加动画到元素
    animate(element, animationName, duration = '0.3s', delay = '0s') {
        const el = typeof element === 'string' ? document.querySelector(element) : element;
        if (!el) return;
        
        el.style.animationDuration = duration;
        el.style.animationDelay = delay;
        el.classList.add(`animate-${animationName}`);
        
        // 动画结束后移除类
        el.addEventListener('animationend', () => {
            el.classList.remove(`animate-${animationName}`);
        }, { once: true });
    }

    // 淡入
    fadeIn(element, duration = '0.3s') {
        this.animate(element, 'fade-in', duration);
    }

    // 淡入上滑
    fadeInUp(element, duration = '0.3s', delay = '0s') {
        this.animate(element, 'fade-in-up', duration, delay);
    }

    // 缩放进入
    scaleIn(element, duration = '0.3s') {
        this.animate(element, 'scale-in', duration);
    }

    // 脉冲效果
    pulse(element) {
        this.animate(element, 'pulse', '2s');
    }

    // 停止动画
    stopAnimation(element) {
        const el = typeof element === 'string' ? document.querySelector(element) : element;
        if (el) {
            el.style.animation = 'none';
            el.offsetHeight; // 触发重排
            el.style.animation = '';
        }
    }

    /* ============================================
       6. 数字计数动画
       ============================================ */
    animateNumber(element, target, duration = 2000, suffix = '') {
        const el = typeof element === 'string' ? document.querySelector(element) : element;
        if (!el) return;

        const start = parseInt(el.textContent) || 0;
        const range = target - start;
        const startTime = performance.now();

        const updateNumber = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // 使用缓动函数
            const easeOutQuart = 1 - Math.pow(1 - progress, 4);
            const current = Math.floor(start + range * easeOutQuart);
            
            el.textContent = current + suffix;
            
            if (progress < 1) {
                requestAnimationFrame(updateNumber);
            }
        };

        requestAnimationFrame(updateNumber);
    }

    /* ============================================
       7. 打字机效果
       ============================================ */
    typewriter(element, text, speed = 50) {
        const el = typeof element === 'string' ? document.querySelector(element) : element;
        if (!el) return;

        el.textContent = '';
        let i = 0;

        const type = () => {
            if (i < text.length) {
                el.textContent += text.charAt(i);
                i++;
                setTimeout(type, speed);
            }
        };

        type();
    }

    /* ============================================
       8. 视差滚动
       ============================================ */
    initParallax() {
        const parallaxElements = document.querySelectorAll('.parallax');
        
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            
            parallaxElements.forEach(el => {
                const speed = el.dataset.speed || 0.5;
                el.style.transform = `translateY(${scrolled * speed}px)`;
            });
        });
    }
}

// 初始化动画系统
const kaelisAnimations = new KaelisAnimations();

// 导出 - UMD格式
const exports = {
    KaelisAnimations,
    kaelisAnimations
};

if (typeof define === 'function' && define.amd) {
    define([], function() { return exports; });
} else if (typeof module === 'object' && module.exports) {
    module.exports = exports;
} else {
    window.Kaelis = window.Kaelis || {};
    window.Kaelis.Animations = exports;
    // 保持向后兼容
    window.KaelisAnimations = KaelisAnimations;
    window.kaelisAnimations = kaelisAnimations;
}
