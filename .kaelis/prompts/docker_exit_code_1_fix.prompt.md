# 任务：增强 Electron 应用 Docker 启动健壮性与用户体验

## 背景
当前应用启动时若 Docker 未运行或端口冲突，会静默失败或显示技术性错误，导致用户无法进入应用。

## 目标
实现以下增强：
1. 启动前检测 Docker 运行状态，若未运行则显示友好弹窗并指引启动。
2. 启动画面显示"正在拉取镜像"进度，避免用户误以为卡死。
3. 端口冲突时提示用户并给出解决建议。
4. 错误发生时支持一键导出诊断日志。

## 修改范围
- `electron/main.cjs`：增强 `startDockerServices()` 函数。
- `electron/preload.cjs`：暴露 IPC 通道用于前端接收启动状态。
- `web/frontend/src/components/StartupProgress.tsx`：展示详细步骤（已内联在 main.cjs 的 splash HTML 中，通过 IPC 更新）。

## 验收标准
- 未启动 Docker 时，弹窗提示并包含"打开 Docker Desktop"按钮。
- 首次启动显示镜像拉取状态（百分比或 spinner）。
- 端口冲突时提示"端口 5432 被占用"，并建议关闭占用程序或更换端口。
- 错误弹窗包含"导出诊断报告"按钮，点击后生成 zip 文件。

## 预估耗时
3 小时
