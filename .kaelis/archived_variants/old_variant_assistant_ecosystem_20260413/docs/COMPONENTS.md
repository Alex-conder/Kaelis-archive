# Kaelis 组件库文档

## 概述

Kaelis 组件库提供了一套统一、可复用的 UI 组件，基于 Handlebars 模板引擎构建。

## 组件列表

### 基础组件

#### Card (卡片)
```handlebars
{{> card 
  header=(object title="标题" action=(object href="#" label="查看更多"))
  content="卡片内容"
  footer="卡片底部"
  hover=true
}}
```

#### Metric (指标)
```handlebars
{{> metric 
  value="1,234"
  label="访问量"
  change="+12%"
  positive=true
}}
```

#### Table (表格)
```handlebars
{{> table
  columns=(array "名称" "状态" "操作")
  rows=(array 
    (array "Item 1" "Active" "Edit")
    (array "Item 2" "Inactive" "Delete")
  )
  pagination=true
  currentPage=1
  totalPages=10
}}
```

#### Form (表单)
```handlebars
{{> form
  id="login-form"
  fields=(array
    (object id="email" label="邮箱" type="email" required=true placeholder="your@email.com")
    (object id="password" label="密码" type="password" required=true)
  )
  submitLabel="登录"
  showCancel=true
}}
```

### 交互组件

#### Modal (弹窗)
```handlebars
{{> modal
  id="confirm-modal"
  title="确认操作"
  content="确定要删除吗？"
  showCancel=true
  showConfirm=true
  cancelLabel="取消"
  confirmLabel="确认"
}}
```

#### Alert (警告)
```handlebars
{{> alert
  type="warning"
  title="注意"
  message="这是一条警告信息"
  dismissible=true
}}
```

#### Tabs (标签页)
```handlebars
{{> tabs
  tabs=(array
    (object id="tab1" label="标签1" active=true content="内容1")
    (object id="tab2" label="标签2" content="内容2")
  )
}}
```

#### Breadcrumb (面包屑)
```handlebars
{{> breadcrumb
  items=(array
    (object label="首页" href="/")
    (object label="产品" href="/products")
    (object label="详情" active=true)
  )
}}
```

#### Pagination (分页)
```handlebars
{{> pagination
  pages=(array
    (object number=1 active=true)
    (object number=2)
    (object ellipsis=true)
    (object number=10)
  )
  hasPrev=false
  hasNext=true
}}
```

## 辅助函数

### 比较
- `{{eq a b}}` - 等于
- `{{ne a b}}` - 不等于
- `{{gt a b}}` - 大于
- `{{lt a b}}` - 小于

### 逻辑
- `{{and a b}}` - 与
- `{{or a b}}` - 或
- `{{not a}}` - 非

### 工具
- `{{json object}}` - 转换为 JSON
- `{{formatDate date}}` - 格式化日期
- `{{uppercase str}}` - 转大写
- `{{lowercase str}}` - 转小写
- `{{truncate str length}}` - 截断字符串

## 使用示例

### 完整页面示例
```handlebars
{{#> main title="页面标题" pageType="dashboard"}}
  <div class="page-container">
    <h1 class="section-title">数据统计</h1>
    
    <div class="grid-4">
      {{#each metrics}}
        {{> metric this}}
      {{/each}}
    </div>
    
    {{> card
      header=(object title="用户列表")
      content=(partial "table" tableData)
    }}
  </div>
{{/main}}
```

## 样式类

### 布局
- `.page-container` - 页面容器
- `.section-title` - 章节标题
- `.grid-2/3/4` - 网格布局
- `.flex-between/center/column` - Flex布局

### 组件
- `.card` - 卡片
- `.metric-card` - 指标卡片
- `.action-card` - 操作卡片
- `.status-list/item` - 状态列表

### 工具
- `.status-dot` - 状态指示点
- `.time-filter` - 时间筛选器
- `.chart-container` - 图表容器
- `.link` - 链接样式
