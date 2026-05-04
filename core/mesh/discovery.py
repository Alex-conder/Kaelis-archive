"""
Kaelis Mesh Discovery
=====================
基于 mDNS (zeroconf) 的本地网络节点发现。

用法:
    from core.mesh.discovery import KaelisDiscovery, get_discovery_service
    disc = get_discovery_service()
    disc.start(port=8765)
    nodes = disc.discover(duration=5)
    disc.stop()
"""

import json
import logging
import time
from typing import Dict, List, Optional

# zeroconf 采用延迟导入，避免 Windows 上网络初始化阻塞启动
def _zeroconf_available() -> bool:
    try:
        from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf, IPVersion  # noqa: F401
        return True
    except ImportError:
        return False
    Zeroconf = None
    IPVersion = None

from core.mesh.identity import get_node_identity

logger = logging.getLogger(__name__)

# ============================================================================
# Config
# ============================================================================

SERVICE_TYPE = "_kaelis._tcp.local."
SERVICE_NAME_PREFIX = "Kaelis Node "
CACHE_TTL_SECONDS = 60


# ============================================================================
# Discovery Service
# ============================================================================

class KaelisDiscovery:
    """
    Kaelis 本地网络发现服务。

    - 通过 mDNS 广播自身存在
    - 扫描网络发现其他 Kaelis 节点
    - 缓存发现结果（60 秒有效期）
    """

    def __init__(self):
        self._zeroconf: Optional[Zeroconf] = None
        self._browser: Optional[ServiceBrowser] = None
        self._service_info: Optional[ServiceInfo] = None
        self._registered = False

        # 发现的节点缓存: {kni: {host, port, display_name, capabilities, discovered_at}}
        self._peers: Dict[str, Dict] = {}
        self._listener = _KaelisServiceListener(self)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self, port: int = 8765) -> bool:
        """注册 mDNS 服务，广播自身存在。"""
        if not ZEROCONF_AVAILABLE:
            logger.error("zeroconf not installed, cannot start discovery")
            return False
        if self._registered:
            logger.warning("Discovery already started")
            return True

        try:
            ni = get_node_identity()
            self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

            # 构建服务元数据
            props = {
                b"kni": ni.kni.encode("utf-8"),
                b"display_name": ni.display_name.encode("utf-8"),
                b"capabilities": json.dumps(ni.capabilities).encode("utf-8"),
                b"version": ni.version.encode("utf-8"),
            }

            service_name = f"{SERVICE_NAME_PREFIX}{ni.kni}.{SERVICE_TYPE}"
            self._service_info = ServiceInfo(
                type_=SERVICE_TYPE,
                name=service_name,
                port=port,
                properties=props,
                server=f"{ni.kni}.local.",
            )

            self._zeroconf.register_service(self._service_info)
            self._registered = True

            # 启动浏览器扫描其他节点
            self._browser = ServiceBrowser(self._zeroconf, SERVICE_TYPE, self._listener)

            logger.info("mDNS discovery started on port %d, KNI=%s", port, ni.kni)
            return True

        except Exception as e:
            logger.error("Failed to start discovery: %s", e)
            return False

    def stop(self):
        """停止 mDNS 广播和扫描。"""
        if self._browser:
            self._browser.cancel()
            self._browser = None

        if self._zeroconf:
            if self._service_info and self._registered:
                try:
                    self._zeroconf.unregister_service(self._service_info)
                except Exception as e:
                    logger.warning("Unregister service failed: %s", e)
            self._zeroconf.close()
            self._zeroconf = None

        self._registered = False
        logger.info("mDNS discovery stopped")

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    def discover(self, duration: float = 5.0) -> List[Dict]:
        """
        扫描本地网络，返回发现的节点列表。

        注意：如果 start() 后已经运行了一段时间，_peers 中已有缓存。
        此方法会等待额外 duration 秒收集新节点。
        """
        if not self._zeroconf:
            logger.warning("Discovery not started, starting temporarily...")
            self.start()

        # 清理过期缓存
        self._prune_cache()

        # 等待新节点加入
        if duration > 0:
            time.sleep(duration)
            self._prune_cache()

        return [
            {
                "kni": kni,
                "display_name": info.get("display_name", "Unknown"),
                "host": info.get("host", ""),
                "port": info.get("port", 0),
                "capabilities": info.get("capabilities", []),
                "discovered_at": info.get("discovered_at", 0),
            }
            for kni, info in self._peers.items()
        ]

    def get_peers(self) -> List[Dict]:
        """获取当前缓存的所有已知节点（不等待）。"""
        self._prune_cache()
        return self.discover(duration=0)

    def _prune_cache(self):
        """移除超过 TTL 的缓存条目。"""
        now = time.time()
        expired = [
            kni for kni, info in self._peers.items()
            if now - info.get("discovered_at", 0) > CACHE_TTL_SECONDS
        ]
        for kni in expired:
            del self._peers[kni]
            logger.info("Peer cache expired: %s", kni)

    # ------------------------------------------------------------------ #
    # Internal callbacks
    # ------------------------------------------------------------------ #

    def _on_service_added(self, name: str, info: ServiceInfo):
        """mDNS 发现新服务时的回调。"""
        try:
            props = info.properties
            kni = props.get(b"kni", b"").decode("utf-8")
            if not kni:
                return

            # 跳过自己
            my_kni = get_node_identity().kni
            if kni == my_kni:
                return

            display_name = props.get(b"display_name", b"Unknown").decode("utf-8")
            capabilities = []
            cap_raw = props.get(b"capabilities", b"[]")
            if cap_raw:
                capabilities = json.loads(cap_raw.decode("utf-8"))

            # 获取 IP 地址
            host = ""
            if info.parsed_addresses(IPVersion.V4Only):
                host = info.parsed_addresses(IPVersion.V4Only)[0]
            elif info.parsed_addresses():
                host = info.parsed_addresses()[0]

            self._peers[kni] = {
                "kni": kni,
                "display_name": display_name,
                "host": host,
                "port": info.port,
                "capabilities": capabilities,
                "discovered_at": time.time(),
            }
            logger.info("Discovered peer: %s@%s:%d (%s)", kni, host, info.port, display_name)

            # Auto-register with mesh transport for handshake
            try:
                from core.mesh.transport import get_mesh_transport
                transport = get_mesh_transport()
                transport.register_peer(kni, host, info.port, capabilities)
            except Exception as e:
                logger.debug("Auto-register peer to transport failed: %s", e)

        except Exception as e:
            logger.warning("Failed to parse service info: %s", e)

    def _on_service_removed(self, name: str):
        """mDNS 服务消失时的回调。"""
        # 暂不主动移除，等待 TTL 过期
        logger.info("Service removed: %s", name)


