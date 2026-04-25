"""
Tests for core.mesh.discovery
C1: isolated via tmp_path; no real network I/O
C4: graceful degradation paths covered
"""

import json
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


@pytest.fixture(autouse=True)
def reset_discovery_and_identity(monkeypatch):
    """Reset singletons before/after each test."""
    import core.mesh.discovery as disc_mod
    import core.mesh.identity as id_mod
    id_mod.reset_identity_instance()
    disc_mod.reset_discovery_instance()
    yield
    disc_mod.reset_discovery_instance()
    id_mod.reset_identity_instance()


@pytest.fixture
def mock_node_identity(monkeypatch):
    """Mock get_node_identity to return a lightweight object."""
    import core.mesh.discovery as disc_mod
    ni = MagicMock()
    ni.kni = "testkni123"
    ni.display_name = "Test Node"
    ni.version = "1.0.0"
    ni.capabilities = ["memory", "skill"]
    monkeypatch.setattr(disc_mod, "get_node_identity", lambda: ni)
    # Also patch identity module used by listener callbacks
    import core.mesh.identity as id_mod
    monkeypatch.setattr(id_mod, "get_node_identity", lambda: ni)
    return ni


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestDiscoveryLifecycle:
    def test_start_stop(self, mock_node_identity, monkeypatch):
        """start/stop 应正确管理 Zeroconf 生命周期。"""
        from core.mesh.discovery import KaelisDiscovery
        mock_zc = MagicMock()
        mock_browser = MagicMock()
        mock_browser_cls = MagicMock(return_value=mock_browser)
        monkeypatch.setattr("core.mesh.discovery.Zeroconf", lambda **kw: mock_zc)
        monkeypatch.setattr("core.mesh.discovery.ServiceBrowser", mock_browser_cls)
        disc = KaelisDiscovery()
        assert disc.start(port=8765) is True
        assert disc._registered is True
        assert mock_zc.register_service.called
        assert mock_browser_cls.called
        disc.stop()
        assert disc._registered is False
        assert mock_zc.unregister_service.called
        assert mock_zc.close.called
        assert mock_browser.cancel.called

    def test_start_when_already_registered(self, mock_node_identity, monkeypatch):
        """重复 start 应返回 True 且不再注册。"""
        from core.mesh.discovery import KaelisDiscovery
        monkeypatch.setattr("core.mesh.discovery.Zeroconf", MagicMock)
        monkeypatch.setattr("core.mesh.discovery.ServiceBrowser", MagicMock)
        disc = KaelisDiscovery()
        disc.start(port=8765)
        assert disc.start(port=8765) is True
        disc.stop()

    def test_start_failure_returns_false(self, mock_node_identity, monkeypatch):
        """Zeroconf 异常时应返回 False (C4)。"""
        from core.mesh.discovery import KaelisDiscovery
        monkeypatch.setattr("core.mesh.discovery.Zeroconf", lambda **kw: (_ for _ in ()).throw(RuntimeError("no network")))
        disc = KaelisDiscovery()
        assert disc.start(port=8765) is False


# ---------------------------------------------------------------------------
# Peer Discovery
# ---------------------------------------------------------------------------

