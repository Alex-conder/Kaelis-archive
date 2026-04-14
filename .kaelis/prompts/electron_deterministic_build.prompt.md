# 任务：Kaelis Electron 确定性打包体系落地

## 背景
Phase 9 P2 Electron 打包过程中出现 `require is not defined` 错误，暴露了构建期契约验证的缺失。现需将 Electron 相关配置纳入 Kaelis 确定性契约体系，建立从配置、校验、构建到验证的全自动化闭环。

## 核心要求

### 1. 创建 Electron 契约文件 `contracts/electron.yaml`
- 定义 `app.name`, `app.appId`, `module_type` (commonjs/module)
- 定义 `main_process.entry`, `main_process.syntax`
- 定义 `build.targets`, `build.asar`, `build.extra_resources`
- 定义 `build_environment.docker_image`, `build_environment.electron_version`

### 2. 实现契约生成器 `scripts/generate_electron_config.py`
- 读取 `contracts/electron.yaml`
- 生成 `electron/package.json`（含正确的 `main` 和 `type` 字段）
- 生成 `electron-builder.json`
- 生成主进程骨架文件（`electron/main.js` 或 `electron/main.cjs`），根据 `module_type` 决定语法

### 3. 增强契约门禁 `scripts/kaelis_guardian.py`
- 新增 `--electron-check` 参数
- 实现 `check_electron_module_consistency()` 函数：
  - 对比契约中声明的 `module_type` 与实际文件语法
  - 不一致时输出修复建议并返回非零退出码

### 4. 更新 Makefile
- 修改 `electron-package` 目标：
  1. 运行 `python scripts/kaelis_guardian.py --electron-check`
  2. 若通过，运行 `python scripts/generate_electron_config.py`（确保配置最新）
  3. 执行 `cd electron && npm run build` 或直接调用 `electron-builder`
  4. 打包完成后运行烟雾测试脚本（若存在）

### 5. 创建烟雾测试脚本 `scripts/smoke_test_electron.py`
- 启动打包后的 `.exe` / `.app`
- 检测窗口出现
- 请求 `http://localhost:5000/api/health`
- 成功后关闭应用，输出成功信息

## 验收标准

1. 执行 `make electron-package` 后，生成的安装包能双击启动，无模块系统错误。
2. 手动将 `contracts/electron.yaml` 中的 `module_type` 改为 `module`，再次运行 `make electron-package`，门禁应阻断并提示语法冲突。
3. 生成的 `electron/package.json` 中的 `type` 字段与契约一致。
4. 烟雾测试脚本能在打包后自动验证应用启动。

## 交付物

- `contracts/electron.yaml`
- `scripts/generate_electron_config.py`
- `scripts/kaelis_guardian.py`（更新）
- `scripts/smoke_test_electron.py`
- `Makefile`（更新）
- `.kaelis/prompts/electron_deterministic_build.prompt.md`（本 Prompt 存档）

---

**此 Prompt 版本：v1.0 | 执行后 Kaelis Electron 打包将获得与后端、前端同等级的确定性契约保障。**
