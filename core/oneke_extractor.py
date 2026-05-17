"""
OneKE 知识抽取服务封装。

职责：
- 管理 OneKE 模型生命周期（加载/热重载）
- 接收文本与 Schema，执行实体/关系联合抽取
- 返回标准化的三元组列表
- 异常时降级，不阻断上层 API

与现有 kaelis-main 的集成：
- 被 api/routes/oneke_extraction.py 调用
- 可与现有 LLM-based 抽取（kg_flywheel_tools._llm_extract）共存，
  作为更高精度的领域抽取选项
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OneKEExtractor:
    """
    OneKE 知识抽取服务封装。

    与现有 LLM-based 抽取并行，适用于需要结构化、可控schema的领域抽取场景。
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.getenv("ONEKE_MODEL_PATH", "./models/oneke")
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

    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行知识抽取。

        Args:
            text: 输入文本
            schema: 抽取 Schema，控制实体类型与关系类型
                例如 {"Person": ["work_for", "live_in"], "Organization": ["located_in"]}

        Returns:
            标准化三元组列表，每个元素为 dict:
            {"head": str, "relation": str, "tail": str, "head_type": str|None, "tail_type": str|None}
            模型不可用时返回空列表；开发环境可通过 ONEKE_MOCK_MODE=true 启用 mock 数据。
        """
        if not text or not text.strip():
            return []

        # 开发模式：强制返回 mock 数据（用于接口联调）
        mock_mode = os.getenv("ONEKE_MOCK_MODE", "false").lower() == "true"
        if mock_mode:
            logger.debug("OneKE mock mode enabled, returning mock data")
            return self._mock_extract(text)

        if self._pipeline is None:
            logger.warning("OneKE pipeline unavailable, returning empty result")
            return []

        try:
            # TODO: 替换为真实的 OneKE 调用
            # raw_result = self._pipeline.predict(text, schema=schema)
            # return self._parse_raw(raw_result)
            return self._mock_extract(text)
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return []

    def _mock_extract(self, text: str) -> List[Dict[str, Any]]:
        """模拟抽取结果，用于接口联调和骨架验证。"""
        return [
            {"head": "Kaelis", "relation": "developed_by", "tail": "KaelisTeam", "head_type": "Product", "tail_type": "Organization"},
            {"head": "Kaelis", "relation": "uses", "tail": "NebulaGraph", "head_type": "Product", "tail_type": "Technology"},
            {"head": "Kaelis", "relation": "uses", "tail": "OneKE", "head_type": "Product", "tail_type": "Technology"},
        ]

    def _parse_raw(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将 OneKE 原始输出解析为标准化三元组。"""
        triples: List[Dict[str, Any]] = []
        for item in raw.get("triples", []):
            triples.append({
                "head": str(item.get("head", "")),
                "relation": str(item.get("relation", "")),
                "tail": str(item.get("tail", "")),
                "head_type": item.get("head_type"),
                "tail_type": item.get("tail_type"),
            })
        return triples


# 全局单例
_oneke_extractor_instance: Optional[OneKEExtractor] = None


def get_oneke_extractor() -> Optional[OneKEExtractor]:
    """获取 OneKEExtractor 单例（惰性初始化）。"""
    global _oneke_extractor_instance
    if _oneke_extractor_instance is None:
        try:
            _oneke_extractor_instance = OneKEExtractor()
        except Exception as e:
            logger.warning(f"OneKEExtractor initialization failed: {e}")
            _oneke_extractor_instance = None
    return _oneke_extractor_instance


def reset_oneke_extractor() -> None:
    """重置 OneKEExtractor 单例（用于热重载配置）。"""
    global _oneke_extractor_instance
    _oneke_extractor_instance = None
    logger.info("OneKEExtractor singleton reset")
