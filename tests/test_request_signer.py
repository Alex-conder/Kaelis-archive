"""
RequestSigner 单元测试
"""

import time
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestRequestSigner(KaelisTestBase):
    """测试请求签名器"""
    
    def setUp(self):
        super().setUp()
        from core.request_signer import RequestSigner
        self.signer = RequestSigner(secret_key="test_secret")
    
    def test_sign_and_verify_roundtrip(self):
        """签名和验证"""
        headers = self.signer.sign_request("POST", "/api/test", {"key": "value"})
        self.assertIn("X-Kaelis-Signature", headers)
        self.assertIn("X-Kaelis-Timestamp", headers)
        self.assertIn("X-Kaelis-Nonce", headers)
        
        valid, reason = self.signer.verify_request(headers, "POST", "/api/test", {"key": "value"})
        self.assertTrue(valid)
        self.assertEqual(reason, "OK")
    
    def test_verify_tampered_body(self):
        """篡改 body 检测"""
        headers = self.signer.sign_request("POST", "/api/test", {"key": "value"})
        valid, reason = self.signer.verify_request(headers, "POST", "/api/test", {"key": "tampered"})
        self.assertFalse(valid)
        self.assertIn("mismatch", reason)
    
    def test_verify_tampered_path(self):
        """篡改 path 检测"""
        headers = self.signer.sign_request("POST", "/api/test", {})
        valid, reason = self.signer.verify_request(headers, "POST", "/api/other", {})
        self.assertFalse(valid)
    
    def test_verify_expired(self):
        """过期检测"""
        old_timestamp = str(int(time.time()) - 400)
        headers = self.signer.sign_request("POST", "/api/test", {}, timestamp=old_timestamp)
        valid, reason = self.signer.verify_request(headers, "POST", "/api/test", {})
        self.assertFalse(valid)
        self.assertIn("expired", reason)
    
    def test_verify_replay(self):
        """重放攻击检测"""
        headers = self.signer.sign_request("POST", "/api/test", {})
        valid1, _ = self.signer.verify_request(headers, "POST", "/api/test", {})
        self.assertTrue(valid1)
        valid2, reason2 = self.signer.verify_request(headers, "POST", "/api/test", {})
        self.assertFalse(valid2)
        self.assertIn("Nonce", reason2)
    
    def test_verify_missing_headers(self):
        """缺少 header"""
        valid, reason = self.signer.verify_request({}, "POST", "/api/test", {})
        self.assertFalse(valid)
        self.assertIn("Missing", reason)
    
    def test_verify_invalid_timestamp(self):
        """无效时间戳"""
        headers = self.signer.sign_request("POST", "/api/test", {})
        headers["X-Kaelis-Timestamp"] = "not_a_number"
        valid, reason = self.signer.verify_request(headers, "POST", "/api/test", {})
        self.assertFalse(valid)
        self.assertIn("Invalid", reason)
    
    def test_generate_nonce(self):
        """生成 nonce"""
        nonce1 = self.signer._generate_nonce()
        nonce2 = self.signer._generate_nonce()
        self.assertNotEqual(nonce1, nonce2)
        self.assertEqual(len(nonce1), 32)
    
    def test_cleanup_nonces(self):
        """清理过期 nonce"""
        self.signer._cleanup_nonces()
        # 不应抛异常
    
    def test_middleware_config(self):
        """中间件配置"""
        config = self.signer.get_middleware_config()
        self.assertIsInstance(config, dict)


class TestRequestSignerSingleton(KaelisTestBase):
    """测试单例"""
    
    def test_get_request_signer(self):
        """单例模式"""
        from core.request_signer import get_request_signer
        s1 = get_request_signer()
        s2 = get_request_signer()
        self.assertIs(s1, s2)


if __name__ == "__main__":
    unittest.main()
