"""
Mesh Gossip — Episodic memory synchronization across Kaelis nodes.

P23-A: Mesh Network Decentralization

Strategy:
- Pull-based anti-entropy: periodically request recent public memories from a random peer
- Filter: only sync memories with privacy_level="public"
- Deduplication by (layer, key, user_id, timestamp)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from core.mesh.identity import get_node_identity
from core.mesh.transport import get_mesh_transport, DEFAULT_MESH_PORT
from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)

GOSSIP_INTERVAL = 30.0  # seconds
MAX_SYNC_PER_ROUND = 50


@dataclass
class MemoryDigest:
    """Lightweight summary of a memory entry for sync."""
    layer: str
    key: str
    user_id: str
    timestamp: float
    privacy_level: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "key": self.key,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "privacy_level": self.privacy_level,
        }


class GossipProtocol:
    """
    Gossip-based memory synchronization.

    Each round:
    1. Select a random active peer
    2. Request their public memory digests
    3. Compare with local digests
    4. Pull missing entries
    5. Write to local L2 (with source_peer annotation)
    """

    def __init__(self):
        self._identity = get_node_identity()
        self._transport = get_mesh_transport()
        self._mm = get_memory_manager()
        self._last_sync: Dict[str, float] = {}  # peer_kni -> last_sync_time

    # ------------------------------------------------------------------ #
    # Digest
    # ------------------------------------------------------------------ #

    def get_public_digests(self, since: float = 0) -> List[Dict[str, Any]]:
        """
        Get digests of all public memories modified since `since`.
        """
        digests = []
        for layer in ("L0", "L1", "L2"):
            try:
                conn = self._mm._get_db_conn(layer)
                cursor = conn.execute(
                    """
                    SELECT key, user_id, timestamp, metadata
                    FROM memories
                    WHERE timestamp > ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (since, MAX_SYNC_PER_ROUND),
                )
                for row in cursor.fetchall():
                    meta = json.loads(row["metadata"] or "{}")
                    privacy = meta.get("privacy_level", "private")
                    if privacy == "public":
                        digests.append({
                            "layer": layer,
                            "key": row["key"],
                            "user_id": row["user_id"],
                            "timestamp": row["timestamp"],
                            "privacy_level": privacy,
                        })
            except Exception as e:
                logger.debug("Failed to get digests for %s: %s", layer, e)
        return digests

    def get_memory_by_digest(self, digest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch full memory entry by digest."""
        try:
            layer = digest["layer"]
            key = digest["key"]
            user_id = digest["user_id"]
            result = self._mm.read(layer=layer, key=key, user_id=user_id)
            if result:
                return {
                    "layer": layer,
                    "key": key,
                    "user_id": user_id,
                    "value": result.get("value"),
                    "metadata": result.get("metadata", {}),
                    "timestamp": result.get("timestamp", time.time()),
                }
        except Exception as e:
            logger.debug("Failed to get memory %s/%s: %s", digest.get("layer"), digest.get("key"), e)
        return None

    # ------------------------------------------------------------------ #
    # Sync
    # ------------------------------------------------------------------ #

    def sync_with_peer(self, peer_kni: str) -> Dict[str, Any]:
        """
        Perform one round of anti-entropy sync with a peer.
        Returns sync statistics.
        """
        sess = self._transport.get_session(peer_kni)
        if not sess or sess.status != "active":
            return {"success": False, "error": "Peer not active", "pulled": 0}

        since = self._last_sync.get(peer_kni, 0)
        local_digests = self.get_public_digests(since=since)
        local_keys = {(d["layer"], d["key"], d["user_id"]) for d in local_digests}

        try:
            # Request peer digests
            url = f"http://{sess.host}:{sess.port}/api/mesh/memory/digests"
            resp = requests.post(
                url,
                json={"since": since, "limit": MAX_SYNC_PER_ROUND},
                headers={"Authorization": f"Bearer {sess.token}"} if sess.token else {},
                timeout=10,
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}", "pulled": 0}

            peer_digests = resp.json().get("data", {}).get("digests", [])
            missing = [
                d for d in peer_digests
                if (d["layer"], d["key"], d["user_id"]) not in local_keys
            ]

            pulled = 0
            for digest in missing:
                full = self._pull_memory(peer_kni, digest)
                if full:
                    self._write_foreign_memory(full, peer_kni)
                    pulled += 1

            self._last_sync[peer_kni] = time.time()
            return {"success": True, "pulled": pulled, "missing_count": len(missing)}

        except Exception as e:
            logger.warning("Sync with %s failed: %s", peer_kni, e)
            return {"success": False, "error": str(e), "pulled": 0}

    def _pull_memory(self, peer_kni: str, digest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Pull a specific memory entry from a peer."""
        sess = self._transport.get_session(peer_kni)
        if not sess:
            return None
        try:
            url = f"http://{sess.host}:{sess.port}/api/mesh/memory/get"
            resp = requests.post(
                url,
                json=digest,
                headers={"Authorization": f"Bearer {sess.token}"} if sess.token else {},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data.get("data", {}).get("memory")
        except Exception as e:
            logger.debug("Pull memory from %s failed: %s", peer_kni, e)
        return None

    def _write_foreign_memory(self, memory: Dict[str, Any], source_peer: str):
        """Write a foreign memory entry into local L2 with attribution."""
        try:
            meta = dict(memory.get("metadata", {}))
            meta["source_peer"] = source_peer
            meta["synced_at"] = time.time()
            meta["privacy_level"] = "public"

            self._mm.write(
                layer=memory.get("layer", "L2"),
                key=memory.get("key"),
                value=memory.get("value"),
                metadata=meta,
                user_id=memory.get("user_id", "anonymous"),
            )
            logger.debug("Synced memory %s/%s from %s", memory.get("layer"), memory.get("key"), source_peer)
        except Exception as e:
            logger.warning("Failed to write foreign memory: %s", e)

    def gossip_round(self) -> Dict[str, Any]:
        """
        Run one gossip round: pick a random active peer and sync.
        Returns stats for all peers touched.
        """
        peers = [
            s for s in self._transport.list_sessions()
            if s["status"] == "active"
        ]
        if not peers:
            return {"success": False, "error": "No active peers", "results": {}}

        import random
        target = random.choice(peers)
        result = self.sync_with_peer(target["kni"])
        return {
            "success": result["success"],
            "target": target["kni"],
            "results": {target["kni"]: result},
        }

    def handle_digests_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming digest request (called by Flask route)."""
        since = payload.get("since", 0)
        limit = payload.get("limit", MAX_SYNC_PER_ROUND)
        digests = self.get_public_digests(since=since)
        return {"success": True, "data": {"digests": digests[:limit]}}

    def handle_memory_get(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming memory pull request (called by Flask route)."""
        memory = self.get_memory_by_digest(payload)
        if memory:
            return {"success": True, "data": {"memory": memory}}
        return {"success": False, "error": "Memory not found"}


# --------------------------------------------------------------------------- #
# Singleton
# --------------------------------------------------------------------------- #

_GossipInstance: Optional[GossipProtocol] = None


def get_gossip_protocol() -> GossipProtocol:
    global _GossipInstance
    if _GossipInstance is None:
        _GossipInstance = GossipProtocol()
    return _GossipInstance
