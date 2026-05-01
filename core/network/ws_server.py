"""
WebSocket Server — Async cross-device message hub.

Runs on a separate port (default 5001) alongside the Flask HTTP server.
Uses Python's `websockets` library for native WebSocket support.

Protocol:
    Client connects → sends auth msg {"type":"auth","device_id":"...","user_id":"...","platform":"..."}
    Server responds → {"type":"auth_ok","device_id":"..."}
    Bidirectional messaging follows.
"""

import asyncio
import json
import logging
import queue as _queue
import threading
import time
import uuid
from typing import Any, Dict, Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol

from core.network.ws_manager import get_ws_manager, WSConnectionManager
from core.network.message_sync import get_message_sync, MessageSync
from core.observability.otel_setup import get_tracer, trace_span, register_trace_callback, get_metrics

logger = logging.getLogger(__name__)

# Tracer for this module
_tracer = get_tracer("kaelis.ws_server")

# Thread-safe queue for trace events to be broadcasted via WebSocket
_trace_event_queue: _queue.Queue = _queue.Queue(maxsize=1000)


def _on_trace_event(event: Dict[str, Any]):
    """Callback invoked by the OTel span processor to queue trace events for WS broadcast."""
    try:
        _trace_event_queue.put_nowait(event)
    except _queue.Full:
        pass


register_trace_callback(_on_trace_event)

DEFAULT_WS_PORT = 5001
HEARTBEAT_INTERVAL = 30.0


