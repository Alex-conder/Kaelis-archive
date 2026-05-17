"""
LLM 抽取器插件

基于 DeepSeek / OpenAI 兼容 API 的知识抽取。
与现有 kg_flywheel_tools._llm_extract 逻辑对齐，
但封装为符合 Plugin 接口的可插拔组件。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from core.plugins import BaseExtractor, PluginMetadata

logger = logging.getLogger(__name__)


class LLMExtractor(BaseExtractor):
    """LLM-based 知识抽取引擎"""

    def __init__(self):
        self._llm_client = None
        self._system_prompt = (
            "You are a knowledge extraction assistant.\n"
            "Extract subject-predicate-object triples from the given text.\n"
            "Return ONLY a JSON array. Each item must have:\n"
            "- subject: entity name\n"
            "- predicate: relation type\n"
            "- object: entity name\n"
            "- confidence: 0.0-1.0\n"
            "- subj_type: entity type (Person/Organization/Location/Concept/Technology/etc.)\n"
            "- obj_type: entity type\n"
        )

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="llm",
            version="1.0.0",
            description="基于大语言模型的知识抽取（DeepSeek/OpenAI兼容）",
            author="Kaelis Team"
        )

    @property
    def available(self) -> bool:
        try:
            from core.llm_client import get_llm_client
            client = get_llm_client()
            return client is not None
        except Exception:
            return False

    def supports_schema(self) -> bool:
        return False  # LLM 目前不支持严格的 schema 约束

    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        try:
            from core.llm_client import get_llm_client
            client = get_llm_client()
            if client is None:
                return []

            prompt = f"Extract triples from this text:\n\n{text}\n\nReturn JSON array only:"
            response = client.chat(
                prompt=prompt,
                system_prompt=self._system_prompt,
                temperature=0.3,
                json_mode=True
            )

            triples = json.loads(response)
            if not isinstance(triples, list):
                return []

            return self._normalize(triples)
        except Exception as e:
            logger.warning(f"LLM extract failed: {e}")
            return []

    @staticmethod
    def _normalize(raw_triples: List[Dict]) -> List[Dict[str, Any]]:
        """将 LLM 原始输出标准化为统一格式"""
        result = []
        for t in raw_triples:
            if not isinstance(t, dict):
                continue
            result.append({
                "head": str(t.get("subject", "")),
                "relation": str(t.get("predicate", "")),
                "tail": str(t.get("object", "")),
                "confidence": float(t.get("confidence", 0.8)),
                "head_type": str(t.get("subj_type", "Concept")),
                "tail_type": str(t.get("obj_type", "Concept")),
            })
        return result
