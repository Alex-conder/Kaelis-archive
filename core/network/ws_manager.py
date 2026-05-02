"""
WebSocket Connection Manager — Cross-device message hub.

Manages persistent WebSocket connections per device, enabling
real-time bidirectional messaging across a user's devices.
"""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class WSDeviceConnection:
    """Represents an active WebSocket connection from a device."""
    device_id: str
    user_id: str
    websocket: Any  # async websocket object (e.g., websockets.WebSocketServerProtocol)
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    capabilities: List[str] = field(default_factory=list)
    platform: str = ""  # electron, browser, vscode, mobile


class WSConnectionManager:
    """
    Central registry for all WebSocket device connections.

    - Maps user_id -> {device_id -> WSDeviceConnection}
    - Supports broadcast, unicast, and user-wide multicast
    - Automatic heartbeat tracking and stale connection pruning
    """

    def __init__(self):
        # user_id -> {device_id: WSDeviceConnection}
        self._connections: Dict[str, Dict[str, WSDeviceConnection]] = {}
        # device_id -> user_id (reverse lookup)
        self._device_to_user: Dict[str, str] = {}
        self._message_handlers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def register(self, device_id: str, websocket: Any, user_id: str,
                 platform: str = "", capabilities: Optional[List[str]] = None) -> WSDeviceConnection:
        """Register a new device WebSocket connection."""
        conn = WSDeviceConnection(
            device_id=device_id,
            user_id=user_id,
            websocket=websocket,
            platform=platform,
            capabilities=capabilities or [],
        )

        with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = {}

            # Close existing connection from same device (reconnect)
            if device_id in self._connections[user_id]:
                old = self._connections[user_id][device_id]
                logger.info("Replacing existing connection for device %s", device_id)
                self._safe_close(old.websocket)

            self._connections[user_id][device_id] = conn
            self._device_to_user[device_id] = user_id

        logger.info("Registered device %s for user %s (platform=%s)", device_id, user_id, platform)
        return conn

    def unregister(self, device_id: str) -> Optional[str]:
        """
        Unregister a device connection. Returns user_id if found.
        Triggers offline notification to paired devices.
        """
        with self._lock:
            user_id = self._device_to_user.pop(device_id, None)
            if not user_id:
                return None

            user_conns = self._connections.get(user_id, {})
            conn = user_conns.pop(device_id, None)
            if conn:
                self._safe_close(conn.websocket)

            if not user_conns:
                self._connections.pop(user_id, None)

        logger.info("Unregistered device %s for user %s", device_id, user_id)

        # Notify other devices of this device going offline
        self._notify_peer_offline(user_id, device_id)
        return user_id

    def _safe_close(self, websocket: Any):
        """Safely close a websocket without raising."""
        try:
            if hasattr(websocket, 'close'):
                import asyncio, inspect
                if inspect.iscoroutinefunction(websocket.close):
                    asyncio.create_task(websocket.close())
                else:
                    websocket.close()
        except Exception as e:
            logger.debug("Error closing websocket: %s", e)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_user_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """Return list of online devices for a user."""
        with self._lock:
            devices = []
            for device_id, conn in self._connections.get(user_id, {}).items():
                devices.append({
                    "device_id": device_id,
                    "platform": conn.platform,
                    "capabilities": conn.capabilities,
                    "connected_at": conn.connected_at,
                    "last_ping": conn.last_ping,
                })
            return devices

    def get_device(self, device_id: str) -> Optional[WSDeviceConnection]:
        """Get a specific device connection."""
        with self._lock:
            user_id = self._device_to_user.get(device_id)
            if not user_id:
                return None
            return self._connections.get(user_id, {}).get(device_id)

    def is_device_online(self, device_id: str) -> bool:
        return device_id in self._device_to_user

    def get_all_online_users(self) -> List[str]:
        return list(self._connections.keys())

    # ------------------------------------------------------------------ #
    # Messaging
    # ------------------------------------------------------------------ #

    async def send_to_device(self, device_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific device."""
        conn = self.get_device(device_id)
        if not conn:
            return False
        try:
            payload = json.dumps(message, default=str)
            if hasattr(conn.websocket, 'send'):
                import inspect
                if inspect.iscoroutinefunction(conn.websocket.send):
                    await conn.websocket.send(payload)
                else:
                    conn.websocket.send(payload)
            return True
        except Exception as e:
            logger.warning("Failed to send to device %s: %s", device_id, e)
            return False

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any],
                                exclude_device: Optional[str] = None) -> Dict[str, bool]:
        """Broadcast a message to all online devices of a user."""
        with self._lock:
            devices = list(self._connections.get(user_id, {}).items())
        results = {}
        for device_id, conn in devices:
            if exclude_device and device_id == exclude_device:
                continue
            results[device_id] = await self.send_to_device(device_id, message)
        return results

    async def broadcast_to_all(self, message: Dict[str, Any]) -> Dict[str, Dict[str, bool]]:
        """Broadcast to all connected devices (admin/system use)."""
        with self._lock:
            users = list(self._connections.keys())
        results = {}
        for user_id in users:
            results[user_id] = await self.broadcast_to_user(user_id, message)
        return results

    # ------------------------------------------------------------------ #
    # Heartbeat & Pruning
    # ------------------------------------------------------------------ #

    def update_ping(self, device_id: str):
        """Update last ping time for a device."""
        with self._lock:
            user_id = self._device_to_user.get(device_id)
            if not user_id:
                return
            conn = self._connections.get(user_id, {}).get(device_id)
            if conn:
                conn.last_ping = time.time()

    def prune_stale(self, timeout: float = 120.0) -> List[str]:
        """Remove connections that haven't pinged within timeout seconds."""
        now = time.time()
        stale = []
        with self._lock:
            for user_id, devices in list(self._connections.items()):
                for device_id, conn in list(devices.items()):
                    if now - conn.last_ping > timeout:
                        stale.append(device_id)
                        # unregister modifies _lock internally, call outside lock to avoid deadlock
        for device_id in stale:
            self.unregister(device_id)
        if stale:
            logger.info("Pruned %d stale connections: %s", len(stale), stale)
        return stale

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _notify_peer_offline(self, user_id: str, offline_device_id: str):
        """Notify other devices of a peer going offline."""
        import asyncio, inspect
        message = {
            "msg_id": str(uuid.uuid4()),
            "type": "peer_offline",
            "payload": {"device_id": offline_device_id},
            "timestamp": time.time(),
        }
        # Fire-and-forget async broadcast
        for device_id, conn in list(self._connections.get(user_id, {}).items()):
            if device_id != offline_device_id:
                try:
                    if hasattr(conn.websocket, 'send'):
                        payload = json.dumps(message, default=str)
                        if inspect.iscoroutinefunction(conn.websocket.send):
                            asyncio.create_task(conn.websocket.send(payload))
                        else:
                            conn.websocket.send(payload)
                except Exception:
                    pass


# ============================================================================
# Singleton
# ============================================================================

_WsManagerInstance: Optional[WSConnectionManager] = None


def get_ws_manager() -> WSConnectionManager:
    global _WsManagerInstance
    if _WsManagerInstance is None:
        _WsManagerInstance = WSConnectionManager()
    return _WsManagerInstance
