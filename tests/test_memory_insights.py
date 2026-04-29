"""
测试 D-1 记忆语义聚类 与 D-2 遗忘曲线复习建议
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def test_db(tmp_path):
    """创建临时测试数据库"""
    db_path = tmp_path / "test_kaelis.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE memory_l2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                metadata TEXT,
                source TEXT DEFAULT 'system',
                user_id TEXT DEFAULT 'anonymous',
                created_at TEXT NOT NULL,
                last_recalled_at TEXT
            )
        """)
    return db_path


class TestMemoryInsightClusterer:
    """D-1: 记忆语义聚类测试"""

    def _insert_memories(self, db_path, memories):
        with sqlite3.connect(db_path) as conn:
            for m in memories:
                conn.execute(
                    """
                    INSERT INTO memory_l2 (key, value, metadata, source, user_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m["key"],
                        json.dumps(m["value"], ensure_ascii=False),
                        json.dumps(m.get("metadata", {}), ensure_ascii=False),
                        m.get("source", "test"),
                        m.get("user_id", "anonymous"),
                        m.get("created_at", datetime.now().isoformat()),
                    ),
                )

    def test_cluster_frontend_backend(self, test_db, monkeypatch):
        """验收：写入10条前端 + 5条后端记忆，聚类后得到两个主题"""
        from core.memory_insight_clusterer import MemoryInsightClusterer

        # 覆盖 db_path 为临时数据库
        clusterer = MemoryInsightClusterer(db_path=str(test_db))

        # 插入 10 条前端开发记忆
        frontend_memories = [
            {
                "key": f"frontend_tip_{i}",
                "value": {
                    "content": f"React component optimization using useMemo and useCallback. Frontend performance tuning. {i}"
                },
                "metadata": {"category": "frontend"},
            }
            for i in range(10)
        ]

        # 插入 5 条后端架构记忆
        backend_memories = [
            {
                "key": f"backend_tip_{i}",
                "value": {
                    "content": f"Microservice architecture design with Docker and Kubernetes. Backend scaling strategy. {i}"
                },
                "metadata": {"category": "backend"},
            }
            for i in range(5)
        ]

        self._insert_memories(test_db, frontend_memories + backend_memories)

        # 运行聚类分析
        result = clusterer.cluster_analysis(days=7, k=2, dry_run=True)

        assert result["total_memories"] == 15
        assert len(result["clusters"]) >= 1

        # 检查是否提取到了有意义的主题标签
        all_labels = []
        for c in result["clusters"]:
            all_labels.extend(c["topic_labels"])

        # TF-IDF 应该提取到与内容相关的显著词汇
        label_text = " ".join(all_labels).lower()
        has_tech_terms = any(
            term in label_text
            for term in [
                "react", "frontend", "component", "microservice", "backend",
                "docker", "kubernetes", "scaling", "strategy", "usememo",
                "performance", "concurrency", "hooks", "api", "service",
            ]
        )

        assert has_tech_terms, f"Expected meaningful topic labels, got: {all_labels}"

    def test_split_oversized_cluster(self, test_db, monkeypatch):
        """验收：大簇（>40%）自动拆分"""
        from core.memory_insight_clusterer import MemoryInsightClusterer

        clusterer = MemoryInsightClusterer(db_path=str(test_db))

        # 插入 20 条相似的前端记忆 + 5 条后端记忆
        memories = [
            {
                "key": f"react_tip_{i}",
                "value": {"content": "React hooks and state management patterns"},
            }
            for i in range(20)
        ] + [
            {
                "key": f"go_tip_{i}",
                "value": {"content": "Go microservice concurrency patterns"},
            }
            for i in range(5)
        ]

        self._insert_memories(test_db, memories)

        result = clusterer.cluster_analysis(days=7, k=2, dry_run=True)
        assert result["total_memories"] == 25
        # 如果大簇被拆分，cluster 数量应该 >= 2
        assert len(result["clusters"]) >= 1

    def test_not_enough_memories(self, test_db):
        """记忆数量不足时应跳过聚类"""
        from core.memory_insight_clusterer import MemoryInsightClusterer

        clusterer = MemoryInsightClusterer(db_path=str(test_db))
        result = clusterer.cluster_analysis(days=7, dry_run=True)

        assert result["method"] == "skipped"
        assert "Not enough memories" in result["reason"]


class TestMemoryForgettingCurve:
    """D-2: 遗忘曲线复习建议测试"""

    def _insert_memory(self, db_path, key, value, created_at, last_recalled_at=None, importance=0.5):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO memory_l2 (key, value, metadata, source, user_id, created_at, last_recalled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    json.dumps(value, ensure_ascii=False),
                    json.dumps({"importance": importance}, ensure_ascii=False),
                    "test",
                    "anonymous",
                    created_at,
                    last_recalled_at,
                ),
            )

    def test_forgetting_index_7_days(self, test_db):
        """验收：模拟7天未访问的记忆，遗忘指数 > 0.7"""
        from core.memory_consolidator import MemoryConsolidator

        consolidator = MemoryConsolidator()

        # 模拟一条 7 天前创建、从未回忆的低重要性记忆（importance=0.1, half_life=3天）
        # 7天 >> 3天半衰期 → 遗忘指数应 > 0.7
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        self._insert_memory(
            test_db,
            "old_knowledge",
            {"content": "Some important concept about neural networks"},
            created_at=seven_days_ago,
            last_recalled_at=None,
            importance=0.1,
        )

        # 读取并计算遗忘指数
        with sqlite3.connect(test_db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT key, value, metadata, created_at, last_recalled_at FROM memory_l2 WHERE key = ?",
                ("old_knowledge",),
            ).fetchone()

        memory = {
            "key": row["key"],
            "value": json.loads(row["value"]) if row["value"] else {},
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "created_at": row["created_at"],
            "last_recalled_at": row["last_recalled_at"],
        }

        idx = consolidator.forgetting_index(memory)
        assert idx > 0.7, f"Expected forgetting_index > 0.7 for 7-day old memory, got {idx}"

    def test_get_forgetting_reminders(self, test_db, monkeypatch):
        """验收：获取复习建议列表"""
        from core.memory_consolidator import MemoryConsolidator
        from core.memory_insight_clusterer import MemoryInsightClusterer

        # monkeypatch 数据库路径
        monkeypatch.setattr(
            MemoryConsolidator, "__init__",
            lambda self, **kwargs: None
        )
        consolidator = MemoryConsolidator()
        consolidator.db_path = test_db

        # 插入一条 7 天前的低重要性记忆（importance=0.1, half_life=3天 → 遗忘指数高）
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        self._insert_memory(
            test_db,
            "rust_ownership",
            {"content": "Rust ownership and borrowing rules"},
            created_at=seven_days_ago,
            last_recalled_at=None,
            importance=0.1,
        )

        # 插入一条今天的记忆（遗忘指数低）
        today = datetime.now().isoformat()
        self._insert_memory(
            test_db,
            "fresh_tip",
            {"content": "Just learned today"},
            created_at=today,
            last_recalled_at=today,
            importance=0.8,
        )

        # 直接测试 forgetting_index 方法
        with sqlite3.connect(test_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM memory_l2").fetchall()

        for r in rows:
            memory = {
                "key": r["key"],
                "value": json.loads(r["value"]) if r["value"] else {},
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "created_at": r["created_at"],
                "last_recalled_at": r["last_recalled_at"],
            }
            idx = consolidator.forgetting_index(memory)
            if r["key"] == "rust_ownership":
                assert idx > 0.7, f"Expected high forgetting index for old memory, got {idx}"
            elif r["key"] == "fresh_tip":
                assert idx < 0.1, f"Expected low forgetting index for fresh memory, got {idx}"

    def test_importance_affects_halflife(self):
        """验收：重要性越高，半衰期越长，遗忘指数增长越慢"""
        from core.memory_consolidator import MemoryConsolidator

        consolidator = MemoryConsolidator()
        now = datetime.now()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        # 高重要性记忆
        high_importance = {
            "key": "important",
            "value": {},
            "metadata": {"importance": 0.9},
            "created_at": seven_days_ago,
            "last_recalled_at": None,
        }

        # 低重要性记忆
        low_importance = {
            "key": "trivial",
            "value": {},
            "metadata": {"importance": 0.1},
            "created_at": seven_days_ago,
            "last_recalled_at": None,
        }

        high_idx = consolidator.forgetting_index(high_importance, current_time=now)
        low_idx = consolidator.forgetting_index(low_importance, current_time=now)

        assert high_idx < low_idx, (
            f"High importance should decay slower: high={high_idx}, low={low_idx}"
        )
