"""
B-4: GDPR 合规与隐私控制 API

提供用户数据导出、删除（被遗忘权）和隐私设置管理。

端点：
- GET  /api/privacy/export      — 导出全部个人数据
- POST /api/privacy/delete      — 执行被遗忘权删除
- GET  /api/privacy/settings    — 获取隐私设置
- POST /api/privacy/settings    — 更新隐私设置
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from core.memory_manager_v2 import get_memory_manager, LAYER_CONFIG

logger = logging.getLogger(__name__)
privacy_bp = Blueprint("privacy", __name__, url_prefix="/api/privacy")


def _get_db_path(layer: str) -> str:
    mm = get_memory_manager()
    return mm._get_db_path(layer)


def _get_user_id() -> str:
    """从请求中提取用户标识（当前回退到 header 或 anonymous）"""
    return request.headers.get("X-User-ID", "anonymous")


# =============================================================================
# 数据导出
# =============================================================================

@privacy_bp.route("/export", methods=["GET"])
def export_data():
    """
    GDPR 数据可携带权 — 导出用户全部个人数据

    Returns:
        JSON 包含所有层的个人数据
    """
    user_id = _get_user_id()
    export_timestamp = datetime.now(timezone.utc).isoformat()
    export_package: Dict[str, Any] = {
        "export_version": "1.0",
        "exported_at": export_timestamp,
        "user_id": user_id,
        "data_controller": "Kaelis AI Agent OS",
        "layers": {},
    }

    try:
        # L0: 系统元数据（仅该用户的配置）
        l0_data = _export_layer("L0", user_id)
        export_package["layers"]["L0"] = l0_data

        # L1: 高频活跃记忆
        l1_data = _export_layer("L1", user_id)
        export_package["layers"]["L1"] = l1_data

        # L2: 事件序列记忆
        l2_data = _export_layer("L2", user_id)
        export_package["layers"]["L2"] = l2_data

        # L3: 知识图谱实体（按 user_id 过滤）
        l3_data = _export_l3(user_id)
        export_package["layers"]["L3"] = l3_data

        # 统计
        total_records = sum(len(v.get("records", [])) for v in export_package["layers"].values())
        export_package["summary"] = {"total_records": total_records}

        logger.info(f"Data exported for user={user_id}, records={total_records}")
        return jsonify({"success": True, "data": export_package})

    except Exception as e:
        logger.error(f"Data export failed for user={user_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _export_layer(layer: str, user_id: str) -> Dict[str, Any]:
    db_path = _get_db_path(layer)
    config = LAYER_CONFIG.get(layer)
    if not config:
        return {"records": []}

    table = config["table"]
    records: List[Dict[str, Any]] = []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if layer == "L0":
            cursor = conn.execute(
                f"SELECT key, value, metadata, updated_at FROM {table} WHERE user_id = ?",
                (user_id,),
            )
            for row in cursor.fetchall():
                records.append({
                    "key": row["key"],
                    "value": json.loads(row["value"]),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "updated_at": row["updated_at"],
                })
        elif layer == "L1":
            cursor = conn.execute(
                f"SELECT key, value, metadata, importance, created_at, expires_at FROM {table} WHERE user_id = ?",
                (user_id,),
            )
            for row in cursor.fetchall():
                records.append({
                    "key": row["key"],
                    "value": json.loads(row["value"]),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "importance": row["importance"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                })
        elif layer == "L2":
            cursor = conn.execute(
                f"SELECT key, value, metadata, source, created_at FROM {table} WHERE user_id = ?",
                (user_id,),
            )
            for row in cursor.fetchall():
                records.append({
                    "key": row["key"],
                    "value": json.loads(row["value"]),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "source": row["source"],
                    "created_at": row["created_at"],
                })

    return {"record_count": len(records), "records": records}


def _export_l3(user_id: str) -> Dict[str, Any]:
    db_path = _get_db_path("L3")
    records: List[Dict[str, Any]] = []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT name, type, source, created_at FROM kg_entities WHERE user_id = ?",
            (user_id,),
        )
        for row in cursor.fetchall():
            records.append({
                "name": row["name"],
                "type": row["type"],
                "source": row["source"],
                "created_at": row["created_at"],
            })

    return {"record_count": len(records), "records": records}


# =============================================================================
# 被遗忘权 — 数据删除
# =============================================================================

@privacy_bp.route("/delete", methods=["POST"])
def delete_data():
    """
    GDPR 被遗忘权 — 删除用户全部个人数据

    Request Body:
        {
            "confirm": true,      // 必须显式确认
            "scope": "all"        // all | memories | skills (预留)
        }

    Returns:
        {"success": true, "deleted": {...}}
    """
    user_id = _get_user_id()
    data = request.get_json() or {}

    if not data.get("confirm"):
        return jsonify({"success": False, "error": "确认标志 required. 请设置 confirm: true"}), 400

    try:
        deleted = {"L0": 0, "L1": 0, "L2": 0, "L3": 0}

        # L0: 删除用户配置（保留系统全局配置）
        deleted["L0"] = _delete_layer_by_user("L0", user_id)
        # L1: 删除活跃记忆
        deleted["L1"] = _delete_layer_by_user("L1", user_id)
        # L2: 删除事件记忆
        deleted["L2"] = _delete_layer_by_user("L2", user_id)
        # L3: 删除知识图谱实体
        deleted["L3"] = _delete_l3_by_user(user_id)

        total = sum(deleted.values())
        logger.info(f"Right to be forgotten executed for user={user_id}, deleted={total}")

        # 记录删除日志到 L2（审计追踪，匿名化）
        try:
            mm = get_memory_manager()
            mm.write(
                layer="L2",
                key=f"gdpr_delete_{datetime.now(timezone.utc).isoformat()}",
                value={"action": "right_to_be_forgotten", "deleted_summary": deleted},
                metadata={"source": "gdpr", "importance": 1.0, "original_user_id_hash": hash(user_id) & 0xFFFFFFFF},
                user_id="gdpr_system",
            )
        except Exception:
            pass

        return jsonify({"success": True, "deleted": deleted, "total": total})

    except Exception as e:
        logger.error(f"Data deletion failed for user={user_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _delete_layer_by_user(layer: str, user_id: str) -> int:
    db_path = _get_db_path(layer)
    config = LAYER_CONFIG.get(layer)
    if not config:
        return 0
    table = config["table"]

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount


def _delete_l3_by_user(user_id: str) -> int:
    db_path = _get_db_path("L3")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM kg_entities WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount


# =============================================================================
# 隐私设置
# =============================================================================

DEFAULT_PRIVACY_SETTINGS = {
    "data_retention_days": 365,          # 数据保留期限
    "allow_analytics": True,             # 是否允许匿名分析
    "allow_model_training": False,       # 是否允许用于模型训练
    "auto_delete_expired": True,         # 自动删除过期记忆
    "share_with_agents": True,           # 是否允许 Agent 间共享
    "export_format": "json",             # 默认导出格式
}

SETTINGS_KEY = "privacy_settings"


@privacy_bp.route("/settings", methods=["GET"])
def get_privacy_settings():
    """获取当前用户的隐私设置"""
    user_id = _get_user_id()
    try:
        mm = get_memory_manager()
        stored = mm.read("L0", SETTINGS_KEY, user_id=user_id)
        if stored and isinstance(stored, dict) and "value" in stored:
            settings = {**DEFAULT_PRIVACY_SETTINGS, **stored["value"]}
        else:
            settings = DEFAULT_PRIVACY_SETTINGS.copy()
        return jsonify({"success": True, "settings": settings})
    except Exception as e:
        logger.error(f"Get privacy settings failed: {e}")
        return jsonify({"success": True, "settings": DEFAULT_PRIVACY_SETTINGS.copy()})


@privacy_bp.route("/settings", methods=["POST"])
def update_privacy_settings():
    """更新隐私设置"""
    user_id = _get_user_id()
    data = request.get_json() or {}
    updates = data.get("settings", {})

    try:
        mm = get_memory_manager()
        stored = mm.read("L0", SETTINGS_KEY, user_id=user_id)
        if stored and isinstance(stored, dict) and "value" in stored:
            current = stored["value"]
        else:
            current = {}

        # 只允许更新白名单内的字段
        allowed_keys = set(DEFAULT_PRIVACY_SETTINGS.keys())
        for key, value in updates.items():
            if key in allowed_keys:
                current[key] = value

        # 填充默认值
        for key, default in DEFAULT_PRIVACY_SETTINGS.items():
            if key not in current:
                current[key] = default

        mm.write("L0", SETTINGS_KEY, current, metadata={"source": "privacy_settings"}, user_id=user_id)
        return jsonify({"success": True, "settings": current})
    except Exception as e:
        logger.error(f"Update privacy settings failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
