"""
Mesh scheduler tests
Covers: start/stop lifecycle, timer registration
"""
import pytest
import time


class TestMeshScheduler:
    """Test mesh background scheduler"""

    @pytest.fixture
    def scheduler(self):
        from core.mesh.scheduler import MeshScheduler
        s = MeshScheduler()
        yield s
        s.stop()

    def test_start_stop(self, scheduler):
        scheduler.start()
        assert scheduler.is_running()
        scheduler.stop()
        assert not scheduler.is_running()

    def test_double_start_idempotent(self, scheduler):
        scheduler.start()
        scheduler.start()  # should not raise
        assert scheduler.is_running()
        scheduler.stop()

    def test_stop_before_start(self, scheduler):
        # should not raise
        scheduler.stop()
        assert not scheduler.is_running()

    def test_get_status(self, scheduler):
        scheduler.start()
        status = scheduler.get_status()
        assert "running" in status
        assert "heartbeat_interval" in status
        scheduler.stop()

    def test_timers_fire(self, scheduler):
        scheduler.start()
        time.sleep(0.5)
        # After start, timers should be scheduled
        assert scheduler._heartbeat_timer is not None
        scheduler.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
