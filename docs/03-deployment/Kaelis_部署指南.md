# Kaelis 智流 - 部署指南

## 目录

- [环境要求](#环境要求)
- [本地部署](#本地部署)
- [生产部署](#生产部署)
- [Docker 部署](#docker-部署)
- [配置说明](#配置说明)
- [监控与维护](#监控与维护)
- [故障排除](#故障排除)

---

## 环境要求

### 最低配置

- **CPU**: 2 核心
- **内存**: 4 GB RAM
- **磁盘**: 10 GB 可用空间
- **Python**: 3.8+
- **操作系统**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+

### 推荐配置

- **CPU**: 4 核心+
- **内存**: 8 GB RAM+
- **磁盘**: 50 GB SSD
- **Python**: 3.10+
- **GPU**: 可选（用于本地模型加速）

---

## 本地部署

### 1. 安装依赖

```bash
# 克隆项目
git clone https://github.com/yourusername/kaelis.git
cd kaelis

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置
nano .env  # 或 vim .env
```

必需配置项：

```env
# LLM API 密钥（至少配置一个）
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...

# 应用配置
KAELIS_SECRET_KEY=your-secret-key-here
FLASK_ENV=production
FLASK_PORT=5000

# 数据库配置
MEMORY_DB_PATH=./data/chroma_db
SQLITE_PATH=./data/memory.db
```

### 3. 初始化数据目录

```bash
# 创建必要目录
mkdir -p data/task_states
mkdir -p data/memory
mkdir -p data/skills
mkdir -p data/logs
mkdir -p data/chroma_db

# 设置权限（Linux/macOS）
chmod -R 755 data/
```

### 4. 启动服务

```bash
# 使用启动脚本
python launch.py

# 或手动启动
python -m flask --app api/server.py run --host=0.0.0.0 --port=5000
```

### 5. 验证部署

```bash
# 运行测试
python test_system.py

# 检查API
curl http://localhost:5000/api/monitor/health

# 打开浏览器访问
# http://localhost:5000
```

---

## 生产部署

### 使用 Gunicorn

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动（4个工作进程）
gunicorn -w 4 -b 0.0.0.0:5000 api.server:app

# 后台运行
nohup gunicorn -w 4 -b 0.0.0.0:5000 api.server:app > logs/gunicorn.log 2>&1 &
```

### 使用 Systemd（Linux）

创建服务文件 `/etc/systemd/system/kaelis.service`：

```ini
[Unit]
Description=Kaelis AI Agent
After=network.target

[Service]
Type=simple
User=kaelis
WorkingDirectory=/opt/kaelis
Environment=PATH=/opt/kaelis/venv/bin
Environment=FLASK_ENV=production
Environment=KAELIS_SECRET_KEY=your-secret-key
ExecStart=/opt/kaelis/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 api.server:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
# 重载 systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable kaelis

# 启动服务
sudo systemctl start kaelis

# 查看状态
sudo systemctl status kaelis

# 查看日志
sudo journalctl -u kaelis -f
```

### 使用 Nginx 反向代理

安装 Nginx：

```bash
# Ubuntu/Debian
sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx
```

配置 `/etc/nginx/sites-available/kaelis`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static {
        alias /opt/kaelis/api/static;
        expires 30d;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/kaelis /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### HTTPS 配置（Let's Encrypt）

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

---

## Docker 部署

### 使用 Dockerfile

创建 `Dockerfile`：

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 创建数据目录
RUN mkdir -p data/task_states data/memory data/skills data/logs data/chroma_db

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "api.server:app"]
```

构建和运行：

```bash
# 构建镜像
docker build -t kaelis:latest .

# 运行容器
docker run -d \
  --name kaelis \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -e OPENAI_API_KEY=sk-... \
  -e KAELIS_SECRET_KEY=secret \
  kaelis:latest

# 查看日志
docker logs -f kaelis
```

### 使用 Docker Compose

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  kaelis:
    build: .
    container_name: kaelis
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - FLASK_ENV=production
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - KAELIS_SECRET_KEY=${KAELIS_SECRET_KEY}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/monitor/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: kaelis-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - kaelis
    restart: unless-stopped
```

启动：

```bash
# 创建环境变量文件
echo "OPENAI_API_KEY=sk-..." > .env
echo "KAELIS_SECRET_KEY=secret" >> .env

# 启动服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f kaelis

# 停止服务
docker-compose down
```

---

## 配置说明

### 环境变量完整列表

```env
# ==================== LLM 配置 ====================
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google
GOOGLE_API_KEY=...

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-01

# DeepSeek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 其他提供商...

# ==================== 应用配置 ====================
FLASK_ENV=production
FLASK_PORT=5000
KAELIS_SECRET_KEY=your-secret-key-here

# ==================== 数据库配置 ====================
MEMORY_DB_PATH=./data/chroma_db
SQLITE_PATH=./data/memory.db
CHROMA_PERSIST_DIRECTORY=./data/chroma_db

# ==================== 记忆系统配置 ====================
MAX_EPISODIC_MEMORIES=10000
MAX_SEMANTIC_MEMORIES=5000
MEMORY_CONSOLIDATION_INTERVAL=86400
FORGETTING_CURVE_DECAY=0.95

# ==================== 监控配置 ====================
ENABLE_MONITORING=true
METRICS_RETENTION_DAYS=30
LOG_LEVEL=INFO

# ==================== 安全配置 ====================
ENABLE_AUTH=false
JWT_SECRET_KEY=jwt-secret
JWT_ACCESS_TOKEN_EXPIRES=3600
RATE_LIMIT_PER_MINUTE=60
```

### 配置文件

创建 `config/production.yaml`：

```yaml
app:
  name: Kaelis
  version: 2.0.0
  debug: false

llm:
  default_provider: deepseek
  default_model: deepseek-chat
  timeout: 30
  max_retries: 3

memory:
  max_identity_tokens: 200
  max_active_tokens: 500
  episodic_top_k: 5
  semantic_top_k: 3

monitoring:
  enabled: true
  interval: 60
  retention_days: 30

security:
  enable_auth: false
  rate_limit: 60
```

---

## 监控与维护

### 系统监控

访问监控仪表盘：

```
http://your-domain.com/monitor.html
```

### 日志管理

```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log

# 日志轮转配置
sudo logrotate -f /etc/logrotate.d/kaelis
```

创建 `/etc/logrotate.d/kaelis`：

```
/opt/kaelis/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 kaelis kaelis
    postrotate
        /bin/kill -HUP `cat /var/run/syslogd.pid 2> /dev/null` 2> /dev/null || true
    endscript
}
```

### 备份策略

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/kaelis"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份数据库
tar -czf $BACKUP_DIR/memory_$DATE.tar.gz data/

# 保留最近30个备份
ls -t $BACKUP_DIR/memory_*.tar.gz | tail -n +31 | xargs rm -f

echo "Backup completed: $DATE"
```

添加到 crontab：

```bash
# 每天凌晨2点备份
0 2 * * * /opt/kaelis/backup.sh
```

### 性能优化

```python
# gunicorn 配置
gunicorn.conf.py

workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# 内存优化
preload_app = True
```

---

## 故障排除

### 常见问题

#### 1. 启动失败

```bash
# 检查依赖
pip list | grep -E "flask|chromadb"

# 检查端口占用
lsof -i :5000

# 检查权限
ls -la data/
```

#### 2. ChromaDB 连接失败

```bash
# 检查目录权限
chmod -R 755 data/chroma_db

# 重置 ChromaDB
rm -rf data/chroma_db/*

# 使用内存模式（临时）
export CHROMA_DB_IMPL=memory
```

#### 3. LLM 调用失败

```bash
# 检查 API 密钥
echo $OPENAI_API_KEY

# 测试连接
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 检查网络
ping api.openai.com
```

#### 4. 内存不足

```bash
# 查看内存使用
free -h

# 限制工作进程数
export WORKERS=2

# 清理旧记忆
python -c "from core.memory_manager_v2 import get_four_layer_memory; m = get_four_layer_memory('default'); m.consolidate_memories()"
```

### 诊断命令

```bash
# 系统状态
python -c "import psutil; print(f'CPU: {psutil.cpu_percent()}%, Memory: {psutil.virtual_memory().percent}%')"

# 数据库状态
python -c "from core.memory_manager_v2 import get_four_layer_memory; print(get_four_layer_memory('default').get_stats())"

# API 测试
curl -s http://localhost:5000/api/monitor/health | python -m json.tool
```

### 获取帮助

- 查看日志: `tail -f logs/error.log`
- 运行测试: `python test_system.py`
- 检查配置: `python -c "from core.config_manager import config_manager; print(config_manager.get_all())"`

---

## 升级指南

### 小版本升级

```bash
# 备份数据
cp -r data data.backup.$(date +%Y%m%d)

# 拉取更新
git pull origin main

# 更新依赖
pip install -r requirements.txt --upgrade

# 重启服务
sudo systemctl restart kaelis
```

### 大版本升级

```bash
# 1. 完整备份
tar -czf kaelis-backup-$(date +%Y%m%d).tar.gz /opt/kaelis

# 2. 查看升级说明
cat UPGRADE.md

# 3. 执行数据库迁移
python scripts/migrate.py

# 4. 逐步重启
sudo systemctl stop kaelis
# 更新代码...
sudo systemctl start kaelis
```

---

> 🚀 **部署完成！**  
> 访问 http://your-domain.com 开始使用 Kaelis 智流
