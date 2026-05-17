#!/bin/bash
# Kaelis 快速部署命令 - 复制粘贴到 SSH 终端执行
# 服务器: 8.137.38.71
# 域名: kaelis.me

set -e
cd /root
mkdir -p kaelis-deploy && cd kaelis-deploy

echo "🚀 开始部署 Kaelis..."

# 1. 安装 Docker
if ! command -v docker &> /dev/null; then
    echo "📦 安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker && systemctl start docker
fi

# 2. 安装 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "📦 安装 Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
fi

# 3. 创建项目配置
echo "⚙️  创建项目配置..."
mkdir -p nginx ssl certbot/www

# 创建 docker-compose.yml
cat > docker-compose.yml <<'DOCKER_EOF'
version: '3.8'
services:
  nginx:
    image: nginx:alpine
    container_name: kaelis-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - backend
    restart: unless-stopped

  backend:
    image: python:3.11-slim
    container_name: kaelis-backend
    working_dir: /app
    expose:
      - "5000"
    environment:
      - ENV=production
      - DATABASE_URL=postgresql://kaelis:kaelis123@postgres:5432/kaelis_prod
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=change-me-in-production-secret-key
      - JWT_SECRET_KEY=change-me-in-production-jwt-key
    volumes:
      - backend_data:/app/data
    command: >
      sh -c "pip install flask flask-cors flask-limiter sqlalchemy psycopg2-binary redis gunicorn prometheus-client
      && gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 app:app"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

  frontend:
    image: nginx:alpine
    container_name: kaelis-frontend
    expose:
      - "80"
    volumes:
      - ./frontend:/usr/share/nginx/html:ro
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
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  redis:
    image: redis:7-alpine
    container_name: kaelis-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M

volumes:
  postgres_data:
  redis_data:
  backend_data:
DOCKER_EOF

# 创建 Nginx 配置
cat > nginx/default.conf <<'NGINX_EOF'
server {
    listen 80;
    server_name kaelis.me www.kaelis.me 8.137.38.71;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    location /api/ {
        proxy_pass http://backend:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    location /ws/ {
        proxy_pass http://backend:5000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX_EOF

# 创建临时前端页面
mkdir -p frontend
cat > frontend/index.html <<'HTML_EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Kaelis - 智流 AI 平台</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 0; 
               display: flex; justify-content: center; align-items: center; height: 100vh; 
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .container { text-align: center; }
        h1 { font-size: 3em; margin-bottom: 0.2em; }
        p { font-size: 1.2em; opacity: 0.9; }
        .status { margin-top: 2em; padding: 1em; background: rgba(255,255,255,0.1); 
                  border-radius: 8px; display: inline-block; }
        .dot { display: inline-block; width: 10px; height: 10px; background: #4ade80; 
               border-radius: 50%; margin-right: 8px; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Kaelis</h1>
        <p>智流 AI 平台</p>
        <div class="status">
            <span class="dot"></span>
            服务运行正常
        </div>
        <p style="margin-top: 2em; font-size: 0.9em; opacity: 0.7;">
            Server: 8.137.38.71 | Domain: kaelis.me
        </p>
    </div>
</body>
</html>
HTML_EOF

# 4. 配置防火墙
echo "🔥 配置防火墙..."
ufw default deny incoming 2>/dev/null || true
ufw default allow outgoing 2>/dev/null || true
ufw allow 22/tcp 2>/dev/null || true
ufw allow 80/tcp 2>/dev/null || true
ufw allow 443/tcp 2>/dev/null || true
ufw --force enable 2>/dev/null || true

# 5. 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 6. 等待并检查
sleep 5
echo ""
echo "🏥 服务状态检查:"
docker-compose ps

echo ""
echo "========================================"
echo "🎉 部署完成!"
echo "========================================"
echo ""
echo "📋 访问地址:"
echo "  HTTP: http://8.137.38.71"
echo "  目录: /root/kaelis-deploy"
echo ""
echo "🔧 常用命令:"
echo "  cd /root/kaelis-deploy"
echo "  docker-compose ps        # 查看状态"
echo "  docker-compose logs -f   # 查看日志"
echo "  docker-compose restart   # 重启服务"
echo ""
echo "⚠️  下一步:"
echo "  1. 配置 DNS: kaelis.me -> 8.137.38.71"
echo "  2. 修改默认密码 (docker-compose.yml)"
echo "  3. 申请 SSL 证书"
echo ""