# ============================================================================
# Zeroconf Listener
# ============================================================================

class _KaelisServiceListener:
    """内部 mDNS 服务监听器。"""

    def __init__(self, discovery: KaelisDiscovery):
        self.discovery = discovery

    def add_service(self, zc: Zeroconf, type_: str, name: str):
        info = zc.get_service_info(type_, name)
        if info:
            self.discovery._on_service_added(name, info)

    def remove_service(self, zc: Zeroconf, type_: str, name: str):
        self.discovery._on_service_removed(name)

    def update_service(self, zc: Zeroconf, type_: str, name: str):
        info = zc.get_service_info(type_, name)
        if info:
            self.discovery._on_service_added(name, info)


# ============================================================================
# Singleton
# ============================================================================

_DiscoveryInstance: Optional[KaelisDiscovery] = None


def get_discovery_service() -> KaelisDiscovery:
    """获取全局发现服务单例。"""
    global _DiscoveryInstance
    if _DiscoveryInstance is None:
        _DiscoveryInstance = KaelisDiscovery()
    return _DiscoveryInstance


def reset_discovery_instance():
    """测试用：重置单例。"""
    global _DiscoveryInstance
    if _DiscoveryInstance:
        _DiscoveryInstance.stop()
    _DiscoveryInstance = None


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kaelis Mesh Discovery")
    parser.add_argument("--start", action="store_true", help="Start broadcasting")
    parser.add_argument("--discover", action="store_true", help="Scan for peers")
    parser.add_argument("--duration", type=int, default=5, help="Discovery duration (seconds)")
    parser.add_argument("--port", type=int, default=8765, help="Service port")
    args = parser.parse_args()

    disc = get_discovery_service()

    if args.start or args.discover:
        disc.start(port=args.port)
        try:
            if args.discover:
                peers = disc.discover(duration=args.duration)
                print(f"\nDiscovered {len(peers)} peer(s):")
                for p in peers:
                    print(f"  - {p['kni']} @ {p['host']}:{p['port']} ({p['display_name']})")
                    print(f"    Capabilities: {p['capabilities']}")
            else:
                print(f"Broadcasting on port {args.port}... Press Ctrl+C to stop")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            disc.stop()
    else:
        print("Usage: python discovery.py --start | --discover")