class TestPeerDiscovery:
    def test_discover_auto_start(self, mock_node_identity, monkeypatch):
        """未 start 时 discover 应自动 start。"""
        from core.mesh.discovery import KaelisDiscovery
        monkeypatch.setattr("core.mesh.discovery.Zeroconf", MagicMock)
        monkeypatch.setattr("core.mesh.discovery.ServiceBrowser", MagicMock)
        disc = KaelisDiscovery()
        # Patch time.sleep to avoid real wait
        monkeypatch.setattr("core.mesh.discovery.time.sleep", lambda x: None)
        peers = disc.discover(duration=0)
        assert disc._registered is True
        disc.stop()

    def test_get_peers_empty(self, mock_node_identity, monkeypatch):
        """无缓存节点时应返回空列表。"""
        from core.mesh.discovery import KaelisDiscovery
        monkeypatch.setattr("core.mesh.discovery.Zeroconf", MagicMock)
        monkeypatch.setattr("core.mesh.discovery.ServiceBrowser", MagicMock)
        disc = KaelisDiscovery()
        disc.start(port=8765)
        peers = disc.get_peers()
        assert peers == []
        disc.stop()

    def test_on_service_added(self, mock_node_identity, monkeypatch):
        """模拟发现新节点。"""
        from core.mesh.discovery import KaelisDiscovery
        disc = KaelisDiscovery()
        mock_info = MagicMock()
        mock_info.properties = {
            b"kni": b"peerkni456",
            b"display_name": b"Peer Node",
            b"capabilities": b'["space"]',
            b"version": b"1.0.0",
        }
        mock_info.port = 8888
        mock_info.parsed_addresses = MagicMock(return_value=["192.168.1.100"])
        disc._on_service_added("Peer", mock_info)
        assert "peerkni456" in disc._peers
        peer = disc._peers["peerkni456"]
        assert peer["display_name"] == "Peer Node"
        assert peer["host"] == "192.168.1.100"
        assert peer["port"] == 8888
        assert peer["capabilities"] == ["space"]

    def test_on_service_added_skip_self(self, mock_node_identity, monkeypatch):
        """发现自己的服务时应跳过。"""
        from core.mesh.discovery import KaelisDiscovery
        disc = KaelisDiscovery()
        mock_info = MagicMock()
        mock_info.properties = {b"kni": b"testkni123"}  # same as mock_node_identity
        disc._on_service_added("Self", mock_info)
        assert "testkni123" not in disc._peers

    def test_on_service_added_no_kni(self, mock_node_identity):
        """缺少 kni 时应忽略。"""
        from core.mesh.discovery import KaelisDiscovery
        disc = KaelisDiscovery()
        mock_info = MagicMock()
        mock_info.properties = {}
        disc._on_service_added("Bad", mock_info)
        assert disc._peers == {}

    def test_on_service_added_invalid_json(self, mock_node_identity):
        """capabilities JSON 解析失败时不应崩溃 (C4)。"""
        from core.mesh.discovery import KaelisDiscovery
        disc = KaelisDiscovery()
        mock_info = MagicMock()
        mock_info.properties = {
            b"kni": b"peerkni789",
            b"display_name": b"Peer",
            b"capabilities": b"not json",
        }
        mock_info.port = 1234
        type(mock_info).parsed_addresses = PropertyMock(return_value=[])
        # Should not raise
        disc._on_service_added("Peer", mock_info)
        # Peer might not be added due to JSON error in capabilities, but no crash
        # Actually the code catches Exception in _on_service_added, so no crash
        assert True

    def test_on_service_added_ipv6_fallback(self, mock_node_identity):
        """无 IPv4 时应回退到任何地址。"""
        from core.mesh.discovery import KaelisDiscovery, IPVersion
        disc = KaelisDiscovery()
        mock_info = MagicMock()
        mock_info.properties = {
            b"kni": b"peerkni999",
            b"display_name": b"Peer",
            b"capabilities": b"[]",
        }
        mock_info.port = 5678
        # First call (with V4Only) returns empty; subsequent calls return IPv6
        call_count = [0]
        def _parsed_addresses(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return []
            return ["fe80::1"]
        mock_info.parsed_addresses = MagicMock(side_effect=_parsed_addresses)
        disc._on_service_added("Peer", mock_info)
        assert disc._peers["peerkni999"]["host"] == "fe80::1"

    def test_on_service_removed(self, mock_node_identity):
        """服务移除回调不应崩溃。"""
        from core.mesh.discovery import KaelisDiscovery
        disc = KaelisDiscovery()
        disc._on_service_removed("SomeService")
        assert True


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class TestDiscoveryCache:
    def test_prune_cache(self, mock_node_identity):
        """过期缓存应被清理。"""
        from core.mesh.discovery import KaelisDiscovery, CACHE_TTL_SECONDS
        disc = KaelisDiscovery()
        disc._peers["old"] = {"discovered_at": time.time() - CACHE_TTL_SECONDS - 1}
        disc._peers["new"] = {"discovered_at": time.time()}
        disc._prune_cache()
        assert "old" not in disc._peers
        assert "new" in disc._peers

    def test_discover_returns_cached(self, mock_node_identity, monkeypatch):
        """discover 应返回缓存的节点。"""
        from core.mesh.discovery import KaelisDiscovery
        monkeypatch.setattr("core.mesh.discovery.time.sleep", lambda x: None)
        disc = KaelisDiscovery()
        disc._peers["peer1"] = {
            "kni": "peer1",
            "display_name": "P1",
            "host": "h1",
            "port": 1,
            "capabilities": [],
            "discovered_at": time.time(),
        }
        result = disc.discover(duration=0)
        assert len(result) == 1
        assert result[0]["kni"] == "peer1"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestDiscoverySingleton:
    def test_get_discovery_service_singleton(self, monkeypatch):
        from core.mesh.discovery import get_discovery_service, reset_discovery_instance
        reset_discovery_instance()
        a = get_discovery_service()
        b = get_discovery_service()
        assert a is b

    def test_reset_discovery_instance_stops_service(self, mock_node_identity, monkeypatch):
        from core.mesh.discovery import get_discovery_service, reset_discovery_instance
        monkeypatch.setattr("core.mesh.discovery.Zeroconf", MagicMock)
        monkeypatch.setattr("core.mesh.discovery.ServiceBrowser", MagicMock)
        reset_discovery_instance()
        disc = get_discovery_service()
        disc.start(port=8765)
        reset_discovery_instance()
        assert disc._registered is False
