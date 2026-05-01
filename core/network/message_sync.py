"""
Message Sync Protocol — Unified cross-device messaging.

Defines standard message format and three sync modes:
1. Real-time push (online devices via WebSocket)
2. Pull mode (offline device comes back online → HTTP GET /api/messages/sync)
3. Conflict resolution (last-write-wins based on timestamp)

Supported message types:
- workflow_completed
- approval_required
- memory_push
- agent_status_change
- peer_online / peer_offline
- sync_request
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from core.network.ws_manager import get_ws_manager
from core.network.offline_queue import get_offline_queue
from core.network.message_encryptor import get_message_encryptor

logger = logging.getLogger(__name__)

SUPPORTED_MSG_TYPES = {
    "workflow_completed",
    "approval_required",
    "memory_push",
    "agent_status_change",
    "peer_online",
    "peer_offline",
    "sync_request",
    "auth_request",
    "auth_granted",
}


def build_message(
    msg_type: str,
    payload: Dict[str, Any],
    source_device: str,
    ttl: int = 86400,
) -> Dict[str, Any]:
    """Build a standardized cross-device message."""
    if msg_type not in SUPPORTED_MSG_TYPES:
        logger.warning("Unknown message type: %s", msg_type)

    return {
        "msg_id": str(uuid.uuid4()),
        "type": msg_type,
        "payload": payload,
        "timestamp": time.time(),
        "source_device": source_device,
        "ttl": ttl,
        "version": 1,
    }


class MessageSync:
    """
    High-level message synchronization orchestrator.

    Coordinates:
    - WSConnectionManager (real-time push)
    - OfflineMessageQueue (offline persistence)
    - MessageEncryptor (E2E encryption)
    """

    def __init__(self):
        self._ws = get_ws_manager()
        self._queue = get_offline_queue()
        self._encryptor = get_message_encryptor()

    # ------------------------------------------------------------------ #
    # Send (auto-routes: online → WS, offline → queue)
    # ------------------------------------------------------------------ #

    async def send_to_device(self, target_device_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a device.
        If online: WebSocket push (optionally encrypted).
        If offline: enqueue to offline queue.
        """
        # Try real-time push first
        if self._ws.is_device_online(target_device_id):
            envelope = message
            if self._encryptor.is_available():
                encrypted = self._encryptor.encrypt(message)
                if encrypted:
                    envelope = {
                        "encrypted": True,
                        **encrypted,
                    }
            success = await self._ws.send_to_device(target_device_id, envelope)
            if success:
                return True

        # Fallback: queue for later
        queued = self._queue.enqueue(target_device_id, message)
        if queued:
            logger.info("Message %s queued for offline device %s",
                        message.get("msg_id"), target_device_id)
        return queued

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any],
                                exclude_device: Optional[str] = None) -> Dict[str, bool]:
        """Broadcast to all user's devices. Offline ones get queued."""
        results = {}
        devices = self._ws.get_user_devices(user_id)
        device_ids = {d["device_id"] for d in devices}

        for device_id in list(device_ids):
            if exclude_device and device_id == exclude_device:
                continue
            results[device_id] = await self.send_to_device(device_id, message)

        return results

    # ------------------------------------------------------------------ #
    # Receive / Pull
    # ------------------------------------------------------------------ #

    def pull_for_device(self, device_id: str, since: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Pull queued messages for a device (called when device comes online).
        If `since` is provided, only return messages with timestamp > since.
        """
        messages = self._queue.dequeue_for_device(device_id)
        if since is not None:
            messages = [m for m in messages if m.get("timestamp", 0) > since]
        return messages

    async def handle_incoming(self, device_id: str, raw_message: Any) -> Optional[Dict[str, Any]]:
        """
        Handle an incoming raw message from a WebSocket.
        Decrypt if needed, validate, and return parsed message.
        """
        try:
            if isinstance(raw_message, str):
                data = json.loads(raw_message)
            else:
                data = raw_message

            # Decrypt if encrypted
            if data.get("encrypted"):
                decrypted = self._encryptor.decrypt(data)
                if decrypted:
                    data = decrypted
                else:
                    logger.warning("Failed to decrypt message from %s", device_id)
                    return None

            # Validate minimal structure
            if "type" not in data or "msg_id" not in data:
                logger.warning("Malformed message from %s: missing type/msg_id", device_id)
                return None

            return data
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from %s", device_id)
            return None
        except Exception as e:
            logger.warning("Error handling message from %s: %s", device_id, e)
            return None

    # ------------------------------------------------------------------ #
    # Conflict resolution
    # ------------------------------------------------------------------ #

    @staticmethod
    def resolve_conflict(local: Dict[str, Any], remote: Dict[str, Any]) -> Dict[str, Any]:
        """
        Last-write-wins conflict resolution.
        Compares timestamps; if equal, prefers remote.
        """
        local_ts = local.get("timestamp", 0)
        remote_ts = remote.get("timestamp", 0)
        if remote_ts >= local_ts:
            return remote
        return local

    # ------------------------------------------------------------------ #
    # Convenience senders
    # ------------------------------------------------------------------ #

    async def notify_workflow_completed(self, user_id: str, workflow_id: str,
                                        result: Dict[str, Any], source_device: str):
        msg = build_message("workflow_completed", {
            "workflow_id": workflow_id,
            "result": result,
        }, source_device)
        return await self.broadcast_to_user(user_id, msg, exclude_device=source_device)

    async def notify_approval_required(self, user_id: str, approval_id: str,
                                       details: Dict[str, Any], source_device: str):
        msg = build_message("approval_required", {
            "approval_id": approval_id,
            "details": details,
        }, source_device)
        return await self.broadcast_to_user(user_id, msg)

    async def push_memory(self, user_id: str, memory_key: str, layer: str,
                          value: Any, source_device: str):
        msg = build_message("memory_push", {
            "memory_key": memory_key,
            "layer": layer,
            "value": value,
        }, source_device)
        return await self.broadcast_to_user(user_id, msg, exclude_device=source_device)

    async def notify_agent_status(self, user_id: str, agent_id: str,
                                  status: str, source_device: str):
        msg = build_message("agent_status_change", {
            "agent_id": agent_id,
            "status": status,
        }, source_device)
        return await self.broadcast_to_user(user_id, msg, exclude_device=source_device)


# ============================================================================
# Singleton
# ============================================================================

_SyncInstance: Optional[MessageSync] = None


def get_message_sync() -> MessageSync:
    global _SyncInstance
    if _SyncInstance is None:
        _SyncInstance = MessageSync()
    return _SyncInstance
