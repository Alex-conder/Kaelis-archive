"""Tests for P20-002: Memory Privacy Level (public/team/private)."""

import json
import tempfile
from pathlib import Path

import pytest

from core.memory_manager_v2 import FourLayerMemoryManager


class TestMemoryPrivacy:
    @pytest.fixture
    def mm(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            # db_dir must end with /data so db_dir.parent becomes the tmpdir root
            db_dir = Path(tmpdir) / "data"
            mm = FourLayerMemoryManager(db_dir=str(db_dir))
            yield mm

    def test_write_with_privacy_level(self, mm):
        """写入时指定 privacy_level，读取时返回"""
        assert mm.write("L2", "key1", {"data": "public"}, privacy_level="public")
        assert mm.write("L2", "key2", {"data": "team"}, privacy_level="team")
        assert mm.write("L2", "key3", {"data": "private"}, privacy_level="private")

        result1 = mm.read("L2", "key1")
        assert result1["privacy_level"] == "public"

        result2 = mm.read("L2", "key2")
        assert result2["privacy_level"] == "team"

        result3 = mm.read("L2", "key3")
        assert result3["privacy_level"] == "private"

    def test_default_privacy_is_private(self, mm):
        """默认 privacy_level 为 private"""
        mm.write("L2", "key_default", {"data": "x"})
        result = mm.read("L2", "key_default")
        assert result["privacy_level"] == "private"

    def test_search_by_privacy_level(self, mm):
        """按隐私级别搜索记忆"""
        mm.write("L2", "pub1", {"type": "announcement"}, privacy_level="public")
        mm.write("L2", "pub2", {"type": "doc"}, privacy_level="public")
        mm.write("L2", "team1", {"type": "meeting"}, privacy_level="team")
        mm.write("L2", "priv1", {"type": "secret"}, privacy_level="private")

        public_memories = mm.search_by_privacy_level("L2", "public", top_k=10)
        assert len(public_memories) == 2
        assert all(m["privacy_level"] == "public" for m in public_memories)

        team_memories = mm.search_by_privacy_level("L2", "team", top_k=10)
        assert len(team_memories) == 1
        assert team_memories[0]["key"] == "team1"

    def test_filter_by_privacy_visibility(self, mm):
        """filter_by_privacy 按可见性过滤"""
        memories = [
            {"key": "a", "privacy_level": "public"},
            {"key": "b", "privacy_level": "team"},
            {"key": "c", "privacy_level": "private"},
            {"key": "d", "privacy_level": "public"},
        ]

        private_only = mm.filter_by_privacy(memories, visibility="private")
        assert len(private_only) == 1
        assert private_only[0]["key"] == "c"

        team_view = mm.filter_by_privacy(memories, visibility="team")
        assert len(team_view) == 2
        assert {m["key"] for m in team_view} == {"b", "c"}

        public_view = mm.filter_by_privacy(memories, visibility="public")
        assert len(public_view) == 4

    def test_privacy_works_on_l1_and_l0(self, mm):
        """L0 和 L1 也支持 privacy_level"""
        mm.write("L0", "sys", {"cfg": 1}, privacy_level="team")
        mm.write("L1", "ctx", {"ctx": "a"}, privacy_level="public")

        r0 = mm.read("L0", "sys")
        assert r0["privacy_level"] == "team"

        r1 = mm.read("L1", "ctx")
        assert r1["privacy_level"] == "public"
