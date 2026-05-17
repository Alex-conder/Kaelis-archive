"""
知识抽取 API 路由。
提供文本 → 三元组的 HTTP 接口。
"""
import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import ExtractionRequest, ExtractionResponse
from app.services.oneke_extractor import OneKEExtractor
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/extraction", tags=["Knowledge Extraction"])

# 服务单例（生产环境建议使用依赖注入系统管理生命周期）
_extractor_service = OneKEExtractor(settings.ONEKE_MODEL_PATH)


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="文本知识抽取",
    description="接收原始文本，使用 OneKE 抽取实体与关系三元组。"
)
async def extract_knowledge(request: ExtractionRequest):
    try:
        triples = _extractor_service.extract(request.text, schema=request.schema)
        return ExtractionResponse(triples=triples, raw_entities=[])
    except Exception as e:
        logger.exception("Extraction API error")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
