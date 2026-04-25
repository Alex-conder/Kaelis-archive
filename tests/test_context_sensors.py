"""Tests for Prompt 3: Context Sensors."""

import pytest
import tempfile
from pathlib import Path

from core.context.sensor_base import SensorRegistry, ContextSnapshot, _compute_hash, BaseContextSensor
from core.context.sensors.file_sensor import FileChangeSensor
from core.context.sensors.process_sensor import ProcessSensor


# ---------------------------------------------------------------------------
# Base framework tests
# ---------------------------------------------------------------------------

class DummySensor(BaseContextSensor):
    """A test sensor that returns fixed data."""

    def __init__(self, data, **kwargs):
        super().__init__(**kwargs)
        self._data = data

    def collect(self):
        return self._data

    def filter_sensitive(self, data):
        return data


def test_compute_hash_stability():
    h1 = _compute_hash({"a": 1, "b": 2})
    h2 = _compute_hash({"b": 2, "a": 1})
    assert h1 == h2


def test_context_snapshot_to_dict():
    snap = ContextSnapshot(
        sensor_id="test",
        data={"x": 1},
        privacy_level="public",
        hash="abc123",
    )
    d = snap.to_dict()
    assert d["sensor_id"] == "test"
    assert d["privacy_level"] == "public"
    assert "timestamp" in d


def test_sensor_registry_register_and_list():
    registry = SensorRegistry()
    s = DummySensor({"val": 1}, sensor_id="s1")
    registry.register(s)
    sensors = registry.list_sensors()
    assert len(sensors) == 1
    assert sensors[0]["sensor_id"] == "s1"


def test_sensor_registry_unregister():
    registry = SensorRegistry()
    s = DummySensor({"val": 1}, sensor_id="s1")
    registry.register(s)
    assert registry.unregister("s1") is True
    assert registry.unregister("s1") is False


def test_sensor_diff_detection():
    registry = SensorRegistry()
    s = DummySensor({"val": 1}, sensor_id="s1")
    registry.register(s)
    snap1 = registry.diff("s1")
    assert snap1 is not None
    snap2 = registry.diff("s1")
    assert snap2 is None  # No change


def test_sensor_force_trigger():
    registry = SensorRegistry()
    s = DummySensor({"val": 1}, sensor_id="s1")
    registry.register(s)
    snap = registry.trigger("s1")
    assert snap is not None
    assert snap.sensor_id == "s1"


def test_sensor_trigger_not_found():
    registry = SensorRegistry()
    assert registry.trigger("missing") is None


# ---------------------------------------------------------------------------
# FileChangeSensor tests
# ---------------------------------------------------------------------------

def test_file_sensor_collects_recent_file(tmp_path):
    import time
    sensor = FileChangeSensor(watch_dir=str(tmp_path))
    # Create a file
    f = tmp_path / "test.py"
    f.write_text("print(1)")
    time.sleep(0.2)  # Allow watchdog to process the event
    data = sensor.collect()
    assert "changed_files" in data
    # The file we just created should appear (within 5 min)
    assert any("test.py" in p for p in data["changed_files"])
    sensor.stop()


def test_file_sensor_filters_sensitive():
    sensor = FileChangeSensor()
    raw = {
        "watch_dir": ".",
        "changed_files": ["src/main.py", ".env", "config/password.txt", "readme.md"],
    }
    filtered = sensor.filter_sensitive(raw)
    names = [Path(p).name for p in filtered["changed_files"]]
    assert "main.py" in names
    assert "readme.md" in names
    assert ".env" not in names
    assert "password.txt" not in names


# ---------------------------------------------------------------------------
# ProcessSensor tests
# ---------------------------------------------------------------------------

def test_process_sensor_collects_processes():
    sensor = ProcessSensor()
    data = sensor.collect()
    assert "total_processes" in data
    assert "top_cpu" in data
    assert "top_memory" in data
    assert len(data["top_cpu"]) <= 10


def test_process_sensor_filters_sensitive_cmdline():
    sensor = ProcessSensor()
    raw = {
        "total_processes": 2,
        "top_cpu": [
            {"pid": 1, "name": "a", "cmdline": "python app.py"},
            {"pid": 2, "name": "b", "cmdline": "python app.py --token SECRET123"},
        ],
        "top_memory": [],
    }
    filtered = sensor.filter_sensitive(raw)
    assert filtered["top_cpu"][0]["cmdline"] == "python app.py"
    assert filtered["top_cpu"][1]["cmdline"] == "<redacted>"
