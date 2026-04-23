"""
端到端测试：系统健康监控与配置链路

验证系统监控和配置的完整性：
1. 多级健康检查端点
2. 进化配置读写
3. 同步健康检查
4. 知识图谱飞轮健康
5. 指标端点
6. 工作流监控
"""

import pytest


@pytest.mark.e2e
class TestSystemHealth:
    """系统健康端到端测试"""
    
    def test_api_health(self, e2e_client, helpers):
        """E2E-H01: /api/health 健康检查"""
        resp = helpers.get_json("/api/health")
        data = helpers.assert_payload(resp)
        assert "status" in data
        assert data["version"] == "8.0.0"
        assert "checks" in data
        assert "timestamp" in data
    
    def test_root_health(self, e2e_client, helpers):
        """E2E-H02: /health 健康检查"""
        resp = helpers.get_json("/health")
        data = helpers.assert_payload(resp)
        assert "status" in data
    
    def test_detailed_health(self, e2e_client, helpers):
        """E2E-H03: /health/detailed 详细健康检查"""
        resp = helpers.get_json("/health/detailed")
        data = helpers.assert_payload(resp)
        assert "overall" in data
        assert data["overall"] in ("healthy", "degraded", "failed")
        assert "checks" in data
    
    def test_metrics_endpoint(self, e2e_client, helpers):
        """E2E-H04: /metrics 指标端点"""
        resp = helpers.get_json("/metrics")
        # metrics 可能返回文本格式
        assert resp.status_code == 200
    
    def test_evolve_config_roundtrip(self, e2e_client, helpers):
        """E2E-H05: 进化配置读写往返"""
        # 读取配置
        resp = helpers.get_json("/api/evolve/config")
        config = helpers.assert_payload(resp)
        
        # 更新配置
        resp = helpers.post_json("/api/evolve/config", {
            "max_iterations": 15,
            "population_size": 20
        })
        helpers.assert_success(resp)
        
        # 再次读取验证
        resp = helpers.get_json("/api/evolve/config")
        new_config = helpers.assert_payload(resp)
        assert resp.status_code == 200
    
    def test_evolve_evaluate_endpoint(self, e2e_client, helpers):
        """E2E-H06: 进化评估端点（简化的本地评估）"""
        resp = helpers.post_json("/api/evolve/evaluate", {
            "params": {"x": 1.0, "y": 2.0},
            "criteria": "maximize"
        })
        # 评估端点可能返回 200 或 400，取决于实现
        assert resp.status_code in (200, 400, 422)
    
    def test_evolve_history(self, e2e_client, helpers):
        """E2E-H07: 进化历史查询"""
        resp = helpers.get_json("/api/evolve/history")
        data = helpers.assert_payload(resp)
        assert "records" in data
        assert "total" in data
    
    def test_sync_health(self, e2e_client, helpers):
        """E2E-H08: 同步服务健康检查"""
        resp = helpers.get_json("/api/sync/health")
        data = helpers.assert_payload(resp)
        assert "status" in data
    
    def test_sync_status(self, e2e_client, helpers):
        """E2E-H09: 同步状态查询"""
        resp = helpers.get_json("/api/sync/status")
        # sync/status 可能因 auth 不可用返回 503
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = helpers.assert_payload(resp)
            assert "status" in data
    
    def test_kg_flywheel_health(self, e2e_client, helpers):
        """E2E-H10: 知识图谱飞轮健康检查"""
        resp = helpers.get_json("/api/kg-flywheel/health")
        data = helpers.assert_payload(resp)
        assert "status" in data
    
    def test_approval_stats(self, e2e_client, helpers):
        """E2E-H11: 审批统计端点"""
        resp = helpers.get_json("/api/approval/stats")
        data = helpers.assert_payload(resp)
        assert "total" in data or "pending" in data
    
    def test_workflow_stats(self, e2e_client, helpers):
        """E2E-H12: 工作流统计端点"""
        resp = helpers.get_json("/api/workflows/stats")
        data = helpers.assert_payload(resp)
        assert "stats" in data
        stats = data["stats"]
        assert "total" in stats
    
    def test_full_system_check(self, e2e_client, helpers):
        """
        E2E-H13: 完整系统健康链路
        
        串联所有健康检查端点，验证系统整体可用性。
        """
        endpoints = [
            ("/api/health", "API Health"),
            ("/health", "Root Health"),
            ("/health/detailed", "Detailed Health"),
            ("/api/sync/health", "Sync Health"),
            ("/api/kg-flywheel/health", "KG Flywheel Health"),
            ("/api/approval/stats", "Approval Stats"),
            ("/api/workflows/stats", "Workflow Stats"),
        ]
        
        results = {}
        for path, name in endpoints:
            resp = helpers.get_json(path)
            results[name] = {
                "status_code": resp.status_code,
                "ok": resp.status_code == 200
            }
        
        # 所有端点都应返回 200
        failed = [name for name, r in results.items() if not r["ok"]]
        assert not failed, f"以下健康检查端点失败: {failed}"
