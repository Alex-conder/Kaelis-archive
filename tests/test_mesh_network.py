"""Tests for core/mesh/ — Mesh Network Decentralization (P23-A)"""
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock, AsyncMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest


class TestMeshIdentity:
    def test_kni_generation(self):
        from core.mesh.identity import NodeIdentity
        ni = NodeIdentity()
        assert ni.kni is not None
        assert len(ni.kni) > 0
        assert ni.public_key_bytes is not None
        assert len(ni.public_key_bytes) == 32

    def test_sign_and_verify(self):
        from core.mesh.identity import NodeIdentity
        ni = NodeIdentity()
        msg = b"hello mesh"
        sig = ni.sign_message(msg)
        assert ni.verify_signature(msg, sig, ni.kni) is True

    def test_signed_metadata(self):
        from core.mesh.identity import NodeIdentity
        ni = NodeIdentity()
        meta = ni.get_signed_metadata()
        assert meta["kni"] == ni.kni
        assert "signature" in meta
        assert NodeIdentity.verify_signed_metadata(meta.copy()) is True


class TestMeshTransport:
    @patch("core.mesh.transport.get_node_identity")
    def test_register_and_list_peers(self, mock_identity):
        from core.mesh.transport import MeshTransport
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi

        transport = MeshTransport(port=9999)
        transport.register_peer("peer1", "127.0.0.1", 8888, ["coder"])
        peers = transport.list_sessions()
        assert len(peers) == 1
        assert peers[0]["kni"] == "peer1"
        assert peers[0]["status"] == "discovered"

    @patch("core.mesh.transport.get_node_identity")
    def test_prune_stale_peers(self, mock_identity):
        from core.mesh.transport import MeshTransport, HEARTBEAT_TIMEOUT
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi

        transport = MeshTransport(port=9999)
        transport.register_peer("peer1", "127.0.0.1", 8888, ["coder"])
        transport._sessions["peer1"].status = "active"
        transport._sessions["peer1"].last_seen = time.time() - HEARTBEAT_TIMEOUT - 1

        transport._prune_stale()
        assert transport._sessions["peer1"].status == "stale"

    @patch("core.mesh.transport.get_node_identity")
    def test_handshake_handler(self, mock_identity):
        from core.mesh.transport import MeshTransport
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        # Create a real key pair for peer
        peer_key = Ed25519PrivateKey.generate()
        peer_pub = peer_key.public_key()
        peer_pub_hex = peer_pub.public_bytes_raw().hex()

        mi = MagicMock()
        mi.kni = "self_node"
        mi.public_key_bytes = b"\x00" * 32
        mi.sign_message = lambda m: b"\x00" * 64
        mock_identity.return_value = mi

        transport = MeshTransport(port=9999)
        challenge = "challenge:test"
        sig = peer_key.sign(challenge.encode("utf-8")).hex()

        payload = {
            "kni": "peer1",
            "challenge": challenge,
            "signature": sig,
            "public_key": peer_pub_hex,
            "host": "127.0.0.1",
            "port": 8888,
            "capabilities": ["coder"],
        }

        result = transport.handle_handshake(payload)
        assert result["success"] is True
        assert result["kni"] == "self_node"
        assert "signature" in result

    @patch("core.mesh.transport.get_node_identity")
    def test_heartbeat_handler(self, mock_identity):
        from core.mesh.transport import MeshTransport
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi

        transport = MeshTransport(port=9999)
        transport.register_peer("peer1", "127.0.0.1", 8888, ["coder"])
        result = transport.handle_heartbeat({"kni": "peer1", "timestamp": time.time()})
        assert result["success"] is True
        assert transport._sessions["peer1"].last_seen > 0

    @patch("core.mesh.transport.get_node_identity")
    @patch("core.mesh.transport.get_authorization_manager")
    @patch("core.tools.universal_tool_registry.ToolGateway")
    def test_handle_invoke(self, mock_gateway, mock_auth, mock_identity):
        from core.mesh.transport import MeshTransport
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi

        auth = MagicMock()
        auth.verify_token.return_value = {
            "iss": "peer1",
            "permissions": [{"resource_type": "mcp_tool", "resource_id": "*", "actions": ["execute"]}],
        }
        mock_auth.return_value = auth

        gateway = MagicMock()
        gateway.execute = AsyncMock(return_value={"status": "ok"})
        mock_gateway.return_value = gateway

        transport = MeshTransport(port=9999)
        result = transport.handle_invoke(
            {"kni": "peer1", "tool_name": "test_tool", "params": {"x": 1}},
            auth_token="valid_token",
        )
        assert result["success"] is True
        assert result["tool"] == "test_tool"

    @patch("core.mesh.transport.get_node_identity")
    @patch("core.mesh.transport.get_authorization_manager")
    def test_handle_invoke_no_token(self, mock_auth, mock_identity):
        from core.mesh.transport import MeshTransport
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi

        transport = MeshTransport(port=9999)
        result = transport.handle_invoke({"tool_name": "test_tool", "params": {}})
        assert result["success"] is False
        assert "Authorization required" in result["error"]

    @patch("core.mesh.transport.get_node_identity")
    @patch("core.mesh.transport.get_authorization_manager")
    def test_handle_invoke_invalid_token(self, mock_auth, mock_identity):
        from core.mesh.transport import MeshTransport
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi

        auth = MagicMock()
        auth.verify_token.return_value = None
        mock_auth.return_value = auth

        transport = MeshTransport(port=9999)
        result = transport.handle_invoke(
            {"kni": "peer1", "tool_name": "test_tool", "params": {}},
            auth_token="bad_token",
        )
        assert result["success"] is False
        assert "Invalid or expired token" in result["error"]


