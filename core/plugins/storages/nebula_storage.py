"""
NebulaGraph 存储器插件

与现有 core.nebula_storage 对齐，封装为符合 BaseStorage 接口的可插拔组件。
"""

import logging
from typing import Any, Dict, List, Optional

from core.plugins import BaseStorage, PluginMetadata

logger = logging.getLogger(__name__)


class NebulaStoragePlugin(BaseStorage):
    """NebulaGraph 图存储后端"""

    def __init__(self):
        self._inner = None

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="nebula",
            version="1.0.0",
            description="NebulaGraph 分布式图存储（补充后端）",
            author="Kaelis Team"
        )

    @property
    def available(self) -> bool:
        try:
            from core.nebula_storage import get_nebula_storage
            storage = get_nebula_storage()
            return storage is not None and storage._pool is not None
        except Exception:
            return False

    def _get_storage(self):
        if self._inner is None:
            from core.nebula_storage import get_nebula_storage
            self._inner = get_nebula_storage()
        return self._inner

    def upsert_vertex(self, vid: str, tag: str, props: Dict[str, Any]) -> bool:
        storage = self._get_storage()
        if storage is None:
            return False
        try:
            return storage.upsert_vertex(tag, vid, props)
        except Exception as e:
            logger.warning(f"Nebula upsert_vertex failed: {e}")
            return False

    def upsert_edge(self, src: str, dst: str, edge_type: str, props: Optional[Dict[str, Any]] = None) -> bool:
        storage = self._get_storage()
        if storage is None:
            return False
        try:
            return storage.upsert_edge(edge_type, src, dst, props)
        except Exception as e:
            logger.warning(f"Nebula upsert_edge failed: {e}")
            return False

    def execute(self, query: str) -> List[Dict[str, Any]]:
        storage = self._get_storage()
        if storage is None:
            return []
        try:
            return storage.execute(query)
        except Exception as e:
            logger.warning(f"Nebula query failed: {e}")
            return []

    def upsert_triple(self, triple: Dict[str, Any]) -> bool:
        """便捷方法：写入一个三元组"""
        head = str(triple.get("head", triple.get("subject", "")))
        tail = str(triple.get("tail", triple.get("object", "")))
        relation = str(triple.get("relation", triple.get("predicate", "RELATES")))

        if not head or not tail:
            return False

        ok1 = self.upsert_vertex(head, "Entity", {"name": head})
        ok2 = self.upsert_vertex(tail, "Entity", {"name": tail})
        ok3 = self.upsert_edge(head, tail, relation)
        return ok1 and ok2 and ok3
