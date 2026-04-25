"""
Tests for core.mesh.identity
C1: test environment isolation via tmp_path + monkeypatch
C4: graceful degradation paths covered
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import base58
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolate_identity_keys(monkeypatch, tmp_path):
    """Redirect identity key file to tmp_path for every test in this module."""
    import core.mesh.identity as id_mod
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(id_mod, "KEYS_DIR", keys_dir)
    monkeypatch.setattr(id_mod, "IDENTITY_KEY_FILE", keys_dir / "node_identity.key")
    # Reset singleton
    id_mod.reset_identity_instance()
    yield
    id_mod.reset_identity_instance()


@pytest.fixture
def mock_memory_manager(monkeypatch):
    """Mock get_memory_manager to avoid real DB initialization."""
    mm = MagicMock()
    mm.read.return_value = None
    mm.write.return_value = True
    monkeypatch.setattr("core.mesh.identity.get_memory_manager", lambda: mm)
    return mm


@pytest.fixture
def fresh_identity(isolate_identity_keys, mock_memory_manager):
    """Return a fresh NodeIdentity instance."""
    from core.mesh.identity import NodeIdentity
    return NodeIdentity()


# ---------------------------------------------------------------------------
# Identity Creation / Loading
# ---------------------------------------------------------------------------

class TestNodeIdentityLifecycle:
    def test_create_new_identity(self, fresh_identity):
        """首次运行应创建新身份。"""
        ni = fresh_identity
        assert ni.kni is not None
        assert len(ni.kni) > 0
        assert ni.public_key_bytes is not None
        assert len(ni.public_key_bytes) == 32
        assert ni.display_name == "Kaelis Node"
        assert ni.capabilities == []

    def test_kni_format(self, fresh_identity):
        """KNI 应为 base58 编码字符串。"""
        kni = fresh_identity.kni
        decoded = base58.b58decode(kni)
        assert len(decoded) == 12

    def test_load_existing_identity(self, isolate_identity_keys, mock_memory_manager):
        """已有密钥文件时应加载而非重新创建。"""
        from core.mesh.identity import NodeIdentity, IDENTITY_KEY_FILE
        # 创建第一个身份
        ni1 = NodeIdentity()
        kni1 = ni1.kni
        pubkey1 = ni1.public_key_bytes
        # 重新实例化（单例已重置）
        from core.mesh.identity import reset_identity_instance
        reset_identity_instance()
        ni2 = NodeIdentity()
        assert ni2.kni == kni1
        assert ni2.public_key_bytes == pubkey1

    def test_key_file_permissions(self, fresh_identity):
        """密钥文件权限应为 0o600（Windows 上可能不生效，仅检查存在）。"""
        from core.mesh.identity import IDENTITY_KEY_FILE
        assert IDENTITY_KEY_FILE.exists()
        data = json.loads(IDENTITY_KEY_FILE.read_text(encoding="utf-8"))
        assert data["format"] == "ed25519+aes256gcm"
        assert "kni" in data
        assert "public_key" in data
        assert "encrypted_private_key" in data


# ---------------------------------------------------------------------------
# Crypto
# ---------------------------------------------------------------------------

class TestNodeIdentityCrypto:
    def test_sign_and_verify(self, fresh_identity):
        """签名和本地验证应成功。"""
        ni = fresh_identity
        msg = b"hello mesh"
        sig = ni.sign_message(msg)
        assert isinstance(sig, bytes)
        assert ni.verify_signature(msg, sig, ni.kni) is True

    def test_verify_signature_tampered(self, fresh_identity):
        """篡改签名后验证应失败。"""
        ni = fresh_identity
        msg = b"hello mesh"
        sig = ni.sign_message(msg)
        bad_sig = bytes(b ^ 0xFF for b in sig[:8]) + sig[8:]
        assert ni.verify_signature(msg, bad_sig, ni.kni) is False

    def test_verify_remote_kni_returns_false(self, fresh_identity):
        """远程 KNI 验证暂不支持，应返回 False (C4)。"""
        ni = fresh_identity
        msg = b"hello"
        sig = ni.sign_message(msg)
        assert ni.verify_signature(msg, sig, "remoteKni123") is False

    def test_sign_without_private_key_raises(self, fresh_identity):
        """私钥未加载时签名应抛异常。"""
        ni = fresh_identity
        ni._private_key = None
        with pytest.raises(RuntimeError):
            ni.sign_message(b"test")


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestNodeIdentityMetadata:
    def test_load_metadata_from_l0(self, isolate_identity_keys, monkeypatch):
        """应从 L0 加载元数据。"""
        mm = MagicMock()
        mm.read.return_value = {
            "value": {
                "display_name": "Test Node",
                "capabilities": ["memory", "skill"],
                "version": "2.0.0",
                "endpoint_url": "http://localhost:9999",
            }
        }
        monkeypatch.setattr("core.mesh.identity.get_memory_manager", lambda: mm)
        from core.mesh.identity import NodeIdentity, reset_identity_instance
        reset_identity_instance()
        ni = NodeIdentity()
        assert ni.display_name == "Test Node"
        assert ni.capabilities == ["memory", "skill"]
        assert ni.version == "2.0.0"
        assert ni.endpoint_url == "http://localhost:9999"

    def test_load_metadata_fallback_when_memory_fails(self, isolate_identity_keys, monkeypatch):
        """L0 加载失败时应使用默认值 (C4)。"""
        mm = MagicMock()
        mm.read.side_effect = RuntimeError("db unavailable")
        monkeypatch.setattr("core.mesh.identity.get_memory_manager", lambda: mm)
        from core.mesh.identity import NodeIdentity, reset_identity_instance
        reset_identity_instance()
        ni = NodeIdentity()
        assert ni.display_name == "Kaelis Node"
        assert ni.capabilities == []

    def test_save_metadata(self, fresh_identity, mock_memory_manager):
        """保存元数据应调用 memory_manager.write。"""
        ni = fresh_identity
        ni.display_name = "Updated"
        result = ni.save_metadata()
        assert result is True
        assert mock_memory_manager.write.called
        args = mock_memory_manager.write.call_args[1]
        assert args["layer"] == "L0"
        assert args["key"] == "node_identity"
        assert args["value"]["display_name"] == "Updated"

    def test_save_metadata_when_memory_raises(self, fresh_identity, monkeypatch):
        """保存失败时应返回 False (C4)。"""
        mm = MagicMock()
        mm.write.side_effect = RuntimeError("write failed")
        monkeypatch.setattr("core.mesh.identity.get_memory_manager", lambda: mm)
        ni = fresh_identity
        assert ni.save_metadata() is False

    def test_get_signed_metadata(self, fresh_identity):
        """get_signed_metadata 应包含有效签名。"""
        ni = fresh_identity
        ni.display_name = "Signed Node"
        signed = ni.get_signed_metadata()
        assert signed["kni"] == ni.kni
        assert signed["display_name"] == "Signed Node"
        assert "signature" in signed
        assert "public_key" in signed

    def test_verify_signed_metadata(self, fresh_identity):
        """verify_signed_metadata 应验证成功。"""
        ni = fresh_identity
        signed = ni.get_signed_metadata()
        assert ni.verify_signed_metadata(signed.copy()) is True

    def test_verify_signed_metadata_missing_fields(self, fresh_identity):
        """缺少签名或公钥时应返回 False (C4)。"""
        assert fresh_identity.verify_signed_metadata({}) is False
        assert fresh_identity.verify_signed_metadata({"signature": "abc"}) is False
        assert fresh_identity.verify_signed_metadata({"public_key": "abc"}) is False

    def test_verify_signed_metadata_tampered(self, fresh_identity):
        """篡改数据后验证应失败。"""
        signed = fresh_identity.get_signed_metadata()
        signed["display_name"] = "Evil"
        assert fresh_identity.verify_signed_metadata(signed.copy()) is False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestNodeIdentitySingleton:
    def test_get_node_identity_singleton(self, isolate_identity_keys, mock_memory_manager):
        """get_node_identity 应返回同一实例。"""
        from core.mesh.identity import get_node_identity, reset_identity_instance
        reset_identity_instance()
        a = get_node_identity()
        b = get_node_identity()
        assert a is b

    def test_reset_identity_instance(self, isolate_identity_keys, mock_memory_manager):
        """reset 后应创建新实例。"""
        from core.mesh.identity import get_node_identity, reset_identity_instance
        reset_identity_instance()
        a = get_node_identity()
        reset_identity_instance()
        b = get_node_identity()
        assert a is not b
