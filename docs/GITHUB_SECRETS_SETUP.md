# GitHub Secrets 配置指南

> 发布流水线 `.github/workflows/publish.yml` 依赖以下 Secrets。
> 配置完成后，推送 `v*.*.*` 标签即可自动触发全平台发布。

---

## 必需 Secrets

### 1. `PYPI_API_TOKEN`
**用途**：上传 Python Wheel 到 PyPI

**获取方式**：
1. 访问 https://pypi.org/manage/account/
2. 生成 API Token（Scope: 选择你的项目或 Entire account）
3. 复制 token（格式：`pypi-AgEIc...`）

**配置路径**：
GitHub Repo → Settings → Secrets and variables → Actions → New repository secret

---

### 2. `VSCE_PAT`
**用途**：发布 VSCode 扩展到 Marketplace

**获取方式**：
1. 访问 https://dev.azure.com/ 并登录
2. 进入 Personal Access Tokens
3. 创建 Token，Scope 选择 `Marketplace: Manage`
4. 复制 token

**配置路径**：同上

---

## 可选 Secrets

### `CODECOV_TOKEN`
**用途**：上传覆盖率报告到 Codecov

**获取方式**：https://codecov.io/ → 关联仓库 → Settings → Copy Token

---

## 验证配置

配置完成后，在本地测试发布流水线：

```bash
# 1. 确认标签格式正确
git tag v0.2.0

# 2. 推送标签触发发布
git push origin v0.2.0

# 3. 在 GitHub Actions 页面观察进度
# https://github.com/Alex-conder/Kaelis-archive/actions
```

---

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| PyPI 上传 403 | Token 权限不足或过期 | 重新生成 Token，确保 Scope 正确 |
| VSCE 发布 401 | PAT 过期或 Scope 错误 | 在 Azure DevOps 重新创建 PAT |
| Electron 打包失败 | 资源路径错误 | 检查 `electron-builder.json` 的 `extraResources` |
| Release 无资产 | Artifact 上传失败 | 检查 `actions/upload-artifact` 步骤日志 |
