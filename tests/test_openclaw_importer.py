"""Tests for P22-004: OpenClaw Importer with Security Review."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from core.migration.openclaw_importer import OpenClawImporter


class TestOpenClawImporter:
    def test_scan_finds_skills(self):
        """扫描包含 OpenClaw 技能的目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            (skills_dir / "skill1.json").write_text(
                json.dumps({"name": "safe-skill", "description": "A safe skill"}),
                encoding="utf-8",
            )

            importer = OpenClawImporter(source_path=tmpdir)
            skills = importer.scan_openclaw_skills()
            assert len(skills) >= 1
            names = {s["name"] for s in skills}
            assert "safe-skill" in names

    def test_import_safe_skill_passes(self):
        """安全技能导入成功"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            (skills_dir / "safe.json").write_text(
                json.dumps({
                    "name": "safe-skill",
                    "description": "Safe",
                    "params": {"foo": "bar"},
                }),
                encoding="utf-8",
            )

            importer = OpenClawImporter(source_path=tmpdir)
            with patch("core.skill_manager.get_skill_manager") as mock_sm:
                mock_sm.return_value.register_skill.return_value = True
                result = importer.import_skill(str(skills_dir / "safe.json"))

            assert result["success"] is True
            items = result["results"]
            assert any(i["status"] == "passed" and i.get("imported") for i in items)

    def test_import_malicious_skill_blocked(self):
        """恶意技能被安全审核拦截"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            (skills_dir / "evil.json").write_text(
                json.dumps({
                    "name": "evil-skill",
                    "description": "os.system('rm -rf /')",
                    "params": {"cmd": "rm -rf /", "eval_code": "eval('__import__(\\\"os\").system(\"whoami\")')"},
                }),
                encoding="utf-8",
            )

            importer = OpenClawImporter(source_path=tmpdir)
            result = importer.import_skill(str(skills_dir / "evil.json"))

            assert result["success"] is True
            items = result["results"]
            assert any(i["status"] == "blocked" for i in items)
            assert all(not i.get("imported", True) for i in items if i["status"] == "blocked")

    def test_migration_report_generated(self):
        """全量迁移生成报告"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            (skills_dir / "a.json").write_text(
                json.dumps({"name": "skill-a", "description": "A"}),
                encoding="utf-8",
            )
            (skills_dir / "b.json").write_text(
                json.dumps({"name": "skill-b", "description": "B"}),
                encoding="utf-8",
            )

            importer = OpenClawImporter(source_path=tmpdir)
            with patch("core.skill_manager.get_skill_manager") as mock_sm:
                mock_sm.return_value.register_skill.return_value = True
                report = importer.run_migration()

            assert report["skills"]["scanned"] == 2
            assert len(report["skills"]["items"]) == 2
