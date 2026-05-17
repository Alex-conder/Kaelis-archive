"""
OneKEExtractor 单元测试

测试范围：
- Mock 模式抽取
- 空文本处理
- Schema 参数传递
- 单例生命周期管理
"""

import os
import sys
import pytest

# 确保能找到 core 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.oneke_extractor import OneKEExtractor, get_oneke_extractor, reset_oneke_extractor


class TestOneKEExtractor:
    """OneKEExtractor 测试类"""

    def test_mock_extract_returns_triples(self):
        """Mock 模式应返回结构化三元组"""
        os.environ["ONEKE_MOCK_MODE"] = "true"
        extractor = OneKEExtractor()
        result = extractor.extract("Kaelis uses NebulaGraph for storage")
        assert isinstance(result, list)
        assert len(result) > 0
        assert "head" in result[0]
        assert "relation" in result[0]
        assert "tail" in result[0]

    def test_extract_empty_text_returns_empty(self):
        """空文本应返回空列表"""
        os.environ["ONEKE_MOCK_MODE"] = "true"
        extractor = OneKEExtractor()
        assert extractor.extract("") == []
        assert extractor.extract("   ") == []

    def test_extract_without_mock_returns_empty_when_model_unavailable(self):
        """非 mock 模式且模型未加载时应返回空列表"""
        os.environ["ONEKE_MOCK_MODE"] = "false"
        reset_oneke_extractor()
        extractor = get_oneke_extractor()
        if extractor is None or extractor._pipeline is None:
            result = extractor.extract("test") if extractor else []
            assert result == []

    def test_singleton_pattern(self):
        """单例模式应返回同一实例"""
        reset_oneke_extractor()
        os.environ["ONEKE_MOCK_MODE"] = "true"
        a = get_oneke_extractor()
        b = get_oneke_extractor()
        assert a is b

    def test_schema_parameter_accepted(self):
        """应接受 schema 参数且不报错"""
        os.environ["ONEKE_MOCK_MODE"] = "true"
        extractor = OneKEExtractor()
        schema = {"Person": ["work_for"], "Organization": ["located_in"]}
        result = extractor.extract("test text", schema=schema)
        assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