class TestMeshGossip:
    @patch("core.mesh.gossip.get_node_identity")
    @patch("core.mesh.gossip.get_mesh_transport")
    @patch("core.mesh.gossip.get_memory_manager")
    def test_get_public_digests_empty(self, mock_mm, mock_transport, mock_identity):
        from core.mesh.gossip import GossipProtocol
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi
        mock_transport.return_value = MagicMock()

        mm = MagicMock()
        mm._get_db_conn.return_value.execute.return_value.fetchall.return_value = []
        mock_mm.return_value = mm

        gossip = GossipProtocol()
        digests = gossip.get_public_digests()
        assert digests == []

    @patch("core.mesh.gossip.get_node_identity")
    @patch("core.mesh.gossip.get_mesh_transport")
    @patch("core.mesh.gossip.get_memory_manager")
    def test_handle_digests_request(self, mock_mm, mock_transport, mock_identity):
        from core.mesh.gossip import GossipProtocol
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi
        mock_transport.return_value = MagicMock()

        mm = MagicMock()
        mm._get_db_conn.return_value.execute.return_value.fetchall.return_value = []
        mock_mm.return_value = mm

        gossip = GossipProtocol()
        result = gossip.handle_digests_request({"since": 0, "limit": 10})
        assert result["success"] is True
        assert "digests" in result["data"]

    @patch("core.mesh.gossip.get_node_identity")
    @patch("core.mesh.gossip.get_mesh_transport")
    @patch("core.mesh.gossip.get_memory_manager")
    def test_handle_memory_get_not_found(self, mock_mm, mock_transport, mock_identity):
        from core.mesh.gossip import GossipProtocol
        mi = MagicMock()
        mi.kni = "self_node"
        mock_identity.return_value = mi
        mock_transport.return_value = MagicMock()

        mm = MagicMock()
        mm.read.return_value = None
        mock_mm.return_value = mm

        gossip = GossipProtocol()
        result = gossip.handle_memory_get({"layer": "L2", "key": "missing", "user_id": "anon"})
        assert result["success"] is False


