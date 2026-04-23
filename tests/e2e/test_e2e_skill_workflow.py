"""
端到端测试：技能创建 → 检索 → 评分 → 搜索 → 删除 完整链路

验证技能管理系统的核心业务流：
1. 列出技能（空列表）
2. 创建技能
3. 获取技能详情
4. 评分技能
5. 记录使用
6. 搜索技能
7. 获取统计
8. 删除技能
9. 验证删除后不可见
"""

import pytest


@pytest.mark.e2e
class TestSkillWorkflow:
    """技能生命周期端到端测试"""
    
    def test_list_skills_empty(self, e2e_client, helpers):
        """E2E-S01: 初始时技能列表返回正确结构"""
        resp = helpers.get_json("/api/skills/")
        data = helpers.assert_payload(resp)
        assert isinstance(data, dict)
        assert "skills" in data
        assert "total" in data
    
    def test_create_and_get_skill(self, e2e_client, helpers):
        """E2E-S02: 创建技能并获取详情"""
        # 创建技能
        resp = helpers.post_json("/api/skills/", {
            "name": "E2E Test Skill",
            "task_type": "e2e_test",
            "params": {"param1": "value1", "threshold": 0.85},
            "description": "Created by e2e test suite",
            "tags": ["e2e", "test", "automated"]
        })
        data = helpers.assert_payload(resp)
        assert "id" in data
        skill_id = data["id"]
        assert resp.status_code == 201
        
        # 获取详情
        resp = helpers.get_json(f"/api/skills/{skill_id}")
        detail = helpers.assert_payload(resp)
        assert detail["name"] == "E2E Test Skill"
        assert detail["task_type"] == "e2e_test"
        assert detail["source"] == "manual"
    
    def test_rate_and_use_skill(self, e2e_client, helpers):
        """E2E-S03: 评分与使用记录"""
        # 先创建技能
        resp = helpers.post_json("/api/skills/", {
            "name": "Rateable Skill",
            "task_type": "e2e_rating",
            "params": {}
        })
        assert resp.status_code == 201
        data = helpers.assert_payload(resp)
        skill_id = data["id"]
        
        # 记录使用（成功）
        resp = helpers.post_json(f"/api/skills/{skill_id}/use", {
            "success": True
        })
        helpers.assert_success(resp)
        
        # 记录使用（失败）
        resp = helpers.post_json(f"/api/skills/{skill_id}/use", {
            "success": False
        })
        helpers.assert_success(resp)
        
        # 评分
        resp = helpers.post_json(f"/api/skills/{skill_id}/rate", {
            "rating": 4.5
        })
        helpers.assert_success(resp)
        
        # 验证更新
        resp = helpers.get_json(f"/api/skills/{skill_id}")
        detail = helpers.assert_payload(resp)
        assert detail["usage_count"] >= 2
        assert detail["rating"] > 0
    
    def test_search_skills(self, e2e_client, helpers):
        """E2E-S04: 技能搜索"""
        # 创建可搜索的技能
        for i in range(3):
            helpers.post_json("/api/skills/", {
                "name": f"Searchable Skill {i}",
                "task_type": "e2e_search",
                "params": {},
                "description": f"skill number {i} for e2e search testing"
            })
        
        # 搜索（参数名为 q，不是 query）
        resp = helpers.get_json("/api/skills/search?q=Searchable&top_k=5")
        data = helpers.assert_payload(resp)
        # 搜索返回 dict 包装: {"count": N, "query": "...", "skills": [...]}
        assert "skills" in data
        assert data["count"] >= 3
    
    def test_skill_statistics(self, e2e_client, helpers):
        """E2E-S05: 技能统计"""
        # 创建多个技能
        for i in range(2):
            helpers.post_json("/api/skills/", {
                "name": f"Stat Skill {i}",
                "task_type": "e2e_stats",
                "params": {}
            })
        
        resp = helpers.get_json("/api/skills/stats")
        data = helpers.assert_payload(resp)
        assert "total" in data
        assert data["total"] >= 2
    
    def test_delete_skill(self, e2e_client, helpers):
        """E2E-S06: 删除技能并验证不可见"""
        # 创建并删除
        resp = helpers.post_json("/api/skills/", {
            "name": "To Be Deleted",
            "task_type": "e2e_delete",
            "params": {}
        })
        assert resp.status_code == 201
        data = helpers.assert_payload(resp)
        skill_id = data["id"]
        
        resp = e2e_client.delete(f"/api/skills/{skill_id}")
        helpers.assert_success(resp)
        
        # 确认删除
        resp = helpers.get_json(f"/api/skills/{skill_id}")
        assert resp.status_code == 404
    
    def test_best_skill_for_task(self, e2e_client, helpers):
        """E2E-S07: 获取任务最佳技能"""
        # 创建两个同类型技能，一个评分更高
        resp1 = helpers.post_json("/api/skills/", {
            "name": "Average Skill",
            "task_type": "e2e_best",
            "params": {}
        })
        assert resp1.status_code == 201
        id1 = helpers.assert_payload(resp1)["id"]
        
        resp2 = helpers.post_json("/api/skills/", {
            "name": "Excellent Skill",
            "task_type": "e2e_best",
            "params": {}
        })
        assert resp2.status_code == 201
        id2 = helpers.assert_payload(resp2)["id"]
        
        # 评分区分
        helpers.post_json(f"/api/skills/{id1}/rate", {"rating": 2.0})
        helpers.post_json(f"/api/skills/{id2}/rate", {"rating": 5.0})
        
        # 获取最佳
        resp = helpers.get_json("/api/skills/best/e2e_best")
        data = helpers.assert_payload(resp)
        assert data["id"] == id2
    
    def test_full_skill_pipeline(self, e2e_client, helpers):
        """
        E2E-S08: 完整技能链路
        
        创建 → 获取 → 评分 → 使用 → 搜索 → 统计 → 删除
        """
        # 1. 创建
        resp = helpers.post_json("/api/skills/", {
            "name": "Full Pipeline Skill",
            "task_type": "e2e_full",
            "params": {"algorithm": "random_forest"},
            "description": "End-to-end test skill",
            "tags": ["ml", "e2e"]
        })
        data = helpers.assert_payload(resp)
        skill_id = data["id"]
        
        # 2. 获取验证
        resp = helpers.get_json(f"/api/skills/{skill_id}")
        detail = helpers.assert_payload(resp)
        assert detail["name"] == "Full Pipeline Skill"
        
        # 3. 评分
        helpers.post_json(f"/api/skills/{skill_id}/rate", {"rating": 4.0})
        
        # 4. 使用
        helpers.post_json(f"/api/skills/{skill_id}/use", {"success": True})
        
        # 5. 搜索
        resp = helpers.get_json("/api/skills/search?q=Pipeline&top_k=5")
        results = helpers.assert_payload(resp)
        skills = results.get("skills", [])
        assert any(s.get("id") == skill_id for s in skills)
        
        # 6. 统计
        resp = helpers.get_json("/api/skills/stats")
        stats = helpers.assert_payload(resp)
        assert stats["total"] >= 1
        
        # 7. 删除
        resp = e2e_client.delete(f"/api/skills/{skill_id}")
        helpers.assert_success(resp)
        
        # 8. 确认删除
        resp = helpers.get_json(f"/api/skills/{skill_id}")
        assert resp.status_code == 404
