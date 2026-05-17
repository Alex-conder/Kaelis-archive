#!/bin/bash
# Kaelis 阿里云服务器部署脚本
# 在服务器上执行: bash <(curl -fsSL https://raw.githubusercontent.com/your-org/kaelis/main/deploy-server.sh)

set -e

DOMAIN="kaelis.me"
EMAIL="admin@kaelis.me"
INSTALL_DIR="/opt/kaelis"

echo "========================================"
echo "🚀 Kaelis 部署脚本"
echo "========================================"
echo ""

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then 
    echo "❌ 请使用 root 权限运行此脚本"
    exit 1
fi

# 系统信息
echo "📋 系统信息:"
echo "  主机名: $(hostname)"
echo "  IP地址: $(hostname -I | awk '{print $1}')"
echo "  系统: $(lsb_release -d | cut -f2)"
echo "  内存: $(free -h | awk '/^Mem:/ {print $2}')"
echo "  磁盘: $(df -h / | awk 'NR==2 {print $4}') 可用"
echo ""

# 1. 更新系统
echo "📦 [1/10] 更新系统..."
apt-get update -qq && apt-get upgrade -y -qq

# 2. 安装基础工具
echo "🔧 [2/10] 安装基础工具..."
apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    git \
    vim \
    htop \
    ufw \
    fail2ban \
    net-tools

# 3. 安装 Docker
echo "🐳 [3/10] 安装 Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker root
    systemctl enable docker
    systemctl start docker
    echo "✅ Docker 安装完成"
else
    echo "✅ Docker 已存在"
fi

# 4. 安装 Docker Compose
echo "📦 [4/10] 安装 Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    echo "✅ Docker Compose 安装完成"
else
    echo "✅ Docker Compose 已存在"
fi

# 5. 配置防火墙
echo "🔥 [5/10] 配置防火墙..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw allow 9090/tcp comment 'Prometheus'
ufw allow 3000/tcp comment 'Grafana'
ufw --force enable
echo "✅ 防火墙配置完成"

# 6. 创建项目目录
echo "📁 [6/10] 创建项目目录..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# 7. 下载项目文件
echo "📥 [7/10] 下载项目配置..."
if [ ! -d "$INSTALL_DIR/Kaelis-Unified" ]; then
    # 创建基本项目结构
    mkdir -p Kaelis-Unified/{nginx,ssl,certbot/www}
    cd Kaelis-Unified
    
    # 下载配置文件 (这里应该替换为实际的下载链接)
    echo "正在下载配置文件..."
    
    # 创建 docker-compose.yml
    cat > docker-compose.aliyun.yml <<'EOF'
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: kaelis-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/aliyun.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - backend
    networks:
      - kaelis-network
    restart: unless-stopped

  backend:
    image: kaelis/backend:latest
    container_name: kaelis-backend
    expose:
      - "5000"
    environment:
      - ENV=production
      - DATABASE_URL=postgresql://kaelis:kaelis123@postgres:5432/kaelis_prod
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-change-me-in-production}
      - RATE_LIMIT_ENABLED=true
    volumes:
      - backend_logs:/app/logs
      - backend_data:/app/data
    depends_on:
      - postgres
      - redis
    networks:
      - kaelis-network
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1.5G

  frontend:
    image: kaelis/frontend:latest
    container_name: kaelis-frontend
    expose:
      - "80"
    networks:
      - kaelis-network
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    container_name: kaelis-postgres
    environment:
      - POSTGRES_USER=kaelis
      - POSTGRES_PASSWORD=kaelis123
      - POSTGRES_DB=kaelis_prod
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - kaelis-network
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 1G

  redis:
    image: redis:7-alpine
    container_name: kaelis-redis
    volumes:
      - redis_data:/data
    networks:
      - kaelis-network
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M

volumes:
  postgres_data:
  redis_data:
  backend_logs:
  backend_data:

networks:
  kaelis-network:
    driver: bridge
EOF

    # 创建 Nginx 配置
    cat > nginx/aliyun.conf <<'EOF'
server {
    listen 80;
    server_name kaelis.me www.kaelis.me;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name kaelis.me www.kaelis.me;
    
    ssl_certificate /etc/nginx/ssl/live/kaelis.me/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/live/kaelis.me/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ {
        proxy_pass http://backend:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /ws/ {
        proxy_pass http://backend:5000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

    echo "✅ 项目配置创建完成"
else
    echo "✅ 项目目录已存在"
    cd Kaelis-Unified
fi

# 8. 生成随机密钥
echo "🔑 [8/10] 生成安全密钥..."
export SECRET_KEY=$(openssl rand -hex 32)
export JWT_SECRET_KEY=$(openssl rand -hex 32)
echo "SECRET_KEY=${SECRET_KEY}" > .env
echo "JWT_SECRET_KEY=${JWT_SECRET_KEY}" >> .env
echo "✅ 密钥已生成并保存到 .env"

# 9. 启动服务
echo "🚀 [9/10] 启动 Kaelis 服务..."
docker-compose -f docker-compose.aliyun.yml pull
docker-compose -f docker-compose.aliyun.yml up -d

# 等待服务启动
sleep 10

# 10. 健康检查
echo "🏥 [10/10] 健康检查..."
if docker ps | grep -q "kaelis-"; then
    echo "✅ 服务容器运行正常"
else
    echo "⚠️  部分容器可能未启动，请检查: docker-compose -f docker-compose.aliyun.yml ps"
fi

echo ""
echo "========================================"
echo "🎉 部署完成!"
echo "========================================"
echo ""
echo "📋 访问地址:"
echo "  HTTP:  http://$(hostname -I | awk '{print $1}')"
echo "  目录:  $INSTALL_DIR/Kaelis-Unified"
echo ""
echo "🔧 常用命令:"
echo "  cd $INSTALL_DIR/Kaelis-Unified"
echo "  docker-compose -f docker-compose.aliyun.yml ps"
echo "  docker-compose -f docker-compose.aliyun.yml logs -f"
echo ""
echo "⚠️  下一步:"
echo "  1. 配置 DNS: kaelis.me -> $(hostname -I | awk '{print $1}')"
echo "  2. 申请 SSL 证书 (首次部署后执行)"
echo "  3. 修改默认密码 (在 .env 文件中)"
echo ""
echo "📖 更多帮助: https://docs.kaelis.me"
echo ""
