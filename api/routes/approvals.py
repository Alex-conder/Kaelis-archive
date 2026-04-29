"""
审批流 API — 高风险操作的用户确认

所有 high/critical 级别的风险评估都会进入此审批队列，
等待用户在 Web UI 中手动确认或拒绝。
"""

import uuid
import threading
from datetime import datetime
from flask import Blueprint, request, jsonify

approvals_bp = Blueprint('approvals', __name__, url_prefix='/api/approvals')

# 内存中的审批队列（单实例模式；多实例应使用 Redis）
_lock = threading.Lock()
_approval_queue: list = []


def submit_for_approval(
    title: str,
    description: str,
    risk: str,
    source: str = "unknown",
    payload: dict = None,
) -> dict:
    """提交一个高风险操作到审批队列"""
    item = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "risk": risk,
        "source": source,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",  # pending | approved | rejected
        "resolved_at": None,
        "payload": payload or {},
    }
    with _lock:
        _approval_queue.append(item)
    return item


@approvals_bp.route('/pending', methods=['GET'])
def list_pending():
    """获取所有待审批的项"""
    with _lock:
        pending = [a for a in _approval_queue if a["status"] == "pending"]
    return jsonify({"success": True, "items": pending})


@approvals_bp.route('/all', methods=['GET'])
def list_all():
    """获取所有审批记录"""
    with _lock:
        items = list(_approval_queue)
    return jsonify({"success": True, "items": items})


@approvals_bp.route('/<approval_id>', methods=['GET'])
def get_approval(approval_id: str):
    with _lock:
        item = next((a for a in _approval_queue if a["id"] == approval_id), None)
    if not item:
        return jsonify({"success": False, "error": "Approval not found"}), 404
    return jsonify({"success": True, "item": item})


@approvals_bp.route('/<approval_id>/approve', methods=['POST'])
def approve(approval_id: str):
    """批准一个操作"""
    with _lock:
        item = next((a for a in _approval_queue if a["id"] == approval_id), None)
        if item:
            item["status"] = "approved"
            item["resolved_at"] = datetime.now().isoformat()
    if not item:
        return jsonify({"success": False, "error": "Approval not found"}), 404
    return jsonify({"success": True, "item": item})


@approvals_bp.route('/<approval_id>/reject', methods=['POST'])
def reject(approval_id: str):
    """拒绝一个操作"""
    with _lock:
        item = next((a for a in _approval_queue if a["id"] == approval_id), None)
        if item:
            item["status"] = "rejected"
            item["resolved_at"] = datetime.now().isoformat()
    if not item:
        return jsonify({"success": False, "error": "Approval not found"}), 404
    return jsonify({"success": True, "item": item})
