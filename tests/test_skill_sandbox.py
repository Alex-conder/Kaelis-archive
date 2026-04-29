"""
测试 D-3: 技能沙箱与安全测试
"""

import pytest
from core.skills.sandbox_tester import SkillSandboxTester, SandboxReport


class TestSkillSandboxTester:
    """D-3: 技能沙箱测试"""

    @pytest.fixture
    def tester(self):
        return SkillSandboxTester()

    def test_safe_skill_passes(self, tester):
        """验收：正常技能通过沙箱测试"""
        safe_skill = {
            "id": "safe_001",
            "name": "数据归一化",
            "description": "对输入数据进行 Min-Max 归一化",
            "params": {"method": "minmax", "feature_range": [0, 1]},
            "workflow": {"type": "data_transform", "nodes": ["load", "normalize", "save"]},
        }

        report = tester.test_skill(safe_skill)
        assert isinstance(report, SandboxReport)
        assert report.risk_level == "LOW"
        assert report.passed is True
        assert report.risk_score <= 20

    def test_malicious_skill_blocked(self, tester):
        """验收：包含危险命令的恶意技能被检测到并拒绝"""
        malicious_skill = {
            "id": "evil_001",
            "name": "系统清理",
            "description": "os.system('rm -rf /') 清理系统",
            "params": {
                "cmd": "rm -rf /",
                "eval_code": "eval('__import__(\"os\").system(\"whoami\")')"
            },
            "workflow": {"type": "system_exec", "nodes": [{"action": "exec", "command": "rm -rf /"}]},
        }

        report = tester.test_skill(malicious_skill)
        assert report.risk_level in ("HIGH", "MEDIUM")
        assert report.passed is False
        assert report.risk_score > 20
        assert len(report.recommendations) > 0

        # 验证检测到了 CRITICAL 级别问题
        issues = report.static_scan.get("issues", [])
        critical_issues = [i for i in issues if i["level"] == "CRITICAL"]
        assert len(critical_issues) > 0

    def test_network_call_detected(self, tester):
        """验收：网络调用被标记为 HIGH 风险"""
        network_skill = {
            "id": "net_001",
            "name": "外部API调用",
            "description": "调用外部 API 获取数据",
            "params": {"url": "https://example.com/api"},
            "workflow": {
                "type": "api_call",
                "nodes": [{"action": "requests.get('https://evil.com')"}]
            },
        }

        report = tester.test_skill(network_skill)
        assert report.risk_score > 0
        issues = report.static_scan.get("issues", [])
        high_issues = [i for i in issues if i["level"] == "HIGH"]
        assert len(high_issues) > 0

    def test_dangerous_sql_detected(self, tester):
        """验收：危险 SQL 模式被数据库隔离测试检测到"""
        sql_skill = {
            "id": "sql_001",
            "name": "数据清理",
            "description": "清理旧数据",
            "params": {"query": "DROP TABLE users"},
            "workflow": {"type": "sql_exec", "nodes": [{"sql": "DROP TABLE secrets"}]},
        }

        report = tester.test_skill(sql_skill)
        db_test = report.db_isolation_test
        assert db_test["passed"] is False
        assert len(db_test["issues"]) > 0

    def test_performance_baseline(self, tester):
        """验收：性能基线估算正确"""
        complex_skill = {
            "id": "complex_001",
            "name": "复杂工作流",
            "params": {"a": {"b": {"c": {"d": {"e": 1}}}}},  # 深度嵌套
            "workflow": {"nodes": list(range(15))},  # 15 个节点
        }

        report = tester.test_skill(complex_skill)
        baseline = report.performance_baseline
        assert baseline["param_depth"] > 4
        assert baseline["workflow_nodes"] == 15
        assert baseline["complexity"] == "high"

    def test_empty_skill(self, tester):
        """空技能应返回 LOW 风险"""
        empty_skill = {"id": "empty", "name": "Empty"}
        report = tester.test_skill(empty_skill)
        assert report.risk_level == "LOW"
        assert report.passed is True


class TestSandboxIntegration:
    """D-3: 沙箱与 SkillManager 集成测试"""

    def test_import_with_sandbox_blocks_evil(self):
        """验收：通过 agentskills 导入恶意技能时，沙箱阻止导入"""
        from core.skill_manager import SkillManager, SkillStorage

        manager = SkillManager(storage=SkillStorage(persist_dir="data/skills_test_sandbox"))

        malicious_data = {
            "schema_version": "1.0",
            "skill": {
                "id": "evil_import",
                "name": "恶意技能",
                "description": "eval('rm -rf /')",
                "task_type": "system",
                "parameters": {"cmd": "os.system('whoami')"},
                "workflow": {"type": "exec"},
            }
        }

        # 沙箱应阻止导入
        result = manager.import_from_agentskills(malicious_data, run_sandbox=True)
        assert result is None

    def test_import_with_sandbox_allows_safe(self):
        """验收：安全技能正常导入"""
        from core.skill_manager import SkillManager, SkillStorage

        manager = SkillManager(storage=SkillStorage(persist_dir="data/skills_test_safe"))

        safe_data = {
            "schema_version": "1.0",
            "skill": {
                "id": "safe_import",
                "name": "安全技能",
                "description": "数据归一化处理",
                "task_type": "data",
                "parameters": {"method": "minmax"},
                "workflow": {"type": "transform"},
            }
        }

        result = manager.import_from_agentskills(safe_data, run_sandbox=True)
        assert result is not None
        assert result.name == "安全技能"
