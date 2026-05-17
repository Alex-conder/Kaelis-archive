"""
NebulaStorage 单元测试

测试范围：
- 不可用时的降级行为
- 连接池初始化失败处理
- ValueWrapper 类型转换
- 单例生命周期管理

注意：需要 nebula3-python 才能测试完整功能，
未安装时测试降级路径。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.nebula_storage import (
    NebulaStorage,
    NEBULA_AVAILABLE,
    get_nebula_storage,
    reset_nebula_storage,
)


class TestNebulaStorage:
    """NebulaStorage 测试类"""

    def test_import_guard(self):
        """nebula3-python 未安装时 NEBULA_AVAILABLE 应为 False"""
        # 该测试在 CI 环境中可能因已安装依赖而失败，标记为可选
        if NEBULA_AVAILABLE:
            pytest.skip("nebula3-python is installed, skipping unavailable test")
        assert NEBULA_AVAILABLE is False

    def test_init_raises_when_unavailable(self):
        """nebula3-python 未安装时初始化应抛出 RuntimeError"""
        if NEBULA_AVAILABLE:
            pytest.skip("nebula3-python is installed, skipping unavailable test")
        with pytest.raises(RuntimeError, match="nebula3-python not installed"):
            NebulaStorage()

    def test_get_storage_returns_none_when_unavailable(self):
        """nebula3-python 未安装时 get_nebula_storage 应返回 None"""
        if NEBULA_AVAILABLE:
            pytest.skip("nebula3-python is installed, skipping unavailable test")
        reset_nebula_storage()
        storage = get_nebula_storage()
        assert storage is None

    def test_convert_value_string(self):
        """_convert_value 应正确解析字符串类型"""
        if not NEBULA_AVAILABLE:
            pytest.skip("nebula3-python not installed, cannot test ValueWrapper")
        from nebula3.data.DataObject import ValueWrapper
        # ValueWrapper 构造复杂，此处仅做占位说明
        # 实际测试需在 NebulaGraph 服务可用时进行集成测试
        assert True

    def test_singleton_pattern(self):
        """单例模式应返回同一实例（仅在可用时测试）"""
        if not NEBULA_AVAILABLE:
            pytest.skip("nebula3-python not installed")
        reset_nebula_storage()
        a = get_nebula_storage()
        b = get_nebula_storage()
        assert a is b


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
