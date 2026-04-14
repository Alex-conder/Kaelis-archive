# Kaelis UI 设计规范 v2.0
## 基于 react-设计文件.zip 官方设计

---

## 1. 设计原则

- **深色主题**: 纯黑背景营造专业科技感
- **紫色品牌**: #8848F9 作为主品牌色
- **蓝色点缀**: #3B82F6 作为辅助色
- **玻璃态效果**: 模糊背景营造层次感
- **光晕装饰**: 紫色/蓝色模糊圆形增添视觉深度

---

## 2. 色彩系统

### 2.1 背景色
| 名称 | 色值 | 用途 |
|------|------|------|
| bg-primary | `#0a0a0a` | 页面主背景 |
| bg-secondary | `#171717` | 卡片、面板背景 |
| bg-tertiary | `#262626` | 次级背景、hover状态 |
| bg-hover | `rgba(255,255,255,0.05)` | 悬停效果 |

### 2.2 主题色
| 名称 | 色值 | 用途 |
|------|------|------|
| accent-purple | `#8848F9` | 主品牌色、按钮、高亮 |
| accent-purple-light | `#BD95FF` | 浅色文字、标签 |
| accent-blue | `#3B82F6` | 辅助色、链接、图标 |
| gradient-primary | `linear-gradient(135deg, #8848F9 0%, #3B82F6 100%)` | 按钮、标题、强调 |

### 2.3 文字色
| 名称 | 色值 | 用途 |
|------|------|------|
| text-primary | `#ffffff` | 主要文字 |
| text-secondary | `#a1a1a1` | 次要文字、描述 |
| text-muted | `#737373` | 静音文字、占位符 |
| text-purple | `#BD95FF` | 品牌色文字 |

### 2.4 边框与分割
| 名称 | 色值 | 用途 |
|------|------|------|
| border-default | `rgba(255,255,255,0.1)` | 默认边框 |
| border-hover | `rgba(255,255,255,0.2)` | 悬停边框 |
| divider | `rgba(255,255,255,0.05)` | 分割线 |

### 2.5 光晕效果
| 名称 | 色值 | 用途 |
|------|------|------|
| glow-purple | `rgba(136, 72, 249, 0.2)` | 紫色光晕 |
| glow-blue | `rgba(59, 130, 246, 0.2)` | 蓝色光晕 |

---

## 3. 字体规范

### 3.1 字体家族
```css
font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
```

### 3.2 字号规范
| 级别 | 大小 | 字重 | 用途 |
|------|------|------|------|
| Display | 36px | 700 | 页面大标题 |
| H1 | 28px | 700 | 区块标题 |
| H2 | 20px | 600 | 卡片标题 |
| Body | 14px | 400 | 正文内容 |
| Small | 12px | 400 | 辅助文字、标签 |
| Caption | 11px | 500 | 徽章、提示 |

### 3.3 行高
- 标题: 1.2
- 正文: 1.5
- 紧凑: 1.3

---

## 4. 组件规范

### 4.1 页面头部
```css
.header {
    background: rgba(23, 23, 23, 0.95);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(255,255,255,0.1);
    padding: 12px 32px;
}
```

### 4.2 卡片
```css
.card {
    background: #171717;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 24px;
    transition: all 0.3s ease;
}
.card:hover {
    border-color: rgba(255,255,255,0.2);
    transform: translateY(-2px);
}
```

### 4.3 按钮

#### 主按钮
```css
.btn-primary {
    background: linear-gradient(135deg, #8848F9 0%, #3B82F6 100%);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}
.btn-primary:hover {
    opacity: 0.9;
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(136, 72, 249, 0.4);
}
```

#### 次级按钮
```css
.btn-secondary {
    background: #171717;
    color: #a1a1a1;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
}
.btn-secondary:hover {
    background: #262626;
    color: #ffffff;
    border-color: rgba(255,255,255,0.2);
}
```

### 4.4 输入框
```css
.input {
    background: #171717;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 12px 16px;
    color: #ffffff;
    font-size: 14px;
    transition: all 0.3s ease;
}
.input:focus {
    outline: none;
    border-color: #8848F9;
    box-shadow: 0 0 0 3px rgba(136, 72, 249, 0.1);
}
.input::placeholder {
    color: #737373;
}
```

