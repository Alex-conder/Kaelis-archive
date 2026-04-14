# Kaelis 系统 UI 风格统一总结

## 更新日期
2026年3月17日

## 设计规范来源
从 `E:\react-设计文件.zip` 提取的设计规范

## 已更新的文件

### 1. 核心样式文件
- `assets/styles/variables.css` - CSS变量定义
- `assets/styles/components.css` - 组件样式

### 2. 页面文件 (9个)
1. `index.html` - 总导航页面
2. `pages/dashboard.html` - 仪表盘
3. `pages/chat.html` - AI对话
4. `pages/research-data.html` - 科研数据
5. `pages/experiment-design.html` - 实验设计
6. `pages/paper-management.html` - 论文管理
7. `pages/peer-review.html` - 科研协作
8. `pages/data-visualization.html` - 数据可视化
9. `pages/research-resources.html` - 科研资源库

## 设计规范应用

### 色彩系统 (已更新)
```css
/* 主背景 */
--bg-primary: #0a0a0a;          /* 主背景色 */
--bg-secondary: #171717;        /* 卡片背景 */
--bg-tertiary: #262626;         /* 次级背景 */

/* 主题色 - 紫蓝渐变 */
--primary-gradient: linear-gradient(135deg, #8848F9 0%, #3B82F6 100%);
--accent-purple: #8848F9;
--accent-purple-light: #BD95FF;
--accent-blue: #3B82F6;

/* 文字颜色 */
--text-primary: #ffffff;
--text-secondary: #a1a1a1;
--text-muted: #737373;

/* 光晕效果 */
--glow-purple: rgba(136, 72, 249, 0.2);
--glow-blue: rgba(59, 130, 246, 0.2);
```

### 主要变更点

1. **深色主题统一**: 所有页面背景改为 `#0a0a0a`
2. **主题色更新**: 从旧渐变 (#667eea → #764ba2) 改为新紫蓝渐变 (#8848F9 → #3B82F6)
3. **背景光晕**: 每个页面添加了紫色和蓝色的背景光晕效果 (filter: blur(64px))
4. **卡片样式**: 统一使用 `#171717` 背景色和 `16px` 圆角
5. **文字颜色**: 统一使用 `#ffffff` (主要)、`#a1a1a1` (次要)、`#737373` (静音)
6. **边框颜色**: 统一使用 `rgba(255, 255, 255, 0.1)`
7. **按钮样式**: 统一使用紫蓝渐变背景
8. **玻璃态效果**: 导航栏使用 `backdrop-filter: blur(10px)`

### 组件样式统一

#### 按钮样式
```css
.btn-primary {
    background: linear-gradient(135deg, #8848F9 0%, #3B82F6 100%);
    color: white;
    border-radius: 10px;
    padding: 12px 24px;
}
```

#### 卡片样式
```css
.card {
    background: #171717;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 24px;
}
```

#### 页面头部
```css
.top-nav, .top-bar {
    background: rgba(23, 23, 23, 0.95);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(255,255,255,0.1);
}
```

### 4. 导航栏统一
所有页面现在使用统一的顶部导航栏：
- **左侧**: Logo 区域（🚀 Kaelis）
- **中间**: 导航菜单（仪表盘、对话、科研数据、实验设计、论文管理等）
- **右侧**: 通知按钮 + 用户头像

### 5. 更新的页面列表

| 页面 | 文件名 | 状态 |
|------|--------|------|
| 仪表盘 | `dashboard.html` | ✅ 已统一 |
| AI对话 | `chat.html` | ✅ 已统一 |
| 科研数据管理 | `research-data.html` | ✅ 已统一 |
| 实验设计 | `experiment-design.html` | ✅ 已统一 |
| 论文管理 | `paper-management.html` | ✅ 已统一 |
| 科研协作 | `peer-review.html` | ✅ 已统一 |
| 数据可视化 | `data-visualization.html` | ✅ 已统一 |
| 科研资源库 | `research-resources.html` | ✅ 已统一 |

### 6. 新增/更新的 CSS 文件

| 文件 | 用途 |
|------|------|
| `assets/styles/variables.css` | CSS 变量定义（色彩、间距、圆角等） |
| `assets/styles/components.css` | 统一组件样式（按钮、卡片、表格等） |

## 设计特点

### 深色主题
- 所有页面采用深色背景，减少眼部疲劳
- 使用半透明卡片营造层次感
- 渐变色彩增添视觉吸引力

### 响应式设计
- 所有页面支持移动端适配
- 使用 CSS Grid 和 Flexbox 实现灵活布局
- 断点：1200px、768px

### 交互效果
- 按钮悬停效果（上浮 + 阴影）
- 卡片悬停效果（边框高亮）
- 导航项激活状态
- 平滑过渡动画

## 使用方式

### 引入样式文件
```html
<link rel="stylesheet" href="../assets/styles/variables.css">
<link rel="stylesheet" href="../assets/styles/components.css">
```

### 使用 CSS 变量
```css
.my-element {
    background: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
}
```

## 后续维护建议

1. **新增页面**: 复制现有页面结构，引入统一样式文件
2. **样式修改**: 修改 `variables.css` 中的变量即可全局生效
3. **组件扩展**: 在 `components.css` 中添加新组件样式
4. **主题切换**: 可通过修改变量实现浅色主题

## 文件结构
```
kaelis/
├── assets/
│   └── styles/
│       ├── variables.css    # CSS 变量
│       ├── components.css   # 组件样式
│       ├── font.css         # 字体样式
│       └── global.css       # 全局样式
├── pages/
│   ├── dashboard.html       # 仪表盘
│   ├── chat.html            # AI对话
│   ├── research-data.html   # 科研数据管理
│   ├── experiment-design.html # 实验设计
│   ├── paper-management.html  # 论文管理
│   ├── peer-review.html     # 科研协作
│   ├── data-visualization.html # 数据可视化
│   └── research-resources.html # 科研资源库
└── index.html               # 主页面
```
