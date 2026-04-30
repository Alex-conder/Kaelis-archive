"""
Test: core/migration/openclaw_connector.py & hermes_connector.py (P19-002 / P20-001)

覆盖率目标：≥80% for new methods
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.migration.openclaw_connector import OpenClawConnector
from core.migration.hermes_connector import HermesConnector


class TestOpenClawConnectorExtended:
    """OpenClaw 迁移增强测试"""

    def test_scan_agent_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent_md = Path(tmp) / "agent.md"
            agent_md.write_text("## Role\n助手\n## Capabilities\n- 搜索\n", encoding="utf-8")
            conn = OpenClawConnector(tmp)
            results = conn.scan_agent_md()
            assert len(results) == 1
            assert "role" in results[0]

    def test_scan_soul_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            soul_md = Path(tmp) / "soul.md"
            soul_md.write_text("## Personality\nFriendly\n## Tone\nProfessional\n", encoding="utf-8")
            conn = OpenClawConnector(tmp)
            results = conn.scan_soul_md()
            assert len(results) == 1
            assert "personality" in results[0]

    def test_convert_context_engine(self):
        conn = OpenClawConnector("/tmp")
        result = conn.convert_context_engine({"session_id": "s1", "content": "hello"})
        assert result["key"].startswith("context_engine_")
        assert result["value"]["memory_type"] == "episodic"
        assert result["value"]["subtype"] == "context_engine"

    def test_run_full_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 创建测试数据
            (Path(tmp) / "skills").mkdir()
            (Path(tmp) / "skills" / "test.json").write_text(
                '{"name": "test_skill", "description": "d", "task_type": "general"}', encoding="utf-8"
            )
            (Path(tmp) / "memory.json").write_text('[{"id": "m1", "text": "hello"}]', encoding="utf-8")
            conn = OpenClawConnector(tmp)
            with patch.object(conn, "import_skills", return_value={"total_found": 1, "imported": 1, "failed": 0}):
                with patch.object(conn, "import_memory_to_l2", return_value={"total_found": 1, "imported": 1}):
                    report = conn.run_full_migration("user_1")
                    assert report["import"]["skills"]["imported"] == 1
                    assert report["import"]["memories"]["imported"] == 1


class TestHermesConnectorExtended:
    """Hermes 迁移增强测试"""

    def test_parse_user_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            user_md = Path(tmp) / "USER.md"
            user_md.write_text(
                "---\npreferences:\n  lang: zh\n---\n## Persona\n研究员\n## Constraints\n- 不泄露隐私\n",
                encoding="utf-8",
            )
            conn = HermesConnector(tmp)
            result = conn.parse_user_md(user_md)
            assert result["persona"] == "研究员"
            assert "不泄露隐私" in result["constraints"]

    def test_classify_memory_layer_l0(self):
        conn = HermesConnector("/tmp")
        assert conn.classify_memory_layer({"title": "x", "content": "short"}) == "L0"

    def test_classify_memory_layer_l3(self):
        conn = HermesConnector("/tmp")
        entry = {"title": "Knowledge Graph", "content": "Entity A relates to B via C. Structured data."}
        assert conn.classify_memory_layer(entry) == "L3"

    def test_import_to_layered_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_md = Path(tmp) / "MEMORY.md"
            mem_md.write_text(
                "# Short fact\nThis is a short fact.\n# Session log\nToday we discussed architecture.\n",
                encoding="utf-8",
            )
            conn = HermesConnector(tmp)
            with patch("core.memory_manager_v2.get_memory_manager") as mock_mm:
                mm = MagicMock()
                mm.write.return_value = True
                mock_mm.return_value = mm
                stats = conn.import_to_layered_memory("user_1")
                assert stats["total_found"] == 2
                assert mm.write.call_count == 2
