"""
LaborMarket — 多 Agent 动态创建与生命周期管理

对标: Kimi Code 的 LaborMarket + Subagent 系统
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path("data/agent_swarm_state.json")
DEFAULT_SPEC_PATH = Path("data/agent_spec.json")


@dataclass
class SubAgentSpec:
    """Subagent 规格定义"""
    name: str
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    toolset: List[str] = field(default_factory=list)
    system_prompt: str = ""
    max_tokens: int = 4096

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubAgentSpec":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SubAgent:
    """
    运行时 Subagent 实例。
    拥有独立的记忆命名空间 agent://{name}/
    """

    def __init__(self, spec: SubAgentSpec, fixed: bool = False):
        self.spec = spec
        self.fixed = fixed
        self.created_at = __import__("datetime").datetime.now().isoformat()
        self.memory_namespace = f"agent://{spec.name}/"

    def memory_write(self, key: str, value: Any, metadata: Optional[Dict] = None) -> bool:
        """在独立命名空间写入记忆"""
        mm = get_memory_manager()
        full_key = f"{self.memory_namespace}{key}"
        return mm.write(
            layer="L2",
            key=full_key,
            value=value,
            metadata=metadata or {},
            user_id=self.memory_namespace,
        )

    def memory_read(self, key: str) -> Optional[Any]:
        """在独立命名空间读取记忆"""
        mm = get_memory_manager()
        full_key = f"{self.memory_namespace}{key}"
        return mm.read(layer="L2", key=full_key, user_id=self.memory_namespace)

    def memory_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """在独立命名空间搜索记忆"""
        mm = get_memory_manager()
        # L2 搜索通过 user_id 隔离
        return mm.search(layer="L2", query=query, top_k=top_k, user_id=self.memory_namespace)

    def execute(self, context: str, **kwargs) -> Dict[str, Any]:
        """
        执行 Subagent 任务。
        默认实现：将 system_prompt + context 组合后返回（实际可接入 LLM）。
        """
        prompt = f"{self.spec.system_prompt}\n\n{context}"
        return {
            "agent": self.spec.name,
            "prompt": prompt,
            "capabilities_used": self.spec.capabilities,
            "result": f"[{self.spec.name}] processed: {context[:80]}...",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "fixed": self.fixed,
            "created_at": self.created_at,
            "memory_namespace": self.memory_namespace,
        }


class LaborMarket:
    """
    Agent 劳动力市场。

    管理 fixed（预定义）和 dynamic（运行时创建）两类 Subagent。
    支持 state.json 持久化与会话恢复。
    """

    def __init__(
        self,
        state_path: Optional[Path] = None,
        spec_path: Optional[Path] = None,
    ):
        self._fixed: Dict[str, SubAgent] = {}
        self._dynamic: Dict[str, SubAgent] = {}
        self.state_path = Path(state_path or DEFAULT_STATE_PATH)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.spec_path = Path(spec_path or DEFAULT_SPEC_PATH)

        self._load_fixed_from_spec()
        self._load_dynamic_from_state()

    # ------------------------------------------------------------------ #
    # Fixed Subagents
    # ------------------------------------------------------------------ #

    def _load_fixed_from_spec(self):
        """从 agent_spec.json 加载固定角色 Agent"""
        if not self.spec_path.exists():
            logger.info(f"No agent_spec.json found at {self.spec_path}, skipping fixed agents load")
            return
        try:
            data = json.loads(self.spec_path.read_text(encoding="utf-8"))
            for name, spec_dict in data.get("agents", {}).items():
                spec = SubAgentSpec.from_dict({"name": name, **spec_dict})
                self._fixed[name] = SubAgent(spec=spec, fixed=True)
                logger.info(f"[LaborMarket] Fixed agent loaded: {name}")
        except Exception as e:
            logger.warning(f"Failed to load agent_spec.json: {e}")

    def add_fixed_subagent(self, name: str, agent_spec: Dict[str, Any]) -> SubAgent:
        """手动添加固定 Agent"""
        spec = SubAgentSpec.from_dict({"name": name, **agent_spec})
        agent = SubAgent(spec=spec, fixed=True)
        self._fixed[name] = agent
        logger.info(f"[LaborMarket] Fixed agent added: {name}")
        return agent

    # ------------------------------------------------------------------ #
    # Dynamic Subagents
    # ------------------------------------------------------------------ #

    def _load_dynamic_from_state(self):
        """从 state.json 恢复运行时创建的 Agent"""
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for name, agent_dict in data.get("dynamic", {}).items():
                spec = SubAgentSpec.from_dict(agent_dict.get("spec", {"name": name}))
                agent = SubAgent(spec=spec, fixed=False)
                agent.created_at = agent_dict.get("created_at", agent.created_at)
                self._dynamic[name] = agent
                logger.info(f"[LaborMarket] Dynamic agent restored: {name}")
        except Exception as e:
            logger.warning(f"Failed to restore dynamic agents from state: {e}")

    def add_dynamic_subagent(
        self,
        name: str,
        description: str = "",
        tools: Optional[List[str]] = None,
        system_prompt: str = "",
        capabilities: Optional[List[str]] = None,
        max_tokens: int = 4096,
    ) -> SubAgent:
        """运行时动态创建临时 Agent"""
        if name in self._fixed:
            raise ValueError(f"Cannot create dynamic agent with same name as fixed agent: {name}")
        if name in self._dynamic:
            raise ValueError(f"Dynamic agent already exists: {name}")

        spec = SubAgentSpec(
            name=name,
            description=description,
            capabilities=capabilities or [],
            toolset=tools or [],
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        agent = SubAgent(spec=spec, fixed=False)
        self._dynamic[name] = agent
        self._save_state()
        logger.info(f"[LaborMarket] Dynamic agent created: {name}")
        return agent

    def remove_subagent(self, name: str) -> bool:
        """移除 Agent（仅 dynamic 可移除，fixed 不可移除）"""
        if name in self._fixed:
            logger.warning(f"Cannot remove fixed agent: {name}")
            return False
        if name not in self._dynamic:
            return False
        del self._dynamic[name]
        self._save_state()
        logger.info(f"[LaborMarket] Dynamic agent removed: {name}")
        return True

    # ------------------------------------------------------------------ #
    # 统一视图
    # ------------------------------------------------------------------ #

    @property
    def subagents(self) -> Dict[str, SubAgent]:
        """合并 fixed 和 dynamic 返回统一视图"""
        return {**self._fixed, **self._dynamic}

    @property
    def fixed_subagents(self) -> Dict[str, SubAgent]:
        return dict(self._fixed)

    @property
    def dynamic_subagents(self) -> Dict[str, SubAgent]:
        return dict(self._dynamic)

    def get_subagent(self, name: str) -> Optional[SubAgent]:
        return self.subagents.get(name)

    def list_subagents(self) -> List[Dict[str, Any]]:
        """返回所有 Subagent 的元数据列表"""
        return [agent.to_dict() for agent in self.subagents.values()]

    def find_by_capability(self, capability: str) -> List[SubAgent]:
        """按能力标签查找 Agent"""
        return [
            agent for agent in self.subagents.values()
            if capability in agent.spec.capabilities
        ]

    # ------------------------------------------------------------------ #
    # 持久化
    # ------------------------------------------------------------------ #

    def _save_state(self):
        """保存 dynamic agents 到 state.json"""
        try:
            data = {
                "dynamic": {
                    name: agent.to_dict()
                    for name, agent in self._dynamic.items()
                },
                "saved_at": __import__("datetime").datetime.now().isoformat(),
            }
            self.state_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save agent swarm state: {e}")

    def reset_dynamic(self):
        """清空所有 dynamic agents（用于测试）"""
        self._dynamic.clear()
        if self.state_path.exists():
            self.state_path.unlink()


# ------------------------------------------------------------------ #
# 全局单例
# ------------------------------------------------------------------ #

_labor_market: Optional[LaborMarket] = None


def get_labor_market() -> LaborMarket:
    """获取全局 LaborMarket 实例"""
    global _labor_market
    if _labor_market is None:
        _labor_market = LaborMarket()
    return _labor_market
