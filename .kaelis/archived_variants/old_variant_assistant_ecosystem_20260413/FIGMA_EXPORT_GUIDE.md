# Kaelis UI - Figma 导出指南

## 页面结构

### Frame: Desktop (1440x900)
- P01_Login
- P02_Dashboard
- P03_Chat
- P04_Plugins
- P05_PluginDetail
- P06_Monitoring
- P07_Security
- P08_Settings
- P09_Profile
- P10_Help
- P11_Voice
- P12_Cluster
- P13_Pipeline
- P14_DisasterRecovery

### Frame: Mobile (375x812)
- M01_Login
- M02_Dashboard
- M03_Chat
- M04_Plugins
- M05_Menu

### Frame: Components
- Atoms/
  - Button/Primary
  - Button/Secondary
  - Button/Ghost
  - Button/Icon
  - Input/Text
  - Input/Search
  - Input/Select
  - Card/Default
  - Card/Metric
  - Card/Plugin
  - Icon/Set

- Molecules/
  - Navigation/Top
  - Navigation/Side
  - Navigation/Bottom
  - List/Item
  - Message/Bubble
  - Alert/Toast

- Organisms/
  - Header
  - Sidebar
  - ChatArea
  - PluginGrid
  - MetricDashboard
  - SecurityScore

## 颜色样式 (Figma Styles)

### Colors
- primary/500: #667eea
- primary/600: #5a67d8
- accent/purple: #764ba2
- accent/pink: #f093fb
- neutral/50: #f8fafc
- neutral/100: #f1f5f9
- neutral/800: #1e293b
- success: #22c55e
- warning: #f59e0b
- error: #ef4444

### Gradients
- gradient-primary: #667eea → #764ba2
- gradient-card: rgba(255,255,255,0.95)
- gradient-dark: #1e293b → #0f172a

## 文本样式 (Figma Styles)

### Display
- H1: Inter Bold 48px
- H2: Inter Bold 32px
- H3: Inter SemiBold 24px

### Body
- Body Large: Inter Regular 18px
- Body: Inter Regular 16px
- Body Small: Inter Regular 14px
- Caption: Inter Regular 12px

## 导出规格

### 图标 (SVG)
尺寸: 24x24px
格式: SVG
命名: icon-[name].svg

### 图片 (PNG)
Logo: 512x512px
插图: 根据使用场景
格式: PNG (透明背景)

### 切图 (PNG @2x)
按钮: 根据实际尺寸 x2
卡片: 根据实际尺寸 x2

## 标注规范

### 间距标注
- 使用 8px 网格
- 标注所有间距值
- 标注组件内边距

### 尺寸标注
- 按钮: 宽度 x 高度
- 输入框: 宽度 x 高度
- 卡片: 宽度 x 高度

### 颜色标注
- 背景色
- 文字色
- 边框色
- 阴影值

### 字体标注
- 字体家族
- 字号
- 字重
- 行高

## 交互原型

### 页面切换
- 转场: 淡入 + 滑动
- 时长: 300ms
- 缓动: ease-out

### 按钮交互
- 悬停: 上浮 2px
- 按下: 缩放 0.95
- 时长: 150ms

### 卡片交互
- 悬停: 阴影增强
- 时长: 200ms

### 语音界面
- 麦克风: 脉冲动画
- 波形: 声音可视化
- 识别: 打字机效果

## 开发交接清单

- [ ] 所有页面设计完成
- [ ] 所有组件设计完成
- [ ] 颜色样式已定义
- [ ] 文本样式已定义
- [ ] 间距已标注
- [ ] 交互原型已制作
- [ ] 资源已导出
- [ ] 设计规范文档已更新

## 设计资源

Figma 文件: Kaelis-UI-v1.0.fig
共享链接: [待创建]
权限: 查看 + 评论

---

*导出日期: 2026-03-17*
*版本: v1.0*
