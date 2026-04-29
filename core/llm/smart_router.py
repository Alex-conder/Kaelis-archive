"""
多模型智能路由与成本控制

SmartRouter + ModelRegistry
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.resilience import get_circuit_breaker
from core.security.credential_vault import CredentialVault

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    endpoint: str
    api_key: str
    cost_per_1m: float          # 每百万 token 成本（美元）
    tags: List[str] = field(default_factory=list)
    context_length: int = 4096


class ModelRegistry:
    """
    模型注册表：管理所有可用 LLM 模型。
    """

    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._load_from_env()

    def add_model(
        self,
        name: str,
        endpoint: str,
        api_key: str,
        cost_per_1m: float,
        tags: Optional[List[str]] = None,
        context_length: int = 4096,
    ) -> bool:
        """注册新模型"""
        self._models[name] = ModelConfig(
            name=name,
            endpoint=endpoint,
            api_key=api_key,
            cost_per_1m=cost_per_1m,
            tags=tags or [],
            context_length=context_length,
        )
        logger.info(f"[ModelRegistry] Registered: {name} (${cost_per_1m}/1M)")
        return True

    def remove_model(self, name: str) -> bool:
        if name in self._models:
            del self._models[name]
            return True
        return False

    def get_model(self, name: str) -> Optional[ModelConfig]:
        return self._models.get(name)

    def get_models(self) -> List[Dict]:
        """返回所有模型配置（字典形式）"""
        return [
            {
                "name": m.name,
                "endpoint": m.endpoint,
                "cost_per_1m": m.cost_per_1m,
                "tags": m.tags,
                "context_length": m.context_length,
            }
            for m in self._models.values()
        ]

    def _load_from_env(self):
        """从环境变量和 CredentialVault 自动加载已配置模型"""
        # 默认加载常见模型占位（实际 API Key 从 vault 或 env 获取）
        vault = CredentialVault()

        # OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY") or vault.get("openai_api_key") or ""
        if openai_key:
            self.add_model(
                name="gpt-4o",
                endpoint="https://api.openai.com/v1",
                api_key=openai_key,
                cost_per_1m=5.0,
                tags=["strong", "code", "analysis", "conversation", "safety"],
                context_length=128000,
            )
            self.add_model(
                name="gpt-4o-mini",
                endpoint="https://api.openai.com/v1",
                api_key=openai_key,
                cost_per_1m=0.15,
                tags=["cheap", "summary", "conversation"],
                context_length=128000,
            )

        # DeepSeek
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY") or vault.get("deepseek_api_key") or ""
        if deepseek_key:
            self.add_model(
                name="deepseek-chat",
                endpoint="https://api.deepseek.com/v1",
                api_key=deepseek_key,
                cost_per_1m=0.14,
                tags=["cheap", "code", "analysis", "conversation"],
                context_length=64000,
            )

        # Claude
        claude_key = os.environ.get("ANTHROPIC_API_KEY") or vault.get("anthropic_api_key") or ""
        if claude_key:
            self.add_model(
                name="claude-3-5-sonnet",
                endpoint="https://api.anthropic.com/v1",
                api_key=claude_key,
                cost_per_1m=3.0,
                tags=["strong", "code", "analysis", "safety"],
                context_length=200000,
            )


class SmartRouter:
    """
    多模型智能路由。

    路由策略：
    1. 任务分类（基于关键词启发式）
    2. 模型匹配（tags 匹配）
    3. 成本排序（cost_per_1m 升序）
    4. 熔断检查（跳过故障模型）
    5. 选择最优模型
    """

    # 任务分类关键词映射
    TASK_CLASSIFICATION = {
        "code": ["代码", "code", "编程", "programming", "算法", "algorithm", "debug", "函数", "class"],
        "analysis": ["分析", "analysis", "评估", "evaluate", "比较", "compare", "研究", "research"],
        "summary": ["总结", "summary", "摘要", "abstract", "概括", "overview", "提炼"],
        "conversation": ["对话", "conversation", "聊天", "chat", "问答", "q&a", "交流"],
        "safety": ["安全", "safety", "审核", "audit", "风险", "risk", "合规", "compliance"],
    }

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or ModelRegistry()

    def _classify_task(self, task_description: str) -> List[str]:
        """基于关键词对任务进行分类"""
        task_lower = task_description.lower()
        categories = []
        for category, keywords in self.TASK_CLASSIFICATION.items():
            if any(kw.lower() in task_lower for kw in keywords):
                categories.append(category)
        if not categories:
            categories.append("conversation")  # 默认分类
        return categories

    def _match_models(self, categories: List[str], context_length_required: int = 0) -> List[ModelConfig]:
        """根据分类匹配候选模型"""
        candidates = []
        for model in self.registry._models.values():
            # 上下文长度检查
            if context_length_required > 0 and model.context_length < context_length_required:
                continue
            # Tags 匹配（至少匹配一个分类）
            if any(cat in model.tags for cat in categories):
                candidates.append(model)
        return candidates

    def route(
        self,
        task_description: str,
        context_length_required: int = 0,
        max_cost_budget: Optional[float] = None,
        strategy: str = "balanced",  # "cost_first" | "quality_first" | "balanced"
    ) -> Optional[Dict]:
        """
        路由到最优模型。
        返回模型配置字典，或 None（无可用模型）。
        """
        categories = self._classify_task(task_description)
        candidates = self._match_models(categories, context_length_required)

        if not candidates:
            # 无匹配时回退到所有模型
            candidates = list(self.registry._models.values())

        # 熔断检查 + 成本过滤
        available = []
        for model in candidates:
            # 成本预算检查
            if max_cost_budget is not None and model.cost_per_1m > max_cost_budget:
                continue

            # 熔断检查
            cb = get_circuit_breaker(f"llm:{model.name}")
            if cb.is_open():
                logger.warning(f"[SmartRouter] Model {model.name} circuit OPEN, skipping")
                continue

            available.append(model)

        if not available:
            return None

        # 根据策略排序
        if strategy == "cost_first":
            available.sort(key=lambda m: m.cost_per_1m)
        elif strategy == "quality_first":
            # 质量优先：context_length 降序 + cost 次要
            available.sort(key=lambda m: (-m.context_length, m.cost_per_1m))
        else:  # balanced
            # 平衡模式：综合评分 = context_length / (cost_per_1m + 0.01)
            available.sort(key=lambda m: m.context_length / (m.cost_per_1m + 0.01), reverse=True)

        winner = available[0]
        return {
            "name": winner.name,
            "endpoint": winner.endpoint,
            "api_key": winner.api_key,
            "cost_per_1m": winner.cost_per_1m,
            "tags": winner.tags,
            "context_length": winner.context_length,
            "matched_categories": categories,
            "strategy": strategy,
        }

    def record_failure(self, model_name: str):
        """记录模型调用失败（供熔断器使用）"""
        cb = get_circuit_breaker(f"llm:{model_name}")
        cb.record_failure()

    def record_success(self, model_name: str):
        """记录模型调用成功"""
        cb = get_circuit_breaker(f"llm:{model_name}")
        cb.record_success()
