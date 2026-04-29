"""
K-11: 分享卡片生成 API

提供用户成长数据的聚合统计，供前端生成社交分享图片。

端点:
- GET /api/sharing/annual-report  — 获取用户年度报告数据
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from core.memory_manager_v2 import get_memory_manager, LAYER_CONFIG

logger = logging.getLogger(__name__)
bp = Blueprint("sharing", __name__, url_prefix="/api/sharing")


def _get_db_path(layer: str) -> str:
    mm = get_memory_manager()
    return mm._get_db_path(layer)


def _get_user_id() -> str:
    return request.headers.get("X-User-ID", "anonymous")


@bp.route("/annual-report", methods=["GET"])
def annual_report():
    """
    用户年度报告数据
    
    Returns:
        {
            "success": True,
            "data": {
                "user_id": "...",
                "report_period": "2025-04-29 ~ 2026-04-29",
                "stats": {
                    "total_memories": 1234,
                    "l1_memories": 100,
                    "l2_memories": 800,
                    "l3_entities": 334,
                    "skills_learned": 12,
                    "days_active": 180,
                    "favorite_topics": ["coding", "ai", "productivity"],
                },
                "milestones": [
                    {"title": "记忆突破1000条", "date": "2026-03-15"},
                    ...
                ],
                "growth_index": 85.5,  # 0-100
            }
        }
    """
    user_id = _get_user_id()
    now = datetime.now(timezone.utc)
    year_ago = (now - timedelta(days=365)).isoformat()

    try:
        stats = {
            "total_memories": 0,
            "l1_memories": 0,
            "l2_memories": 0,
            "l3_entities": 0,
            "skills_learned": 0,
            "days_active": 0,
            "favorite_topics": [],
        }

        # L1 计数
        db_path = _get_db_path("L1")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM memory_l1 WHERE user_id = ? AND created_at > ?",
                (user_id, year_ago),
            )
            stats["l1_memories"] = cursor.fetchone()[0]

        # L2 计数
        db_path = _get_db_path("L2")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM memory_l2 WHERE user_id = ? AND created_at > ?",
                (user_id, year_ago),
            )
            stats["l2_memories"] = cursor.fetchone()[0]

        # L3 实体计数
        db_path = _get_db_path("L3")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM kg_entities WHERE user_id = ? AND created_at > ?",
                (user_id, year_ago),
            )
            stats["l3_entities"] = cursor.fetchone()[0]

        stats["total_memories"] = stats["l1_memories"] + stats["l2_memories"] + stats["l3_entities"]

        # 活跃天数（基于 L2 中不同日期数）
        db_path = _get_db_path("L2")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(DISTINCT date(created_at)) FROM memory_l2 WHERE user_id = ? AND created_at > ?",
                (user_id, year_ago),
            )
            stats["days_active"] = cursor.fetchone()[0]

        # 技能计数
        skills_path = Path("data/skills/skills.json")
        if skills_path.exists():
            try:
                skills_data = json.loads(skills_path.read_text(encoding="utf-8"))
                stats["skills_learned"] = len(skills_data.get("skills", []))
            except Exception:
                pass

        #  favorite_topics: 从 L2 metadata 中提取 source 频率最高的 3 个
        db_path = _get_db_path("L2")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM memory_l2 WHERE user_id = ? AND created_at > ? GROUP BY source ORDER BY cnt DESC LIMIT 3",
                (user_id, year_ago),
            )
            stats["favorite_topics"] = [row[0] for row in cursor.fetchall() if row[0]]

        # 成长指数 (0-100): 综合计算
        growth_index = min(100, round(
            (stats["days_active"] / 365) * 30 +
            (min(stats["total_memories"], 5000) / 5000) * 40 +
            (min(stats["skills_learned"], 50) / 50) * 30
        , 1))

        # 里程碑
        milestones = []
        if stats["total_memories"] >= 1000:
            milestones.append({"title": "记忆突破 1000 条", "icon": "brain"})
        if stats["days_active"] >= 100:
            milestones.append({"title": "连续活跃 100 天", "icon": "flame"})
        if stats["skills_learned"] >= 10:
            milestones.append({"title": "掌握 10+ 项技能", "icon": "zap"})
        if not milestones:
            milestones.append({"title": "Kaelis 旅程开启", "icon": "rocket"})

        return jsonify({
            "success": True,
            "data": {
                "user_id": user_id,
                "report_period": f"{year_ago[:10]} ~ {now.isoformat()[:10]}",
                "stats": stats,
                "milestones": milestones,
                "growth_index": growth_index,
            }
        })

    except Exception as e:
        logger.error(f"Annual report generation failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