### 4.5 徽章/标签
```css
.badge {
    background: #171717;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 9999px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
    color: #BD95FF;
}
.badge-new {
    background: rgba(136, 72, 249, 0.2);
    color: #BD95FF;
}
.badge-hot {
    background: rgba(239, 68, 68, 0.2);
    color: #ef4444;
}
```

### 4.6 导航链接
```css
.nav-link {
    color: #a1a1a1;
    text-decoration: none;
    padding: 10px 18px;
    border-radius: 8px;
    font-size: 14px;
    transition: all 0.3s ease;
}
.nav-link:hover,
.nav-link.active {
    color: #ffffff;
    background: rgba(255,255,255,0.1);
}
```

---

## 5. 布局规范

### 5.1 页面结构
```
┌─────────────────────────────────────────┐
│  Header (固定顶部，玻璃态效果)            │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  背景光晕装饰 (紫色/蓝色)        │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  内容区域 (卡片式布局)           │   │
│  │  ┌─────┐ ┌─────┐ ┌─────┐       │   │
│  │  │Card │ │Card │ │Card │       │   │
│  │  └─────┘ └─────┘ └─────┘       │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

### 5.2 间距系统
| 名称 | 值 | 用途 |
|------|-----|------|
| space-xs | 4px | 紧凑间距 |
| space-sm | 8px | 小间距 |
| space-md | 16px | 标准间距 |
| space-lg | 24px | 大间距 |
| space-xl | 32px | 区块间距 |
| space-2xl | 48px | 大区块间距 |

### 5.3 容器宽度
- 最大宽度: 1400px
- 页面内边距: 32px (桌面) / 16px (移动)
- 卡片间隙: 20px

---

## 6. 特效规范

### 6.1 背景光晕
```css
.glow-purple {
    position: absolute;
    width: 384px;
    height: 384px;
    border-radius: 50%;
    filter: blur(64px);
    background: rgba(136, 72, 249, 0.2);
    opacity: 0.5;
    pointer-events: none;
}
.glow-blue {
    position: absolute;
    width: 384px;
    height: 384px;
    border-radius: 50%;
    filter: blur(64px);
    background: rgba(59, 130, 246, 0.2);
    opacity: 0.5;
    pointer-events: none;
}
```

### 6.2 玻璃态效果
```css
.glass {
    background: rgba(23, 23, 23, 0.8);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.1);
}
```

### 6.3 过渡动画
```css
/* 默认过渡 */
transition: all 0.3s ease;

/* 悬停效果 */
hover: transform: translateY(-2px);
hover: box-shadow: 0 4px 20px rgba(136, 72, 249, 0.3);

/* 按钮点击 */
active: transform: scale(0.98);
```

---

## 7. 响应式断点

| 断点 | 宽度 | 说明 |
|------|------|------|
| sm | 640px | 小屏手机 |
| md | 768px | 平板 |
| lg | 1024px | 小桌面 |
| xl | 1280px | 标准桌面 |
| 2xl | 1400px | 大桌面 |

---

## 8. 图标规范

- 使用 emoji 或 SVG 图标
- 图标尺寸: 20px (小), 24px (中), 32px (大)
- 图标颜色: 跟随文字颜色或使用品牌色

---

## 9. 文件位置

```
kaelis/
├── DESIGN_SPEC.md          # 本设计规范文档
├── index.html              # 总导航（已统一）
└── pages/
    ├── dashboard.html      # 仪表盘（已统一）
    ├── chat.html           # AI对话（已统一）
    ├── research-data.html  # 科研数据（已统一）
    ├── experiment-design.html # 实验设计（已统一）
    ├── paper-management.html  # 论文管理（已统一）
    ├── peer-review.html    # 科研协作（已统一）
    ├── data-visualization.html # 数据可视化（已统一）
    └── research-resources.html # 科研资源库（已统一）
```

---

**版本**: v2.0  
**基于**: react-设计文件.zip  
**更新日期**: 2026-03-17  
**设计工具**: Pixso/Figma