class TestMeshAPIRoutes:
    def test_mesh_peers_endpoint(self):
        from tests.test_base import FlaskAppTestBase
        # Use a minimal app test
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("api.routes.mesh.get_node_identity") as mock_ni, \
             patch("api.routes.mesh.get_mesh_transport") as mock_tr, \
             patch("api.routes.mesh.get_discovery_service") as mock_dc:
            mock_ni.return_value = MagicMock(kni="test", display_name="Test")
            mock_tr.return_value = MagicMock(list_sessions=lambda: [])
            mock_dc.return_value = MagicMock(get_peers=lambda: [])

            resp = client.get("/api/mesh/peers")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert "self" in data["data"]

    def test_mesh_handshake_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("api.routes.mesh.get_mesh_transport") as mock_tr:
            transport = MagicMock()
            transport.handle_handshake.return_value = {"success": True, "kni": "peer"}
            mock_tr.return_value = transport

            resp = client.post("/api/mesh/handshake", json={"kni": "peer", "challenge": "c"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True

    def test_mesh_heartbeat_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("api.routes.mesh.get_mesh_transport") as mock_tr:
            transport = MagicMock()
            transport.handle_heartbeat.return_value = {"success": True}
            mock_tr.return_value = transport

            resp = client.post("/api/mesh/heartbeat", json={"kni": "peer"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True

    def test_mesh_invoke_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("api.routes.mesh.get_mesh_transport") as mock_tr:
            transport = MagicMock()
            transport.handle_invoke.return_value = {"success": True, "result": {"status": "ok"}}
            mock_tr.return_value = transport

            resp = client.post(
                "/api/mesh/invoke",
                json={"kni": "peer1", "tool_name": "test_tool", "params": {"x": 1}},
                headers={"Authorization": "Bearer test_token"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True

    def test_mesh_memory_digests_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("api.routes.mesh.get_gossip_protocol") as mock_gossip:
            gossip = MagicMock()
            gossip.handle_digests_request.return_value = {"success": True, "data": {"digests": []}}
            mock_gossip.return_value = gossip

            resp = client.post("/api/mesh/memory/digests", json={"since": 0, "limit": 10})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert "digests" in data["data"]

    def test_mesh_memory_get_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("api.routes.mesh.get_gossip_protocol") as mock_gossip:
            gossip = MagicMock()
            gossip.handle_memory_get.return_value = {"success": True, "data": {"memory": {"key": "test"}}}
            mock_gossip.return_value = gossip

            resp = client.post("/api/mesh/memory/get", json={"layer": "L2", "key": "test", "user_id": "anon"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True

    def test_mesh_sync_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("api.routes.mesh.get_gossip_protocol") as mock_gossip:
            gossip = MagicMock()
            gossip.sync_with_peer.return_value = {"success": True, "pulled": 3}
            mock_gossip.return_value = gossip

            resp = client.post("/api/mesh/sync", json={"target_kni": "peer1"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True

    def test_mesh_auth_request_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("api.routes.mesh.get_node_identity") as mock_ni, \
             patch("core.memory_manager_v2.get_memory_manager") as mock_mm:
            mock_ni.return_value = MagicMock(kni="self_node")
            mm = MagicMock()
            mm.read.return_value = None
            mock_mm.return_value = mm

            resp = client.post("/api/mesh/auth/request", json={
                "request_id": "req_001",
                "requester_kni": "peer1",
                "resource_type": "memory",
                "actions": ["read"],
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["request_id"] == "req_001"

    def test_mesh_auth_pending_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("core.memory_manager_v2.get_memory_manager") as mock_mm:
            mm = MagicMock()
            mm.read.return_value = {
                "value": [
                    {"id": "req_001", "status": "pending", "requester_kni": "peer1"},
                    {"id": "req_002", "status": "granted", "requester_kni": "peer2"},
                ]
            }
            mock_mm.return_value = mm

            resp = client.get("/api/mesh/auth/pending")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert len(data["data"]["requests"]) == 1

    def test_mesh_auth_approve_endpoint(self):
        from flask import Flask
        from api.routes.mesh import mesh_bp
        app = Flask(__name__)
        app.register_blueprint(mesh_bp)
        client = app.test_client()

        with patch("core.memory_manager_v2.get_memory_manager") as mock_mm, \
             patch("api.routes.mesh.get_authorization_manager") as mock_auth, \
             patch("api.routes.mesh.get_node_identity") as mock_ni:
            mock_ni.return_value = MagicMock(kni="self_node")
            mm = MagicMock()
            mm.read.return_value = {
                "value": [
                    {"id": "req_001", "status": "pending", "requester_kni": "peer1", "resource_type": "memory", "actions": ["read"]},
                ]
            }
            mock_mm.return_value = mm

            auth = MagicMock()
            auth.grant_permission.return_value = "perm_001"
            auth.create_token.return_value = "token_001"
            mock_auth.return_value = auth

            resp = client.post("/api/mesh/auth/approve", json={
                "request_id": "req_001",
                "approved_actions": ["read", "write"],
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["permission_id"] == "perm_001"
            assert data["token"] == "token_001"


class TestMeshAuthorization:
    @patch("core.mesh.authorization.get_node_identity")
    @patch("core.mesh.transport.get_mesh_transport")
    def test_verify_local_token(self, mock_transport, mock_identity):
        from core.mesh.authorization import AuthorizationManager
        from core.mesh.identity import NodeIdentity

        ni = NodeIdentity()
        mock_identity.return_value = ni

        auth = AuthorizationManager()
        token = auth.create_token(
            issuer_kni=ni.kni,
            subject_kni="peer1",
            permissions=[{"resource_type": "memory", "resource_id": "L1", "actions": ["read"]}],
            ttl_hours=1,
        )
        payload = auth.verify_token(token)
        assert payload is not None
        assert payload["iss"] == ni.kni

    @patch("core.mesh.authorization.get_node_identity")
    @patch("core.mesh.transport.get_mesh_transport")
    def test_verify_remote_token(self, mock_transport, mock_identity):
        """Test verifying a token from a remote peer using cached public key."""
        from core.mesh.authorization import AuthorizationManager
        from core.mesh.identity import NodeIdentity
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        import jwt

        # Create a real remote key pair
        remote_key = Ed25519PrivateKey.generate()
        remote_pub = remote_key.public_key()
        remote_pub_hex = remote_pub.public_bytes_raw().hex()

        # Self identity
        self_ni = NodeIdentity()
        mock_identity.return_value = self_ni

        # Mock transport session with remote peer's public key
        sess = MagicMock()
        sess.public_key_hex = remote_pub_hex
        transport = MagicMock()
        transport.get_session.return_value = sess
        mock_transport.return_value = transport

        auth = AuthorizationManager()

        # Create a token signed by the remote peer
        from datetime import datetime, timezone, timedelta
        token = jwt.encode(
            {
                "iss": "remote_peer",
                "sub": self_ni.kni,
                "permissions": [{"resource_type": "mcp_tool", "resource_id": "*", "actions": ["execute"]}],
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            key=remote_key,
            algorithm="EdDSA",
        )

        payload = auth.verify_token(token)
        assert payload is not None
        assert payload["iss"] == "remote_peer"

    @patch("core.mesh.authorization.get_node_identity")
    @patch("core.mesh.transport.get_mesh_transport")
    def test_verify_remote_token_no_session(self, mock_transport, mock_identity):
        """Test that remote token fails when no session cached."""
        from core.mesh.authorization import AuthorizationManager
        from core.mesh.identity import NodeIdentity

        self_ni = NodeIdentity()
        mock_identity.return_value = self_ni

        transport = MagicMock()
        transport.get_session.return_value = None
        mock_transport.return_value = transport

        auth = AuthorizationManager()
        # A dummy token with remote issuer — signature won't match but unverified decode works
        import jwt
        dummy_token = jwt.encode(
            {"iss": "remote_peer", "sub": self_ni.kni, "iat": 0},
            key=self_ni._private_key,
            algorithm="EdDSA",
        )
        payload = auth.verify_token(dummy_token)
        assert payload is None


class TestMeshScheduler:
    @patch("core.mesh.transport.get_mesh_transport")
    @patch("core.mesh.gossip.get_gossip_protocol")
    def test_scheduler_start_stop(self, mock_gossip, mock_transport):
        from core.mesh.scheduler import MeshScheduler
        scheduler = MeshScheduler()
        assert not scheduler.is_running()

        scheduler.start()
        assert scheduler.is_running()

        scheduler.stop()
        assert not scheduler.is_running()

    @patch("core.mesh.transport.get_mesh_transport")
    @patch("core.mesh.gossip.get_gossip_protocol")
    def test_scheduler_status(self, mock_gossip, mock_transport):
        from core.mesh.scheduler import MeshScheduler
        transport = MagicMock()
        transport.list_sessions.return_value = [
            {"kni": "p1", "status": "active"},
            {"kni": "p2", "status": "stale"},
        ]
        mock_transport.return_value = transport

        scheduler = MeshScheduler()
        status = scheduler.get_status()
        assert status["peers_total"] == 2
        assert status["peers_active"] == 1
        assert status["running"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
