# Kaelis 全栈 Docker 镜像
# 多阶段构建：Node 构建前端 → Python 构建后端 → 生产镜像

# ============================================================
# Stage 1: 前端构建
# ============================================================
FROM node:20 AS frontend-builder

WORKDIR /app/web/frontend
COPY web/frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY web/frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: Python 依赖安装
# ============================================================
FROM python:3.11-slim AS python-builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================================
# Stage 3: 生产镜像
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# 复制前端构建产物
COPY --from=frontend-builder /app/web/frontend/dist /app/web/frontend/dist

# 复制 Python 依赖
COPY --from=python-builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码
COPY . .

# 环境变量默认值
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV ONEKE_MOCK_MODE=false

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

EXPOSE 5000

CMD ["python", "launch.py"]
