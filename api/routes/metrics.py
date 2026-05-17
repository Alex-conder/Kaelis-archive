"""
Metrics API - 前端性能指标收集
Phase 3: Web Vitals 性能监控

端点:
  POST /api/metrics/frontend   上报前端性能指标
  GET  /api/metrics/frontend   查询历史指标
"""
import sqlite3
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)
metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


def _init_metrics_table():
    """初始化前端性能指标表"""
    try:
        with sqlite3.connect("data/kaelis_graph.db") as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS frontend_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL,
                    rating TEXT,
                    delta REAL,
                    nav_type TEXT,
                    page_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON frontend_metrics(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_created ON frontend_metrics(created_at)")
    except Exception as e:
        logger.warning(f"Metrics table init failed: {e}")


@metrics_bp.route("/frontend", methods=["POST"])
def report_frontend_metrics():
    """接收前端 Web Vitals 指标"""
    try:
        data = request.get_json(silent=True) or {}
        _init_metrics_table()
        with sqlite3.connect("data/kaelis_graph.db") as conn:
            conn.execute(
                """
                INSERT INTO frontend_metrics (name, value, rating, delta, nav_type, page_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("name"),
                    data.get("value"),
                    data.get("rating"),
                    data.get("delta"),
                    data.get("navType"),
                    data.get("pagePath"),
                ),
            )
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Frontend metrics report failed: {e}")
        return jsonify({"error": str(e)}), 500


@metrics_bp.route("/frontend", methods=["GET"])
def get_frontend_metrics():
    """查询前端性能指标历史"""
    try:
        name = request.args.get("name")
        hours = request.args.get("hours", 24, type=int)
        _init_metrics_table()
        with sqlite3.connect("data/kaelis_graph.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM frontend_metrics
                WHERE created_at > datetime('now', ?)
                  AND (? IS NULL OR name = ?)
                ORDER BY created_at DESC
                LIMIT 1000
                """,
                (f"-{hours} hours", name, name),
            )
            rows = [dict(r) for r in cursor.fetchall()]
        # 计算聚合统计
        stats = {}
        if rows:
            from collections import defaultdict
            grouped = defaultdict(list)
            for r in rows:
                grouped[r["name"]].append(r["value"])
            for metric_name, values in grouped.items():
                stats[metric_name] = {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 2),
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                }
        return jsonify({"metrics": rows, "stats": stats})
    except Exception as e:
        logger.error(f"Frontend metrics query failed: {e}")
        return jsonify({"error": str(e)}), 500
