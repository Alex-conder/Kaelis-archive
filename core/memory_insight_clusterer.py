"""
记忆语义聚类与主题自动发现
D-1: 让记忆从存储变为理解

功能：
1. 对最近 N 天的 L2 记忆进行 K-means 语义聚类
2. 每个簇提取 TF-IDF 关键词作为主题标签
3. 自动拆分子簇（大簇 > 40% 时）
4. 将聚类结果写入 L3 Semantic（belongs_to_cluster 关系）
"""

import json
import logging
import math
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 可选依赖：scikit-learn 用于聚类和 TF-IDF（延迟导入，避免启动阻塞）
def _sklearn_available() -> bool:
    try:
        from sklearn.cluster import KMeans  # noqa: F401
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: F401
        from sklearn.metrics.pairwise import cosine_similarity  # noqa: F401
        return True
    except ImportError:
        return False


class MemoryInsightClusterer:
    """
    记忆语义聚类器

    自动发现记忆库中的主题结构，让用户知道"我的记忆库在发生什么"。
    """

    def __init__(
        self,
        db_path: str = "data/kaelis_dev.db",
        min_cluster_size: int = 3,
        max_cluster_ratio: float = 0.40,
    ):
        self.db_path = Path(db_path)
        self.min_cluster_size = min_cluster_size
        self.max_cluster_ratio = max_cluster_ratio

    # ------------------------------------------------------------------ #
    # 主入口
    # ------------------------------------------------------------------ #

    def cluster_analysis(
        self,
        days: int = 7,
        k: Optional[int] = None,
        user_id: str = "anonymous",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        对最近 `days` 天的 L2 记忆进行聚类分析。

        Args:
            days: 分析最近多少天的记忆
            k: 聚类数，None 时自动推断（sqrt(N/2)）
            user_id: 用户隔离
            dry_run: 仅分析，不写入 L3

        Returns:
            {"clusters": [...], "total_memories": int, "method": str}
        """
        memories = self._fetch_recent_memories(days, user_id)
        total = len(memories)

        if total < self.min_cluster_size:
            return {
                "clusters": [],
                "total_memories": total,
                "method": "skipped",
                "reason": f"Not enough memories ({total} < {self.min_cluster_size})",
            }

        # 自动推断 K
        if k is None:
            k = max(2, min(5, int(math.sqrt(total / 2))))

        # 执行聚类
        if _sklearn_available() and total >= k:
            clusters = self._sklearn_cluster(memories, k)
        else:
            clusters = self._fallback_keyword_cluster(memories, k)

        # 检查大簇并拆分
        clusters = self._split_oversized_clusters(clusters, memories)

        # 为每个簇提取主题标签
        for c in clusters:
            c["topic_labels"] = self._extract_keywords(c["memories"])

        # 写入 L3（如果不 dry_run）
        if not dry_run:
            self._persist_to_l3(clusters, user_id)

        return {
            "clusters": [
                {
                    "cluster_id": c["id"],
                    "topic_labels": c["topic_labels"],
                    "memory_count": len(c["memories"]),
                    "memory_keys": [m["key"] for m in c["memories"]],
                }
                for c in clusters
            ],
            "total_memories": total,
            "method": "sklearn" if _sklearn_available() else "fallback",
        }

    # ------------------------------------------------------------------ #
    # 数据获取
    # ------------------------------------------------------------------ #

    def _fetch_recent_memories(
        self, days: int, user_id: str
    ) -> List[Dict[str, Any]]:
        """从 L2 获取最近 N 天的记忆。"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        memories = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT id, key, value, metadata, source, created_at
                    FROM memory_l2
                    WHERE user_id = ? AND created_at > ?
                    ORDER BY created_at DESC
                    """,
                    (user_id, cutoff),
                ).fetchall()

            for r in rows:
                text = self._extract_text(r)
                if text:
                    memories.append(
                        {
                            "id": r["id"],
                            "key": r["key"],
                            "value": json.loads(r["value"]) if r["value"] else {},
                            "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                            "source": r["source"],
                            "created_at": r["created_at"],
                            "text": text,
                        }
                    )
        except Exception as e:
            logger.error(f"Fetch recent memories failed: {e}")

        return memories

    @staticmethod
    def _extract_text(row: sqlite3.Row) -> str:
        """从记忆行中提取可聚类的文本。"""
        key = row["key"] or ""
        try:
            value = json.loads(row["value"]) if row["value"] else {}
        except Exception:
            value = str(row["value"])

        if isinstance(value, dict):
            # 优先取 content / text / summary 字段
            text = str(value.get("content", value.get("text", value.get("summary", ""))))
        elif isinstance(value, list):
            text = " ".join(str(v) for v in value[:5])
        else:
            text = str(value)

        return f"{key} {text}".strip()

    # ------------------------------------------------------------------ #
    # 聚类算法
    # ------------------------------------------------------------------ #

    def _sklearn_cluster(
        self, memories: List[Dict], k: int
    ) -> List[Dict[str, Any]]:
        """使用 sklearn KMeans + TF-IDF 进行聚类。"""
        from sklearn.cluster import KMeans
        from sklearn.feature_extraction.text import TfidfVectorizer

        texts = [m["text"] for m in memories]

        # TF-IDF 向量化
        vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        X = vectorizer.fit_transform(texts)

        # KMeans 聚类
        n_clusters = min(k, len(memories))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)

        # 组装结果
        clusters: Dict[int, List[Dict]] = {}
        for mem, label in zip(memories, labels):
            clusters.setdefault(label, []).append(mem)

        return [
            {"id": f"cluster_{i}", "memories": mems}
            for i, mems in clusters.items()
        ]

    def _fallback_keyword_cluster(
        self, memories: List[Dict], k: int
    ) -> List[Dict[str, Any]]:
        """无 sklearn 时的简化关键词聚类。"""
        # 提取高频词作为种子主题
        all_words = []
        for m in memories:
            words = [
                w.lower()
                for w in m["text"].split()
                if len(w) > 3 and w.isalpha()
            ]
            all_words.extend(words)

        top_words = [w for w, _ in Counter(all_words).most_common(k)]
        clusters = {w: [] for w in top_words}
        clusters["other"] = []

        for m in memories:
            best = "other"
            best_score = 0
            text_lower = m["text"].lower()
            for word in top_words:
                score = text_lower.count(word)
                if score > best_score:
                    best_score = score
                    best = word
            clusters[best].append(m)

        return [
            {"id": f"cluster_{word}", "memories": mems}
            for word, mems in clusters.items()
            if mems
        ]

    def _split_oversized_clusters(
        self, clusters: List[Dict], all_memories: List[Dict]
    ) -> List[Dict[str, Any]]:
        """如果某个簇超过总数的 40%，递归拆分为子簇。"""
        total = len(all_memories)
        result = []

        for c in clusters:
            ratio = len(c["memories"]) / total if total else 0
            if ratio > self.max_cluster_ratio and len(c["memories"]) >= self.min_cluster_size * 2:
                # 递归拆分为 2 个子簇
                sub_k = 2
                sub_clusters = self._sklearn_cluster(c["memories"], sub_k)
                result.extend(sub_clusters)
                logger.info(
                    f"Split oversized cluster {c['id']} ({len(c['memories'])} items) into {len(sub_clusters)} sub-clusters"
                )
            else:
                result.append(c)

        # 重新分配 ID
        for i, c in enumerate(result):
            c["id"] = f"cluster_{i}"

        return result

    # ------------------------------------------------------------------ #
    # 关键词提取
    # ------------------------------------------------------------------ #

    def _extract_keywords(self, memories: List[Dict], top_n: int = 3) -> List[str]:
        """用 TF-IDF 从簇中提取关键词作为主题标签。"""
        texts = [m["text"] for m in memories]
        if not texts:
            return []

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            vectorizer = TfidfVectorizer(
                max_features=100,
                stop_words="english",
                ngram_range=(1, 2),
                min_df=1,
            )
            X = vectorizer.fit_transform(texts)
            scores = X.sum(axis=0).A1
            terms = vectorizer.get_feature_names_out()
            top_indices = scores.argsort()[-top_n:][::-1]
            return [terms[i] for i in top_indices]
        except Exception:
            # fallback: 简单词频
            words = []
            for t in texts:
                words.extend(
                    [w.lower() for w in t.split() if len(w) > 3 and w.isalpha()]
                )
            return [w for w, _ in Counter(words).most_common(top_n)]

    # ------------------------------------------------------------------ #
    # 持久化到 L3
    # ------------------------------------------------------------------ #

    def _persist_to_l3(self, clusters: List[Dict], user_id: str) -> None:
        """将聚类结果写入 L3 Semantic（kg_entities 表）。"""
        try:
            l3_db = Path("data/kaelis_graph.db")
            with sqlite3.connect(l3_db) as conn:
                # 确保关系表存在
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kg_relations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        target TEXT NOT NULL,
                        relation_type TEXT NOT NULL,
                        properties TEXT,
                        user_id TEXT DEFAULT 'anonymous',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                for c in clusters:
                    cluster_name = f"cluster:{c['id']}"
                    labels = c.get("topic_labels", [])
                    label_str = ", ".join(labels) if labels else "unknown"

                    # 写入簇实体
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO kg_entities
                        (name, type, source, user_id, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            cluster_name,
                            "Cluster",
                            f"insight_clusterer: {label_str}",
                            user_id,
                            datetime.now().isoformat(),
                        ),
                    )

                    # 写入 belongs_to_cluster 关系
                    for m in c["memories"]:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO kg_relations
                            (source, target, relation_type, properties, user_id)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                m["key"],
                                cluster_name,
                                "belongs_to_cluster",
                                json.dumps(
                                    {"topic_labels": labels, "cluster_id": c["id"]},
                                    ensure_ascii=False,
                                ),
                                user_id,
                            ),
                        )

            logger.info(f"Persisted {len(clusters)} clusters to L3")
        except Exception as e:
            logger.error(f"Persist to L3 failed: {e}")


# 全局实例
_clusterer_instance: Optional[MemoryInsightClusterer] = None


def get_insight_clusterer() -> MemoryInsightClusterer:
    """获取全局聚类器实例。"""
    global _clusterer_instance
    if _clusterer_instance is None:
        _clusterer_instance = MemoryInsightClusterer()
    return _clusterer_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    clusterer = MemoryInsightClusterer()
    result = clusterer.cluster_analysis(days=7, dry_run=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
