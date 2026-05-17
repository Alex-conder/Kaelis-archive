"""
OneKE 抽取器插件

基于 OneKE 模型的结构化知识抽取。
与现有 core.oneke_extractor 对齐，封装为 Plugin 接口。
"""

import logging
import os
from typing import Any, Dict, List, Optional

from core.plugins import BaseExtractor, PluginMetadata

logger = logging.getLogger(__name__)


class OneKEExtractorPlugin(BaseExtractor):
    """OneKE 结构化知识抽取引擎"""

    def __init__(self):
        self._inner = None

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="oneke",
            version="1.0.0",
            description="基于 OneKE 的高精度结构化知识抽取",
            author="Kaelis Team"
        )

    @property
    def available(self) -> bool:
        # 如果 inner extractor 已加载或 ONEKE_MOCK_MODE 启用，则认为可用
        if os.getenv("ONEKE_MOCK_MODE", "false").lower() == "true":
            return True
        try:
            from core.oneke_extractor import get_oneke_extractor
            ex = get_oneke_extractor()
            return ex is not None and ex._pipeline is not None
        except Exception:
            return False

    def supports_schema(self) -> bool:
        return True

    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        try:
            from core.oneke_extractor import get_oneke_extractor
            extractor = get_oneke_extractor()
            if extractor is None:
                return []

            raw = extractor.extract(text, schema=schema)
            return self._normalize(raw)
        except Exception as e:
            logger.warning(f"OneKE extract failed: {e}")
            return []

    @staticmethod
    def _normalize(raw_triples: List[Dict]) -> List[Dict[str, Any]]:
        """标准化为统一格式"""
        result = []
        for t in raw_triples:
            result.append({
                "head": str(t.get("head", "")),
                "relation": str(t.get("relation", "")),
                "tail": str(t.get("tail", "")),
                "confidence": float(t.get("confidence", 0.9)),
                "head_type": str(t.get("head_type", "Concept")),
                "tail_type": str(t.get("tail_type", "Concept")),
            })
        return result
