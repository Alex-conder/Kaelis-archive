"""
Device Registry — Discovery and pairing for cross-device sync.

Supports:
- LAN auto-discovery via mDNS (wraps core.mesh.discovery)
- Manual pairing via pairing code
- Encrypted storage of pairing info in L0 Identity layer
"""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from core.mesh.identity import get_node_identity

logger = logging.getLogger(__name__)

L0_PAIRINGS_KEY = "device_pairings"
L0_DEVICE_PROFILE_KEY = "device_profile"


@dataclass
class DeviceProfile:
    """Local device self-description."""
    device_id: str
    hostname: str
    os: str
    platform: str  # electron, browser, vscode, mobile
    app_version: str
    capabilities: List[str]
    created_at: float


@dataclass
class PairedDevice:
    """A remote device that has been paired/trusted."""
    device_id: str
    pairing_code: str
    display_name: str
    platform: str
    public_key_hex: Optional[str] = None
    paired_at: float = 0
    last_seen: float = 0
    trusted: bool = False
    capabilities: List[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.paired_at == 0:
            self.paired_at = time.time()


class DeviceRegistry:
    """
    Manages local device profile and paired remote devices.

    - Generates unique device_id from hostname + OS + platform
    - Stores pairing records in L0 Identity layer
    - Integrates with mDNS discovery for LAN auto-discovery
    """

    def __init__(self):
        self._identity = get_node_identity()
        self._profile: Optional[DeviceProfile] = None

    # ------------------------------------------------------------------ #
    # Local device profile
    # ------------------------------------------------------------------ #

    def get_or_create_profile(self, platform: str = "unknown",
                              app_version: str = "0.0.0",
                              capabilities: Optional[List[str]] = None) -> DeviceProfile:
        """Get existing profile or create one deterministically."""
        if self._profile:
            return self._profile

        # Try load from L0
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            existing = mm.read(layer="L0", key=L0_DEVICE_PROFILE_KEY, user_id="system")
            if existing and isinstance(existing.get("value"), dict):
                data = existing["value"]
                self._profile = DeviceProfile(**data)
                return self._profile
        except Exception as e:
            logger.debug("Failed to load device profile: %s", e)

        # Create new profile
        import platform as platmod
        import socket

        hostname = socket.gethostname()
        os_name = platmod.system()
        device_id = self._generate_device_id(hostname, os_name, platform)

        self._profile = DeviceProfile(
            device_id=device_id,
            hostname=hostname,
            os=os_name,
            platform=platform,
            app_version=app_version,
            capabilities=capabilities or [],
            created_at=time.time(),
        )

        self._save_profile()
        return self._profile

    def _generate_device_id(self, hostname: str, os_name: str, platform: str) -> str:
        """Generate a deterministic unique device_id."""
        seed = f"{hostname}:{os_name}:{platform}:{self._identity.kni}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"dev_{digest}"

    def _save_profile(self):
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            mm.write(
                layer="L0",
                key=L0_DEVICE_PROFILE_KEY,
                value=asdict(self._profile),
                metadata={"type": "device_profile"},
                user_id="system",
                agent_id="kaelis_self",
            )
        except Exception as e:
            logger.warning("Failed to save device profile: %s", e)

    # ------------------------------------------------------------------ #
    # Pairing management
    # ------------------------------------------------------------------ #

    def generate_pairing_code(self) -> str:
        """Generate a short human-readable pairing code."""
        code = uuid.uuid4().hex[:6].upper()
        return code

    def add_paired_device(self, device: PairedDevice) -> bool:
        """Add or update a paired device record."""
        try:
            pairings = self._load_pairings()
            pairings[device.device_id] = asdict(device)
            self._save_pairings(pairings)
            logger.info("Paired device %s (%s)", device.device_id, device.display_name)
            return True
        except Exception as e:
            logger.error("Failed to save pairing: %s", e)
            return False

    def remove_paired_device(self, device_id: str) -> bool:
        """Remove a paired device."""
        try:
            pairings = self._load_pairings()
            if device_id in pairings:
                del pairings[device_id]
                self._save_pairings(pairings)
                logger.info("Removed paired device %s", device_id)
                return True
            return False
        except Exception as e:
            logger.error("Failed to remove pairing: %s", e)
            return False

    def get_paired_devices(self) -> List[PairedDevice]:
        """List all paired devices."""
        pairings = self._load_pairings()
        devices = []
        for data in pairings.values():
            try:
                devices.append(PairedDevice(**data))
            except Exception:
                continue
        return devices

    def get_paired_device(self, device_id: str) -> Optional[PairedDevice]:
        pairings = self._load_pairings()
        data = pairings.get(device_id)
        if data:
            return PairedDevice(**data)
        return None

    def is_paired(self, device_id: str) -> bool:
        return device_id in self._load_pairings()

    # ------------------------------------------------------------------ #
    # LAN discovery integration
    # ------------------------------------------------------------------ #

    def discover_lan_peers(self, duration: int = 5) -> List[Dict[str, Any]]:
        """
        Discover Kaelis peers on local network via mDNS.
        Returns list of discovered devices that are not yet paired.
        """
        try:
            from core.mesh.discovery import get_discovery_service, ZEROCONF_AVAILABLE
            if not ZEROCONF_AVAILABLE:
                logger.debug("zeroconf not available, skipping LAN discovery")
                return []

            disc = get_discovery_service()
            if not disc._registered:
                disc.start()

            peers = disc.discover(duration=duration)
            paired_ids = {d.device_id for d in self.get_paired_devices()}
            self_profile = self.get_or_create_profile()

            discovered = []
            for p in peers:
                # Skip self
                if p.get("kni") == self._identity.kni:
                    continue
                device_id = f"dev_{p['kni'][:16]}"
                if device_id not in paired_ids:
                    discovered.append({
                        "device_id": device_id,
                        "kni": p.get("kni"),
                        "display_name": p.get("display_name", "Unknown"),
                        "host": p.get("host"),
                        "port": p.get("port"),
                        "capabilities": p.get("capabilities", []),
                    })
            return discovered
        except Exception as e:
            logger.debug("LAN discovery failed: %s", e)
            return []

    # ------------------------------------------------------------------ #
    # L0 persistence helpers
    # ------------------------------------------------------------------ #

    def _load_pairings(self) -> Dict[str, Dict]:
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            existing = mm.read(layer="L0", key=L0_PAIRINGS_KEY, user_id="system")
            if existing and isinstance(existing.get("value"), dict):
                return existing["value"]
        except Exception as e:
            logger.debug("Failed to load pairings: %s", e)
        return {}

    def _save_pairings(self, pairings: Dict[str, Dict]):
        from core.memory_manager_v2 import get_memory_manager
        mm = get_memory_manager()
        mm.write(
            layer="L0",
            key=L0_PAIRINGS_KEY,
            value=pairings,
            metadata={"type": "device_pairings"},
            user_id="system",
            agent_id="kaelis_self",
        )


# ============================================================================
# Singleton
# ============================================================================

_RegistryInstance: Optional[DeviceRegistry] = None


def get_device_registry() -> DeviceRegistry:
    global _RegistryInstance
    if _RegistryInstance is None:
        _RegistryInstance = DeviceRegistry()
    return _RegistryInstance
