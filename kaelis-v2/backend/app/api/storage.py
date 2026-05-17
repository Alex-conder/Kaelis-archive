"""
图存储 API 路由。
提供 nGQL 查询和三元组批量写入接口。
"""
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from app.models.schemas import GraphQueryRequest, GraphQueryResponse
from app.services.nebula_storage import NebulaStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["Graph Storage"])

_storage_service = NebulaStorage()


@router.post(
    "/query",
    response_model=GraphQueryResponse,
    summary="执行 nGQL 查询"
)
async def query_graph(request: GraphQueryRequest):
    try:
        rows = _storage_service.execute(request.query)
        columns = list(rows[0].keys()) if rows else []
        return GraphQueryResponse(data=rows, columns=columns)
    except Exception as e:
        logger.exception("Graph query API error")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post(
    "/upsert-triples",
    summary="批量写入三元组",
    description="将抽取得到的三元组批量写入 NebulaGraph。"
)
async def upsert_triples(triples: List[Dict[str, Any]]):
    try:
        for t in triples:
            head = str(t.get("head", ""))
            tail = str(t.get("tail", ""))
            relation = str(t.get("relation", "RELATES"))

            # 写入顶点（使用 name 作为 vid）
            _storage_service.upsert_vertex("Entity", head, {"name": head})
            _storage_service.upsert_vertex("Entity", tail, {"name": tail})

            # 写入边
            _storage_service.upsert_edge(relation, head, tail)

        return {"status": "ok", "inserted": len(triples)}
    except Exception as e:
        logger.exception("Upsert triples API error")
        raise HTTPException(status_code=500, detail=f"Upsert failed: {str(e)}")
