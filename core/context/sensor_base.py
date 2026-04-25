"""
Context Sensor Base Framework (Prompt 3)

Provides the base classes and registry for environment context sensors.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ContextSnapshot:
    """A snapshot of sensor data at a point in time."""
    sensor_id: str
    data: Dict[str, Any]
    privacy_level: str  # public / internal / sensitive
    hash: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "data": self.data,
            "privacy_level": self.privacy_level,
            "hash": self.hash,
            "timestamp": self.timestamp,
        }


def _compute_hash(data: Dict[str, Any]) -> str:
    """Compute a stable hash of sensor data for diff detection."""
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class BaseContextSensor(ABC):
    """
    Abstract base class for context sensors.

    Subclasses must implement:
        - collect() -> Dict
        - filter_sensitive(data) -> Dict
    """

    def __init__(self, sensor_id: str, privacy_level: str = "internal"):
        self.sensor_id = sensor_id
        self.privacy_level = privacy_level
        self._last_hash: Optional[str] = None

    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """Collect raw sensor data. Must be implemented by subclass."""
        pass

    @abstractmethod
    def filter_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out sensitive information from raw data."""
        pass

    async def snapshot(self) -> Optional[ContextSnapshot]:
        """
        Differential collection: return a snapshot only if data changed.
        Returns None if no change since last snapshot.
        """
        try:
            raw_data = self.collect()
            filtered = self.filter_sensitive(raw_data)
            current_hash = _compute_hash(filtered)

            if self._last_hash == current_hash:
                return None

            self._last_hash = current_hash
            return ContextSnapshot(
                sensor_id=self.sensor_id,
                data=filtered,
                privacy_level=self.privacy_level,
                hash=current_hash,
            )
        except Exception as e:
            logger.warning(f"Sensor {self.sensor_id} snapshot failed: {e}")
            return None

    def force_snapshot(self) -> Optional[ContextSnapshot]:
        """Force a snapshot regardless of change detection (synchronous)."""
        try:
            raw_data = self.collect()
            filtered = self.filter_sensitive(raw_data)
            current_hash = _compute_hash(filtered)
            self._last_hash = current_hash
            return ContextSnapshot(
                sensor_id=self.sensor_id,
                data=filtered,
                privacy_level=self.privacy_level,
                hash=current_hash,
            )
        except Exception as e:
            logger.warning(f"Sensor {self.sensor_id} force snapshot failed: {e}")
            return None


class SensorRegistry:
    """Registry for all active context sensors."""

    def __init__(self):
        self._sensors: Dict[str, BaseContextSensor] = {}

    def register(self, sensor: BaseContextSensor) -> None:
        self._sensors[sensor.sensor_id] = sensor
        logger.info(f"Registered sensor: {sensor.sensor_id}")

    def unregister(self, sensor_id: str) -> bool:
        if sensor_id in self._sensors:
            del self._sensors[sensor_id]
            logger.info(f"Unregistered sensor: {sensor_id}")
            return True
        return False

    def list_sensors(self) -> List[Dict[str, str]]:
        return [
            {"sensor_id": s.sensor_id, "privacy_level": s.privacy_level}
            for s in self._sensors.values()
        ]

    def get_sensor(self, sensor_id: str) -> Optional[BaseContextSensor]:
        return self._sensors.get(sensor_id)

    def trigger(self, sensor_id: str) -> Optional[ContextSnapshot]:
        sensor = self._sensors.get(sensor_id)
        if sensor is None:
            return None
        return sensor.force_snapshot()

    def diff(self, sensor_id: str) -> Optional[ContextSnapshot]:
        sensor = self._sensors.get(sensor_id)
        if sensor is None:
            return None
        # Run synchronously since snapshot is not actually async in current impl
        import asyncio
        try:
            return asyncio.run(sensor.snapshot())
        except Exception:
            return sensor.force_snapshot()
