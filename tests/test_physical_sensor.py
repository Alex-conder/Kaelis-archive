"""Tests for core.context.sensors.physical_sensor."""

import pytest

from core.context.sensors.physical_sensor import (
    IsaacSimSensor,
    OmniverseSensor,
    PhysicalSensor,
    PhysicalSensorRegistry,
    get_physical_sensor_registry,
)


# ==========================================================================
# IsaacSimSensor
# ==========================================================================

class TestIsaacSimSensor:
    def test_init_mock_mode_when_isaac_unavailable(self):
        sensor = IsaacSimSensor()
        assert sensor._mock_mode is True

    def test_collect_spatial_data_mock(self):
        sensor = IsaacSimSensor()
        data = sensor.collect_spatial_data()
        assert "position" in data
        assert len(data["position"]) == 3
        assert data["mock"] is True

    def test_get_robot_state_mock(self):
        sensor = IsaacSimSensor()
        data = sensor.get_robot_state()
        assert "joint_positions" in data
        assert data["mock"] is True

    def test_get_digital_twin_state(self):
        sensor = IsaacSimSensor(robot_prim_path="/World/TurtleBot")
        data = sensor.get_digital_twin_state()
        assert data["prim_path"] == "/World/TurtleBot"
        assert data["simulator"] == "isaac_sim"

    def test_collect_aggregates_all(self):
        sensor = IsaacSimSensor()
        data = sensor.collect()
        assert "spatial" in data
        assert "robot" in data
        assert "digital_twin" in data
        assert data["sensor_type"] == "IsaacSimSensor"

    def test_filter_sensitive_default(self):
        sensor = IsaacSimSensor()
        data = {"foo": "bar"}
        assert sensor.filter_sensitive(data) == data


# ==========================================================================
# OmniverseSensor
# ==========================================================================

class TestOmniverseSensor:
    def test_init_mock_mode_when_omni_unavailable(self):
        sensor = OmniverseSensor()
        assert sensor._mock_mode is True

    def test_collect_spatial_data_mock(self):
        sensor = OmniverseSensor()
        data = sensor.collect_spatial_data()
        assert "translation" in data
        assert len(data["translation"]) == 3
        assert data["mock"] is True

    def test_get_robot_state_returns_meta(self):
        sensor = OmniverseSensor(prim_path="/World/Twin")
        data = sensor.get_robot_state()
        assert data["prim_path"] == "/World/Twin"
        assert data["has_physics"] is False

    def test_get_digital_twin_state_mock(self):
        sensor = OmniverseSensor(usd_path="/path/to/scene.usd")
        data = sensor.get_digital_twin_state()
        assert data["usd_path"] == "/path/to/scene.usd"
        assert data["mock"] is True

    def test_collect_aggregates_all(self):
        sensor = OmniverseSensor()
        data = sensor.collect()
        assert "spatial" in data
        assert "robot" in data
        assert "digital_twin" in data
        assert data["sensor_type"] == "OmniverseSensor"


# ==========================================================================
# PhysicalSensorRegistry
# ==========================================================================

class TestPhysicalSensorRegistry:
    def test_register_and_list(self):
        reg = PhysicalSensorRegistry()
        reg.register("arm1", IsaacSimSensor())
        reg.register("twin1", OmniverseSensor())
        items = reg.list_sensors()
        assert len(items) == 2
        assert items[0]["name"] == "arm1"

    def test_collect_all(self):
        reg = PhysicalSensorRegistry()
        reg.register("arm1", IsaacSimSensor())
        data = reg.collect_all()
        assert "arm1" in data
        assert "spatial" in data["arm1"]

    def test_collect_all_graceful_on_failure(self):
        reg = PhysicalSensorRegistry()
        bad_sensor = IsaacSimSensor()
        bad_sensor.collect = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        reg.register("bad", bad_sensor)
        data = reg.collect_all()
        assert "bad" in data
        assert "error" in data["bad"]


# ==========================================================================
# Singleton
# ==========================================================================

class TestPhysicalSensorSingleton:
    def test_get_physical_sensor_registry_singleton(self):
        r1 = get_physical_sensor_registry()
        r2 = get_physical_sensor_registry()
        assert r1 is r2
