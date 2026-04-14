# 任务：Kaelis 项目变体识别与确定性统一

## 背景
Kaelis 项目在发展过程中可能产生了多个副本或变体（如桌面散落文件夹、不同命名版本、旧备份等）。当前主项目位于 `C:\Users\11526\OneDrive\Desktop\Kaelis`（或当前工作区的 `Kaelis/`）。为防止资产分散、版本混淆，需进行全盘扫描、比对、合并与清理。

## 核心原则（源自确定性契约）
- **单一事实源**：所有 Kaelis 资产（代码、文档、配置、契约）必须归于 `Kaelis/` 目录，并符合契约化结构。
- **确定性转换**：变体识别基于文件指纹（SHA256）和目录结构签名，合并策略由差异类型决定。
- **先归档后清理**：不确定的变体先移至 `.kaelis/archived_variants/`，观察一周后再删除。

## 执行步骤

### 第一阶段：全盘扫描与变体识别

1. **扫描范围**：用户桌面（`~/Desktop`）及文档目录中所有包含以下特征之一的文件夹：
   - 文件夹名包含 `kaelis`、`Kaelis`、`KAELIS`（不区分大小写）
   - 文件夹内包含 `launch.py`、`contracts/openapi.yaml`、`Makefile` 中任意两个
   - 文件夹内包含 `.kaelis/` 隐藏目录

2. **生成变体清单**：
   ```powershell
   # 示例扫描命令（在桌面执行）
   Get-ChildItem -Path $env:USERPROFILE\Desktop -Directory -Recurse -Depth 2 |
       Where-Object { $_.Name -match 'kaelis' -or (Test-Path "$_.FullName\launch.py") } |
       Select-Object FullName, LastWriteTime, @{N='FileCount';E={(Get-ChildItem $_ -Recurse -File).Count}}
   ```

3. **对比主项目**：
   - 主项目基准路径：`Kaelis/`
   - 对于每个变体，计算其与主项目的结构相似度（基于 `contracts/`、`api/`、`web/` 等关键目录存在性）
   - 通过 `git log -1` 或 `version.txt` 判断变体可能对应的分支/阶段

### 第二阶段：差异分析与合并策略

| 变体类型 | 识别特征 | 处理策略 |
|:---|:---|:---|
| **完整副本（较新）** | 目录结构与主项目高度一致，且 `LastWriteTime` 晚于主项目 | **覆盖合并**：将变体中较新的文件覆盖到主项目，并记录于 `.kaelis/merge_log.yaml` |
| **完整副本（较旧）** | 结构一致但时间更早 | **归档后删除**：移动至 `.kaelis/archived_variants/old_副本_日期/` |
| **部分残留（如仅 `web/`）** | 仅包含个别子目录，且主项目中已存在对应目录 | **逐文件比对**：若主项目对应目录为空或更旧，则合并；否则归档 |
| **独立开发分支** | 包含 `git` 目录，或存在 `BRANCH.md` 说明 | **提取唯一资产**：检查是否有主项目未包含的文档、脚本、配置，提取后归档原目录 |
| **压缩包/备份** | `.zip`、`.tar.gz`、`.7z` 格式 | **解压检查**：若内容非最新，直接删除；若含唯一资产，提取后删除压缩包 |

### 第三阶段：确定性合并执行

1. **创建归档区**：
   ```powershell
   New-Item -ItemType Directory -Force -Path .\Kaelis\.kaelis\archived_variants
   ```

2. **逐变体处理**（以变体 `Kaelis_backup_20250401` 为例）：
   - 使用 `robocopy` 进行镜像比较：
     ```powershell
     robocopy ".\Kaelis_backup_20250401" ".\Kaelis" /MIR /L /LOG:diff.txt
     ```
   - 人工确认差异列表后，执行实际合并（去除 `/L` 参数）
   - 将合并来源信息追加到 `.kaelis/merge_log.yaml`：
     ```yaml
     - date: 2026-04-13
       source: "Kaelis_backup_20250401"
       merged_items:
         - path: "docs/代谢组学报告.md"
           reason: "主项目缺失此文档"
         - path: "scripts/deploy.sh"
           reason: "版本更新"
     ```

3. **清理原变体**：
   - 合并后，将原变体文件夹移动到 `archived_variants/`（保留 7 天）
   - 移动后验证主项目完整性（运行 `kaelis doctor` 或 `make check`）

### 第四阶段：最终验证与契约同步

1. **运行项目体检**：
   ```bash
   cd Kaelis
   make physician           # 完整体检（若存在）
   kaelis converge audit    # 契约审计
   ```

2. **更新文档索引**：
   - 若合并了新的文档，更新 `Kaelis/docs/README.md` 及各分类 `INDEX.md`

3. **提交变更**（若有 Git）：
   ```bash
   git add .
   git commit -m "chore: 合并变体资产，统一项目结构"
   ```

## 输出要求

执行完成后，请生成一份 **《Kaelis 变体统一报告》**，包含：

- **扫描到的变体清单**（路径、大小、最后修改时间）
- **采取的操作**（合并/归档/删除）
- **合并的资产列表**（新增或更新的文件）
- **当前项目完整性状态**（`make physician` 结果摘要）

## 注意事项

- **禁止直接删除不确定的变体**，一律先移至 `archived_variants/`
- **若变体位于云同步目录（如 OneDrive）**，操作前确保已同步完成
- **若变体包含敏感数据（密钥、数据库）**，确认后使用安全删除工具处理

## 历史执行记录

- **2026-04-13**: 首次执行，识别 5 个变体，归档 2 个，提取 7 项唯一资产

## 示例执行命令（供参考）

```powershell
# 在桌面执行扫描
Get-ChildItem -Directory | Where-Object { $_.Name -like "*kaelis*" -or (Test-Path "$_.FullName\contracts\openapi.yaml") } | ForEach-Object {
    Write-Host "发现变体: $($_.FullName)"
}
```

---

**此 Prompt 可由用户直接执行，或交由 AI 助手根据实际环境调整后运行。**
