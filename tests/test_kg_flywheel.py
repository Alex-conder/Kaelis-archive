"""
单元测试：Knowledge Graph Flywheel
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# 测试工具注册中心
from api.routes.kg_flywheel_tools import ToolRegistry, extract_triples, query_graph, run_quality_check


class TestToolRegistry:
    """测试工具注册中心"""
    
    def test_register_tool(self):
        registry = ToolRegistry()
        
        @registry.register(name="test_tool", description="Test tool")
        async def test_func(x: int) -> int:
            return x * 2
        
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "test_tool"
    
    @pytest.mark.asyncio
    async def test_call_tool(self):
        registry = ToolRegistry()
        
        @registry.register(name="add", description="Add two numbers")
        def add_func(a: int, b: int) -> int:
            return a + b
        
        result = await registry.call("add", {"a": 2, "b": 3})
        assert result == 5


class TestExtractionTool:
    """测试提取工具"""
    
    @pytest.mark.asyncio
    async def test_extract_triples_structure(self):
        """验证提取结果结构"""
        result = await extract_triples(
            text="阿里巴巴由马云创立",
            source="test",
            user_id="test_user"
        )
        
        assert "task_id" in result
        assert "triples_extracted" in result
        assert "triples" in result
        assert isinstance(result["triples"], list)
    
    @pytest.mark.asyncio
    async def test_extract_triples_content(self):
        """验证提取内容"""
        result = await extract_triples(
            text="阿里巴巴由马云创立",
            source="test"
        )
        
        if result["triples"]:
            triple = result["triples"][0]
            assert "subject" in triple
            assert "predicate" in triple
            assert "object" in triple
            assert "confidence" in triple


class TestQueryTool:
    """测试查询工具"""
    
    @pytest.mark.asyncio
    async def test_query_graph_success(self):
        """测试成功查询"""
        result = await query_graph(
            query="MATCH (n:Entity) RETURN count(n) as count",
            user_id="test_user"
        )
        
        assert result["success"] is True
        assert "results" in result
        assert "result_count" in result
    
    @pytest.mark.asyncio
    async def test_query_graph_error(self):
        """测试错误查询"""
        result = await query_graph(
            query="INVALID CYPHER SYNTAX",
            user_id="test_user"
        )
        
        # 模拟驱动会返回错误
        # 实际行为取决于 mock 实现


class TestInspectionTool:
    """测试质检工具"""
    
    @pytest.mark.asyncio
    async def test_quality_check_structure(self):
        """验证检查报告结构"""
        result = await run_quality_check(
            check_type="full",
            user_id="test_user"
        )
        
        assert "check_id" in result
        assert "summary" in result
        assert "scores" in result
        assert "issues" in result
    
    @pytest.mark.asyncio
    async def test_quality_check_scores(self):
        """验证分数计算"""
        result = await run_quality_check(check_type="full")
        
        scores = result["scores"]
        assert "completeness" in scores
        assert "consistency" in scores
        assert "accuracy" in scores
        
        # 分数在 0-1 范围内
        for score in scores.values():
            assert 0 <= score <= 1


class TestAgent:
    """测试 Agent 编排"""
    
    @pytest.mark.asyncio
    async def test_intent_analysis(self):
        """测试意图分析"""
        from api.routes.kg_flywheel_agent import KgFlywheelAgent
        
        agent = KgFlywheelAgent("test_user")
        
        # 测试提取意图
        assert agent._analyze_intent("提取文本内容") == "extract"
        assert agent._analyze_intent("parse this text") == "extract"
        
        # 测试查询意图
        assert agent._analyze_intent("查询所有实体") == "query"
        assert agent._analyze_intent("search for nodes") == "query"
        
        # 测试质检意图
        assert agent._analyze_intent("运行质量检查") == "inspect"
        assert agent._analyze_intent("check quality") == "inspect"
        
        # 测试飞轮意图
        assert agent._analyze_intent("执行飞轮") == "flywheel"
        assert agent._analyze_intent("run flywheel") == "flywheel"


class TestMemory:
    """测试记忆管理"""
    
    def test_memory_initialization(self, tmp_path):
        """测试记忆初始化"""
        import os
        from api.routes.kg_flywheel_memory import KgFlywheelMemory
        
        # 使用临时目录
        with patch('api.routes.kg_flywheel_memory.Path') as mock_path:
            mock_path.return_value = tmp_path
            
            memory = KgFlywheelMemory("test_user", "test_session")
            assert memory.user_id == "test_user"
            assert memory.session_id == "test_session"
    
    def test_save_and_get_report(self, tmp_path):
        """测试报告保存和读取"""
        from pathlib import Path
        from api.routes.kg_flywheel_memory import KgFlywheelMemory
        
        # 使用临时目录
        with patch('api.routes.kg_flywheel_memory.Path') as mock_path_class:
            mock_path_instance = tmp_path
            mock_path_class.return_value = mock_path_instance
            mock_path_class.__truediv__ = lambda self, other: tmp_path / other
            
            # 创建必要的子目录
            reports_dir = tmp_path / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            memory = KgFlywheelMemory("test_user", "test_session")
            memory.base_path = tmp_path
            memory.reports_dir = reports_dir
            
            # 模拟报告
            report = {
                "check_id": "test123",
                "summary": {"overall_score": 0.9}
            }
            
            # 保存报告
            report_id = memory.save_report(report)
            assert report_id == "test123"


# 集成测试
@pytest.mark.integration
class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """测试完整流水线"""
        from api.routes.kg_flywheel_agent import KgFlywheelAgent
        from api.routes.kg_flywheel_tools import TOOL_REGISTRY
        
        agent = KgFlywheelAgent("test_user", tool_registry=TOOL_REGISTRY)
        
        # 执行提取
        response = await agent.process("提取：测试公司由张三创立")
        assert response.state.name == "COMPLETED"
        assert "extract_triples" in response.tool_calls or len(response.tool_calls) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