class KaelisWebSocketServer:
    """
    Async WebSocket server for cross-device real-time messaging.
    """

    def __init__(self, port: int = DEFAULT_WS_PORT):
        self._port = port
        self._ws_manager = get_ws_manager()
        self._msg_sync = get_message_sync()
        self._server: Optional[websockets.Server] = None
        self._task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._shutdown_event = asyncio.Event()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start_in_thread(self):
        """Start the WebSocket server in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("WebSocket server already running")
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("WebSocket server thread started")

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error("WebSocket server error: %s", e)
        finally:
            self._loop.close()

    async def _serve(self):
        self._server = await websockets.serve(
            self._handle_connection,
            host="0.0.0.0",
            port=self._port,
            ping_interval=HEARTBEAT_INTERVAL,
            ping_timeout=10,
        )
        logger.info("WebSocket server listening on ws://0.0.0.0:%d", self._port)

        # Start background tasks
        prune_task = asyncio.create_task(self._prune_loop())
        trace_broadcast_task = asyncio.create_task(self._trace_broadcast_loop())
        metrics_broadcast_task = asyncio.create_task(self._metrics_broadcast_loop())

        try:
            await self._shutdown_event.wait()
        finally:
            prune_task.cancel()
            trace_broadcast_task.cancel()
            metrics_broadcast_task.cancel()
            self._server.close()
            await self._server.wait_closed()

    def stop(self):
        """Signal the server to shutdown."""
        if self._loop and self._shutdown_event:
            self._loop.call_soon_threadsafe(self._shutdown_event.set)
        logger.info("WebSocket server shutdown signaled")

    # ------------------------------------------------------------------ #
    # Connection handler
    # ------------------------------------------------------------------ #

    @trace_span("ws.handle_connection")
    async def _handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle a single client connection."""
        device_id: Optional[str] = None
        user_id: Optional[str] = None

        try:
            # Wait for auth message (5 second timeout)
            raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            auth_msg = json.loads(raw) if isinstance(raw, str) else raw

            if auth_msg.get("type") != "auth":
                await websocket.send(json.dumps({"type": "error", "error": "Auth required"}))
                return

            device_id = auth_msg.get("device_id")
            user_id = auth_msg.get("user_id")
            platform = auth_msg.get("platform", "unknown")
            capabilities = auth_msg.get("capabilities", [])

            if not device_id or not user_id:
                await websocket.send(json.dumps({"type": "error", "error": "Missing device_id or user_id"}))
                return

            # Register connection
            self._ws_manager.register(
                device_id=device_id,
                websocket=websocket,
                user_id=user_id,
                platform=platform,
                capabilities=capabilities,
            )

            await websocket.send(json.dumps({
                "type": "auth_ok",
                "device_id": device_id,
                "server_time": time.time(),
            }))

            logger.info("WS auth ok: device=%s user=%s platform=%s", device_id, user_id, platform)

            # Push any queued offline messages
            await self._push_offline_messages(device_id)

            # Message loop
            async for message in websocket:
                try:
                    if isinstance(message, str):
                        data = json.loads(message)
                    else:
                        data = message

                    await self._handle_message(device_id, data, websocket)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"type": "error", "error": "Invalid JSON"}))
                except Exception as e:
                    logger.warning("Message handling error for %s: %s", device_id, e)

        except asyncio.TimeoutError:
            logger.warning("WS auth timeout from %s", websocket.remote_address)
            try:
                await websocket.send(json.dumps({"type": "error", "error": "Auth timeout"}))
            except Exception:
                pass
        except websockets.exceptions.ConnectionClosed:
            logger.debug("WS connection closed: %s", device_id)
        except Exception as e:
            logger.warning("WS connection error: %s", e)
        finally:
            if device_id:
                self._ws_manager.unregister(device_id)

    @trace_span("ws.handle_message")
    async def _handle_message(self, device_id: str, data: Dict[str, Any],
                              websocket: WebSocketServerProtocol):
        """Handle a message from a connected device."""
        # Decrypt payload if encrypted
        payload = data.get("payload", {})
        if isinstance(payload, dict) and payload.get("__encrypted"):
            from core.network.message_encryptor import get_message_encryptor
            encryptor = get_message_encryptor()
            decrypted = encryptor.decrypt(payload)
            if decrypted:
                data["payload"] = decrypted
            else:
                logger.warning("Failed to decrypt message from %s", device_id)
                await websocket.send(json.dumps({"type": "error", "error": "Decryption failed"}))
                return

        msg_type = data.get("type", "unknown")

        if msg_type == "ping":
            self._ws_manager.update_ping(device_id)
            await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))

        elif msg_type == "broadcast":
            # Forward to all user's other devices
            user_id = self._ws_manager._device_to_user.get(device_id)
            if user_id:
                payload = data.get("payload", {})
                msg = {
                    "msg_id": str(uuid.uuid4()),
                    "type": data.get("msg_type", "user_message"),
                    "payload": payload,
                    "timestamp": time.time(),
                    "source_device": device_id,
                }
                await self._ws_manager.broadcast_to_user(user_id, msg, exclude_device=device_id)

        elif msg_type == "send_to_device":
            target = data.get("target_device_id")
            if target:
                payload = data.get("payload", {})
                msg = {
                    "msg_id": str(uuid.uuid4()),
                    "type": data.get("msg_type", "direct_message"),
                    "payload": payload,
                    "timestamp": time.time(),
                    "source_device": device_id,
                }
                await self._msg_sync.send_to_device(target, msg)

        else:
            # Pass through to message sync handler
            parsed = await self._msg_sync.handle_incoming(device_id, data)
            if parsed:
                logger.debug("Received %s from %s", parsed.get("type"), device_id)

    async def _push_offline_messages(self, device_id: str):
        """Push queued offline messages to a newly connected device."""
        from core.network.offline_queue import get_offline_queue
        queue = get_offline_queue()
        messages = queue.dequeue_for_device(device_id)
        if not messages:
            return

        conn = self._ws_manager.get_device(device_id)
        if not conn:
            return

        websocket = conn.websocket
        for msg in messages:
            try:
                await websocket.send(json.dumps({
                    "type": "offline_batch",
                    "message": msg,
                }, default=str))
            except Exception as e:
                logger.debug("Failed to push offline msg to %s: %s", device_id, e)

        logger.info("Pushed %d offline messages to %s", len(messages), device_id)

    # ------------------------------------------------------------------ #
    # Background tasks
    # ------------------------------------------------------------------ #

    async def _prune_loop(self):
        """Periodically prune stale connections."""
        while True:
            try:
                await asyncio.sleep(60)
                self._ws_manager.prune_stale(timeout=120.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Prune loop error: %s", e)

    async def _trace_broadcast_loop(self):
        """Drain trace events from the queue and broadcast to monitoring clients."""
        loop = asyncio.get_running_loop()
        while True:
            try:
                event = await loop.run_in_executor(None, _trace_event_queue.get)
                msg = {
                    "msg_id": str(uuid.uuid4()),
                    "type": "trace_event",
                    "payload": event,
                    "timestamp": time.time(),
                }
                # Broadcast to all connected users; fire-and-forget
                try:
                    await self._ws_manager.broadcast_to_all(msg)
                except Exception as e:
                    logger.debug("Trace broadcast error: %s", e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Trace broadcast loop error: %s", e)

    async def _metrics_broadcast_loop(self):
        """Periodically broadcast metrics snapshot to all connected clients."""
        while True:
            try:
                await asyncio.sleep(5)
                metrics = get_metrics()
                msg = {
                    "msg_id": str(uuid.uuid4()),
                    "type": "metrics_snapshot",
                    "payload": metrics,
                    "timestamp": time.time(),
                }
                try:
                    await self._ws_manager.broadcast_to_all(msg)
                except Exception as e:
                    logger.debug("Metrics broadcast error: %s", e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Metrics broadcast loop error: %s", e)


# ============================================================================
# Singleton & Convenience
# ============================================================================

_WsServerInstance: Optional[KaelisWebSocketServer] = None


def get_ws_server(port: int = DEFAULT_WS_PORT) -> KaelisWebSocketServer:
    global _WsServerInstance
    if _WsServerInstance is None:
        _WsServerInstance = KaelisWebSocketServer(port=port)
    return _WsServerInstance
