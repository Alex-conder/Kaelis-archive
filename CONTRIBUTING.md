# Contributing to Kaelis

感谢你对 Kaelis 的兴趣！以下是参与贡献的指南。

## 🚀 快速开始

1. **Fork 本仓库** 并克隆到本地
2. **创建虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. **安装开发依赖**
   ```bash
   pip install -e ".[all]"
   ```
4. **运行测试**
   ```bash
   pytest -m "not slow" --tb=short
   ```

## 🧪 测试规范

- 所有代码变更必须伴随测试
- 使用 `pytest` 运行测试套件
- 集成性能测试标记为 `@pytest.mark.slow`，默认不运行
- 测试必须使用临时目录，禁止写入生产数据路径（见 `tests/` 中的示例）

## 📝 代码风格

- Python：遵循 PEP 8
- TypeScript：使用项目自带的 `tsconfig.json`
- 提交信息使用中文或英文，清晰描述变更意图

## 🐛 提交 Issue

- 使用明确的标题描述问题
- 提供复现步骤和环境信息（Python/Node 版本、操作系统）
- 如可能，附上最小复现代码

## 🔀 提交 Pull Request

1. 从 `main` 分支创建功能分支：`git checkout -b feature/my-feature`
2. 确保测试通过：`pytest`
3. 更新相关文档（README、docstrings）
4. 提交 PR 并描述变更内容

## 🏷️ 发布流程

维护者推送 tag 时自动触发 PyPI 发布：

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 💬 社区

- GitHub Discussions: [讨论区](https://github.com/kaelis/kaelis/discussions)
- Issues: [问题反馈](https://github.com/kaelis/kaelis/issues)
