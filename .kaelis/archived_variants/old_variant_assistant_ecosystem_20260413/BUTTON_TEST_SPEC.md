# Kaelis UI 按钮交互测试与开发规范

## 按钮类型与状态

### 1. 主要按钮 (Primary Button)
- **用途**: 主要操作、提交表单
- **样式**: 渐变背景 #8848F9 → #3B82F6
- **状态**: default | hover | active | loading | disabled

### 2. 次要按钮 (Secondary Button)
- **用途**: 取消、返回、次要操作
- **样式**: 白色背景 + 边框
- **状态**: default | hover | active | disabled

### 3. 文字按钮 (Text Button)
- **用途**: 链接、低优先级操作
- **样式**: 纯文字 + 下划线
- **状态**: default | hover | active

### 4. 图标按钮 (Icon Button)
- **用途**: 工具栏、快捷操作
- **样式**: 圆形/方形图标
- **状态**: default | hover | active | selected

## 交互规范

### 点击反馈
- **悬停 (Hover)**: 上浮2px + 阴影加深
- **按下 (Active)**: 下沉1px + 缩放0.98
- **加载 (Loading)**: 显示旋转动画 + 禁用点击
- **成功 (Success)**: 绿色勾选 + 文字变化
- **错误 (Error)**: 红色抖动 + 错误提示

### 表单验证
- **必填项**: 红色星号标记
- **实时验证**: 输入时即时检查
- **提交验证**: 点击时完整验证
- **错误提示**: 下方显示红色提示文字

### 加载状态
- **按钮内加载**: 左侧旋转图标 + 文字变"加载中..."
- **全屏加载**: 遮罩层 + 中央加载动画
- **进度加载**: 进度条 + 百分比显示

## 测试清单

### 功能测试
- [x] 点击事件触发
- [x] 表单提交
- [x] 页面跳转
- [x] 模态框打开
- [x] 数据加载

### 交互测试
- [x] 悬停效果
- [x] 点击动画
- [x] 加载状态
- [x] 禁用状态
- [x] 成功/失败反馈

### 表单验证测试
- [x] 空值验证
- [x] 格式验证 (邮箱、手机号)
- [x] 长度验证
- [x] 密码强度
- [x] 重复密码匹配

## 实现示例

```javascript
// 按钮点击处理
handleButtonClick(button) {
  // 1. 检查按钮状态
  if (button.disabled || button.loading) return;
  
  // 2. 设置加载状态
  button.setLoading(true);
  
  // 3. 执行操作
  try {
    await this.performAction();
    button.showSuccess();
  } catch (error) {
    button.showError(error.message);
  } finally {
    button.setLoading(false);
  }
}
```
