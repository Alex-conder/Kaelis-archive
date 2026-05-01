"""
Shared memory space tests
"""
import pytest
import tempfile
import shutil
import time


class TestSharedMemorySpace:
    @pytest.fixture
    def sms(self):
        import core.shared_memory_space as sms_module
        tmpdir = tempfile.mkdtemp()
        sms_module._shared_memory_space_instance = None
        from core.shared_memory_space import SharedMemorySpace
        s = SharedMemorySpace(db_dir=tmpdir)
        yield s
        sms_module._shared_memory_space_instance = None
        time.sleep(0.1)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_space(self, sms):
        space = sms.create_space(name="TeamSpace", owner_id="user1")
        assert isinstance(space, dict)
        assert space["name"] == "TeamSpace"

    def test_get_space(self, sms):
        created = sms.create_space(name="S1", owner_id="u1")
        fetched = sms.get_space(created["space_id"], user_id="u1")
        assert fetched is not None
        assert fetched["space_id"] == created["space_id"]

    def test_list_spaces(self, sms):
        sms.create_space(name="A", owner_id="u1")
        sms.create_space(name="B", owner_id="u1")
        spaces = sms.list_spaces(user_id="u1")
        assert len(spaces) >= 2

    def test_delete_space(self, sms):
        from core.shared_memory_space import SpaceNotFoundError
        space = sms.create_space(name="Del", owner_id="u1")
        sms.delete_space(space["space_id"], user_id="u1")
        with pytest.raises(SpaceNotFoundError):
            sms.get_space(space["space_id"], user_id="u1")

    def test_add_remove_member(self, sms):
        space = sms.create_space(name="Collab", owner_id="u1")
        sms.add_member(space["space_id"], target_user_id="u2", role="writer", added_by="u1")
        status = sms.get_member_status(space["space_id"], user_id="u2")
        assert status is not None
        sms.remove_member(space["space_id"], target_user_id="u2", removed_by="u1")
        # After removal u2 has no permission; check as owner u1
        status_after = sms.get_member_status(space["space_id"], user_id="u1")
        assert not any(m["user_id"] == "u2" for m in status_after)

    def test_write_read_memory(self, sms):
        space = sms.create_space(name="Memo", owner_id="u1")
        sms.write_memory(space["space_id"], key="greeting", value="hello", user_id="u1")
        result = sms.read_memory(space["space_id"], key="greeting", user_id="u1")
        assert result is not None
        assert result["value"] == "hello"

    def test_list_memories(self, sms):
        space = sms.create_space(name="Memo2", owner_id="u1")
        sms.write_memory(space["space_id"], key="k1", value="v1", user_id="u1")
        sms.write_memory(space["space_id"], key="k2", value="v2", user_id="u1")
        mems = sms.list_memories(space["space_id"], user_id="u1")
        assert len(mems) == 2

    def test_search_memory(self, sms):
        space = sms.create_space(name="Search", owner_id="u1")
        sms.write_memory(space["space_id"], key="apple", value="fruit", user_id="u1")
        results = sms.search_memory(space["space_id"], query="apple", user_id="u1")
        assert len(results) >= 1

    def test_stats(self, sms):
        space = sms.create_space(name="Stats", owner_id="u1")
        stats = sms.stats(space["space_id"])
        assert isinstance(stats, dict)

    def test_get_audit_log(self, sms):
        space = sms.create_space(name="Audit", owner_id="u1")
        log = sms.get_audit_log(space["space_id"], user_id="u1")
        assert isinstance(log, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
