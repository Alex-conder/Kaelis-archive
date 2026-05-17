# Kaelis v2 — 知识图谱构建与可视化

基于 **FastAPI + NebulaGraph + Vue 3 + AntV G6 + OneKE** 的新一代 Kaelis 架构。

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI (Python 3.10+) | 高性能异步 Web 框架，自动生成 OpenAPI 文档 |
| 图数据库 | NebulaGraph | 分布式高性能图数据库 |
| 知识抽取 | OneKE | 基于大模型的开源信息抽取框架 |
| 前端框架 | Vue 3 + Vite | 组合式 API，极速构建 |
| 可视化 | AntV G6 v5 | 专业图可视化引擎 |

## 快速开始

### 1. 启动 NebulaGraph

确保 NebulaGraph 服务已启动，并创建 Space：

```ngql
CREATE SPACE IF NOT EXISTS kaelis(vid_type=FIXED_STRING(256));
USE kaelis;
CREATE TAG IF NOT EXISTS Entity(name string);
```

### 2. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env 填入你的 NebulaGraph 密码等配置

uvicorn main:app --reload --port 8000
```

Swagger 文档将自动暴露在 http://localhost:8000/docs

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器运行在 http://localhost:5173

## 项目结构

```
kaelis-v2/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py          # 全局配置
│   │   ├── models/
│   │   │   └── schemas.py         # Pydantic 数据模型
│   │   ├── services/
│   │   │   ├── oneke_extractor.py # OneKE 抽取封装
│   │   │   └── nebula_storage.py  # NebulaGraph 存储封装
│   │   └── api/
│   │       ├── extraction.py      # 抽取 API 路由
│   │       └── storage.py         # 图存储 API 路由
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.js
        ├── App.vue
        ├── components/
        │   └── GraphVisualizer.vue  # G6 图谱可视化组件
        └── services/
            └── api.js               # Axios 后端接口封装
```

## 核心 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/extraction/extract` | POST | 文本知识抽取 |
| `/api/graph/query` | POST | 执行 nGQL 查询 |
| `/api/graph/upsert-triples` | POST | 批量写入三元组 |
| `/health` | GET | 健康检查 |
| `/docs` | GET | Swagger UI |

## 设计原则

- **完全解耦**：LLM/抽取逻辑与可视化层通过 REST API 通信，无直接依赖
- **降级容错**：OneKE 模型加载失败时，后端仍可启动，API 返回空列表而非崩溃
- **连接安全**：NebulaGraph 连接池通过上下文管理器确保释放，防止连接泄漏
- **CORS 就绪**：开发环境已配置前端跨域，生产环境按需调整 `allow_origins`
