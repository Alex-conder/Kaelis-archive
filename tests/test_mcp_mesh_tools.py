"""
Tests for core.mcp.mesh_tools
C1: isolated; no real network or DB
C4: graceful degradation paths covered
"""

import json
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@pytest.fixture
def mock_mcp():
    """Return a mock MCP instance that collects registered tools."""
    registered = {}
    mcp = MagicMock()

    def mock_tool_decorator():
        def decorator(f):
            registered[f.__name__] = f
            return f
        return decorator

    mcp.tool = mock_tool_decorator
    return mcp, registered


@pytest.fixture
def mock_identity(monkeypatch):
    """Mock node identity with real Ed25519 keys."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    ni = MagicMock()
    ni.kni = "localkni"
    ni.display_name = "Local Node"
    ni.version = "1.0.0"
    ni.capabilities = ["memory"]
    ni._private_key = private_key
    ni._public_key = public_key
    monkeypatch.setattr("core.mcp.mesh_tools.get_node_identity", lambda: ni)
    return ni


@pytest.fixture
def mock_discovery(monkeypatch):
    """Mock discovery service."""
    disc = MagicMock()
    disc.get_peers.return_value = []
    monkeypatch.setattr("core.mcp.mesh_tools.get_discovery_service", lambda: disc)
    return disc


@pytest.fixture
def mock_auth(monkeypatch, mock_identity):
    """Mock authorization manager."""
    auth = MagicMock()
    auth.list_permissions.return_value = []
    auth.check_permission.return_value = True
    auth.grant_permission.return_value = "perm_123"
    auth.create_token.return_value = "mock.jwt.token"
    monkeypatch.setattr("core.mcp.mesh_tools.get_authorization_manager", lambda: auth)
    return auth


@pytest.fixture
def mock_memory(monkeypatch):
    """Mock memory manager for L0 operations."""
    mm = MagicMock()
    mm.read.return_value = None
    mm.write.return_value = True
    monkeypatch.setattr("core.memory_manager_v2.get_memory_manager", lambda: mm)
    return mm


@pytest.fixture
def mesh_tools(mock_mcp, mock_identity, mock_discovery, mock_auth, mock_memory):
    """Register mesh tools and return the registered functions dict."""
    from core.mcp.mesh_tools import register_mesh_tools
    mcp, registered = mock_mcp
    register_mesh_tools(mcp)
    return registered


# ---------------------------------------------------------------------------
# mesh_list_nodes
# ---------------------------------------------------------------------------

class TestMeshListNodes:
    def test_list_nodes_empty(self, mesh_tools, mock_identity):
        result = mesh_tools["mesh_list_nodes"]()
        data = json.loads(result)
        assert data["success"] is True
        assert data["count"] == 0
        assert data["self"]["kni"] == "localkni"

    def test_list_nodes_with_peers(self, mesh_tools, mock_discovery):
        mock_discovery.get_peers.return_value = [
            {"kni": "peer1", "display_name": "Peer One", "host": "10.0.0.1", "port": 1234, "capabilities": ["skill"]},
        ]
        result = mesh_tools["mesh_list_nodes"]()
        data = json.loads(result)
        assert data["count"] == 1
        assert data["nodes"][0]["kni"] == "peer1"
        assert data["nodes"][0]["status"] == "discovered"

    def test_list_nodes_with_authorized_only(self, mesh_tools, mock_auth):
        mock_auth.list_permissions.return_value = [
            {"requester_kni": "peer2", "resource_type": "memory", "resource_id": "L1", "actions": ["read"]},
        ]
        result = mesh_tools["mesh_list_nodes"]()
        data = json.loads(result)
        assert data["count"] == 1
        assert data["nodes"][0]["status"] == "authorized_only"

    def test_list_nodes_when_discovery_raises(self, mesh_tools, mock_discovery):
        """discovery 异常时应返回错误 JSON (C4)。"""
        mock_discovery.get_peers.side_effect = RuntimeError("discovery down")
        result = mesh_tools["mesh_list_nodes"]()
        data = json.loads(result)
        assert data["success"] is False
        assert "discovery down" in data["error"]


# ---------------------------------------------------------------------------
# mesh_request_access
# ---------------------------------------------------------------------------

class TestMeshRequestAccess:
    def test_request_access_success(self, mesh_tools, mock_memory, mock_identity):
        result = mesh_tools["mesh_request_access"](
            target_kni="peerkni",
            resource_type="memory",
            actions="read,write",
        )
        data = json.loads(result)
        assert data["success"] is True
        assert "request_id" in data
        assert "peerkni" in data["message"]
        # Verify it was written to L0
        assert mock_memory.write.called
        key = mock_memory.write.call_args[1]["key"]
        assert key == "mesh_pending_requests"

    def test_request_access_when_memory_raises(self, mesh_tools, mock_memory):
        """memory 异常时应返回错误 JSON (C4)。"""
        mock_memory.read.side_effect = RuntimeError("memory down")
        result = mesh_tools["mesh_request_access"](
            target_kni="peerkni",
            resource_type="memory",
            actions="read",
        )
        data = json.loads(result)
        assert data["success"] is False
        assert "memory down" in data["error"]


# ---------------------------------------------------------------------------
# mesh_grant_access
# ---------------------------------------------------------------------------

class TestMeshGrantAccess:
    def test_grant_access_success(self, mesh_tools, mock_memory, mock_auth):
        req_id = "req_localkni_peerkni_memory_12345"
        mock_memory.read.return_value = {
            "value": [
                {
                    "id": req_id,
                    "requester_kni": "peerkni",
                    "target_kni": "localkni",
                    "resource_type": "memory",
                    "actions": ["read"],
                    "status": "pending",
                }
            ]
        }
        result = mesh_tools["mesh_grant_access"](
            request_id=req_id,
            approved_actions="read",
        )
        data = json.loads(result)
        assert data["success"] is True
        assert data["permission_id"] == "perm_123"
        assert "token" in data
        assert mock_auth.grant_permission.called
        assert mock_auth.create_token.called

    def test_grant_access_request_not_found(self, mesh_tools, mock_memory):
        mock_memory.read.return_value = {"value": []}
        result = mesh_tools["mesh_grant_access"](
            request_id="nosuch",
            approved_actions="read",
        )
        data = json.loads(result)
        assert data["success"] is False
        assert "not found" in data["error"]

    def test_grant_access_when_memory_raises(self, mesh_tools, mock_memory):
        """memory 异常时应返回错误 JSON (C4)。"""
        mock_memory.read.side_effect = RuntimeError("memory down")
        result = mesh_tools["mesh_grant_access"](
            request_id="x",
            approved_actions="read",
        )
        data = json.loads(result)
        assert data["success"] is False
        assert "memory down" in data["error"]


# ---------------------------------------------------------------------------
# mesh_call_remote
# ---------------------------------------------------------------------------

class TestMeshCallRemote:
    def test_call_remote_success(self, mesh_tools, mock_discovery, mock_auth):
        mock_discovery.get_peers.return_value = [
            {"kni": "peerkni", "display_name": "Peer", "host": "10.0.0.2", "port": 5678, "capabilities": []},
        ]
        result = mesh_tools["mesh_call_remote"](
            target_kni="peerkni",
            tool_name="echo",
            params_json='{"msg": "hi"}',
        )
        data = json.loads(result)
        assert data["success"] is True
        assert data["target"]["kni"] == "peerkni"
        assert data["tool"] == "echo"
        assert data["params"]["msg"] == "hi"
        assert mock_auth.create_token.called

    def test_call_remote_no_permission(self, mesh_tools, mock_auth):
        mock_auth.check_permission.return_value = False
        result = mesh_tools["mesh_call_remote"](
            target_kni="peerkni",
            tool_name="echo",
            params_json="{}",
        )
        data = json.loads(result)
        assert data["success"] is False
        assert "No permission" in data["error"]

    def test_call_remote_node_not_found(self, mesh_tools, mock_discovery, mock_auth):
        mock_discovery.get_peers.return_value = []
        result = mesh_tools["mesh_call_remote"](
            target_kni="peerkni",
            tool_name="echo",
            params_json="{}",
        )
        data = json.loads(result)
        assert data["success"] is False
        assert "not found" in data["error"]

    def test_call_remote_when_discovery_raises(self, mesh_tools, mock_discovery, mock_auth):
        """discovery 异常时应返回错误 JSON (C4)。"""
        mock_discovery.get_peers.side_effect = RuntimeError("discovery down")
        result = mesh_tools["mesh_call_remote"](
            target_kni="peerkni",
            tool_name="echo",
            params_json="{}",
        )
        data = json.loads(result)
        assert data["success"] is False
        assert "discovery down" in data["error"]
