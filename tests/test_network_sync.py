"""Tests for core/network/ — Cross-device WebSocket sync infrastructure."""
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest


class TestWSConnectionManager:
    def test_register_and_unregister(self):
        from core.network.ws_manager import WSConnectionManager
        mgr = WSConnectionManager()
        ws = MagicMock()
        conn = mgr.register("dev_a", ws, "user_1", platform="electron")
        assert conn.device_id == "dev_a"
        assert mgr.is_device_online("dev_a") is True

        user_id = mgr.unregister("dev_a")
        assert user_id == "user_1"
        assert mgr.is_device_online("dev_a") is False

    def test_get_user_devices(self):
        from core.network.ws_manager import WSConnectionManager
        mgr = WSConnectionManager()
        mgr.register("dev_a", MagicMock(), "user_1", platform="electron")
        mgr.register("dev_b", MagicMock(), "user_1", platform="browser")
        devices = mgr.get_user_devices("user_1")
        assert len(devices) == 2
        assert {d["platform"] for d in devices} == {"electron", "browser"}

    def test_prune_stale(self):
        from core.network.ws_manager import WSConnectionManager
        mgr = WSConnectionManager()
        mgr.register("dev_a", MagicMock(), "user_1")
        # Manually set last_ping to be stale
        mgr._connections["user_1"]["dev_a"].last_ping = time.time() - 200
        stale = mgr.prune_stale(timeout=120.0)
        assert "dev_a" in stale
        assert mgr.is_device_online("dev_a") is False

    def test_broadcast_to_user(self):
        import asyncio
        from core.network.ws_manager import WSConnectionManager
        mgr = WSConnectionManager()
        ws1 = MagicMock()
        loop = asyncio.new_event_loop()
        ws1.send = MagicMock(return_value=loop.create_future())
        ws1.send.return_value.set_result(None)
        mgr.register("dev_a", ws1, "user_1")

        results = loop.run_until_complete(
            mgr.broadcast_to_user("user_1", {"type": "test"})
        )
        loop.close()
        assert "dev_a" in results


class TestDeviceRegistry:
    @patch("core.network.device_registry.get_node_identity")
    @patch("core.memory_manager_v2.get_memory_manager")
    def test_profile_generation(self, mock_mm, mock_identity):
        from core.network.device_registry import DeviceRegistry
        ni = MagicMock()
        ni.kni = "test_kni"
        mock_identity.return_value = ni
        mock_mm.return_value = MagicMock()

        reg = DeviceRegistry()
        profile = reg.get_or_create_profile(platform="electron", capabilities=["memory"])
        assert profile.platform == "electron"
        assert "memory" in profile.capabilities
        assert profile.device_id.startswith("dev_")

    def test_pairing_management(self):
        from core.network.device_registry import DeviceRegistry, PairedDevice
        reg = DeviceRegistry.__new__(DeviceRegistry)
        reg._identity = MagicMock(kni="test_kni")
        reg._profile = None
        reg._pairings_cache = {}

        # Patch L0 persistence to use in-memory dict
        def _load_pairings():
            return reg._pairings_cache
        def _save_pairings(pairings):
            reg._pairings_cache = pairings
        reg._load_pairings = _load_pairings
        reg._save_pairings = _save_pairings

        device = PairedDevice(
            device_id="dev_remote",
            pairing_code="ABC123",
            display_name="Remote Device",
            platform="browser",
        )
        assert reg.add_paired_device(device) is True
        assert reg.is_paired("dev_remote") is True
        devices = reg.get_paired_devices()
        assert len(devices) == 1
        assert reg.remove_paired_device("dev_remote") is True
        assert reg.is_paired("dev_remote") is False


