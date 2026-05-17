"""
OneKE 知识抽取服务封装。

职责：
- 管理 OneKE 模型生命周期（加载/热重载）
- 接收文本与 Schema，执行实体/关系联合抽取
- 返回标准化的 Triple 列表
- 异常时降级，不阻断上层 API
"""
import logging
from typing import List, Optional, Dict, Any

from app.models.schemas import Triple
from app.core.config import settings

logger = logging.getLogger(__name__)


class OneKEExtractor:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.ONEKE_MODEL_PATH
        self._pipeline = None
        self._load_model()

    def _load_model(self) -> None:
        """延迟加载模型。失败时记录错误，服务仍可启动（降级模式）。"""
        try:
            # TODO: 替换为真实的 OneKE 导入
            # from oneke import OneKEPipeline
            # self._pipeline = OneKEPipeline(self.model_path)
            logger.info(f"OneKE model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load OneKE model: {e}")
            self._pipeline = None

    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> List[Triple]:
        """
        执行知识抽取。

        Args:
            text: 输入文本
            schema: 抽取 Schema，控制实体类型与关系类型

        Returns:
            标准化三元组列表。模型不可用时返回空列表。
        """
        if not text or not text.strip():
            return []

        if self._pipeline is None:
            logger.warning("OneKE pipeline unavailable, returning empty result")
            return []

        try:
            # TODO: 替换为真实的 OneKE 调用
            # raw_result = self._pipeline.predict(text, schema=schema)
            # return self._parse_raw(raw_result)

            # 以下为框架演示用的模拟数据
            return self._mock_extract(text)
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return []

    def _mock_extract(self, text: str) -> List[Triple]:
        """模拟抽取结果，用于接口联调和骨架验证。"""
        return [
            Triple(head="Kaelis", relation="developed_by", tail="KaelisTeam"),
            Triple(head="Kaelis", relation="uses", tail="NebulaGraph"),
            Triple(head="Kaelis", relation="uses", tail="OneKE"),
        ]

    def _parse_raw(self, raw: Dict[str, Any]) -> List[Triple]:
        """将 OneKE 原始输出解析为标准化 Triple。"""
        triples: List[Triple] = []
        for item in raw.get("triples", []):
            triples.append(Triple(
                head=str(item.get("head", "")),
                relation=str(item.get("relation", "")),
                tail=str(item.get("tail", "")),
                head_type=item.get("head_type"),
                tail_type=item.get("tail_type"),
            ))
        return triples
