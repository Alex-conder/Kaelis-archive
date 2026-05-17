# 🚀 Kaelis 阿里云快速启动

**只需 3 步，10 分钟完成部署！**

---

## 第一步: 准备服务器

```bash
# 登录阿里云服务器
ssh root@8.137.38.71
```

---

## 第二步: 执行一键部署

```bash
# 下载部署脚本
curl -fsSL https://kaelis.me/deploy.sh -o deploy.sh
chmod +x deploy.sh

# 执行部署
./deploy.sh
```

或者手动执行：

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 3. 克隆并启动
git clone https://github.com/your-org/Kaelis-Unified.git
cd Kaelis-Unified

# 4. 配置环境 (编辑 .env 文件)
cp .env.example .env
nano .env

# 5. 启动服务
docker-compose -f docker-compose.aliyun.yml up -d
```

---

## 第三步: 配置 DNS

在域名管理后台添加 A 记录：

| 主机记录 | 记录值 |
|---------|--------|
| @ | 8.137.38.71 |
| www | 8.137.38.71 |
| monitor | 8.137.38.71 |

等待 DNS 生效（通常 5-30 分钟）

---

## ✅ 验证部署

访问以下地址验证：

- 🌐 **主站**: https://kaelis.me
- 📊 **监控**: https://monitor.kaelis.me
- 🔍 **健康检查**: https://kaelis.me/api/status

---

## 📋 默认账号

| 服务 | 账号 | 密码位置 |
|------|------|----------|
| Grafana | admin | `.env` 文件中的 `GRAFANA_PASSWORD` |

---

## 🔧 常用命令

```bash
cd ~/Kaelis-Unified

# 查看状态
docker-compose -f docker-compose.aliyun.yml ps

# 查看日志
docker-compose -f docker-compose.aliyun.yml logs -f

# 重启服务
docker-compose -f docker-compose.aliyun.yml restart

# 更新代码
git pull && docker-compose -f docker-compose.aliyun.yml up -d
```

---

## ⚠️ 安全提示

部署完成后请立即：

1. **修改默认密码** - 检查 `.env` 文件中的密码
2. **配置防火墙** - 确保只开放必要端口
3. **保存密钥** - 备份 `.env` 文件到安全位置

---

**🎉 部署完成！欢迎使用 Kaelis！**
