"""
Neo4j 存储器插件

与现有 kg_flywheel_tools 中的 Neo4j 写入逻辑对齐，
封装为符合 BaseStorage 接口的可插拔组件。
"""

import logging
from typing import Any, Dict, List, Optional

from core.plugins import BaseStorage, PluginMetadata

logger = logging.getLogger(__name__)


class Neo4jStoragePlugin(BaseStorage):
    """Neo4j 图存储后端"""

    def __init__(self):
        self._driver = None

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="neo4j",
            version="1.0.0",
            description="Neo4j 图数据库主存储",
            author="Kaelis Team"
        )

    @property
    def available(self) -> bool:
        try:
            from api.routes.kg_flywheel_tools import get_neo4j_driver
            driver = get_neo4j_driver()
            return driver is not None
        except Exception:
            return False

    def _get_driver(self):
        if self._driver is None:
            from api.routes.kg_flywheel_tools import get_neo4j_driver
            self._driver = get_neo4j_driver()
        return self._driver

    def upsert_vertex(self, vid: str, tag: str, props: Dict[str, Any]) -> bool:
        driver = self._get_driver()
        if driver is None:
            return False
        try:
            with driver.session() as session:
                session.run(
                    "MERGE (e:Entity {name: $name, type: $type})",
                    name=vid,
                    type=props.get("type", tag)
                )
            return True
        except Exception as e:
            logger.warning(f"Neo4j upsert_vertex failed: {e}")
            return False

    def upsert_edge(self, src: str, dst: str, edge_type: str, props: Optional[Dict[str, Any]] = None) -> bool:
        driver = self._get_driver()
        if driver is None:
            return False
        try:
            with driver.session() as session:
                session.run(
                    """MATCH (s:Entity {name: $src}), (o:Entity {name: $dst})
                       MERGE (s)-[r:RELATES {type: $etype}]->(o)
                       SET r.confidence = $conf""",
                    src=src,
                    dst=dst,
                    etype=edge_type,
                    conf=props.get("confidence", 0.8) if props else 0.8
                )
            return True
        except Exception as e:
            logger.warning(f"Neo4j upsert_edge failed: {e}")
            return False

    def execute(self, query: str) -> List[Dict[str, Any]]:
        driver = self._get_driver()
        if driver is None:
            return []
        try:
            with driver.session() as session:
                result = session.run(query)
                return [record.data() for record in result]
        except Exception as e:
            logger.warning(f"Neo4j query failed: {e}")
            return []

    def upsert_triple(self, triple: Dict[str, Any]) -> bool:
        """便捷方法：写入一个三元组"""
        head = str(triple.get("head", triple.get("subject", "")))
        tail = str(triple.get("tail", triple.get("object", "")))
        relation = str(triple.get("relation", triple.get("predicate", "RELATES")))
        confidence = float(triple.get("confidence", 0.8))

        if not head or not tail:
            return False

        ok1 = self.upsert_vertex(head, "Entity", {"type": triple.get("head_type", "Concept")})
        ok2 = self.upsert_vertex(tail, "Entity", {"type": triple.get("tail_type", "Concept")})
        ok3 = self.upsert_edge(head, tail, relation, {"confidence": confidence})
        return ok1 and ok2 and ok3
