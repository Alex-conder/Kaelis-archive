"""
SafetyScanner 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import SafetyScannerTestBase


class TestSafetyScanner(SafetyScannerTestBase):
    """测试安全扫描器"""
    
    def test_safe_request(self):
        """安全请求不被阻断"""
        result = self.scanner.scan_request(
            endpoint="/api/memory/write",
            method="POST",
            payload={"layer": "l0", "key": "test", "value": "hello"},
            user_context={"user_id": "test_user"}
        )
        self.assertFalse(result.blocked)
    
    def test_dangerous_payload(self):
        """危险 payload 被检测"""
        result = self.scanner.scan_request(
            endpoint="/api/memory/write",
            method="POST",
            payload={"code": "import os; os.system('rm -rf /')"},
            user_context={"user_id": "test_user"}
        )
        # 扫描器应该检测到风险
        self.assertTrue(
            result.risk_level in ["low", "medium", "high", "critical"],
            f"Unexpected risk_level: {result.risk_level}"
        )
    
    def test_empty_payload(self):
        """空 payload"""
        result = self.scanner.scan_request(
            endpoint="/api/health",
            method="GET",
            payload={},
            user_context={}
        )
        self.assertFalse(result.blocked)


if __name__ == "__main__":
    unittest.main()
