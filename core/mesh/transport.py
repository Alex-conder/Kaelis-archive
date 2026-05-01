"""
Mesh Transport — HTTP challenge-response handshake, heartbeat, and remote invocation.

P23-A: Mesh Network Decentralization
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from core.mesh.identity import get_node_identity, NodeIdentity
from core.mesh.authorization import get_authorization_manager

logger = logging.getLogger(__name__)

DEFAULT_MESH_PORT = 8765
HEARTBEAT_INTERVAL = 15.0
HEARTBEAT_TIMEOUT = 45.0


@dataclass
class PeerSession:
    """Established session with a remote peer."""
    kni: str
    host: str
    port: int
    public_key_hex: Optional[str] = None
    token: Optional[str] = None
    last_seen: float = field(default_factory=time.time)
    status: str = "discovered"  # discovered | handshaking | active | stale
    capabilities: List[str] = field(default_factory=list)


class MeshTransport:
    """
    Manages HTTP transport to remote Kaelis nodes.

    - Challenge-response handshake to verify identity
    - Periodic heartbeat to detect failures
    - Remote MCP tool invocation with JWT
    """

    def __init__(self, port: int = DEFAULT_MESH_PORT):
        self._identity = get_node_identity()
        self._port = port
        self._sessions: Dict[str, PeerSession] = {}
        self._auth = get_authorization_manager()

    # ------------------------------------------------------------------ #
    # Session Management
    # ------------------------------------------------------------------ #

    def register_peer(self, kni: str, host: str, port: int, capabilities: List[str]) -> PeerSession:
        """Register a discovered peer and initiate handshake if new."""
        if kni == self._identity.kni:
            return None  # skip self

        if kni in self._sessions:
            sess = self._sessions[kni]
            sess.host = host
            sess.port = port
            sess.capabilities = capabilities
            sess.last_seen = time.time()
            return sess

        sess = PeerSession(
            kni=kni,
            host=host,
            port=port,
            capabilities=capabilities,
            status="discovered",
        )
        self._sessions[kni] = sess
        logger.info("Registered peer %s@%s:%d", kni, host, port)
        return sess

    def get_session(self, kni: str) -> Optional[PeerSession]:
        return self._sessions.get(kni)

    def list_sessions(self) -> List[Dict[str, Any]]:
        self._prune_stale()
        return [
            {
                "kni": s.kni,
                "host": s.host,
                "port": s.port,
                "status": s.status,
                "last_seen": s.last_seen,
                "capabilities": s.capabilities,
            }
            for s in self._sessions.values()
        ]

    def _prune_stale(self):
        now = time.time()
        stale = [
            kni for kni, s in self._sessions.items()
            if s.status == "active" and now - s.last_seen > HEARTBEAT_TIMEOUT
        ]
        for kni in stale:
            self._sessions[kni].status = "stale"
            logger.warning("Peer %s marked stale (no heartbeat for %.0fs)", kni, HEARTBEAT_TIMEOUT)

    # ------------------------------------------------------------------ #
    # Handshake
    # ------------------------------------------------------------------ #

    def perform_handshake(self, kni: str) -> bool:
        """
        Initiate challenge-response handshake with a peer.
        Returns True if handshake succeeded.
        """
        sess = self._sessions.get(kni)
        if not sess:
            logger.warning("Cannot handshake: peer %s not registered", kni)
            return False

        sess.status = "handshaking"
        try:
            # Step 1: Send challenge (random nonce signed by us)
            challenge = f"challenge:{self._identity.kni}:{kni}:{time.time()}"
            signature = self._identity.sign_message(challenge.encode("utf-8")).hex()

            url = f"http://{sess.host}:{sess.port}/api/mesh/handshake"
            payload = {
                "kni": self._identity.kni,
                "challenge": challenge,
                "signature": signature,
                "public_key": self._identity.public_key_bytes.hex() if self._identity.public_key_bytes else None,
                "display_name": self._identity.display_name,
                "capabilities": self._identity.capabilities,
            }

            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                logger.warning("Handshake failed with %s: HTTP %d", kni, resp.status_code)
                sess.status = "discovered"
                return False

            data = resp.json()
            if not data.get("success"):
                logger.warning("Handshake rejected by %s: %s", kni, data.get("error"))
                sess.status = "discovered"
                return False

            # Step 2: Verify peer's response
            peer_pub_hex = data.get("public_key")
            peer_sig = data.get("signature")
            peer_challenge = data.get("challenge")

            if not peer_pub_hex or not peer_sig or not peer_challenge:
                logger.warning("Handshake response incomplete from %s", kni)
                sess.status = "discovered"
                return False

            # Verify peer signed the challenge
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            peer_pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(peer_pub_hex))
            try:
                peer_pub.verify(bytes.fromhex(peer_sig), peer_challenge.encode("utf-8"))
            except Exception:
                logger.warning("Handshake signature verification failed for %s", kni)
                sess.status = "discovered"
                return False

            # Store session info
            sess.public_key_hex = peer_pub_hex
            sess.status = "active"
            sess.last_seen = time.time()

            # Create token for future calls
            sess.token = self._auth.create_token(
                issuer_kni=self._identity.kni,
                subject_kni=kni,
                permissions=[{"resource_type": "memory", "resource_id": "*", "actions": ["read", "write"]}],
                ttl_hours=24,
            )

            logger.info("Handshake successful with %s", kni)
            return True

        except Exception as e:
            logger.warning("Handshake exception with %s: %s", kni, e)
            sess.status = "discovered"
            return False

    def handle_handshake(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming handshake request (called by Flask route).
        Returns response dict.
        """
        try:
            peer_kni = payload.get("kni")
            challenge = payload.get("challenge", "")
            signature = payload.get("signature", "")
            peer_pub_hex = payload.get("public_key")

            if not peer_kni or not signature or not peer_pub_hex:
                return {"success": False, "error": "Missing fields"}

            # Verify peer signature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            peer_pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(peer_pub_hex))
            try:
                peer_pub.verify(bytes.fromhex(signature), challenge.encode("utf-8"))
            except Exception:
                return {"success": False, "error": "Invalid signature"}

            # Register/update peer
            sess = self.register_peer(
                peer_kni,
                payload.get("host", ""),
                payload.get("port", DEFAULT_MESH_PORT),
                payload.get("capabilities", []),
            )
            if sess:
                sess.public_key_hex = peer_pub_hex
                sess.status = "active"
                sess.last_seen = time.time()

            # Respond with our own challenge signature
            response_challenge = f"response:{peer_kni}:{self._identity.kni}:{time.time()}"
            our_sig = self._identity.sign_message(response_challenge.encode("utf-8")).hex()

            return {
                "success": True,
                "kni": self._identity.kni,
                "challenge": response_challenge,
                "signature": our_sig,
                "public_key": self._identity.public_key_bytes.hex() if self._identity.public_key_bytes else None,
            }

        except Exception as e:
            logger.exception("Handshake handling failed")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Heartbeat
    # ------------------------------------------------------------------ #

    def send_heartbeat(self, kni: str) -> bool:
        """Send heartbeat to a peer."""
        sess = self._sessions.get(kni)
        if not sess or not sess.token:
            return False
        try:
            url = f"http://{sess.host}:{sess.port}/api/mesh/heartbeat"
            resp = requests.post(
                url,
                json={"kni": self._identity.kni, "timestamp": time.time()},
                headers={"Authorization": f"Bearer {sess.token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                sess.last_seen = time.time()
                if sess.status == "stale":
                    sess.status = "active"
                return True
        except Exception as e:
            logger.debug("Heartbeat to %s failed: %s", kni, e)
        return False

    def handle_heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming heartbeat (called by Flask route)."""
        peer_kni = payload.get("kni")
        if peer_kni and peer_kni in self._sessions:
            self._sessions[peer_kni].last_seen = time.time()
        return {"success": True, "kni": self._identity.kni, "timestamp": time.time()}

    def heartbeat_all(self) -> Dict[str, bool]:
        """Send heartbeat to all active sessions. Returns results."""
        self._prune_stale()
        results = {}
        for kni, sess in list(self._sessions.items()):
            if sess.status in ("active", "stale"):
                results[kni] = self.send_heartbeat(kni)
        return results

    # ------------------------------------------------------------------ #
    # Remote Invocation
    # ------------------------------------------------------------------ #

    def invoke_remote(
        self,
        kni: str,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Invoke a remote MCP tool via HTTP."""
        sess = self._sessions.get(kni)
        if not sess:
            return {"success": False, "error": f"Peer {kni} not found"}
        if sess.status != "active":
            return {"success": False, "error": f"Peer {kni} not active (status={sess.status})"}

        try:
            url = f"http://{sess.host}:{sess.port}/api/mesh/invoke"
            resp = requests.post(
                url,
                json={
                    "kni": self._identity.kni,
                    "tool_name": tool_name,
                    "params": params,
                },
                headers={"Authorization": f"Bearer {sess.token}"},
                timeout=30,
            )
            return resp.json()
        except Exception as e:
            logger.warning("Remote invoke to %s failed: %s", kni, e)
            return {"success": False, "error": str(e)}

    def handle_invoke(
        self,
        payload: Dict[str, Any],
        auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle incoming remote invocation (called by Flask route).

        1. Verify JWT token (if provided)
        2. Check permissions for the requested tool
        3. Dispatch to local ToolGateway
        """
        tool_name = payload.get("tool_name")
        params = payload.get("params", {})
        source_kni = payload.get("kni", "unknown")

        if not tool_name:
            return {"success": False, "error": "Missing tool_name"}

        # Step 1: Verify JWT
        if auth_token:
            try:
                token_payload = self._auth.verify_token(auth_token)
                if not token_payload:
                    return {"success": False, "error": "Invalid or expired token"}

                # Step 2: Check permission
                perms = token_payload.get("permissions", [])
                allowed = False
                for p in perms:
                    if p.get("resource_type") == "mcp_tool":
                        rid = p.get("resource_id", "")
                        actions = p.get("actions", [])
                        if (rid == "*" or rid == tool_name) and "execute" in actions:
                            allowed = True
                            break

                if not allowed:
                    return {
                        "success": False,
                        "error": f"Permission denied for tool '{tool_name}'",
                    }

            except Exception as e:
                logger.warning("Token verification failed: %s", e)
                return {"success": False, "error": "Token verification failed"}
        else:
            # No token: require local loopback or explicit dev mode
            return {
                "success": False,
                "error": "Authorization required. Provide Bearer token.",
            }

        # Step 3: Dispatch to ToolGateway
        try:
            from core.tools.universal_tool_registry import ToolGateway

            gateway = ToolGateway()
            import asyncio

            result = asyncio.run(gateway.execute(source_kni, tool_name, params))
            return {
                "success": True,
                "result": result,
                "tool": tool_name,
            }
        except Exception as e:
            logger.warning("Tool execution failed for %s: %s", tool_name, e)
            return {"success": False, "error": str(e), "tool": tool_name}


# --------------------------------------------------------------------------- #
# Singleton
# --------------------------------------------------------------------------- #

_TransportInstance: Optional[MeshTransport] = None


def get_mesh_transport(port: int = DEFAULT_MESH_PORT) -> MeshTransport:
    global _TransportInstance
    if _TransportInstance is None:
        _TransportInstance = MeshTransport(port=port)
    return _TransportInstance
