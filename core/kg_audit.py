"""
KGAuditEngine - 知识图谱审计与溯源引擎

对标 Anthropic 的来源追踪（Source Trace）与 MCP 协议的审计设计。
为知识图谱中的每个三元组提供完整的溯源信息：
- 来源文本（Provenance）
- 抽取引擎（Extractor）
- 置信度（Confidence）
- 验证状态（Verified / Unverified / Disputed）
- 时间线（Timeline）

同时支持 KG 健康度审计：孤立实体、冗余关系、置信度分布。
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    """三元组验证状态"""
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    DEPRECATED = "deprecated"


@dataclass
class TripleProvenance:
    """单个三元组的溯源信息"""
    triple_id: Optional[int] = None
    subject: str = ""
    predicate: str = ""
    object: str = ""
    subject_type: Optional[str] = None
    object_type: Optional[str] = None
    confidence: float = 1.0
    extractor: str = "unknown"  # llm / oneke / hybrid / manual
    source_text: Optional[str] = None
    source_document: Optional[str] = None
    verification_status: str = VerificationStatus.UNVERIFIED.value
    verified_by: Optional[str] = None  # user_id / system / human_reviewer
    verified_at: Optional[str] = None
    created_at: Optional[str] = None
    user_id: str = "anonymous"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triple_id": self.triple_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "subject_type": self.subject_type,
            "object_type": self.object_type,
            "confidence": round(self.confidence, 3),
            "extractor": self.extractor,
            "source_text": self.source_text,
            "source_document": self.source_document,
            "verification_status": self.verification_status,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "created_at": self.created_at,
            "user_id": self.user_id,
            "metadata": self.metadata,
        }


@dataclass
class KGAuditReport:
    """KG 审计报告"""
    audit_timestamp: str
    total_triples: int = 0
    total_entities: int = 0
    verification_distribution: Dict[str, int] = field(default_factory=dict)
    confidence_stats: Dict[str, float] = field(default_factory=dict)
    extractor_distribution: Dict[str, int] = field(default_factory=dict)
    orphaned_entities: List[str] = field(default_factory=list)
    redundant_relations: List[Dict[str, Any]] = field(default_factory=list)
    low_confidence_triples: List[Dict[str, Any]] = field(default_factory=list)
    recent_changes: List[Dict[str, Any]] = field(default_factory=list)
    health_score: float = 1.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_timestamp": self.audit_timestamp,
            "total_triples": self.total_triples,
            "total_entities": self.total_entities,
            "verification_distribution": self.verification_distribution,
            "confidence_stats": self.confidence_stats,
            "extractor_distribution": self.extractor_distribution,
            "orphaned_entities_count": len(self.orphaned_entities),
            "orphaned_entities": self.orphaned_entities[:20],
            "redundant_relations_count": len(self.redundant_relations),
            "redundant_relations": self.redundant_relations[:10],
            "low_confidence_triples_count": len(self.low_confidence_triples),
            "low_confidence_triples": self.low_confidence_triples[:10],
            "recent_changes": self.recent_changes[:10],
            "health_score": round(self.health_score, 3),
            "recommendations": self.recommendations,
        }


class KGAuditEngine:
    """
    知识图谱审计与溯源引擎。

    使用示例：
        audit = KGAuditEngine()
        
        # 查询单个三元组的溯源
        prov = audit.get_triple_provenance(subject="Kaelis", predicate="uses", object="NebulaGraph")
        
        # 运行完整审计
        report = audit.run_audit()
    """

    def __init__(self, db_path: Optional[str] = None):
        import os
        data_dir = os.environ.get("KAELIS_DATA_DIR", "data")
        self.db_path = db_path or str(Path(data_dir) / "kaelis_graph.db")
        self._ensure_schema()

    def _ensure_schema(self):
        """确保 kg_triples 表包含审计字段"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            # 先确保基础表存在（兼容独立使用场景）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_triples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    subject_type TEXT,
                    object_type TEXT,
                    confidence REAL DEFAULT 1.0,
                    source TEXT,
                    user_id TEXT DEFAULT 'anonymous',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    source_text TEXT,
                    user_id TEXT DEFAULT 'anonymous',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT,
                    source TEXT,
                    user_id TEXT DEFAULT 'anonymous',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, user_id)
                )
            """)
            # 尝试添加审计字段（幂等）
            audit_columns = [
                ("extractor", "TEXT DEFAULT 'unknown'"),
                ("confidence", "REAL DEFAULT 1.0"),
                ("verification_status", "TEXT DEFAULT 'unverified'"),
                ("verified_by", "TEXT"),
                ("verified_at", "TIMESTAMP"),
                ("source_document", "TEXT"),
                ("metadata_json", "TEXT"),
            ]
            for col_name, col_type in audit_columns:
                try:
                    conn.execute(f"ALTER TABLE kg_triples ADD COLUMN {col_name} {col_type}")
                    logger.info(f"[KGAudit] Added column {col_name} to kg_triples")
                except sqlite3.OperationalError:
                    pass  # 列已存在

            # 同样为 kg_relations 添加字段
            relation_columns = [
                ("extractor", "TEXT DEFAULT 'unknown'"),
                ("confidence", "REAL DEFAULT 1.0"),
                ("verification_status", "TEXT DEFAULT 'unverified'"),
                ("source_document", "TEXT"),
                ("metadata_json", "TEXT"),
            ]
            for col_name, col_type in relation_columns:
                try:
                    conn.execute(f"ALTER TABLE kg_relations ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass

            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_kg_extracted ON kg_triples(extractor)",
                "CREATE INDEX IF NOT EXISTS idx_kg_verification ON kg_triples(verification_status)",
                "CREATE INDEX IF NOT EXISTS idx_kg_confidence ON kg_triples(confidence)",
            ]:
                try:
                    conn.execute(idx_sql)
                except sqlite3.OperationalError:
                    pass  # 表可能不存在

    def record_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        extractor: str = "unknown",
        confidence: float = 1.0,
        source_text: Optional[str] = None,
        source_document: Optional[str] = None,
        user_id: str = "anonymous",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        记录三元组并附加审计信息。
        优先写入 kg_triples 表（含审计字段），其次 kg_relations 表。
        """
        now = datetime.now().isoformat()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)

        try:
            with sqlite3.connect(self.db_path) as conn:
                # 尝试插入到 kg_triples（如果表结构支持）
                try:
                    conn.execute(
                        """
                        INSERT INTO kg_triples
                        (subject, predicate, object, source, user_id, created_at,
                         extractor, confidence, source_document, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (subject, predicate, object, source_text, user_id, now,
                         extractor, confidence, source_document, metadata_json),
                    )
                except sqlite3.OperationalError as e:
                    # 如果 kg_triples 没有新字段，回退到基本插入
                    logger.debug(f"kg_triples extended insert failed, fallback: {e}")
                    conn.execute(
                        """
                        INSERT INTO kg_triples
                        (subject, predicate, object, source, user_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (subject, predicate, object, source_text, user_id, now),
                    )

                # 同步到 kg_relations（兼容性）
                try:
                    conn.execute(
                        """
                        INSERT INTO kg_relations
                        (source, target, relation, source_text, user_id, created_at,
                         extractor, confidence, source_document, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (subject, object, predicate, source_text, user_id, now,
                         extractor, confidence, source_document, metadata_json),
                    )
                except sqlite3.OperationalError:
                    conn.execute(
                        """
                        INSERT INTO kg_relations
                        (source, target, relation, source_text, user_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (subject, object, predicate, source_text, user_id, now),
                    )
            return True
        except Exception as e:
            logger.error(f"[KGAudit] record_triple failed: {e}")
            return False

    def get_triple_provenance(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        triple_id: Optional[int] = None,
    ) -> Optional[TripleProvenance]:
        """查询单个三元组的完整溯源信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if triple_id:
                    row = conn.execute(
                        "SELECT * FROM kg_triples WHERE id = ?",
                        (triple_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT * FROM kg_triples
                        WHERE subject = ? AND predicate = ? AND object = ?
                        ORDER BY created_at DESC LIMIT 1
                        """,
                        (subject, predicate, object),
                    ).fetchone()

                if not row:
                    return None

                def _get(row, col, default=None):
                    try:
                        return row[col]
                    except (KeyError, IndexError):
                        return default
                
                return TripleProvenance(
                    triple_id=_get(row, "id"),
                    subject=_get(row, "subject"),
                    predicate=_get(row, "predicate"),
                    object=_get(row, "object"),
                    subject_type=_get(row, "subject_type"),
                    object_type=_get(row, "object_type"),
                    confidence=_get(row, "confidence", 1.0) or 1.0,
                    extractor=_get(row, "extractor", "unknown") or "unknown",
                    source_text=_get(row, "source"),
                    source_document=_get(row, "source_document"),
                    verification_status=_get(row, "verification_status", "unverified") or "unverified",
                    verified_by=_get(row, "verified_by"),
                    verified_at=_get(row, "verified_at"),
                    created_at=_get(row, "created_at"),
                    user_id=_get(row, "user_id", "anonymous"),
                    metadata=json.loads(_get(row, "metadata_json", "{}")) if _get(row, "metadata_json") else {},
                )
        except Exception as e:
            logger.error(f"[KGAudit] get_triple_provenance failed: {e}")
            return None

    def verify_triple(
        self,
        triple_id: int,
        status: str,
        verified_by: str = "system",
        reason: Optional[str] = None,
    ) -> bool:
        """标记三元组的验证状态"""
        now = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE kg_triples
                    SET verification_status = ?, verified_by = ?, verified_at = ?,
                        metadata_json = json_patch(metadata_json, ?)
                    WHERE id = ?
                    """,
                    (status, verified_by, now,
                     json.dumps({"verification_reason": reason}, ensure_ascii=False),
                     triple_id),
                )
            return True
        except Exception as e:
            # 如果 json_patch 不支持，回退到简单更新
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        UPDATE kg_triples
                        SET verification_status = ?, verified_by = ?, verified_at = ?
                        WHERE id = ?
                        """,
                        (status, verified_by, now, triple_id),
                    )
                return True
            except Exception as e2:
                logger.error(f"[KGAudit] verify_triple failed: {e2}")
                return False

    def run_audit(self, user_id: Optional[str] = None) -> KGAuditReport:
        """运行完整的 KG 审计"""
        report = KGAuditReport(audit_timestamp=datetime.now().isoformat())

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # 基础统计
                where = "WHERE user_id = ?" if user_id else ""
                params = (user_id,) if user_id else ()

                row = conn.execute(
                    f"SELECT COUNT(*) as cnt FROM kg_triples {where}", params
                ).fetchone()
                report.total_triples = row["cnt"] if row else 0

                row = conn.execute(
                    f"SELECT COUNT(DISTINCT name) as cnt FROM kg_entities {where.replace('kg_triples', 'kg_entities')}",
                    params,
                ).fetchone()
                report.total_entities = row["cnt"] if row else 0

                # 验证状态分布
                rows = conn.execute(
                    f"SELECT verification_status, COUNT(*) as cnt FROM kg_triples {where} GROUP BY verification_status",
                    params,
                ).fetchall()
                report.verification_distribution = {
                    r["verification_status"] or "unverified": r["cnt"] for r in rows
                }

                # 置信度统计
                row = conn.execute(
                    f"SELECT AVG(confidence) as avg, MIN(confidence) as min, MAX(confidence) as max FROM kg_triples {where}",
                    params,
                ).fetchone()
                if row:
                    report.confidence_stats = {
                        "avg": round(row["avg"] or 1.0, 3),
                        "min": round(row["min"] or 1.0, 3),
                        "max": round(row["max"] or 1.0, 3),
                    }

                # 抽取引擎分布
                rows = conn.execute(
                    f"SELECT extractor, COUNT(*) as cnt FROM kg_triples {where} GROUP BY extractor",
                    params,
                ).fetchall()
                report.extractor_distribution = {
                    r["extractor"] or "unknown": r["cnt"] for r in rows
                }

                # 低置信度三元组
                low_conf = conn.execute(
                    f"""
                    SELECT id, subject, predicate, object, confidence, extractor, created_at
                    FROM kg_triples {where}
                    ORDER BY confidence ASC
                    LIMIT 20
                    """,
                    params,
                ).fetchall()
                report.low_confidence_triples = [
                    {
                        "triple_id": r["id"],
                        "subject": r["subject"],
                        "predicate": r["predicate"],
                        "object": r["object"],
                        "confidence": r["confidence"],
                        "extractor": r["extractor"],
                        "created_at": r["created_at"],
                    }
                    for r in low_conf
                    if (r["confidence"] or 1.0) < 0.7
                ]

                # 孤立实体（有实体但没有关系）
                all_entities = set()
                for r in conn.execute("SELECT DISTINCT name FROM kg_entities").fetchall():
                    all_entities.add(r["name"])
                related_entities = set()
                for r in conn.execute("SELECT DISTINCT source FROM kg_relations UNION SELECT DISTINCT target FROM kg_relations").fetchall():
                    related_entities.add(r[0])
                report.orphaned_entities = list(all_entities - related_entities)[:50]

                # 近期变更
                cutoff = (datetime.now() - timedelta(days=7)).isoformat()
                recent = conn.execute(
                    f"""
                    SELECT id, subject, predicate, object, extractor, created_at
                    FROM kg_triples {where}
                    WHERE created_at > ?
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (*params, cutoff) if user_id else (cutoff,),
                ).fetchall()
                report.recent_changes = [
                    {
                        "triple_id": r["id"],
                        "subject": r["subject"],
                        "predicate": r["predicate"],
                        "object": r["object"],
                        "extractor": r["extractor"],
                        "created_at": r["created_at"],
                    }
                    for r in recent
                ]

            # 计算健康度分数
            report.health_score = self._calculate_health_score(report)
            report.recommendations = self._generate_recommendations(report)

        except Exception as e:
            logger.error(f"[KGAudit] run_audit failed: {e}")
            report.recommendations.append(f"审计过程中发生错误: {str(e)}")

        return report

    def _calculate_health_score(self, report: KGAuditReport) -> float:
        """计算 KG 健康度分数 (0-1)"""
        score = 1.0
        if report.total_triples == 0:
            return 0.0

        # 低置信度惩罚
        low_conf_ratio = len(report.low_confidence_triples) / max(report.total_triples, 1)
        score -= low_conf_ratio * 0.3

        # 未验证比例惩罚
        unverified = report.verification_distribution.get("unverified", 0)
        unverified_ratio = unverified / max(report.total_triples, 1)
        score -= unverified_ratio * 0.2

        # 孤立实体惩罚
        if report.total_entities > 0:
            orphan_ratio = len(report.orphaned_entities) / report.total_entities
            score -= orphan_ratio * 0.2

        return max(0.0, min(1.0, round(score, 3)))

    def _generate_recommendations(self, report: KGAuditReport) -> List[str]:
        """生成改进建议"""
        recs = []
        if report.health_score < 0.5:
            recs.append("KG 健康度较低，建议运行质量检查和人工审核。")
        if len(report.low_confidence_triples) > 5:
            recs.append(f"发现 {len(report.low_confidence_triples)} 个低置信度三元组，建议复核或重新抽取。")
        if len(report.orphaned_entities) > 10:
            recs.append(f"发现 {len(report.orphaned_entities)} 个孤立实体，建议补充关系或清理。")
        unverified = report.verification_distribution.get("unverified", 0)
        if unverified > 20:
            recs.append(f"有 {unverified} 个未验证三元组，建议分批审核。")
        if not recs:
            recs.append("KG 状态良好，继续保持。")
        return recs


# ------------------------------------------------------------------
# 单例
# ------------------------------------------------------------------
_kg_audit_instance: Optional[KGAuditEngine] = None


def get_kg_audit_engine() -> KGAuditEngine:
    """获取 KG 审计引擎单例"""
    global _kg_audit_instance
    if _kg_audit_instance is None:
        _kg_audit_instance = KGAuditEngine()
    return _kg_audit_instance
