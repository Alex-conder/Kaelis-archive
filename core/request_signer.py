"""
请求签名验证模块 (P14-003)

为 API 请求提供 HMAC-SHA256 签名验证，防止重放攻击：
1. 客户端生成签名：HMAC-SHA256(timestamp + method + path + body)
2. 服务端验证签名、时间戳、nonce
3. 拒绝过期请求（>5 分钟）和重复 nonce

安全目标：
- 防篡改：任何请求内容修改都会导致签名不匹配
- 防重放：时间戳 + nonce 双重保护
- 时效性：请求有效期 5 分钟

使用方式：
    from core.request_signer import RequestSigner
    signer = RequestSigner(secret_key="your-secret")
    
    # 客户端签名
    headers = signer.sign_request("POST", "/api/memory/write", body={"key": "x"})
    
    # 服务端验证
    valid, reason = signer.verify_request(headers, "POST", "/api/memory/write", body={"key": "x"})
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class RequestSigner:
    """
    HMAC-SHA256 请求签名验证器
    
    Header 格式:
        X-Kaelis-Timestamp: 1716144000
        X-Kaelis-Nonce: abcdef123456
        X-Kaelis-Signature: sha256=abc123...
    """
    
    DEFAULT_TTL_SECONDS = 300  # 5 分钟有效期
    
    def __init__(self, secret_key: Optional[str] = None, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        """
        Args:
            secret_key: 签名密钥（None 时从环境变量读取）
            ttl_seconds: 请求有效期（秒）
        """
        if secret_key is None:
            import os
            secret_key = os.getenv("KAELIS_API_SECRET", "default-secret-change-me")
        
        self.secret_key = secret_key.encode("utf-8")
        self.ttl_seconds = ttl_seconds
        self._used_nonces: set = set()  # 防重放 nonce 缓存
        self._nonce_cache_limit = 10000
    
    def sign_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        timestamp: Optional[int] = None,
        nonce: Optional[str] = None
    ) -> Dict[str, str]:
        """
        为请求生成签名头
        
        Args:
            method: HTTP 方法
            path: 请求路径
            body: 请求体
            timestamp: 时间戳（秒），默认当前时间
            nonce: 随机字符串，默认自动生成
            
        Returns:
            Dict: 签名头字典
        """
        ts = timestamp or int(time.time())
        nonce = nonce or self._generate_nonce()
        
        signature = self._calculate_signature(method, path, body, ts, nonce)
        
        return {
            "X-Kaelis-Timestamp": str(ts),
            "X-Kaelis-Nonce": nonce,
            "X-Kaelis-Signature": f"sha256={signature}"
        }
    
    def verify_request(
        self,
        headers: Dict[str, str],
        method: str,
        path: str,
        body: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        验证请求签名
        
        Args:
            headers: 请求头（必须包含 X-Kaelis-*）
            method: HTTP 方法
            path: 请求路径
            body: 请求体
            
        Returns:
            Tuple[bool, str]: (是否有效, 失败原因)
        """
        # 1. 检查必要头
        timestamp_str = headers.get("X-Kaelis-Timestamp") or headers.get("x-kaelis-timestamp")
        nonce = headers.get("X-Kaelis-Nonce") or headers.get("x-kaelis-nonce")
        signature = headers.get("X-Kaelis-Signature") or headers.get("x-kaelis-signature")
        
        if not all([timestamp_str, nonce, signature]):
            return False, "Missing signature headers"
        
        # 2. 验证时间戳
        try:
            timestamp = int(timestamp_str)
        except ValueError:
            return False, "Invalid timestamp"
        
        now = int(time.time())
        if abs(now - timestamp) > self.ttl_seconds:
            return False, f"Request expired (delta={abs(now - timestamp)}s)"
        
        # 3. 验证 nonce（防重放）
        if nonce in self._used_nonces:
            return False, "Nonce already used (replay attack?)"
        
        # 4. 验证签名
        expected = self._calculate_signature(method, path, body, timestamp, nonce)
        provided = signature.replace("sha256=", "")
        
        if not hmac.compare_digest(expected, provided):
            return False, "Signature mismatch"
        
        # 5. 记录 nonce
        self._used_nonces.add(nonce)
        self._cleanup_nonces()
        
        return True, "OK"
    
    def _calculate_signature(
        self,
        method: str,
        path: str,
        body: Optional[Dict],
        timestamp: int,
        nonce: str
    ) -> str:
        """计算 HMAC-SHA256 签名"""
        body_str = json.dumps(body, sort_keys=True, ensure_ascii=False) if body else ""
        message = f"{timestamp}:{nonce}:{method.upper()}:{path}:{body_str}"
        
        signature = hmac.new(
            self.secret_key,
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _generate_nonce(self) -> str:
        """生成随机 nonce"""
        import secrets
        return secrets.token_hex(16)
    
    def _cleanup_nonces(self):
        """清理过期的 nonce 缓存（简单策略：超过限制时清空）"""
        if len(self._used_nonces) > self._nonce_cache_limit:
            self._used_nonces.clear()
    
    def get_middleware_config(self) -> Dict[str, Any]:
        """获取 Flask/Django 中间件配置示例"""
        return {
            "required_headers": ["X-Kaelis-Timestamp", "X-Kaelis-Nonce", "X-Kaelis-Signature"],
            "ttl_seconds": self.ttl_seconds,
            "algorithm": "HMAC-SHA256",
            "skip_paths": ["/api/health", "/api/auth/login"]  # 不需要签名的路径
        }


# 全局实例
_signer_instance: Optional[RequestSigner] = None


def get_request_signer(secret_key: Optional[str] = None) -> RequestSigner:
    """获取全局签名验证器"""
    global _signer_instance
    if _signer_instance is None:
        _signer_instance = RequestSigner(secret_key=secret_key)
    return _signer_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试请求签名验证 ===")
    signer = RequestSigner(secret_key="test-secret-key")
    
    # 1. 正常签名验证
    headers = signer.sign_request("POST", "/api/memory/write", body={"key": "test", "value": 123})
    print(f"Generated headers: {headers}")
    
    valid, reason = signer.verify_request(headers, "POST", "/api/memory/write", body={"key": "test", "value": 123})
    print(f"Valid request: {valid} ({reason})")
    
    # 2. 篡改检测
    tampered_headers = headers.copy()
    tampered_headers["X-Kaelis-Signature"] = "sha256=fake"
    valid, reason = signer.verify_request(tampered_headers, "POST", "/api/memory/write", body={"key": "test", "value": 123})
    print(f"Tampered request: {valid} ({reason})")
    
    # 3. 过期检测
    old_headers = signer.sign_request("GET", "/api/stats", timestamp=int(time.time()) - 600)
    valid, reason = signer.verify_request(old_headers, "GET", "/api/stats")
    print(f"Expired request: {valid} ({reason})")
    
    # 4. 重放检测
    valid, reason = signer.verify_request(headers, "POST", "/api/memory/write", body={"key": "test", "value": 123})
    print(f"Replay request: {valid} ({reason})")
    
    print("\n[OK] RequestSigner test completed")
