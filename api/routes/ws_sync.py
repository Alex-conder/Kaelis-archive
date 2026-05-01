"""
WebSocket Sync REST API — HTTP fallback for cross-device messaging.

Provides:
- Device registration and discovery
- Message sending (HTTP → WebSocket or offline queue)
- Message pulling (for offline devices coming back online)
- Device pairing (LAN + manual)
"""

import logging
import time
from flask import Blueprint, jsonify, request

from core.network.ws_manager import get_ws_manager
from core.network.offline_queue import get_offline_queue
from core.network.message_sync import get_message_sync, build_message
from core.network.device_registry import get_device_registry

logger = logging.getLogger(__name__)

ws_sync_bp = Blueprint("ws_sync", __name__, url_prefix="/api/sync")


# --------------------------------------------------------------------------- #
# Device management
# --------------------------------------------------------------------------- #

@ws_sync_bp.route("/devices", methods=["GET"])
def list_devices():
    """List all online devices for the current user."""
    user_id = request.args.get("user_id", "anonymous")
    ws = get_ws_manager()
    devices = ws.get_user_devices(user_id)
    return jsonify({
        "success": True,
        "data": {"devices": devices, "count": len(devices)},
    })


@ws_sync_bp.route("/devices/register", methods=["POST"])
def register_device():
    """
    Register a device for push notification targeting.
    Called by clients that cannot maintain a persistent WebSocket (e.g., mobile PWA).
    """
    data = request.get_json() or {}
    device_id = data.get("device_id")
    user_id = data.get("user_id")
    platform = data.get("platform", "unknown")
    capabilities = data.get("capabilities", [])

    if not device_id or not user_id:
        return jsonify({"success": False, "error": "Missing device_id or user_id"}), 400

    registry = get_device_registry()
    profile = registry.get_or_create_profile(platform=platform, capabilities=capabilities)

    return jsonify({
        "success": True,
        "data": {
            "device_id": profile.device_id,
            "registered": True,
        },
    })


@ws_sync_bp.route("/devices/discover", methods=["GET"])
def discover_devices():
    """Discover nearby devices via LAN (mDNS)."""
    duration = request.args.get("duration", 5, type=int)
    registry = get_device_registry()
    discovered = registry.discover_lan_peers(duration=duration)
    paired = registry.get_paired_devices()
    paired_ids = {d.device_id for d in paired}

    return jsonify({
        "success": True,
        "data": {
            "discovered": [d for d in discovered if d["device_id"] not in paired_ids],
            "paired": [{"device_id": d.device_id, "display_name": d.display_name,
                        "platform": d.platform, "trusted": d.trusted} for d in paired],
        },
    })


@ws_sync_bp.route("/devices/pair", methods=["POST"])
def pair_device():
    """Manually pair with a device using a pairing code."""
    data = request.get_json() or {}
    device_id = data.get("device_id")
    display_name = data.get("display_name", "Unknown Device")
    platform = data.get("platform", "unknown")
    pairing_code = data.get("pairing_code", "")

    if not device_id:
        return jsonify({"success": False, "error": "Missing device_id"}), 400

    registry = get_device_registry()
    from core.network.device_registry import PairedDevice

    device = PairedDevice(
        device_id=device_id,
        pairing_code=pairing_code,
        display_name=display_name,
        platform=platform,
        trusted=True,
    )
    ok = registry.add_paired_device(device)
    return jsonify({"success": ok, "device_id": device_id})


@ws_sync_bp.route("/devices/unpair", methods=["POST"])
def unpair_device():
    """Remove a paired device."""
    data = request.get_json() or {}
    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"success": False, "error": "Missing device_id"}), 400

    registry = get_device_registry()
    ok = registry.remove_paired_device(device_id)
    return jsonify({"success": ok})


# --------------------------------------------------------------------------- #
# Messaging
# --------------------------------------------------------------------------- #

@ws_sync_bp.route("/messages/send", methods=["POST"])
def send_message():
    """
    Send a message to a device via HTTP.
    If target is online → WebSocket push.
    If offline → queued for later.
    """
    data = request.get_json() or {}
    target_device_id = data.get("target_device_id")
    msg_type = data.get("msg_type", "user_message")
    payload = data.get("payload", {})
    source_device = data.get("source_device", "unknown")
    ttl = data.get("ttl", 86400)
    encrypt_flag = data.get("encrypt", False)

    if not target_device_id:
        return jsonify({"success": False, "error": "Missing target_device_id"}), 400

    # Encrypt payload if requested
    if encrypt_flag:
        from core.network.message_encryptor import get_message_encryptor
        encryptor = get_message_encryptor()
        envelope = encryptor.encrypt(payload)
        if envelope:
            payload = {"__encrypted": True, **envelope}
        else:
            logger.warning("Encryption requested but not available, sending plaintext")

    msg = build_message(msg_type, payload, source_device, ttl)

    # Try sync push if target online
    ws = get_ws_manager()
    if ws.is_device_online(target_device_id):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            ok = loop.run_until_complete(ws.send_to_device(target_device_id, msg))
            if ok:
                return jsonify({"success": True, "delivered": True, "msg_id": msg["msg_id"]})
        except Exception as e:
            logger.debug("Sync send failed, queuing: %s", e)

    # Queue for offline delivery
    queue = get_offline_queue()
    queued = queue.enqueue(target_device_id, msg)
    return jsonify({
        "success": queued,
        "delivered": False,
        "queued": queued,
        "msg_id": msg["msg_id"],
    })


@ws_sync_bp.route("/messages/sync", methods=["GET"])
def sync_messages():
    """Pull queued messages for a device (called on reconnect)."""
    device_id = request.args.get("device_id")
    since = request.args.get("since", type=float)

    if not device_id:
        return jsonify({"success": False, "error": "Missing device_id"}), 400

    queue = get_offline_queue()
    messages = queue.dequeue_for_device(device_id)
    if since is not None:
        messages = [m for m in messages if m.get("timestamp", 0) > since]

    return jsonify({
        "success": True,
        "data": {
            "messages": messages,
            "count": len(messages),
        },
    })


@ws_sync_bp.route("/messages/pending", methods=["GET"])
def pending_messages():
    """Peek at pending message count without removing them."""
    device_id = request.args.get("device_id")
    if not device_id:
        return jsonify({"success": False, "error": "Missing device_id"}), 400

    queue = get_offline_queue()
    count = queue.count_for_device(device_id)
    return jsonify({"success": True, "data": {"pending_count": count}})


# --------------------------------------------------------------------------- #
# Server info
# --------------------------------------------------------------------------- #

@ws_sync_bp.route("/ws-info", methods=["GET"])
def ws_info():
    """Return WebSocket server connection info for clients."""
    from core.network.ws_server import DEFAULT_WS_PORT
    ws = get_ws_manager()
    return jsonify({
        "success": True,
        "data": {
            "ws_url": f"ws://{request.host.split(':')[0]}:{DEFAULT_WS_PORT}",
            "online_users": len(ws.get_all_online_users()),
        },
    })
