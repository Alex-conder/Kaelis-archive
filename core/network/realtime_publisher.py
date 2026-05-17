"""
Realtime Publisher — Synchronous bridge from Flask to the async WebSocket layer.

Provides a thread-safe way for synchronous API routes to broadcast real-time
events to connected browser/Electron clients without blocking the HTTP thread.

Usage:
    from core.network.realtime_publisher import publish_event
    publish_event(user_id="alice", event_type="workflow_status", payload={...})
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from core.network.ws_manager import get_ws_manager
from core.network.ws_server import get_ws_server

logger = logging.getLogger(__name__)


def publish_event(
    user_id: str,
    event_type: str,
    payload: Dict[str, Any],
    exclude_device: Optional[str] = None,
) -> bool:
    """
    Publish a real-time event to all online devices of a user.

    This is a **synchronous** wrapper that safely submits the async broadcast
    to the WebSocket server's event loop via ``asyncio.run_coroutine_threadsafe``.

    Args:
        user_id: Target user identifier.
        event_type: Semantic event name (e.g. ``workflow_status``, ``memory_push``).
        payload: Arbitrary JSON-serializable payload.
        exclude_device: Optional device_id to skip (e.g. the sender).

    Returns:
        True if the task was successfully submitted to the event loop,
        False if the WS server is not running or has no loop.
    """
    ws_server = get_ws_server()
    loop = ws_server.get_loop()
    if loop is None or loop.is_closed():
        logger.debug("Realtime publish skipped: WS server loop not ready")
        return False

    ws_manager = get_ws_manager()
    message = {
        "type": event_type,
        "payload": payload,
    }

    try:
        coro = ws_manager.broadcast_to_user(user_id, message, exclude_device=exclude_device)
        asyncio.run_coroutine_threadsafe(coro, loop)
        return True
    except Exception as e:
        logger.warning("Realtime publish failed: %s", e)
        return False


def publish_to_all(
    event_type: str,
    payload: Dict[str, Any],
) -> bool:
    """
    Publish a real-time event to **all** connected users (admin/system use).
    """
    ws_server = get_ws_server()
    loop = ws_server.get_loop()
    if loop is None or loop.is_closed():
        logger.debug("Realtime broadcast skipped: WS server loop not ready")
        return False

    ws_manager = get_ws_manager()
    message = {
        "type": event_type,
        "payload": payload,
    }

    try:
        coro = ws_manager.broadcast_to_all(message)
        asyncio.run_coroutine_threadsafe(coro, loop)
        return True
    except Exception as e:
        logger.warning("Realtime broadcast failed: %s", e)
        return False
