"""
Skills API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestSkillsAPI(FlaskAppTestBase):
    """测试技能市场 API"""
    
    def test_list_skills(self):
        """GET /api/skills/"""
        r = self.json_get('/api/skills/')
        data = self.assert_json_success(r)
        payload = data.get("data", data)
        self.assertIn("skills", payload)
    
    def test_get_skill_detail(self):
        """GET /api/skills/<skill_id>"""
        r = self.json_get('/api/skills/nonexistent')
        self.assertIn(r.status_code, [200, 404])
    
    def test_create_skill(self):
        """POST /api/skills/"""
        r = self.json_post('/api/skills/', {
            "name": "test_skill",
            "task_type": "test",
            "params": {}
        })
        self.assertIn(r.status_code, [200, 201, 503])
    
    def test_search_skills(self):
        """GET /api/skills/search"""
        r = self.json_get('/api/skills/search?q=test')
        data = self.assert_json_success(r)
        payload = data.get("data", data)
        self.assertIn("skills", payload)
    
    def test_search_skills_missing_q(self):
        """GET /api/skills/search 缺少 q 参数"""
        r = self.json_get('/api/skills/search')
        self.assertIn(r.status_code, [400, 200])
    
    def test_get_best_skill(self):
        """GET /api/skills/best/<task_type>"""
        r = self.json_get('/api/skills/best/test_task')
        self.assertIn(r.status_code, [200, 404])
    
    def test_use_skill(self):
        """POST /api/skills/<skill_id>/use"""
        r = self.json_post('/api/skills/test/use', {"success": True})
        self.assertIn(r.status_code, [200, 404])
    
    def test_rate_skill(self):
        """POST /api/skills/<skill_id>/rate"""
        r = self.json_post('/api/skills/test/rate', {"rating": 4.5})
        self.assertIn(r.status_code, [200, 404])
    
    def test_get_stats(self):
        """GET /api/skills/stats"""
        r = self.json_get('/api/skills/stats')
        data = self.assert_json_success(r)
        payload = data.get("data", data)
        self.assertIn("total", payload)
    
    def test_delete_skill(self):
        """DELETE /api/skills/<skill_id>"""
        r = self.client.delete('/api/skills/test')
        self.assertIn(r.status_code, [200, 404])
    
    def test_get_evolution_skills(self):
        """GET /api/skills/evolution"""
        r = self.json_get('/api/skills/evolution')
        data = self.assert_json_success(r)
        payload = data.get("data", data)
        self.assertIn("skills", payload)

    def test_create_skill_no_body(self):
        """POST /api/skills/ 无 body 返回 400/500"""
        r = self.client.post('/api/skills/', content_type='application/json')
        self.assertIn(r.status_code, [400, 500, 503])

    def test_rate_skill_missing_rating(self):
        """POST /api/skills/<id>/rate 缺少 rating"""
        r = self.json_post('/api/skills/test/rate', {})
        self.assertIn(r.status_code, [400, 404])

    def test_rate_skill_invalid_rating(self):
        """POST /api/skills/<id>/rate rating 超出范围"""
        r = self.json_post('/api/skills/test/rate', {"rating": 6})
        self.assertIn(r.status_code, [400, 404])

    def test_get_skills_when_service_unavailable(self):
        """SKILL_MANAGER_AVAILABLE=False 时返回 503"""
        from unittest.mock import patch
        with patch("api.routes.skills.SKILL_MANAGER_AVAILABLE", False):
            endpoints = [
                ('/api/skills/', 'get'),
                ('/api/skills/test', 'get'),
                ('/api/skills/', 'post'),
                ('/api/skills/test', 'delete'),
                ('/api/skills/search?q=test', 'get'),
                ('/api/skills/best/test', 'get'),
                ('/api/skills/test/use', 'post'),
                ('/api/skills/test/rate', 'post'),
                ('/api/skills/stats', 'get'),
            ]
            for path, method in endpoints:
                if method == 'get':
                    r = self.client.get(path)
                elif method == 'post':
                    r = self.client.post(path, json={})
                elif method == 'delete':
                    r = self.client.delete(path)
                self.assertEqual(r.status_code, 503, f"{path} should return 503")

    def test_create_skill_failed(self):
        """创建技能返回 None 返回 500"""
        from unittest.mock import patch, MagicMock
        mock_manager = MagicMock()
        mock_manager.create_skill.return_value = None
        with patch("api.routes.skills.get_skill_manager", return_value=mock_manager):
            r = self.json_post('/api/skills/', {
                "name": "test_skill",
                "task_type": "test",
                "params": {}
            })
            self.assertEqual(r.status_code, 500)

    def test_delete_skill_exception(self):
        """删除技能抛出异常返回 500"""
        from unittest.mock import patch, MagicMock
        mock_manager = MagicMock()
        mock_manager.delete_skill.side_effect = RuntimeError("boom")
        with patch("api.routes.skills.get_skill_manager", return_value=mock_manager):
            r = self.client.delete('/api/skills/test')
            self.assertEqual(r.status_code, 500)

    def test_use_skill_exception(self):
        """使用技能抛出异常返回 500"""
        from unittest.mock import patch, MagicMock
        mock_manager = MagicMock()
        mock_manager.use_skill.side_effect = RuntimeError("boom")
        with patch("api.routes.skills.get_skill_manager", return_value=mock_manager):
            r = self.json_post('/api/skills/test/use', {"success": True})
            self.assertEqual(r.status_code, 500)

    def test_rate_skill_exception(self):
        """评分技能抛出异常返回 500"""
        from unittest.mock import patch, MagicMock
        mock_manager = MagicMock()
        mock_manager.rate_skill.side_effect = RuntimeError("boom")
        with patch("api.routes.skills.get_skill_manager", return_value=mock_manager):
            r = self.json_post('/api/skills/test/rate', {"rating": 4.5})
            self.assertEqual(r.status_code, 500)

    def test_search_skills_exception(self):
        """搜索技能抛出异常返回 500"""
        from unittest.mock import patch, MagicMock
        mock_manager = MagicMock()
        mock_manager.search_skills.side_effect = RuntimeError("boom")
        with patch("api.routes.skills.get_skill_manager", return_value=mock_manager):
            r = self.json_get('/api/skills/search?q=test')
            self.assertEqual(r.status_code, 500)


if __name__ == "__main__":
    unittest.main()
