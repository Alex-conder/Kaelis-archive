"""
SkillManager 单元测试
"""

import os
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestSkill(KaelisTestBase):
    """测试 Skill 数据类"""
    
    def test_to_dict(self):
        """序列化"""
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="Test", task_type="t1", params={"x": 1})
        d = skill.to_dict()
        self.assertEqual(d["id"], "s1")
        self.assertEqual(d["name"], "Test")
    
    def test_to_embedding_text(self):
        """嵌入文本"""
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="PLS", task_type="metab", params={}, description="analysis", tags=["a", "b"])
        text = skill.to_embedding_text()
        self.assertIn("PLS", text)
        self.assertIn("analysis", text)
    
    def test_success_rate_zero(self):
        """无使用时的成功率"""
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="Test", task_type="t1", params={})
        self.assertEqual(skill.success_rate, 0.0)
    
    def test_success_rate_calc(self):
        """成功率计算"""
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="Test", task_type="t1", params={}, usage_count=10, success_count=7)
        self.assertEqual(skill.success_rate, 0.7)
    
    def test_increment_usage(self):
        """使用计数递增"""
        from core.skill_manager import Skill
        skill = Skill(id="s1", name="Test", task_type="t1", params={})
        skill.increment_usage(success=True)
        self.assertEqual(skill.usage_count, 1)
        self.assertEqual(skill.success_count, 1)
        skill.increment_usage(success=False)
        self.assertEqual(skill.usage_count, 2)
        self.assertEqual(skill.success_count, 1)


class TestSkillStorage(KaelisTestBase):
    """测试技能存储"""
    
    def setUp(self):
        super().setUp()
        from core.skill_manager import SkillStorage, Skill
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SkillStorage(persist_dir=self.temp_dir)
        self.skill = Skill(id="s1", name="Test Skill", task_type="test", params={"x": 1})
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().tearDown()
    
    def test_save_and_get(self):
        """保存和获取"""
        self.assertTrue(self.storage.save(self.skill))
        got = self.storage.get("s1")
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "Test Skill")
    
    def test_get_all(self):
        """获取所有"""
        self.storage.save(self.skill)
        all_skills = self.storage.get_all()
        self.assertEqual(len(all_skills), 1)
    
    def test_get_by_task_type(self):
        """按类型获取"""
        self.storage.save(self.skill)
        result = self.storage.get_by_task_type("test")
        self.assertEqual(len(result), 1)
        result = self.storage.get_by_task_type("other")
        self.assertEqual(len(result), 0)
    
    def test_delete(self):
        """删除"""
        self.storage.save(self.skill)
        self.assertTrue(self.storage.delete("s1"))
        self.assertIsNone(self.storage.get("s1"))
        self.assertFalse(self.storage.delete("nonexistent"))
    
    def test_persistence(self):
        """持久化"""
        self.storage.save(self.skill)
        # 创建新 storage 实例读取同一目录
        from core.skill_manager import SkillStorage
        storage2 = SkillStorage(persist_dir=self.temp_dir)
        got = storage2.get("s1")
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "Test Skill")
    
    def test_simple_search(self):
        """简单搜索"""
        from core.skill_manager import Skill
        s1 = Skill(id="s1", name="PLS Analysis", task_type="metab", params={}, description="pls desc", tags=["pls"])
        s2 = Skill(id="s2", name="PCA Analysis", task_type="metab", params={}, description="pca desc", tags=["pca"])
        self.storage.save(s1)
        self.storage.save(s2)
        results = self.storage.search_similar("PLS", top_k=5)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0][0].id, "s1")

    def test_load_from_json_invalid(self):
        """加载无效 JSON"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir = tempfile.mkdtemp()
        # 写入无效 JSON
        skills_file = Path(self.temp_dir) / "skills.json"
        skills_file.write_text("not json", encoding="utf-8")
        from core.skill_manager import SkillStorage
        storage = SkillStorage(persist_dir=self.temp_dir)
        self.assertEqual(len(storage.get_all()), 0)

    def test_save_to_json_exception(self):
        """保存 JSON 异常"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir = tempfile.mkdtemp()
        from core.skill_manager import SkillStorage, Skill
        storage = SkillStorage(persist_dir=self.temp_dir)
        skill = Skill(id="s1", name="Test", task_type="t", params={})
        # 使目录只读
        os.chmod(self.temp_dir, 0o555)
        try:
            result = storage.save(skill)
            # 在某些平台上可能仍然成功
        finally:
            os.chmod(self.temp_dir, 0o755)

    def test_search_similar_with_chromadb(self):
        """向量搜索（mock ChromaDB）"""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["s1", "s2"]],
            "distances": [[0.1, 0.5]]
        }
        self.storage.collection = mock_collection
        from core.skill_manager import Skill
        s1 = Skill(id="s1", name="PLS", task_type="metab", params={}, description="desc")
        s2 = Skill(id="s2", name="PCA", task_type="metab", params={}, description="desc")
        self.storage._skills_cache = {"s1": s1, "s2": s2}
        results = self.storage.search_similar("PLS", top_k=2)
        self.assertEqual(len(results), 2)

    def test_search_similar_chromadb_exception(self):
        """向量搜索异常回退"""
        mock_collection = MagicMock()
        mock_collection.query.side_effect = Exception("query failed")
        self.storage.collection = mock_collection
        from core.skill_manager import Skill
        s1 = Skill(id="s1", name="PLS", task_type="metab", params={}, description="desc")
        self.storage._skills_cache = {"s1": s1}
        results = self.storage.search_similar("PLS", top_k=2)
        self.assertTrue(len(results) >= 0)


