"""
Test: core/tools/notifier.py

覆盖率目标：≥80%
"""

import pytest
import asyncio
from unittest.mock import MagicMock

from core.tools.notifier import (
    Notifier,
    NotificationChannel,
    ApprovalRequest,
)


class TestNotifier:
    """Notifier 测试套件"""

    @pytest.fixture
    def notifier(self):
        n = Notifier()
        n.set_channel(NotificationChannel.LOG)
        return n

    @pytest.mark.asyncio
    async def test_request_approval_returns_id(self, notifier):
        req_id = await notifier.request_approval(
            source_agent="agent_1",
            tool_name="file.delete",
            params={"path": "/tmp/x"},
            risk_level="high",
            reason="Deleting system file",
        )
        assert req_id.startswith("appr-")
        assert req_id in notifier._pending

    @pytest.mark.asyncio
    async def test_resolve_approval(self, notifier):
        req_id = await notifier.request_approval(
            source_agent="a1",
            tool_name="t1",
            params={},
            risk_level="low",
            reason="test",
        )
        cb_mock = MagicMock()
        notifier.on_resolved(req_id, cb_mock)

        ok = await notifier.resolve(req_id, approved=True)
        assert ok is True
        assert notifier._pending[req_id].status == "approved"
        cb_mock.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_resolve_unknown_id(self, notifier):
        ok = await notifier.resolve("no-such-id", approved=True)
        assert ok is False

    @pytest.mark.asyncio
    async def test_async_callback(self, notifier):
        req_id = await notifier.request_approval(
            source_agent="a1",
            tool_name="t1",
            params={},
            risk_level="low",
            reason="test",
        )
        results = []

        async def async_cb(approved):
            results.append(approved)

        notifier.on_resolved(req_id, async_cb)
        await notifier.resolve(req_id, approved=False)
        assert results == [False]

    @pytest.mark.asyncio
    async def test_websocket_channel(self, notifier):
        handler = MagicMock()
        notifier.set_channel(NotificationChannel.WEBSOCKET)
        notifier.register_handler(handler)

        await notifier.request_approval(
            source_agent="a1",
            tool_name="t1",
            params={},
            risk_level="medium",
            reason="ws test",
        )
        handler.assert_called_once()
        payload = handler.call_args[0][0]
        assert payload["type"] == "approval_request"

    def test_get_pending(self, notifier):
        asyncio.run(
            notifier.request_approval(
                source_agent="a1",
                tool_name="t1",
                params={},
                risk_level="low",
                reason="r1",
            )
        )
        pending = notifier.get_pending()
        assert len(pending) == 1
        assert pending[0].tool_name == "t1"

    def test_get_request(self, notifier):
        req_id = asyncio.run(
            notifier.request_approval(
                source_agent="a1",
                tool_name="t1",
                params={},
                risk_level="low",
                reason="r1",
            )
        )
        req = notifier.get_request(req_id)
        assert req is not None
        assert req.request_id == req_id
