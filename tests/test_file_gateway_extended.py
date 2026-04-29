"""
Test: core/security/file_gateway.py (Extended)

补充测试：白名单、审批流、便捷方法。
覆盖率目标：≥80%
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.security.file_gateway import (
    FileGateway,
    FileOperationRequest,
    FileOperationType,
    FileOperationResult,
)
from core.security.risk_gateway import RiskDecision


class TestFileGatewayExtended:
    """FileGateway 扩展测试"""

    @pytest.fixture
    def gateway(self):
        fg = FileGateway()
        fg.allowed_directories = []
        return fg

    # ------------------------------------------------------------------ #
    # 白名单管理
    # ------------------------------------------------------------------ #

    def test_add_allowed_directory(self, gateway):
        tmp = Path(os.getcwd())
        gateway.add_allowed_directory(str(tmp))
        assert len(gateway.allowed_directories) == 1

    def test_remove_allowed_directory(self, gateway):
        tmp = Path(os.getcwd())
        gateway.add_allowed_directory(str(tmp))
        ok = gateway.remove_allowed_directory(str(tmp))
        assert ok is True
        assert len(gateway.allowed_directories) == 0

    def test_remove_nonexistent_dir(self, gateway):
        ok = gateway.remove_allowed_directory("/nonexistent/path")
        assert ok is False

    def test_whitelist_blocks_unauthorized_write(self, gateway):
        gateway.add_allowed_directory("/tmp/allowed")
        req = FileOperationRequest(
            source="test",
            operation=FileOperationType.WRITE,
            file_path="/tmp/outside/file.txt",
        )
        result = gateway.evaluate(req)
        assert result.decision == RiskDecision.BLOCK
        assert "白名单" in result.reason

    def test_whitelist_allows_read(self, gateway):
        gateway.add_allowed_directory("/tmp/allowed")
        req = FileOperationRequest(
            source="test",
            operation=FileOperationType.READ,
            file_path="/tmp/outside/file.txt",
        )
        result = gateway.evaluate(req)
        assert result.decision != RiskDecision.BLOCK or "白名单" not in result.reason

    # ------------------------------------------------------------------ #
    # 便捷方法
    # ------------------------------------------------------------------ #

    def test_read_file(self, gateway):
        result = gateway.read_file("test", "/tmp/readme.md")
        assert isinstance(result, FileOperationResult)

    def test_write_file(self, gateway):
        result = gateway.write_file("test", "/tmp/write.md", "# Hello")
        assert isinstance(result, FileOperationResult)

    def test_delete_file(self, gateway):
        result = gateway.delete_file("test", "/tmp/old.md")
        assert isinstance(result, FileOperationResult)

    # ------------------------------------------------------------------ #
    # 审批流
    # ------------------------------------------------------------------ #

    def test_resolve_approval(self, gateway):
        req = FileOperationRequest(
            source="test",
            operation=FileOperationType.DELETE,
            file_path="/tmp/test.txt",
        )
        result = gateway.evaluate(req)
        if result.decision == RiskDecision.CONFIRM:
            assert result.approval_id is not None
            ok = gateway.resolve(result.approval_id, "approved")
            assert ok is True
            # 审计日志应更新
            log = gateway.audit_log()
            entry = [e for e in log if e.get("approval_id") == result.approval_id]
            assert len(entry) == 1
            assert entry[0]["status"] == "approved"

    def test_get_pending(self, gateway):
        req = FileOperationRequest(
            source="test",
            operation=FileOperationType.DELETE,
            file_path="/tmp/test.txt",
        )
        gateway.evaluate(req)
        pending = gateway.get_pending()
        assert isinstance(pending, list)

    def test_audit_log(self, gateway):
        before = len(gateway.audit_log())
        gateway.read_file("test", "/tmp/test.md")
        after = len(gateway.audit_log())
        assert after > before
