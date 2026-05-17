"""
Pydantic 数据模型。
用于请求体验证、响应序列化和自动 OpenAPI 文档生成。
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Triple(BaseModel):
    """知识三元组"""
    head: str = Field(..., description="头实体")
    relation: str = Field(..., description="关系类型")
    tail: str = Field(..., description="尾实体")
    head_type: Optional[str] = Field(None, description="头实体类型")
    tail_type: Optional[str] = Field(None, description="尾实体类型")


class ExtractionRequest(BaseModel):
    """知识抽取请求"""
    text: str = Field(..., min_length=1, description="待抽取的原始文本")
    schema: Optional[Dict[str, Any]] = Field(
        None, description="OneKE 抽取 Schema，如 {'Person': ['work_for']}"
    )


class ExtractionResponse(BaseModel):
    """知识抽取响应"""
    triples: List[Triple] = Field(default_factory=list)
    raw_entities: Optional[List[Dict]] = Field(None, description="原始实体列表")


class GraphQueryRequest(BaseModel):
    """图查询请求"""
    query: str = Field(..., description="nGQL 查询语句")


class GraphQueryResponse(BaseModel):
    """图查询响应"""
    data: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
