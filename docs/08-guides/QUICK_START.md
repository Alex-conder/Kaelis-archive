# Kaelis 快速启动指南

## 🚀 5 分钟启动本地服务

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务（自动选择 Neo4j/Mock）
python launch.py

# 3. 访问 http://localhost:5000/kg-flywheel
```

## 📊 一键生成运维报告

```powershell
.\scripts\generate-ops-report.ps1
```

## 🐳 Docker 部署

```bash
# 启动全部服务（含 Neo4j）
docker-compose up -d

# 查看状态
docker-compose ps
```

## ☁️ 云上部署

```bash
# 1. 构建镜像
docker build -t kaelis:latest .

# 2. 推送镜像
docker push your-registry/kaelis:latest

# 3. 部署到 K8s
kubectl apply -f k8s/deployment.yaml
```

详细上云指南: [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md)

## 🖥️ 桌面版打包

```bash
cd electron
npm install
npm run build:win
```

## ✅ 验证安装

```bash
# 运行测试
pytest tests/test_kg_flywheel.py -v

# 访问健康检查
curl http://localhost:5000/api/kg-flywheel/health
```

## 📚 文档索引

| 文档 | 内容 |
|------|------|
| [PROJECT_STATUS_OVERVIEW.md](PROJECT_STATUS_OVERVIEW.md) | 项目全栈状态总览 |
| [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md) | 上云部署详细指南 |
| [NEO4J_SETUP.md](NEO4J_SETUP.md) | Neo4j 切换指南 |
| [KG_FLYWHEEL_README.md](KG_FLYWHEEL_README.md) | 知识图谱飞轮模块文档 |
| [KG_FLYWHEEL_INTEGRATION.md](KG_FLYWHEEL_INTEGRATION.md) | 集成验证指南 |
| [KG_FLYWHEEL_ROADMAP.md](KG_FLYWHEEL_ROADMAP.md) | 路线图 |

## 🆘 常见问题

**Q: Neo4j 连接失败怎么办？**  
A: 系统会自动降级到 Mock 驱动，不影响使用。如需真实 Neo4j，运行 `docker-compose up -d neo4j`

**Q: 如何切换回真实 Neo4j？**  
A: 启动 Neo4j 容器后，服务会自动检测并连接

**Q: 如何打包 Windows 桌面版？**  
A: 见 [electron/README.md](electron/README.md)（待生成）

---

**当前版本**: v1.0.0  
**最后更新**: 2026-04-10
