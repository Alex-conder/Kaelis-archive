# Kaelis 阿里云服务器部署指南

**服务器**: 8.137.38.71 (Ubuntu)  
**域名**: kaelis.me  
**配置**: 2 vCPU / 4 GiB / 50 GiB ESSD

---

## 📋 部署前准备

### 1. 配置 DNS 解析
在域名服务商处添加 A 记录：
```
kaelis.me      -> 8.137.38.71
www.kaelis.me  -> 8.137.38.71
monitor.kaelis.me -> 8.137.38.71
```

### 2. 配置阿里云安全组
开放以下端口：
- 22 (SSH)
- 80 (HTTP)
- 443 (HTTPS)
- 9090 (Prometheus，可选)
- 3000 (Grafana，可选)

### 3. 准备 SSH 登录
```bash
ssh root@8.137.38.71
# 或使用密钥登录
ssh -i your-key.pem root@8.137.38.71
```

---

## 🚀 一键部署 (推荐)

### 方式 1: 自动初始化脚本

```bash
# 登录服务器
ssh root@8.137.38.71

# 下载并执行初始化脚本
curl -fsSL https://raw.githubusercontent.com/your-org/kaelis/main/scripts/setup-aliyun-server.sh | bash

# 或者手动执行
git clone https://github.com/your-org/Kaelis-Unified.git
cd Kaelis-Unified
chmod +x scripts/setup-aliyun-server.sh
./scripts/setup-aliyun-server.sh
```

### 方式 2: 手动部署

```bash
# 1. 登录服务器
ssh root@8.137.38.71

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 3. 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. 克隆项目
git clone https://github.com/your-org/Kaelis-Unified.git
cd Kaelis-Unified

# 5. 配置环境变量
cp .env.example .env
vim .env  # 编辑数据库密码、API密钥等

# 6. 获取 SSL 证书
docker run -it --rm \
  -v $(pwd)/ssl:/etc/letsencrypt \
  -v $(pwd)/certbot/www:/var/www/certbot \
  certbot/certbot certonly \
  --standalone \
  --agree-tos \
  -m admin@kaelis.me \
  -d kaelis.me -d www.kaelis.me

# 7. 启动服务
docker-compose -f docker-compose.aliyun.yml up -d

# 8. 查看状态
docker-compose -f docker-compose.aliyun.yml ps
```

---

## 📁 项目结构

```
~/kaelis/
├── Kaelis-Unified/           # 项目代码
│   ├── docker-compose.aliyun.yml
│   ├── nginx/
│   │   └── aliyun.conf
│   ├── ssl/                  # SSL 证书
│   │   └── live/kaelis.me/
│   ├── certbot/
│   │   └── www/              # Certbot 验证文件
│   └── .env                  # 环境变量
└── logs/                     # 日志文件
```

---

## 🔧 常用命令

### 服务管理
```bash
cd ~/kaelis/Kaelis-Unified

# 查看服务状态
docker-compose -f docker-compose.aliyun.yml ps

# 查看日志
docker-compose -f docker-compose.aliyun.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.aliyun.yml logs -f backend

# 重启服务
docker-compose -f docker-compose.aliyun.yml restart

# 停止服务
docker-compose -f docker-compose.aliyun.yml down

# 启动服务
docker-compose -f docker-compose.aliyun.yml up -d
```

### 更新部署
```bash
cd ~/kaelis/Kaelis-Unified

# 拉取最新代码
git pull

# 重新构建并启动
docker-compose -f docker-compose.aliyun.yml pull
docker-compose -f docker-compose.aliyun.yml up -d

# 清理旧镜像
docker image prune -f
```

### 备份数据
```bash
# 备份数据库
docker exec kaelis-postgres pg_dump -U kaelis kaelis_prod > backup_$(date +%Y%m%d).sql

# 备份 SSL 证书
tar czvf ssl_backup_$(date +%Y%m%d).tar.gz ssl/
```

---

## 🔒 SSL 证书管理

### 手动更新证书
```bash
docker run -it --rm \
  -v $(pwd)/ssl:/etc/letsencrypt \
  -v $(pwd)/certbot/www:/var/www/certbot \
  certbot/certbot renew

# 重启 Nginx
docker-compose -f docker-compose.aliyun.yml restart nginx
```

### 证书自动续期
项目已配置自动续期，certbot 容器每 12 小时检查一次。

---

## 📊 监控访问

| 服务 | 地址 | 默认账号 |
|------|------|----------|
| 主站 | https://kaelis.me | - |
| Grafana | https://monitor.kaelis.me | admin / (见 .env) |
| Prometheus | http://8.137.38.71:9090 | - |

---

## 🐛 故障排查

### 服务无法启动
```bash
# 查看详细日志
docker-compose -f docker-compose.aliyun.yml logs

# 检查端口占用
sudo netstat -tlnp | grep -E '80|443|5000'

# 检查磁盘空间
df -h

# 检查内存使用
free -h
```

### 数据库连接失败
```bash
# 检查数据库状态
docker-compose -f docker-compose.aliyun.yml ps postgres
docker-compose -f docker-compose.aliyun.yml logs postgres

# 进入数据库容器
docker exec -it kaelis-postgres psql -U kaelis -d kaelis_prod
```

### SSL 证书问题
```bash
# 检查证书有效期
openssl x509 -in ssl/live/kaelis.me/fullchain.pem -noout -dates

# 重新申请证书
docker run -it --rm \
  -v $(pwd)/ssl:/etc/letsencrypt \
  -v $(pwd)/certbot/www:/var/www/certbot \
  certbot/certbot certonly --force-renew \
  -d kaelis.me -d www.kaelis.me
```

---

## 💡 性能优化建议

### 系统优化
已配置：
- ✅ TCP 连接优化
- ✅ 文件描述符限制增加
- ✅ 内存参数调优
- ✅ Docker 资源限制

### 扩展建议
如需更高性能，建议：
1. 升级服务器到 4C8G
2. 使用阿里云 RDS 替代本地 PostgreSQL
3. 使用阿里云 Redis 企业版
4. 配置 CDN 加速静态资源

---

## 📞 支持

遇到问题？
- 查看日志：`docker-compose -f docker-compose.aliyun.yml logs`
- 检查状态：`docker-compose -f docker-compose.aliyun.yml ps`
- 提交 Issue：https://github.com/your-org/kaelis/issues
