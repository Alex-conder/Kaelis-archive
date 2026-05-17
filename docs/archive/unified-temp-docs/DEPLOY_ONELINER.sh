#!/bin/bash
mkdir -p /opt/kaelis && cd /opt/kaelis && apt-get update -qq && apt-get install -y -qq docker.io docker-compose git && systemctl enable docker && systemctl start docker && mkdir -p nginx ssl frontend && cat > docker-compose.yml << 'EOF'
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
      - ./frontend:/usr/share/nginx/html:ro
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    container_name: kaelis-postgres
    environment:
      POSTGRES_USER: kaelis
      POSTGRES_PASSWORD: kaelis123
      POSTGRES_DB: kaelis_prod
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: kaelis-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
EOF

cat > nginx/default.conf << 'EOF'
server {
    listen 80;
    server_name kaelis.me www.kaelis.me 8.137.38.71 _;
    
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    location /api/ {
        proxy_pass http://host.docker.internal:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

cat > frontend/index.html << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kaelis - 智流 AI 平台</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 {
            font-size: 4rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }
        .subtitle {
            font-size: 1.5rem;
            opacity: 0.9;
            margin-bottom: 2rem;
        }
        .status {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 1rem 2rem;
            background: rgba(255,255,255,0.1);
            border-radius: 50px;
            backdrop-filter: blur(10px);
        }
        .dot {
            width: 12px;
            height: 12px;
            background: #4ade80;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.1); }
        }
        .info {
            margin-top: 3rem;
            font-size: 0.9rem;
            opacity: 0.7;
        }
        .features {
            margin-top: 2rem;
            display: flex;
            gap: 2rem;
            justify-content: center;
            flex-wrap: wrap;
        }
        .feature {
            padding: 1rem;
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
            min-width: 150px;
        }
        .feature-icon {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Kaelis</h1>
        <p class="subtitle">智流 AI 平台</p>
        
        <div class="status">
            <span class="dot"></span>
            <span>服务运行正常</span>
        </div>
        
        <div class="features">
            <div class="feature">
                <div class="feature-icon">🤖</div>
                <div>AI 编排</div>
            </div>
            <div class="feature">
                <div class="feature-icon">📊</div>
                <div>工作流</div>
            </div>
            <div class="feature">
                <div class="feature-icon">🧬</div>
                <div>组学分析</div>
            </div>
        </div>
        
        <div class="info">
            <p>Server: 8.137.38.71</p>
            <p>Domain: kaelis.me</p>
            <p>Deployed: 2026-04-09</p>
        </div>
    </div>
</body>
</html>
EOF

docker-compose up -d && echo "" && echo "========================================" && echo "🎉 Kaelis 部署成功!" && echo "========================================" && echo "" && echo "🌐 访问地址:" && echo "  http://8.137.38.71" && echo "  http://kaelis.me (配置DNS后)" && echo "" && echo "📁 项目目录: /opt/kaelis" && echo "" && echo "🔧 常用命令:" && echo "  docker-compose ps       查看状态" && echo "  docker-compose logs -f  查看日志" && echo "  docker-compose restart  重启服务" && echo "  docker-compose down     停止服务" && echo ""
