"""End-to-end WebSocket tests — verify actual connection + message flow."""
import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import websockets

from core.network.ws_server import KaelisWebSocketServer
from core.network.ws_manager import get_ws_manager
from core.network.offline_queue import get_offline_queue


@pytest.fixture(autouse=True)
def reset_singletons(tmp_path):
    """Reset singletons between tests and use temp DB for offline queue."""
    from core.network.ws_server import _WsServerInstance
    from core.network.ws_manager import _WsManagerInstance
    from core.network.offline_queue import _QueueInstance, DEFAULT_DB_PATH
    global _WsServerInstance, _WsManagerInstance, _QueueInstance

    # Patch offline queue to use temp database
    orig_db_path = DEFAULT_DB_PATH
    from core.network import offline_queue as oq_mod
    oq_mod.DEFAULT_DB_PATH = tmp_path / "offline_messages.db"

    _WsServerInstance = None
    _WsManagerInstance = None
    _QueueInstance = None
    yield
    # Clean up any lingering connections in the manager
    if _WsManagerInstance is not None:
        _WsManagerInstance._connections.clear()
        _WsManagerInstance._device_to_user.clear()
    _WsServerInstance = None
    _WsManagerInstance = None
    _QueueInstance = None
    oq_mod.DEFAULT_DB_PATH = orig_db_path


class TestWSE2E:
    async def _run_server(self, port: int = 8765):
        """Start a test WS server and return it."""
        server = KaelisWebSocketServer(port=port)
        server.start_in_thread()
        await asyncio.sleep(0.3)  # Wait for server to start
        return server

    @pytest.mark.asyncio
    async def test_auth_handshake(self):
        server = await self._run_server(port=18765)
        try:
            uri = "ws://localhost:18765"
            async with websockets.connect(uri) as ws:
                # Send auth
                await ws.send(json.dumps({
                    "type": "auth",
                    "device_id": "dev_test_1",
                    "user_id": "user_test",
                    "platform": "test",
                }))
                # Receive auth_ok
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                assert msg["type"] == "auth_ok"
                assert msg["device_id"] == "dev_test_1"
        finally:
            server.stop()
            await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_ping_pong(self):
        server = await self._run_server(port=18766)
        try:
            uri = "ws://localhost:18766"
            async with websockets.connect(uri) as ws:
                # Auth first
                await ws.send(json.dumps({
                    "type": "auth",
                    "device_id": "dev_test_2",
                    "user_id": "user_test",
                }))
                await asyncio.wait_for(ws.recv(), timeout=2.0)

                # Send ping
                await ws.send(json.dumps({"type": "ping"}))
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                assert msg["type"] == "pong"
                assert "timestamp" in msg
        finally:
            server.stop()
            await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_broadcast_between_devices(self):
        server = await self._run_server(port=18767)
        try:
            uri = "ws://localhost:18767"

            # Connect device A
            ws_a = await websockets.connect(uri)
            await ws_a.send(json.dumps({
                "type": "auth",
                "device_id": "dev_a",
                "user_id": "user_1",
            }))
            await asyncio.wait_for(ws_a.recv(), timeout=2.0)

            # Connect device B (same user)
            ws_b = await websockets.connect(uri)
            await ws_b.send(json.dumps({
                "type": "auth",
                "device_id": "dev_b",
                "user_id": "user_1",
            }))
            await asyncio.wait_for(ws_b.recv(), timeout=2.0)

            # Device A broadcasts
            await ws_a.send(json.dumps({
                "type": "broadcast",
                "msg_type": "test_msg",
                "payload": {"hello": "world"},
            }))

            # Device B should receive it (may need to skip offline_batch)
            raw = await asyncio.wait_for(ws_b.recv(), timeout=2.0)
            msg = json.loads(raw)
            # If offline messages were queued, skip them
            while msg.get("type") == "offline_batch":
                raw = await asyncio.wait_for(ws_b.recv(), timeout=2.0)
                msg = json.loads(raw)
            assert msg["type"] == "test_msg"
            assert msg["payload"]["hello"] == "world"
            assert msg["source_device"] == "dev_a"

            await ws_a.close()
            await ws_b.close()
        finally:
            server.stop()
            await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_offline_message_delivery(self):
        server = await self._run_server(port=18768)
        try:
            # Queue a message for dev_offline before it connects
            queue = get_offline_queue()
            queue.enqueue("dev_offline", {
                "msg_id": "offline_1",
                "type": "workflow_completed",
                "payload": {"wf_id": "123"},
                "timestamp": time.time(),
                "source_device": "dev_sender",
            })

            uri = "ws://localhost:18768"
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({
                    "type": "auth",
                    "device_id": "dev_offline",
                    "user_id": "user_2",
                }))
                # auth_ok
                await asyncio.wait_for(ws.recv(), timeout=2.0)

                # Should receive offline batch
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                assert msg["type"] == "offline_batch"
                assert msg["message"]["msg_id"] == "offline_1"
        finally:
            server.stop()
            await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_auth_timeout(self):
        server = await self._run_server(port=18769)
        try:
            uri = "ws://localhost:18769"
            async with websockets.connect(uri) as ws:
                # Don't send auth — wait for timeout
                raw = await asyncio.wait_for(ws.recv(), timeout=7.0)
                msg = json.loads(raw)
                assert msg["type"] == "error"
                assert "timeout" in msg["error"].lower()
        finally:
            server.stop()
            await asyncio.sleep(0.2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
