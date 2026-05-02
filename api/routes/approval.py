"""
敏感操作审批流 API (P14-002)

为安全扫描器拦截的敏感操作提供审批机制：
1. 提交审批请求
2. 查询审批状态
3. 审批人通过/拒绝
4. 审批通过后执行原操作

审批配置：
    config/kaelis.yaml:
      security:
        approvers:
          - user_id: "admin"
            role: "super_admin"
          - user_id: "ops"
            role: "operator"
        auto_approve_low_risk: false
        approval_timeout_hours: 24
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

approval_bp = Blueprint('approval', __name__, url_prefix='/api/approval')


@dataclass
class ApprovalRequest:
    """审批请求"""
    request_id: str
    endpoint: str
    method: str
    payload: Dict[str, Any]
    risk_level: str
    reason: str
    requester: str
    status: str = "pending"  # pending, approved, rejected, expired
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolver: Optional[str] = None
    resolution_note: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at_iso"] = datetime.fromtimestamp(self.created_at).isoformat()
        if self.resolved_at:
            data["resolved_at_iso"] = datetime.fromtimestamp(self.resolved_at).isoformat()
        return data
    
    def is_expired(self, timeout_hours: int = 24) -> bool:
        """检查是否已过期"""
        if self.status != "pending":
            return False
        elapsed = time.time() - self.created_at
        return elapsed > timeout_hours * 3600


class ApprovalManager:
    """
    审批管理器
    
    内存存储（生产环境应使用 Redis / 数据库）
    """
    
    def __init__(self, timeout_hours: int = 24):
        self.requests: Dict[str, ApprovalRequest] = {}
        self.timeout_hours = timeout_hours
        self.approvers: List[Dict] = self._load_approvers()
    
    def _load_approvers(self) -> List[Dict]:
        """从配置文件加载审批人列表"""
        import os
        from pathlib import Path
        
        # 默认审批人
        default_approvers = [
            {"user_id": "admin", "role": "super_admin"},
        ]
        
        # 尝试从配置文件加载
        config_paths = [
            Path("config/kaelis.yaml"),
            Path("config/security.yaml"),
        ]
        
        for path in config_paths:
            if path.exists():
                try:
                    import yaml
                    with open(path, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                    approvers = config.get("security", {}).get("approvers")
                    if approvers:
                        return approvers
                except Exception as e:
                    logger.warning(f"Failed to load approvers from {path}: {e}")
        
        # 环境变量覆盖
        env_approvers = os.getenv("APPROVERS")
        if env_approvers:
            try:
                return json.loads(env_approvers)
            except Exception:
                pass
        
        return default_approvers
    
    def is_approver(self, user_id: str) -> bool:
        """检查用户是否是审批人"""
        return any(a.get("user_id") == user_id for a in self.approvers)
    
    def submit(
        self,
        endpoint: str,
        method: str,
        payload: Dict[str, Any],
        risk_level: str,
        reason: str,
        requester: str
    ) -> ApprovalRequest:
        """提交审批请求"""
        request_id = f"apr_{uuid.uuid4().hex[:12]}"
        
        req = ApprovalRequest(
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            payload=payload,
            risk_level=risk_level,
            reason=reason,
            requester=requester
        )
        
        self.requests[request_id] = req
        logger.info(f"Approval submitted: {request_id} for {endpoint} by {requester}")
        return req
    
    def resolve(
        self,
        request_id: str,
        resolver: str,
        approved: bool,
        note: str = ""
    ) -> Optional[ApprovalRequest]:
        """审批人处理请求"""
        req = self.requests.get(request_id)
        if not req:
            return None
        
        if req.status != "pending":
            logger.warning(f"Request {request_id} already {req.status}")
            return req
        
        if req.is_expired(self.timeout_hours):
            req.status = "expired"
            logger.warning(f"Request {request_id} expired")
            return req
        
        if not self.is_approver(resolver):
            logger.warning(f"User {resolver} is not an approver")
            return None
        
        req.status = "approved" if approved else "rejected"
        req.resolved_at = time.time()
        req.resolver = resolver
        req.resolution_note = note
        
        action = "approved" if approved else "rejected"
        logger.info(f"Request {request_id} {action} by {resolver}")
        return req
    
    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        """获取请求状态"""
        req = self.requests.get(request_id)
        if req and req.status == "pending" and req.is_expired(self.timeout_hours):
            req.status = "expired"
        return req
    
    def list_pending(self) -> List[ApprovalRequest]:
        """列出待审批请求"""
        pending = []
        for req in self.requests.values():
            if req.status == "pending" and not req.is_expired(self.timeout_hours):
                pending.append(req)
        return sorted(pending, key=lambda x: x.created_at)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        statuses = {}
        for req in self.requests.values():
            statuses[req.status] = statuses.get(req.status, 0) + 1
        return {
            "total": len(self.requests),
            "by_status": statuses,
            "approvers": len(self.approvers),
            "timeout_hours": self.timeout_hours
        }


# 全局管理器
_approval_manager: Optional[ApprovalManager] = None


def get_approval_manager() -> ApprovalManager:
    """获取全局审批管理器"""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager


# ==================== API 路由 ====================

@approval_bp.route('/submit', methods=['POST'])
def submit_approval():
    """
    提交审批请求
    
    Request Body:
        {
            "endpoint": "/api/memory/delete",
            "method": "POST",
            "payload": {"layer": "L1", "clear_layer": true},
            "risk_level": "high",
            "reason": "清空记忆层",
            "requester": "user_001"
        }
    """
    try:
        data = request.get_json() or {}
        
        required = ["endpoint", "method", "payload", "risk_level", "reason"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"success": False, "error": f"Missing fields: {missing}"}), 400
        
        manager = get_approval_manager()
        req = manager.submit(
            endpoint=data["endpoint"],
            method=data["method"],
            payload=data["payload"],
            risk_level=data["risk_level"],
            reason=data["reason"],
            requester=data.get("requester", "anonymous")
        )
        
        return jsonify({
            "success": True,
            "data": req.to_dict(),
            "message": "Approval request submitted"
        })
        
    except Exception as e:
        logger.error(f"Submit approval failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@approval_bp.route('/<request_id>', methods=['GET'])
def get_approval_status(request_id):
    """查询审批状态"""
    try:
        manager = get_approval_manager()
        req = manager.get(request_id)
        
        if not req:
            return jsonify({"success": False, "error": "Request not found"}), 404
        
        return jsonify({
            "success": True,
            "data": req.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Get approval status failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@approval_bp.route('/<request_id>/resolve', methods=['POST'])
def resolve_approval(request_id):
    """
    审批人处理请求
    
    Request Body:
        {
            "resolver": "admin",
            "approved": true,
            "note": "已确认操作必要性"
        }
    """
    try:
        data = request.get_json() or {}
        resolver = data.get("resolver")
        approved = data.get("approved")
        
        if not resolver or approved is None:
            return jsonify({"success": False, "error": "resolver and approved required"}), 400
        
        manager = get_approval_manager()
        
        if not manager.is_approver(resolver):
            return jsonify({"success": False, "error": "Unauthorized resolver"}), 403
        
        req = manager.resolve(
            request_id=request_id,
            resolver=resolver,
            approved=approved,
            note=data.get("note", "")
        )
        
        if not req:
            return jsonify({"success": False, "error": "Request not found or already resolved"}), 404
        
        return jsonify({
            "success": True,
            "data": req.to_dict(),
            "message": f"Request {request_id} {'approved' if approved else 'rejected'}"
        })
        
    except Exception as e:
        logger.error(f"Resolve approval failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@approval_bp.route('/pending', methods=['GET'])
def list_pending():
    """列出待审批请求"""
    try:
        manager = get_approval_manager()
        pending = manager.list_pending()
        
        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in pending],
            "count": len(pending)
        })
        
    except Exception as e:
        logger.error(f"List pending failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@approval_bp.route('/stats', methods=['GET'])
def approval_stats():
    """获取审批统计"""
    try:
        manager = get_approval_manager()
        return jsonify({"success": True, "data": manager.get_stats()})
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def register_approval_routes(app):
    """注册审批路由到 Flask 应用"""
    app.register_blueprint(approval_bp)
    logger.info("Approval routes registered")


if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    register_approval_routes(app)
    
    print("Approval routes registered:")
    for rule in app.url_map.iter_rules():
        if 'approval' in str(rule):
            print(f"  {rule}")
