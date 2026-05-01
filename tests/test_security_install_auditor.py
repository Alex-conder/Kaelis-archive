"""
Install auditor tests
"""
import pytest


class TestInstallAuditor:
    @pytest.fixture
    def auditor(self):
        from core.security.install_auditor import InstallAuditor
        return InstallAuditor()

    def test_run_full_audit(self, auditor):
        report = auditor.run_full_audit()
        assert report is not None
        assert hasattr(report, "stats") or isinstance(report.to_dict(), dict)

    def test_can_proceed(self, auditor):
        auditor.run_full_audit()
        proceed = auditor.can_proceed()
        assert isinstance(proceed, bool)

    def test_report_to_dict(self, auditor):
        report = auditor.run_full_audit()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "stats" in d or "overall_level" in d

    def test_report_to_cli_table(self, auditor):
        report = auditor.run_full_audit()
        table = report.to_cli_table()
        assert isinstance(table, str)

    def test_report_to_markdown(self, auditor):
        report = auditor.run_full_audit()
        md = report.to_markdown()
        assert isinstance(md, str)
        assert "##" in md or len(md) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
