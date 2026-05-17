"""
Kaelis 插件系统 —— 闭环可插拔架构核心

设计原则：
1. 面向接口：所有插件通过抽象基类定义契约
2. 自注册：插件在导入时自动注册到注册中心
3. 惰性加载：插件实例在首次使用时创建
4. 容错隔离：单个插件失败不影响其他插件和主流程
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class PluginMetadata:
    """插件元数据"""
    def __init__(self, name: str, version: str, description: str, author: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.author = author


class BasePlugin(ABC):
    """
    所有插件的抽象基类。
    
    子类必须实现：
    - metadata: 返回 PluginMetadata
    - available: 返回当前环境是否支持该插件
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """插件元数据"""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """
        检查当前环境是否支持该插件。
        例如：检查依赖库是否安装、配置是否正确、外部服务是否可达。
        """
        ...

    def health_check(self) -> Dict[str, Any]:
        """健康检查，返回详细状态信息"""
        return {
            "name": self.metadata.name,
            "available": self.available,
            "version": self.metadata.version,
        }


class BaseExtractor(BasePlugin):
    """
    知识抽取引擎插件基类。
    
    所有抽取器（LLM、OneKE、Mock、自定义）必须实现此接口。
    """

    @abstractmethod
    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        从文本中抽取知识三元组。

        Returns:
            标准化三元组列表，每个元素包含：
            - subject / head: 头实体
            - predicate / relation: 关系
            - object / tail: 尾实体
            - confidence: 置信度（可选）
            - subj_type / head_type: 头实体类型（可选）
            - obj_type / tail_type: 尾实体类型（可选）
        """
        ...

    @abstractmethod
    def supports_schema(self) -> bool:
        """是否支持结构化 Schema 约束抽取"""
        ...


class BaseStorage(BasePlugin):
    """
    图存储后端插件基类。
    
    所有存储后端（Neo4j、NebulaGraph、SQLite 等）必须实现此接口。
    """

    @abstractmethod
    def upsert_vertex(self, vid: str, tag: str, props: Dict[str, Any]) -> bool:
        """插入或更新顶点"""
        ...

    @abstractmethod
    def upsert_edge(self, src: str, dst: str, edge_type: str, props: Optional[Dict[str, Any]] = None) -> bool:
        """插入或更新边"""
        ...

    @abstractmethod
    def execute(self, query: str) -> List[Dict[str, Any]]:
        """执行查询语句"""
        ...

    @abstractmethod
    def upsert_triple(self, triple: Dict[str, Any]) -> bool:
        """
        便捷方法：直接写入一个三元组。
        底层自动转换为顶点+边。
        """
        ...


class PluginRegistry:
    """
    插件注册中心。

    支持按类型（extractor / storage / renderer）注册和检索插件。
    单例模式，全局唯一实例。
    """

    _instance: Optional["PluginRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._extractors: Dict[str, BaseExtractor] = {}
            cls._instance._storages: Dict[str, BaseStorage] = {}
            cls._instance._initialized = False
        return cls._instance

    # ------------------------------------------------------------------
    # Extractor 管理
    # ------------------------------------------------------------------

    def register_extractor(self, extractor: BaseExtractor) -> None:
        """注册抽取引擎插件"""
        name = extractor.metadata.name
        self._extractors[name] = extractor
        logger.info(f"Extractor registered: {name} (available={extractor.available})")

    def get_extractor(self, name: str) -> Optional[BaseExtractor]:
        """获取指定名称的抽取引擎"""
        return self._extractors.get(name)

    def list_extractors(self, available_only: bool = False) -> List[str]:
        """列出所有已注册的抽取引擎名称"""
        if available_only:
            return [name for name, p in self._extractors.items() if p.available]
        return list(self._extractors.keys())

    def get_default_extractor(self) -> Optional[BaseExtractor]:
        """获取默认抽取引擎（优先返回第一个可用的）"""
        for name, extractor in self._extractors.items():
            if extractor.available:
                return extractor
        return None

    # ------------------------------------------------------------------
    # Storage 管理
    # ------------------------------------------------------------------

    def register_storage(self, storage: BaseStorage) -> None:
        """注册存储后端插件"""
        name = storage.metadata.name
        self._storages[name] = storage
        logger.info(f"Storage registered: {name} (available={storage.available})")

    def get_storage(self, name: str) -> Optional[BaseStorage]:
        """获取指定名称的存储后端"""
        return self._storages.get(name)

    def list_storages(self, available_only: bool = False) -> List[str]:
        """列出所有已注册的存储后端名称"""
        if available_only:
            return [name for name, p in self._storages.items() if p.available]
        return list(self._storages.keys())

    def get_default_storage(self) -> Optional[BaseStorage]:
        """获取默认存储后端（优先返回第一个可用的）"""
        for name, storage in self._storages.items():
            if storage.available:
                return storage
        return None

    # ------------------------------------------------------------------
    # 批量操作
    # ------------------------------------------------------------------

    def health_check_all(self) -> Dict[str, Any]:
        """对所有插件执行健康检查"""
        return {
            "extractors": {name: ext.health_check() for name, ext in self._extractors.items()},
            "storages": {name: st.health_check() for name, st in self._storages.items()},
        }

    def auto_register_builtin_plugins(self) -> None:
        """自动注册所有内置插件"""
        if self._initialized:
            return
        self._initialized = True

        # 注册内置抽取器
        try:
            from .extractors.llm_extractor import LLMExtractor
            self.register_extractor(LLMExtractor())
        except Exception as e:
            logger.debug(f"LLMExtractor auto-register skipped: {e}")

        try:
            from .extractors.oneke_extractor import OneKEExtractorPlugin
            self.register_extractor(OneKEExtractorPlugin())
        except Exception as e:
            logger.debug(f"OneKEExtractor auto-register skipped: {e}")

        try:
            from .extractors.mock_extractor import MockExtractor
            self.register_extractor(MockExtractor())
        except Exception as e:
            logger.debug(f"MockExtractor auto-register skipped: {e}")

        # 注册内置存储器
        try:
            from .storages.neo4j_storage import Neo4jStoragePlugin
            self.register_storage(Neo4jStoragePlugin())
        except Exception as e:
            logger.debug(f"Neo4jStorage auto-register skipped: {e}")

        try:
            from .storages.nebula_storage import NebulaStoragePlugin
            self.register_storage(NebulaStoragePlugin())
        except Exception as e:
            logger.debug(f"NebulaStorage auto-register skipped: {e}")


# 全局便捷函数

def get_plugin_registry() -> PluginRegistry:
    """获取插件注册中心单例"""
    registry = PluginRegistry()
    registry.auto_register_builtin_plugins()
    return registry
