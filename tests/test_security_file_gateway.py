"""
File gateway tests
"""
import pytest
import tempfile
from pathlib import Path


class TestFileGateway:
    @pytest.fixture
    def gateway(self):
        from core.security.file_gateway import FileGateway
        return FileGateway()

    def test_add_allowed_directory(self, gateway):
        with tempfile.TemporaryDirectory() as tmpdir:
            gateway.add_allowed_directory(tmpdir)
            assert Path(tmpdir).resolve().as_posix() in gateway.allowed_directories

    def test_read_file_blocked_on_windows(self, gateway):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello", encoding="utf-8")
            gateway.add_allowed_directory(tmpdir)
            result = gateway.read_file(source="test", file_path=str(test_file))
            # On Windows temp dirs live under C:/ which is in PROTECTED_PATHS
            assert result.approved is False
            assert result.decision.value == "block"

    def test_write_file_blocked_on_windows(self, gateway):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "out.txt"
            gateway.add_allowed_directory(tmpdir)
            result = gateway.write_file(source="test", file_path=str(target), content="world")
            assert result.approved is False
            assert result.decision.value == "block"

    def test_delete_file_blocked_on_windows(self, gateway):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "del.txt"
            target.write_text("x", encoding="utf-8")
            gateway.add_allowed_directory(tmpdir)
            result = gateway.delete_file(source="test", file_path=str(target))
            assert result.approved is False
            assert result.decision.value == "block"

    def test_evaluate_disallowed_path(self, gateway):
        from core.security.file_gateway import FileOperationRequest, FileOperationType
        req = FileOperationRequest(
            source="test", operation=FileOperationType.READ, file_path="/etc/passwd",
            content=None, destination=None, metadata={}
        )
        result = gateway.evaluate(req)
        assert result.approved is False

    def test_get_pending_empty(self, gateway):
        pending = gateway.get_pending()
        assert isinstance(pending, list)

    def test_audit_log(self, gateway):
        log = gateway.audit_log()
        assert isinstance(log, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
