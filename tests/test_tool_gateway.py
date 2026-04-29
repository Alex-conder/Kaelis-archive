"""Tests for Prompt: Universal Tool Registry + File Security Gateway."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.tools.universal_tool_registry import ToolGateway, ToolRegistry
from core.security.exceptions import PermissionDeniedError
from core.security.file_gateway import FileGateway, FileOperationType


class TestToolRegistry:
    def test_register_and_discover(self):
        reg = ToolRegistry()
        reg.register("test_tool", lambda x: x, {"desc": "test"})
        tools = reg.discover()
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register("test_tool", lambda x: x)
        assert reg.unregister("test_tool") is True
        assert reg.unregister("missing") is False


class TestToolGateway:
    def test_normal_call(self):
        gateway = ToolGateway()
        gateway.registry.register("echo", lambda msg: f"echo:{msg}")

        import asyncio
        result = asyncio.run(gateway.execute("agent_1", "echo", {"msg": "hello"}))
        assert result == "echo:hello"

    def test_blocked_call_raises(self):
        gateway = ToolGateway()
        gateway.registry.register("danger", lambda: None)

        import asyncio
        with pytest.raises(PermissionDeniedError):
            asyncio.run(gateway.execute("agent_1", "danger", {"password": "secret"}))

    def test_tool_not_found_raises(self):
        gateway = ToolGateway()
        import asyncio
        with pytest.raises(PermissionDeniedError):
            asyncio.run(gateway.execute("agent_1", "missing", {}))


class TestFileGatewayWhitelist:
    def test_add_and_remove_allowed_directory(self):
        fg = FileGateway()
        fg.add_allowed_directory("/tmp/test_allowed")
        assert "/tmp/test_allowed" in fg.allowed_directories

        fg.remove_allowed_directory("/tmp/test_allowed")
        assert "/tmp/test_allowed" not in fg.allowed_directories

    def test_write_outside_whitelist_blocked(self):
        fg = FileGateway()
        fg.add_allowed_directory("/tmp/allowed_zone")

        from core.security.file_gateway import FileOperationRequest
        req = FileOperationRequest(
            source="test",
            operation=FileOperationType.WRITE,
            file_path="/tmp/outside_zone/file.txt",
            content="data",
        )
        result = fg.evaluate(req)
        assert result.approved is False
        assert "不在授权目录" in result.reason

    def test_read_outside_whitelist_allowed(self):
        fg = FileGateway()
        fg.add_allowed_directory("/tmp/allowed_zone")

        from core.security.file_gateway import FileOperationRequest
        req = FileOperationRequest(
            source="test",
            operation=FileOperationType.READ,
            file_path="/tmp/outside_zone/file.txt",
        )
        result = fg.evaluate(req)
        # 读取操作不受白名单限制，应通过规则引擎
        assert result.approved is True