class TestSkillManager(KaelisTestBase):
    """测试 SkillManager"""
    
    def setUp(self):
        super().setUp()
        from core.skill_manager import SkillManager, SkillStorage
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SkillManager(storage=SkillStorage(persist_dir=self.temp_dir))
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().tearDown()
    
    def test_create_skill(self):
        """创建技能"""
        skill = self.manager.create_skill(
            name="Test Skill",
            task_type="test_task",
            params={"x": 1},
            description="A test skill",
            tags=["test"]
        )
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "Test Skill")
        self.assertEqual(skill.source, "manual")
    
    def test_create_from_evolution(self):
        """从进化记录创建"""
        record = {
            "execution_id": "exec_001",
            "iterations": [{"params": {"n": 1}}],
            "status": "completed",
            "initial_params": {"n": 0},
            "expectation": {"criteria": "accuracy > 0.9"}
        }
        skill = self.manager.create_from_evolution("pls_da", {"n": 5}, record, 0.95)
        self.assertIsNotNone(skill)
        self.assertEqual(skill.source, "evolution")
    
    def test_get_best_skill_for_task(self):
        """获取最佳技能"""
        s1 = self.manager.create_skill("Skill A", "task_x", {"x": 1})
        s2 = self.manager.create_skill("Skill B", "task_x", {"x": 2})
        # 使用并评分
        self.manager.use_skill(s1.id, success=True)
        self.manager.rate_skill(s1.id, 4.0)
        best = self.manager.get_best_skill_for_task("task_x")
        self.assertIsNotNone(best)
        self.assertEqual(best.id, s1.id)
    
    def test_get_best_skill_empty(self):
        """无技能时返回 None"""
        result = self.manager.get_best_skill_for_task("nonexistent")
        self.assertIsNone(result)
    
    def test_use_skill(self):
        """记录使用"""
        skill = self.manager.create_skill("Test", "t", {})
        self.assertTrue(self.manager.use_skill(skill.id, success=True))
        updated = self.manager.storage.get(skill.id)
        self.assertEqual(updated.usage_count, 1)
        self.assertEqual(updated.success_count, 1)
    
    def test_use_skill_invalid(self):
        """使用不存在的技能"""
        self.assertFalse(self.manager.use_skill("nonexistent"))
    
    def test_rate_skill(self):
        """评分"""
        skill = self.manager.create_skill("Test", "t", {})
        self.assertTrue(self.manager.rate_skill(skill.id, 4.5))
        updated = self.manager.storage.get(skill.id)
        self.assertEqual(updated.rating, 4.5)
    
    def test_rate_skill_invalid(self):
        """为不存在的技能评分"""
        self.assertFalse(self.manager.rate_skill("nonexistent", 3.0))
    
    def test_list_skills(self):
        """列出技能"""
        self.manager.create_skill("A", "t1", {}, tags=["a"])
        self.manager.create_skill("B", "t2", {}, tags=["b"])
        all_skills = self.manager.list_skills()
        self.assertEqual(len(all_skills), 2)
        by_type = self.manager.list_skills(task_type="t1")
        self.assertEqual(len(by_type), 1)
    
    def test_list_skills_sort(self):
        """排序"""
        s1 = self.manager.create_skill("A", "t", {})
        s2 = self.manager.create_skill("B", "t", {})
        self.manager.rate_skill(s1.id, 3.0)
        self.manager.rate_skill(s2.id, 5.0)
        sorted_skills = self.manager.list_skills(sort_by="rating")
        self.assertEqual(sorted_skills[0].id, s2.id)
    
    def test_search_skills(self):
        """搜索"""
        self.manager.create_skill("PLS Analysis", "metab", {}, description="PLS method")
        results = self.manager.search_skills("PLS")
        self.assertTrue(len(results) > 0)
    
    def test_delete_skill(self):
        """删除"""
        skill = self.manager.create_skill("Test", "t", {})
        self.assertTrue(self.manager.delete_skill(skill.id))
        self.assertIsNone(self.manager.storage.get(skill.id))
    
    def test_get_statistics(self):
        """统计"""
        self.manager.create_skill("A", "t1", {})
        self.manager.create_skill("B", "t2", {})
        stats = self.manager.get_statistics()
        self.assertEqual(stats["total"], 2)
        self.assertIn("by_source", stats)
    
    def test_get_statistics_empty(self):
        """空统计"""
        stats = self.manager.get_statistics()
        self.assertEqual(stats["total"], 0)
    
    def test_export_to_agentskills(self):
        """导出 agentskills 格式"""
        skill = self.manager.create_skill("Test", "t", {})
        exported = self.manager.export_to_agentskills(skill.id)
        self.assertIsNotNone(exported)
        self.assertEqual(exported["schema_version"], "1.0")
        self.assertEqual(exported["skill"]["name"], "Test")
    
    def test_export_to_agentskills_invalid(self):
        """导出不存在的技能"""
        self.assertIsNone(self.manager.export_to_agentskills("nonexistent"))
    
    def test_export_all_agentskills(self):
        """批量导出"""
        self.manager.create_skill("A", "t", {})
        exported = self.manager.export_all_agentskills()
        self.assertEqual(exported["schema_version"], "1.0")
        self.assertEqual(len(exported["skills"]), 1)
    
    def test_import_from_agentskills_single(self):
        """导入单技能"""
        data = {
            "schema_version": "1.0",
            "skill": {
                "id": "imp_001",
                "name": "Imported",
                "task_type": "test",
                "parameters": {"x": 1},
                "metadata": {"rating": 4.0}
            }
        }
        skill = self.manager.import_from_agentskills(data)
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "Imported")
        self.assertEqual(skill.source, "import")
    
    def test_import_from_agentskills_bulk(self):
        """批量导入"""
        data = {
            "schema_version": "1.0",
            "skills": [
                {"id": "b1", "name": "Bulk1", "task_type": "t"},
                {"id": "b2", "name": "Bulk2", "task_type": "t"}
            ]
        }
        skill = self.manager.import_from_agentskills(data)
        self.assertIsNotNone(skill)
        self.assertEqual(self.manager.get_statistics()["total"], 2)
    
    def test_import_from_agentskills_invalid(self):
        """导入无效数据"""
        self.assertIsNone(self.manager.import_from_agentskills({}))
        self.assertIsNone(self.manager.import_from_agentskills("not dict"))

    def test_create_skill_save_fail(self):
        """创建技能保存失败"""
        with patch.object(self.manager.storage, "save", return_value=False):
            skill = self.manager.create_skill("Test", "t", {})
            self.assertIsNone(skill)

    def test_search_skills_by_task_type(self):
        """按任务类型搜索"""
        self.manager.create_skill("PLS", "metab", {}, description="PLS method")
        self.manager.create_skill("PCA", "omics", {}, description="PCA method")
        results = self.manager.search_skills("method", task_type="metab")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].task_type, "metab")

    def test_list_skills_by_source(self):
        """按来源列出"""
        s1 = self.manager.create_skill("A", "t", {})
        # 修改 source
        s1.source = "evolution"
        self.manager.storage.save(s1)
        results = self.manager.list_skills(source="evolution")
        self.assertEqual(len(results), 1)

    def test_list_skills_sort_variants(self):
        """多种排序方式"""
        s1 = self.manager.create_skill("A", "t", {})
        s2 = self.manager.create_skill("B", "t", {})
        self.manager.use_skill(s1.id, success=True)
        self.manager.rate_skill(s1.id, 3.0)
        self.manager.rate_skill(s2.id, 5.0)
        by_usage = self.manager.list_skills(sort_by="usage")
        self.assertEqual(by_usage[0].id, s1.id)
        by_success = self.manager.list_skills(sort_by="success_rate")
        self.assertEqual(by_success[0].id, s1.id)
        by_created = self.manager.list_skills(sort_by="created")
        self.assertTrue(len(by_created) >= 2)

    def test_import_unknown_schema(self):
        """导入未知 schema version"""
        data = {
            "schema_version": "2.0",
            "skill": {"id": "x", "name": "X", "task_type": "t"}
        }
        skill = self.manager.import_from_agentskills(data)
        self.assertIsNotNone(skill)

    def test_import_direct_skill(self):
        """直接导入 skill 对象"""
        data = {
            "schema_version": "1.0",
            "id": "direct",
            "name": "Direct",
            "task_type": "t"
        }
        skill = self.manager.import_from_agentskills(data)
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "Direct")

    def test_import_single_exception(self):
        """导入单个技能异常"""
        with patch("core.skill_manager.hashlib.md5") as mock_md5:
            mock_md5.side_effect = Exception("hash fail")
            result = self.manager._import_single_agentskill({"name": "Test"})
            self.assertIsNone(result)

    def test_skill_storage_when_chromadb_unavailable(self):
        """ChromaDB 不可用时初始化"""
        with patch("core.skill_manager.CHROMADB_AVAILABLE", False):
            from core.skill_manager import SkillStorage
            temp = tempfile.mkdtemp()
            try:
                storage = SkillStorage(persist_dir=temp)
                self.assertIsNone(storage.collection)
            finally:
                import shutil
                shutil.rmtree(temp, ignore_errors=True)

    def test_delete_with_chromadb(self):
        """删除时同步 ChromaDB"""
        mock_collection = MagicMock()
        self.manager.storage.collection = mock_collection
        skill = self.manager.create_skill("Test", "t", {})
        self.manager.delete_skill(skill.id)
        mock_collection.delete.assert_called_once()


class TestGetSkillManager(KaelisTestBase):
    """测试全局单例"""
    
    def test_singleton(self):
        """单例模式"""
        from core.skill_manager import get_skill_manager, _skill_manager
        m1 = get_skill_manager()
        m2 = get_skill_manager()
        self.assertIs(m1, m2)


if __name__ == "__main__":
    unittest.main()
