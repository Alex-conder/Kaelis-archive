"""
Tests for core.mesh.authorization
C1: isolated via tmp_path; no real DB
C4: graceful degradation paths covered
"""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@pytest.fixture
def mock_identity(monkeypatch):
    """Mock get_node_identity with a real Ed25519 keypair for JWT."""
    import core.mesh.authorization as auth_mod
    import core.mesh.identity as id_mod

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    ni = MagicMock()
    ni.kni = "localkni"
    ni._private_key = private_key
    ni._public_key = public_key
    ni.public_key_bytes = public_key.public_bytes_raw()

    monkeypatch.setattr(auth_mod, "get_node_identity", lambda: ni)
    monkeypatch.setattr(id_mod, "get_node_identity", lambda: ni)
    return ni


@pytest.fixture
def mock_memory_manager(monkeypatch):
    """Mock memory manager for L0 operations."""
    mm = MagicMock()
    mm.read.return_value = None
    mm.write.return_value = True
    monkeypatch.setattr("core.mesh.authorization.get_memory_manager", lambda: mm)
    return mm


@pytest.fixture
def auth_manager(mock_identity, mock_memory_manager):
    """Fresh AuthorizationManager with mocked dependencies."""
    from core.mesh.authorization import AuthorizationManager
    return AuthorizationManager()


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

class TestJWT:
    def test_create_and_verify_token(self, auth_manager):
        """签发并验证 JWT。"""
        token = auth_manager.create_token(
            issuer_kni="localkni",
            subject_kni="peerkni",
            permissions=[{"resource_type": "memory", "resource_id": "L1", "actions": ["read"]}],
            ttl_hours=1,
        )
        assert isinstance(token, str)
        payload = auth_manager.verify_token(token)
        assert payload is not None
        assert payload["iss"] == "localkni"
        assert payload["sub"] == "peerkni"
        assert len(payload["permissions"]) == 1

    def test_create_token_wrong_issuer_raises(self, auth_manager):
        """非本节点 issuer 应抛 ValueError。"""
        with pytest.raises(ValueError, match="Only local node can issue tokens"):
            auth_manager.create_token(
                issuer_kni="otherkni",
                subject_kni="peerkni",
                permissions=[],
            )

    def test_verify_token_expired(self, auth_manager):
        """过期 token 应返回 None。"""
        token = auth_manager.create_token(
            issuer_kni="localkni",
            subject_kni="peerkni",
            permissions=[],
            ttl_hours=0,
        )
        # 等一秒确保过期
        time.sleep(1.1)
        assert auth_manager.verify_token(token) is None

    def test_verify_token_invalid_signature(self, auth_manager, mock_identity):
        """篡改 token 应返回 None。"""
        token = auth_manager.create_token(
            issuer_kni="localkni",
            subject_kni="peerkni",
            permissions=[],
            ttl_hours=1,
        )
        # 伪造一个用不同密钥签名的 token
        evil_key = Ed25519PrivateKey.generate()
        bad_token = jwt.encode({"iss": "localkni", "sub": "x"}, evil_key, algorithm="EdDSA")
        assert auth_manager.verify_token(bad_token) is None

    def test_verify_token_malformed(self, auth_manager):
        """格式错误的 token 应返回 None (C4)。"""
        assert auth_manager.verify_token("not.a.token") is None

    def test_verify_token_remote_issuer_returns_none(self, auth_manager, mock_identity, monkeypatch):
        """远程 issuer 的 token 暂不支持验证，应返回 None (C4)。"""
        # 用远程密钥签发
        remote_key = Ed25519PrivateKey.generate()
        token = jwt.encode(
            {"iss": "remotekni", "sub": "localkni", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            remote_key,
            algorithm="EdDSA",
        )
        assert auth_manager.verify_token(token) is None


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class TestPermissions:
    def test_grant_permission(self, auth_manager, mock_memory_manager):
        """授权应记录到 L0。"""
        perm_id = auth_manager.grant_permission(
            requester_kni="peerkni",
            resource_type="memory",
            resource_id="L1",
            actions=["read", "write"],
        )
        assert perm_id.startswith("perm_")
        assert mock_memory_manager.write.called
        args = mock_memory_manager.write.call_args[1]
        assert args["key"] == "mesh_permissions"
        assert len(args["value"]) == 1

    def test_revoke_permission(self, auth_manager, mock_memory_manager):
        """撤销权限应从列表移除。"""
        perm_id = auth_manager.grant_permission("peerkni", "memory", "L1", ["read"])
        mock_memory_manager.read.return_value = {
            "value": [
                {"id": perm_id, "requester_kni": "peerkni", "resource_type": "memory", "resource_id": "L1", "actions": ["read"]},
                {"id": "other", "requester_kni": "other", "resource_type": "skill", "resource_id": "S1", "actions": ["execute"]},
            ]
        }
        result = auth_manager.revoke_permission(perm_id)
        assert result is True
        # write should be called with filtered list
        written = mock_memory_manager.write.call_args[1]["value"]
        assert len(written) == 1
        assert written[0]["id"] == "other"

    def test_revoke_permission_not_found(self, auth_manager, mock_memory_manager):
        """撤销不存在的权限应返回 False (C4)。"""
        mock_memory_manager.read.return_value = {"value": []}
        assert auth_manager.revoke_permission("nosuch") is False

    def test_list_permissions(self, auth_manager, mock_memory_manager):
        """列出权限。"""
        mock_memory_manager.read.return_value = {
            "value": [
                {"id": "p1", "requester_kni": "peerkni", "resource_type": "memory", "resource_id": "L1", "actions": ["read"]},
                {"id": "p2", "requester_kni": "other", "resource_type": "skill", "resource_id": "S1", "actions": ["execute"]},
            ]
        }
        perms = auth_manager.list_permissions()
        assert len(perms) == 2
        filtered = auth_manager.list_permissions(requester_kni="peerkni")
        assert len(filtered) == 1
        assert filtered[0]["id"] == "p1"

    def test_list_permissions_empty(self, auth_manager, mock_memory_manager):
        """无权限时应返回空列表。"""
        mock_memory_manager.read.return_value = None
        assert auth_manager.list_permissions() == []

    def test_list_permissions_when_memory_raises(self, auth_manager, mock_memory_manager):
        """读取失败时应返回空列表 (C4)。"""
        mock_memory_manager.read.side_effect = RuntimeError("db down")
        assert auth_manager.list_permissions() == []

    def test_check_permission_granted(self, auth_manager, mock_memory_manager):
        """已授权的操作应返回 True。"""
        mock_memory_manager.read.return_value = {
            "value": [
                {"id": "p1", "requester_kni": "peerkni", "resource_type": "memory", "resource_id": "L1", "actions": ["read"]},
            ]
        }
        assert auth_manager.check_permission("peerkni", "memory", "L1", "read") is True

    def test_check_permission_denied(self, auth_manager, mock_memory_manager):
        """未授权的操作应返回 False。"""
        mock_memory_manager.read.return_value = {"value": []}
        assert auth_manager.check_permission("peerkni", "memory", "L1", "read") is False

    def test_revoke_permission_when_memory_raises(self, auth_manager, mock_memory_manager):
        """撤销时写入失败应返回 False (C4)。"""
        mock_memory_manager.read.return_value = {"value": [{"id": "x"}]}
        mock_memory_manager.write.side_effect = RuntimeError("write failed")
        assert auth_manager.revoke_permission("x") is False
