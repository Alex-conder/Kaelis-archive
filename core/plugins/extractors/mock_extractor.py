"""
Mock 抽取器插件

用于开发和测试环境，不依赖任何外部模型或服务。
通过正则模式匹配进行简单抽取，无法识别时返回示例数据。
"""

import re
from typing import Any, Dict, List, Optional

from core.plugins import BaseExtractor, PluginMetadata


class MockExtractor(BaseExtractor):
    """Mock 知识抽取引擎（开发/测试用）"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock",
            version="1.0.0",
            description="Mock 抽取器，用于开发和测试环境",
            author="Kaelis Team"
        )

    @property
    def available(self) -> bool:
        return True  # 始终可用

    def supports_schema(self) -> bool:
        return False

    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        triples = []
        patterns = [
            (r"(\w+)由(\w+)创立", "创立者"),
            (r"(\w+)是(\w+)的创始人", "创立者"),
            (r"(\w+)成立于(\d{4})年?", "成立时间"),
            (r"(\w+)总部位于(\w+)", "总部位置"),
            (r"(\w+)是(\w+)的?子公司", "母公司"),
        ]

        for pattern, relation in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    subj, obj = match
                else:
                    continue
                triples.append({
                    "head": subj,
                    "relation": relation,
                    "tail": obj,
                    "confidence": 0.85,
                    "head_type": "Organization",
                    "tail_type": "Person" if "人" in relation or "者" in relation else "Location",
                })

        if not triples and len(text) > 10:
            triples.append({
                "head": text[:10] + "...",
                "relation": "相关于",
                "tail": "知识图谱",
                "confidence": 0.7,
                "head_type": "Concept",
                "tail_type": "Concept",
            })

        return triples