class TestOfflineQueue:
    def test_enqueue_and_dequeue(self, tmp_path):
        from core.network.offline_queue import OfflineMessageQueue
        db = tmp_path / "test_queue.db"
        queue = OfflineMessageQueue(db_path=db)

        msg = {
            "msg_id": "msg_001",
            "type": "workflow_completed",
            "payload": {"workflow_id": "wf_1"},
            "timestamp": time.time(),
            "source_device": "dev_a",
        }
        assert queue.enqueue("dev_b", msg) is True
        assert queue.count_for_device("dev_b") == 1

        messages = queue.dequeue_for_device("dev_b")
        assert len(messages) == 1
        assert messages[0]["msg_id"] == "msg_001"
        assert queue.count_for_device("dev_b") == 0

    def test_max_queue_size(self, tmp_path):
        from core.network.offline_queue import OfflineMessageQueue, MAX_MESSAGES_PER_DEVICE
        db = tmp_path / "test_queue2.db"
        queue = OfflineMessageQueue(db_path=db)

        for i in range(MAX_MESSAGES_PER_DEVICE + 10):
            queue.enqueue("dev_c", {
                "msg_id": f"msg_{i}",
                "type": "test",
                "payload": {},
                "timestamp": time.time(),
                "source_device": "dev_a",
            })

        count = queue.count_for_device("dev_c")
        assert count == MAX_MESSAGES_PER_DEVICE

    def test_ttl_expiration(self, tmp_path):
        from core.network.offline_queue import OfflineMessageQueue
        db = tmp_path / "test_queue3.db"
        queue = OfflineMessageQueue(db_path=db)

        queue.enqueue("dev_d", {
            "msg_id": "msg_old",
            "type": "test",
            "payload": {},
            "timestamp": time.time(),
            "source_device": "dev_a",
            "ttl": 1,  # 1 second TTL
        })
        time.sleep(1.1)
        messages = queue.dequeue_for_device("dev_d")
        assert len(messages) == 0  # expired


class TestMessageEncryptor:
    def test_encrypt_decrypt_roundtrip(self):
        from core.network.message_encryptor import MessageEncryptor
        enc = MessageEncryptor()
        # Force key derivation via mock
        enc._cached_key = b"x" * 32

        plaintext = {"secret": "data", "number": 42}
        envelope = enc.encrypt(plaintext)
        assert envelope is not None
        assert "ciphertext" in envelope
        assert "nonce" in envelope
        assert "tag" in envelope

        decrypted = enc.decrypt(envelope)
        assert decrypted == plaintext

    def test_decrypt_wrong_key_fails(self):
        from core.network.message_encryptor import MessageEncryptor
        enc1 = MessageEncryptor()
        enc1._cached_key = b"a" * 32
        enc2 = MessageEncryptor()
        enc2._cached_key = b"b" * 32

        envelope = enc1.encrypt({"test": "data"})
        decrypted = enc2.decrypt(envelope)
        assert decrypted is None


class TestMessageSync:
    def test_build_message(self):
        from core.network.message_sync import build_message
        msg = build_message("workflow_completed", {"id": "wf1"}, "dev_a", ttl=3600)
        assert msg["type"] == "workflow_completed"
        assert msg["payload"]["id"] == "wf1"
        assert msg["source_device"] == "dev_a"
        assert "msg_id" in msg
        assert "timestamp" in msg

    def test_conflict_resolution(self):
        from core.network.message_sync import MessageSync
        local = {"timestamp": 1000, "data": "local"}
        remote = {"timestamp": 2000, "data": "remote"}
        assert MessageSync.resolve_conflict(local, remote) == remote

        local2 = {"timestamp": 3000, "data": "local2"}
        assert MessageSync.resolve_conflict(local2, remote) == local2


class TestWSSyncAPIRoutes:
    def test_ws_info_endpoint(self):
        from flask import Flask
        from api.routes.ws_sync import ws_sync_bp
        app = Flask(__name__)
        app.register_blueprint(ws_sync_bp)
        client = app.test_client()
        resp = client.get("/api/sync/ws-info")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "ws_url" in data["data"]

    def test_devices_discover_endpoint(self):
        from flask import Flask
        from api.routes.ws_sync import ws_sync_bp
        app = Flask(__name__)
        app.register_blueprint(ws_sync_bp)
        client = app.test_client()

        with patch("core.network.device_registry.get_device_registry") as mock_reg:
            reg = MagicMock()
            reg.discover_lan_peers.return_value = []
            reg.get_paired_devices.return_value = []
            mock_reg.return_value = reg

            resp = client.get("/api/sync/devices/discover")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True

    def test_messages_send_endpoint(self):
        from flask import Flask
        from api.routes.ws_sync import ws_sync_bp
        app = Flask(__name__)
        app.register_blueprint(ws_sync_bp)
        client = app.test_client()

        with patch("core.network.ws_manager.get_ws_manager") as mock_ws, \
             patch("core.network.offline_queue.get_offline_queue") as mock_q:
            ws = MagicMock()
            ws.is_device_online.return_value = False
            mock_ws.return_value = ws
            q = MagicMock()
            q.enqueue.return_value = True
            mock_q.return_value = q

            resp = client.post("/api/sync/messages/send", json={
                "target_device_id": "dev_b",
                "msg_type": "test",
                "payload": {"hello": "world"},
                "source_device": "dev_a",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["queued"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
