# 团队记忆最小模型（预研）

## 目标

为实验室/团队场景设计命名空间隔离的共享记忆系统，支持成员 AI 共享集体经验。

## 命名空间设计

```
team://{team_id}/memory/{layer}/{key}
```

示例：
- `team://lab-001/memory/l2/experiment-2026-04`
- `team://lab-001/memory/l3/project-knowledge-graph`

## 权限位

采用 Unix 风格的权限模型：

| 位 | 权限 | 说明 |
|---|---|---|
| r | read | 读取记忆 |
| w | write | 写入/修改记忆 |
| x | execute | 触发进化/执行技能 |

角色映射：
- `owner` → `rwx`
- `admin` → `rwx`（不可转让所有权）
- `writer` → `rw-`
- `reader` → `r--`
- `guest` → `r--`（限时访问）

## 数据模型扩展

在现有 `shared_memory_space` 基础上增加：

```sql
ALTER TABLE shared_spaces ADD COLUMN team_id TEXT;
ALTER TABLE shared_spaces ADD COLUMN permissions INTEGER DEFAULT 755; -- Unix mode
ALTER TABLE shared_memories ADD COLUMN injectable BOOLEAN DEFAULT 1;   -- 是否允许注入到 Agent prompt
```

## 使用场景

| 场景 | 示例 |
|------|------|
| 实验室知识沉淀 | 每次实验参数和结果自动写入 `team://lab-001/memory/l2` |
| 课程辅助 | 学生 AI 共享课程资料，教师管理权限 |
| 代码审查 | 团队代码规范记忆，新成员 AI 自动继承 |

## Phase 19 对接

- 实现 `TeamMemoryManager` 类
- 前端 Team Console 页面
- 与 `context_aware_push` 集成，支持 `team_id` 过滤
