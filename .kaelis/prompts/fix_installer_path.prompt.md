# 任务：Kaelis Windows 安装包支持自定义安装目录

## 背景
当前 `Kaelis AI Workbench Setup.exe` 采用一键安装模式，跳过目录选择页，直接安装至 `C:\Users\<用户名>\AppData\Local\Programs`。导致 C 盘空间紧张的用户无法安装，体验受损。

## 目标
修改 Electron 打包配置，使安装向导显示 **"选择安装位置"** 页面，用户可自由指定盘符和目录。

## 核心原则（源自确定性契约）
- **单一事实源**：安装行为配置必须源于 `contracts/electron.yaml`。
- **确定性转换**：通过 `generate_electron_config.py` 自动同步契约到 `electron-builder.json`。
- **最小改动**：仅修改契约和生成器，不触碰主进程代码。

## 执行步骤

### 步骤 1：更新契约文件
编辑 `contracts/electron.yaml`，在 `build` 节点下增加 `installer` 配置：

```yaml
build:
  # ... 已有配置保持不变
  installer:
    windows:
      one_click: false                # 显示安装步骤向导
      allow_directory_change: true    # 允许用户修改安装目录
      per_machine: false              # 按用户安装（无需管理员），如需所有用户改为 true
      create_desktop_shortcut: true   # 创建桌面快捷方式
      create_start_menu_shortcut: true
```

### 步骤 2：更新配置生成器
编辑 `scripts/generate_electron_config.py`，在生成 `electron-builder.json` 的逻辑中读取上述契约并写入 `nsis` 段：

```python
# 读取 installer 配置
installer = contract.get('build', {}).get('installer', {}).get('windows', {})
nsis_config = {
    "oneClick": installer.get('one_click', False),
    "allowToChangeInstallationDirectory": installer.get('allow_directory_change', True),
    "perMachine": installer.get('per_machine', False),
    "createDesktopShortcut": installer.get('create_desktop_shortcut', True),
    "createStartMenuShortcut": installer.get('create_start_menu_shortcut', True)
}
# 将 nsis_config 写入 electron-builder.json 的 build.nsis 字段
```

### 步骤 3：重新生成配置并打包
执行以下命令：

```bash
cd C:\Users\11526\OneDrive\Desktop\Kaelis
python scripts/generate_electron_config.py   # 重新生成 electron-builder.json
cd web/frontend
npm run build                                # 重新构建前端（若有改动）
npx electron-builder --config ../../electron-builder.json --win
```

### 步骤 4：验证安装包
在带 GUI 的 Windows 环境中：
1. 双击生成的 `release\Kaelis AI Workbench Setup 1.0.0.exe`。
2. 确认出现 **"选择安装位置"** 页面，并成功修改为 `D:\Kaelis`。
3. 安装完成后，桌面快捷方式指向正确路径，应用可正常启动。

## 验收标准
- [ ] 安装向导包含目录选择步骤。
- [ ] 用户可输入或浏览任意盘符路径。
- [ ] 安装后应用功能正常（Docker 启动、后端调用、前端展示）。
- [ ] 契约门禁 `python scripts/kaelis_guardian.py --electron-check` 通过。

## 预估耗时
- 修改契约与生成器：5 分钟
- 重新打包：10 分钟
- 验证：5 分钟
- **总计**：20 分钟

## 扩展性说明
此改动为未来交付体验契约化（`contracts/delivery.yaml`）奠定基础。后续可将 `installer` 配置迁移至独立契约，并扩展支持 macOS dmg 背景、Linux 包格式等。
