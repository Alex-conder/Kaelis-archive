"""
Test: core/skills/sandbox_tester.py (P19-003 Extended)

覆盖率目标：≥80% for new methods
"""

import pytest
from unittest.mock import patch, MagicMock

from core.skills.sandbox_tester import (
    SkillSandboxTester,
    SandboxReport,
    CWE_PATTERNS,
    RISK_WEIGHTS,
    RISK_THRESHOLD_LOW,
)


class TestCWEPatterns:
    """CWE 漏洞映射测试"""

    def test_cwe_78_os_system(self):
        assert "CWE-78" in str(CWE_PATTERNS)

    def test_cwe_94_eval(self):
        assert "CWE-94" in str(CWE_PATTERNS)

    def test_clawhavoc_patterns_present(self):
        """OpenClaw ClawHavoc 模式必须存在"""
        from core.skills.sandbox_tester import DANGEROUS_PATTERNS
        all_patterns = []
        for level, pts in DANGEROUS_PATTERNS.items():
            all_patterns.extend(pts)
        combined = "\n".join(all_patterns)
        assert "base64" in combined.lower() or "b64decode" in combined.lower()
        assert "__builtins__" in combined


class TestExecSandboxTest:
    """子进程隔离执行测试"""

    def test_exec_safe_code(self):
        tester = SkillSandboxTester()
        skill = {
            "id": "safe",
            "name": "safe",
            "code": "x = 1 + 1\nprint(x)",
        }
        result = tester.exec_sandbox_test(skill)
        assert result["passed"] is True
        assert result["returncode"] == 0

    def test_exec_timeout(self):
        tester = SkillSandboxTester()
        skill = {
            "id": "loop",
            "name": "loop",
            "code": "while True: pass",
        }
        result = tester.exec_sandbox_test(skill)
        assert result["passed"] is False
        assert result["timeout"] is True

    def test_exec_network_blocked(self):
        tester = SkillSandboxTester()
        skill = {
            "id": "net",
            "name": "net",
            "code": "import urllib.request; urllib.request.urlopen('http://example.com', timeout=2)",
        }
        result = tester.exec_sandbox_test(skill)
        # 应该因为网络被阻断而失败
        assert result["passed"] is False


class TestMarketplaceGate:
    """技能市场门禁测试"""

    def test_safe_skill_allowed(self):
        skill = {
            "id": "safe",
            "name": "safe",
            "params": {"method": "minmax"},
            "workflow": {"type": "transform"},
        }
        gate = SkillSandboxTester.marketplace_gate(skill)
        assert gate["allowed"] is True

    def test_malicious_skill_blocked(self):
        skill = {
            "id": "evil",
            "name": "evil",
            "params": {"cmd": "rm -rf /"},
            "workflow": {"type": "exec"},
        }
        gate = SkillSandboxTester.marketplace_gate(skill)
        assert gate["allowed"] is False
        assert "risk" in gate["reason"].lower() or "HIGH" in gate["reason"]
