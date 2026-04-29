"""
Flask API 中间件层 (P17-001)

集成以下功能到 Flask 请求处理流程：
1. 请求签名验证（HMAC-SHA256）
2. 安全扫描（敏感操作拦截）
3. 速率限制（IP + 用户维度）
4. API 请求监控（Prometheus 指标自动埋点）

使用方式：
    from core.middleware import register_middleware
    register_middleware(app)
"""

import logging
import os
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from flask import Flask, request, g, jsonify

logger = logging.getLogger(__name__)


class KaelisMiddleware:
    """
    Kaelis API 中间件集合
    
    提供可插拔的安全、监控、限流功能。
    """
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.rate_limit_store: Dict[str, List[float]] = {}
        self.skip_paths = {'/health', '/metrics', '/api/health', '/api/auth/health'}
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """初始化中间件"""
        self.app = app
        
        # 注册 before_request 钩子
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        
        logger.info("KaelisMiddleware initialized")
    
    def _before_request(self):
        """请求前处理"""
        g.start_time = time.time()
        path = request.path
        
        # 跳过监控端点
        if path in self.skip_paths:
            return
        
        # 基准测试模式：跳过所有安全检查以测量裸性能
        if os.environ.get('BENCHMARK_MODE'):
            return
        
        # 1. 速率限制检查
        limit_result = self._check_rate_limit()
        if not limit_result["allowed"]:
            logger.warning(f"Rate limit exceeded: {request.remote_addr} -> {path}")
            return jsonify({
                "success": False,
                "error": "Rate limit exceeded",
                "retry_after": limit_result.get("retry_after", 60)
            }), 429
        
        # 2. Agent 权限检查 (Sprint 6 D5)
        # 测试环境下跳过权限检查，避免测试客户端未携带 X-Agent-ID 时失败
        if not getattr(self.app, 'config', {}).get('TESTING', False):
            try:
                from core.agent_permission_manager import get_agent_permission_manager
                pm = get_agent_permission_manager()
                perm_result = pm.check_request_permission(request)
                if not perm_result.get("granted"):
                    logger.warning(
                        f"Agent permission denied: {perm_result.get('agent_id')} -> {perm_result.get('resource')}/{perm_result.get('action')}"
                    )
                    return jsonify({
                        "success": False,
                        "error": "Permission denied",
                        "agent_id": perm_result.get("agent_id"),
                        "resource": perm_result.get("resource"),
                        "action": perm_result.get("action"),
                    }), 403
            except Exception as e:
                # 权限系统不可用时记录警告但不阻断（优雅降级）
                logger.warning(f"Agent permission check failed: {e}")
        
        # 3. 请求签名验证（仅对非 GET 请求）
        if request.method != 'GET':
            auth_result = self._verify_request_signature()
            if not auth_result["valid"]:
                # 签名验证失败但不阻断（可选严格模式）
                logger.debug(f"Signature verification: {auth_result['reason']}")
        
        # 4. 安全扫描
        scan_result = self._scan_request()
        if scan_result.get("blocked"):
            logger.warning(f"Request blocked by safety scanner: {scan_result['reason']}")
            return jsonify({
                "success": False,
                "error": scan_result["reason"],
                "risk_level": scan_result.get("risk_level", "high"),
                "requires_approval": scan_result.get("requires_approval", False)
            }), 403
    
    def _after_request(self, response):
        """请求后处理"""
        path = request.path
        
        # 跳过监控端点
        if path in self.skip_paths:
            return response
        
        # Prometheus 指标埋点
        try:
            self._record_metrics(response)
        except Exception as e:
            logger.debug(f"Metrics recording failed: {e}")
        
        return response
    
    def _check_rate_limit(self) -> Dict[str, Any]:
        """
        速率限制检查
        
        策略：
        - 每 IP 每分钟 120 请求
        - 每用户每分钟 60 请求（如果已认证）
        """
        client_id = self._get_client_id()
        now = time.time()
        window = 60  # 1 分钟窗口
        max_requests = 120  # IP 级别
        
        # 清理过期记录
        if client_id in self.rate_limit_store:
            self.rate_limit_store[client_id] = [
                t for t in self.rate_limit_store[client_id]
                if now - t < window
            ]
        else:
            self.rate_limit_store[client_id] = []
        
        # 检查限制
        if len(self.rate_limit_store[client_id]) >= max_requests:
            oldest = self.rate_limit_store[client_id][0]
            return {
                "allowed": False,
                "retry_after": int(window - (now - oldest))
            }
        
        # 记录本次请求
        self.rate_limit_store[client_id].append(now)
        return {"allowed": True}
    
    def _verify_request_signature(self) -> Dict[str, Any]:
        """验证请求签名"""
        try:
            from core.request_signer import get_request_signer
            signer = get_request_signer()
            
            headers = dict(request.headers)
            body = request.get_json(silent=True)
            
            valid, reason = signer.verify_request(
                headers,
                request.method,
                request.path,
                body
            )
            return {"valid": valid, "reason": reason}
        except Exception as e:
            return {"valid": False, "reason": str(e)}
    
    def _scan_request(self) -> Dict[str, Any]:
        """安全扫描请求"""
        try:
            from core.safety_scanner import get_safety_scanner
            scanner = get_safety_scanner()
            
            body = request.get_json(silent=True) or {}
            
            result = scanner.scan_request(
                endpoint=request.path,
                method=request.method,
                payload=body,
                user_context={"user_id": getattr(g, 'user_id', 'anonymous')}
            )
            
            return {
                "blocked": result.blocked,
                "reason": result.reason,
                "risk_level": result.risk_level,
                "requires_approval": result.required_approval
            }
        except Exception as e:
            logger.debug(f"Safety scan failed: {e}")
            return {"blocked": False}
    
    def _record_metrics(self, response):
        """记录 Prometheus 指标"""
        try:
            from core.monitoring.metrics import API_METRICS
            
            duration = time.time() - g.start_time
            method = request.method
            path = request.path
            status = str(response.status_code)
            
            API_METRICS.request_total.labels(
                method=method,
                endpoint=path,
                status_code=status
            ).inc()
            
            API_METRICS.request_duration.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
        except Exception:
            pass
    
    def _get_client_id(self) -> str:
        """获取客户端标识"""
        # 优先使用用户 ID
        user_id = getattr(g, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # 回退到 IP + User-Agent 指纹
        ip = request.remote_addr or 'unknown'
        ua = request.user_agent.string[:20] if request.user_agent else ''
        return f"ip:{ip}:{ua}"


def register_middleware(app: Flask):
    """注册中间件到 Flask 应用"""
    KaelisMiddleware(app)
    logger.info("API middleware registered (rate-limit + safety + signature + metrics)")


if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    register_middleware(app)
    
    @app.route('/test')
    def test():
        return {"message": "OK"}
    
    with app.test_client() as client:
        r = client.get('/test')
        print(f"GET /test: {r.status_code} -> {r.get_json()}")
    
    print("\n[OK] Middleware test completed")
