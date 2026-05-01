"""
Mesh Background Scheduler
==========================
自动维护 Kaelis Mesh 网络连接：
- 定期心跳探测（默认 15s）
- 定期 Gossip 反熵同步（默认 30s）
- 定期 mDNS 发现（默认 5min）

用法:
    from core.mesh.scheduler import get_mesh_scheduler
    scheduler = get_mesh_scheduler()
    scheduler.start()
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15.0   # seconds
GOSSIP_INTERVAL = 30.0      # seconds
DISCOVER_INTERVAL = 300.0   # seconds


class MeshScheduler:
    """
    Mesh 网络后台维护调度器。

    使用 threading.Timer 实现轻量级周期性任务，
    避免引入额外依赖（如 APScheduler）。
    """

    def __init__(self):
        self._heartbeat_timer: Optional[threading.Timer] = None
        self._gossip_timer: Optional[threading.Timer] = None
        self._discover_timer: Optional[threading.Timer] = None
        self._running = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self):
        """启动所有定时任务。"""
        with self._lock:
            if self._running:
                return
            self._running = True

        logger.info("MeshScheduler starting (heartbeat=%.0fs, gossip=%.0fs, discover=%.0fs)",
                    HEARTBEAT_INTERVAL, GOSSIP_INTERVAL, DISCOVER_INTERVAL)
        self._schedule_heartbeat()
        self._schedule_gossip()
        self._schedule_discover()

    def stop(self):
        """停止所有定时任务。"""
        with self._lock:
            self._running = False
            for t in (self._heartbeat_timer, self._gossip_timer, self._discover_timer):
                if t:
                    t.cancel()
            self._heartbeat_timer = None
            self._gossip_timer = None
            self._discover_timer = None
        logger.info("MeshScheduler stopped")

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------ #
    # Heartbeat
    # ------------------------------------------------------------------ #

    def _schedule_heartbeat(self):
        if not self._running:
            return
        self._heartbeat_timer = threading.Timer(HEARTBEAT_INTERVAL, self._run_heartbeat)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _run_heartbeat(self):
        try:
            from core.mesh.transport import get_mesh_transport
            transport = get_mesh_transport()
            results = transport.heartbeat_all()
            success = sum(1 for v in results.values() if v)
            if results:
                logger.debug("Heartbeat round: %d/%d peers responded", success, len(results))
        except Exception as e:
            logger.debug("Heartbeat round failed: %s", e)
        finally:
            self._schedule_heartbeat()

    # ------------------------------------------------------------------ #
    # Gossip
    # ------------------------------------------------------------------ #

    def _schedule_gossip(self):
        if not self._running:
            return
        self._gossip_timer = threading.Timer(GOSSIP_INTERVAL, self._run_gossip)
        self._gossip_timer.daemon = True
        self._gossip_timer.start()

    def _run_gossip(self):
        try:
            from core.mesh.gossip import get_gossip_protocol
            gossip = get_gossip_protocol()
            result = gossip.gossip_round()
            if result.get("success"):
                peer_result = result.get("results", {})
                for kni, r in peer_result.items():
                    logger.info("Gossip sync with %s: pulled=%d", kni, r.get("pulled", 0))
            else:
                logger.debug("Gossip round: %s", result.get("error", "no active peers"))
        except Exception as e:
            logger.debug("Gossip round failed: %s", e)
        finally:
            self._schedule_gossip()

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    def _schedule_discover(self):
        if not self._running:
            return
        self._discover_timer = threading.Timer(DISCOVER_INTERVAL, self._run_discover)
        self._discover_timer.daemon = True
        self._discover_timer.start()

    def _run_discover(self):
        try:
            from core.mesh.discovery import get_discovery_service, ZEROCONF_AVAILABLE
            if not ZEROCONF_AVAILABLE:
                logger.debug("Discovery skipped: zeroconf not installed")
                return

            discovery = get_discovery_service()
            if not discovery._registered:
                discovery.start()

            peers = discovery.discover(duration=5)
            if peers:
                logger.info("Discovery round: %d peers found", len(peers))
                from core.mesh.transport import get_mesh_transport
                transport = get_mesh_transport()
                for p in peers:
                    kni = p.get("kni")
                    if kni:
                        transport.register_peer(
                            kni,
                            p.get("host", ""),
                            p.get("port", 8765),
                            p.get("capabilities", []),
                        )
                        # Auto-handshake if new peer
                        sess = transport.get_session(kni)
                        if sess and sess.status == "discovered":
                            transport.perform_handshake(kni)
            else:
                logger.debug("Discovery round: no new peers")
        except Exception as e:
            logger.debug("Discovery round failed: %s", e)
        finally:
            self._schedule_discover()

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def get_status(self) -> Dict[str, Any]:
        """返回调度器当前状态。"""
        from core.mesh.transport import get_mesh_transport
        from core.mesh.gossip import get_gossip_protocol

        transport = get_mesh_transport()
        gossip = get_gossip_protocol()

        peers = transport.list_sessions()
        active = [p for p in peers if p["status"] == "active"]

        return {
            "running": self._running,
            "peers_total": len(peers),
            "peers_active": len(active),
            "heartbeat_interval": HEARTBEAT_INTERVAL,
            "gossip_interval": GOSSIP_INTERVAL,
            "discover_interval": DISCOVER_INTERVAL,
        }


# ============================================================================
# Singleton
# ============================================================================

_SchedulerInstance: Optional[MeshScheduler] = None


def get_mesh_scheduler() -> MeshScheduler:
    global _SchedulerInstance
    if _SchedulerInstance is None:
        _SchedulerInstance = MeshScheduler()
    return _SchedulerInstance
