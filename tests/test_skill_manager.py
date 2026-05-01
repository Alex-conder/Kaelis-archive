"""
Skill manager tests
"""
import pytest
import tempfile
import shutil
import time


class TestSkill:
    def test_to_dict(self):
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="TestSkill", task_type="test", params={})
        d = skill.to_dict()
        assert d["id"] == "s1"
        assert d["name"] == "TestSkill"

    def test_success_rate_initial(self):
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="TestSkill", task_type="test", params={})
        assert skill.success_rate == 0.0

    def test_increment_usage(self):
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="TestSkill", task_type="test", params={})
        skill.increment_usage(success=True)
        assert skill.usage_count == 1
        assert skill.success_count == 1
        skill.increment_usage(success=False)
        assert skill.usage_count == 2
        assert skill.success_count == 1


class TestSkillStorage:
    @pytest.fixture
    def storage(self):
        from core.skill_manager import SkillStorage
        tmpdir = tempfile.mkdtemp()
        yield SkillStorage(persist_dir=tmpdir)
        time.sleep(0.1)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_save_and_get(self, storage):
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="Test", task_type="t", params={})
        storage.save(skill)
        retrieved = storage.get("s1")
        assert retrieved is not None
        assert retrieved.name == "Test"

    def test_get_all(self, storage):
        from core.skill_manager import Skill
        storage.save(Skill(id="a", name="A", task_type="t", params={}))
        storage.save(Skill(id="b", name="B", task_type="t", params={}))
        all_skills = storage.get_all()
        assert len(all_skills) == 2

    def test_delete(self, storage):
        from core.skill_manager import Skill
        storage.save(Skill(id="del", name="Del", task_type="t", params={}))
        storage.delete("del")
        assert storage.get("del") is None

    def test_get_by_task_type(self, storage):
        from core.skill_manager import Skill
        storage.save(Skill(id="x", name="X", task_type="type_a", params={}))
        storage.save(Skill(id="y", name="Y", task_type="type_b", params={}))
        results = storage.get_by_task_type("type_a")
        assert len(results) == 1
        assert results[0].id == "x"


class TestSkillManager:
    @pytest.fixture
    def manager(self):
        import core.skill_manager as sm_module
        tmpdir = tempfile.mkdtemp()
        sm_module._skill_manager_instance = None
        from core.skill_manager import SkillManager, SkillStorage
        m = SkillManager(storage=SkillStorage(persist_dir=tmpdir))
        yield m
        sm_module._skill_manager_instance = None
        time.sleep(0.1)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_skill(self, manager):
        skill = manager.create_skill(name="NewSkill", task_type="test", params={})
        assert skill is not None
        assert skill.name == "NewSkill"

    def test_search_skills(self, manager):
        manager.create_skill(name="Alpha", task_type="search", params={})
        manager.create_skill(name="Beta", task_type="search", params={})
        results = manager.search_skills("Alpha")
        assert len(results) >= 1

    def test_list_skills(self, manager):
        manager.create_skill(name="S1", task_type="t", params={})
        skills = manager.list_skills()
        assert len(skills) >= 1

    def test_get_statistics(self, manager):
        stats = manager.get_statistics()
        assert isinstance(stats, dict)

    def test_rate_skill(self, manager):
        skill = manager.create_skill(name="Ratable", task_type="t", params={})
        manager.rate_skill(skill.id, 4.5)
        updated = manager.list_skills()[0]
        assert updated.rating >= 4.0

    def test_delete_skill(self, manager):
        skill = manager.create_skill(name="ToDelete", task_type="t", params={})
        manager.delete_skill(skill.id)
        assert manager.search_skills("ToDelete") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
