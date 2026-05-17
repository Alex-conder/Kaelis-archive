"""
Kaelis FastAPI 后端入口。

注册路由、中间件、CORS，并暴露自动生成的 OpenAPI (Swagger) 文档。
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import extraction, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Kaelis API",
    description="Kaelis 知识图谱构建与可视化后端服务",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 允许前端开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册业务路由
app.include_router(extraction.router)
app.include_router(storage.router)


@app.get("/health", summary="健康检查")
async def health_check():
    return {"status": "healthy", "service": "kaelis-backend"}
