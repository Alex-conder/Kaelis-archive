"""
多模型智能路由与成本控制

SmartRouter + ModelRegistry
"""

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.resilience import get_circuit_breaker
from core.security.credential_vault import CredentialVault, resolve_llm_api_key

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


class CostTracker:
    """
    成本追踪器：记录每个模型的调用次数、token 使用量与累计成本。
    数据保存在内存中，重启清零（生产环境可持久化到 SQLite）。
    """

    def __init__(self):
        self._calls: Dict[str, int] = {}
        self._tokens: Dict[str, int] = {}
        self._cost: Dict[str, float] = {}
        self._monthly_start = time.time()

    def record_call(self, model_name: str, tokens_used: int = 0):
        """记录一次调用"""
        self._calls[model_name] = self._calls.get(model_name, 0) + 1
        self._tokens[model_name] = self._tokens.get(model_name, 0) + tokens_used
        cost = (tokens_used / 1_000_000) * self._get_model_cost(model_name)
        self._cost[model_name] = self._cost.get(model_name, 0.0) + cost

    def _get_model_cost(self, model_name: str) -> float:
        # 延迟引用外部 registry，避免循环依赖
        return 0.0

    def get_stats(self) -> Dict[str, Any]:
        total_calls = sum(self._calls.values())
        total_cost = sum(self._cost.values())
        return {
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 6),
            "monthly_start_iso": time.strftime("%Y-%m-%d", time.localtime(self._monthly_start)),
            "by_model": {
                name: {
                    "calls": self._calls.get(name, 0),
                    "tokens": self._tokens.get(name, 0),
                    "cost_usd": round(self._cost.get(name, 0.0), 6),
                }
                for name in set(list(self._calls.keys()) + list(self._tokens.keys()) + list(self._cost.keys()))
            },
        }

    def reset(self):
        self._calls.clear()
        self._tokens.clear()
        self._cost.clear()
        self._monthly_start = time.time()


class ModelRegistry:
    """
    模型注册表：管理所有可用 LLM 模型。
    支持环境变量预置 + SQLite 持久化的用户自定义模型。
    """

    def __init__(self, db_path: Optional[str] = None):
        self._models: Dict[str, ModelConfig] = {}
        self._db_path = Path(db_path or os.path.expanduser("~/.kaelis/llm_models.db"))
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._vault = CredentialVault()
        self._init_db()
        self._load_from_env()
        self._load_from_db()

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #

    def _init_db(self):
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_user_models (
                    name TEXT PRIMARY KEY,
                    endpoint TEXT NOT NULL,
                    cost_per_1m REAL NOT NULL,
                    tags TEXT,
                    context_length INTEGER DEFAULT 4096,
                    created_at TEXT
                )
            """)
            conn.commit()

    def _save_to_db(self, name: str, endpoint: str, cost_per_1m: float,
                    tags: List[str], context_length: int):
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO llm_user_models
                (name, endpoint, cost_per_1m, tags, context_length, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, endpoint, cost_per_1m, json.dumps(tags), context_length,
                  time.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()

    def _delete_from_db(self, name: str):
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("DELETE FROM llm_user_models WHERE name = ?", (name,))
            conn.commit()

    def _load_from_db(self):
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                rows = conn.execute("SELECT * FROM llm_user_models").fetchall()
                for row in rows:
                    name, endpoint, cost_per_1m, tags_raw, context_length, _ = row
                    api_key = self._vault.get(f"model:{name}:api_key") or ""
                    if api_key:
                        self._models[name] = ModelConfig(
                            name=name,
                            endpoint=endpoint,
                            api_key=api_key,
                            cost_per_1m=cost_per_1m,
                            tags=json.loads(tags_raw) if tags_raw else [],
                            context_length=context_length or 4096,
                        )
                        logger.info("[ModelRegistry] Loaded from DB: %s", name)
        except Exception as e:
            logger.warning("[ModelRegistry] Failed to load from DB: %s", e)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def add_model(
        self,
        name: str,
        endpoint: str,
        api_key: str,
        cost_per_1m: float,
        tags: Optional[List[str]] = None,
        context_length: int = 4096,
    ) -> bool:
        """注册新模型（自动持久化到 SQLite + Vault）"""
        self._models[name] = ModelConfig(
            name=name,
            endpoint=endpoint,
            api_key=api_key,
            cost_per_1m=cost_per_1m,
            tags=tags or [],
            context_length=context_length,
        )
        # 持久化：配置写入 SQLite，API Key 写入 Vault
        try:
            self._save_to_db(name, endpoint, cost_per_1m, tags or [], context_length)
            if api_key:
                self._vault.set(f"model:{name}:api_key", api_key)
        except Exception as e:
            logger.warning("[ModelRegistry] Failed to persist model %s: %s", name, e)
        logger.info("[ModelRegistry] Registered: %s ($%s/1M)", name, cost_per_1m)
        return True

    def remove_model(self, name: str) -> bool:
        if name in self._models:
            del self._models[name]
            try:
                self._delete_from_db(name)
                self._vault.delete(f"model:{name}:api_key")
            except Exception as e:
                logger.warning("[ModelRegistry] Failed to remove persisted model %s: %s", name, e)
            return True
        return False

    def update_model(
        self,
        name: str,
        endpoint: str,
        api_key: str,
        cost_per_1m: float,
        tags: Optional[List[str]] = None,
        context_length: int = 4096,
    ) -> bool:
        """更新已有模型配置（内存 + SQLite + Vault）"""
        if name not in self._models:
            return False
        self._models[name] = ModelConfig(
            name=name,
            endpoint=endpoint,
            api_key=api_key,
            cost_per_1m=cost_per_1m,
            tags=tags or [],
            context_length=context_length,
        )
        try:
            self._save_to_db(name, endpoint, cost_per_1m, tags or [], context_length)
            if api_key:
                self._vault.set(f"model:{name}:api_key", api_key)
        except Exception as e:
            logger.warning("[ModelRegistry] Failed to persist updated model %s: %s", name, e)
        logger.info("[ModelRegistry] Updated: %s", name)
        return True

    def test_model_connection(self, name: str) -> Dict[str, Any]:
        """探测模型端点连通性，返回 {success, latency_ms, error}。不记录 API Key。"""
        import requests

        model = self._models.get(name)
        if not model:
            return {"success": False, "error": "Model not found"}

        start = time.time()
        try:
            headers = {"Authorization": f"Bearer {model.api_key}"}
            test_url = model.endpoint.rstrip("/") + "/models"
            resp = requests.get(test_url, headers=headers, timeout=10, allow_redirects=True)
            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return {"success": True, "latency_ms": latency_ms}
            if resp.status_code in (401, 403):
                return {"success": False, "error": "Authentication error"}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Connection error"}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_model(self, name: str) -> Optional[ModelConfig]:
        return self._models.get(name)

    def get_models(self) -> List[Dict]:
        """返回所有模型配置（字典形式，不含 api_key）"""
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
        """从环境变量和 CredentialVault 自动加载预置模型"""
        # OpenAI
        openai_key = resolve_llm_api_key("openai")
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
        deepseek_key = resolve_llm_api_key("deepseek")
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
        claude_key = resolve_llm_api_key("anthropic")
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
    1. 任务分类（基于关键词启发式 + 可选 LLM 分类）
    2. 模型匹配（tags 匹配）
    3. 成本排序（cost_per_1m 升序）
    4. 熔断检查（跳过故障模型）
    5. 预算约束（排除超预算模型）
    6. 选择最优模型
    """

    # 任务分类关键词映射
    TASK_CLASSIFICATION = {
        "code": ["代码", "code", "编程", "programming", "算法", "algorithm", "debug", "函数", "class", "optimize", "优化", "query", "sql", "database"],
        "analysis": ["分析", "analysis", "评估", "evaluate", "比较", "compare", "研究", "research"],
        "summary": ["总结", "summary", "摘要", "abstract", "概括", "overview", "提炼"],
        "conversation": ["对话", "conversation", "聊天", "chat", "问答", "q&a", "交流"],
        "safety": ["安全", "safety", "审核", "audit", "风险", "risk", "合规", "compliance"],
    }

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or ModelRegistry()
        self.tracker = CostTracker()
        self._strategy: str = "balanced"

    @property
    def strategy(self) -> str:
        return self._strategy

    @strategy.setter
    def strategy(self, value: str):
        if value not in ("cost_first", "quality_first", "balanced"):
            raise ValueError(f"Unknown strategy: {value}")
        self._strategy = value

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

    def _filter_available(
        self,
        candidates: List[ModelConfig],
        max_cost_budget: Optional[float] = None,
    ) -> List[ModelConfig]:
        """应用预算和熔断过滤"""
        available = []
        for model in candidates:
            if max_cost_budget is not None and model.cost_per_1m > max_cost_budget:
                continue
            cb = get_circuit_breaker(f"llm:{model.name}")
            if cb.is_open():
                logger.warning(f"[SmartRouter] Model {model.name} circuit OPEN, skipping")
                continue
            available.append(model)
        return available

    def _sort_by_strategy(self, models: List[ModelConfig], strategy: str) -> List[ModelConfig]:
        """根据策略排序模型"""
        if strategy == "cost_first":
            models.sort(key=lambda m: m.cost_per_1m)
        elif strategy == "quality_first":
            models.sort(key=lambda m: (-m.context_length, m.cost_per_1m))
        else:  # balanced
            models.sort(key=lambda m: m.context_length / (m.cost_per_1m + 0.01), reverse=True)
        return models

    def _estimate_cost(self, model: ModelConfig, context_length_required: int = 0) -> float:
        """估算单次调用成本（假设 1K 输出 tokens）"""
        input_tokens = max(context_length_required, 1000)
        output_tokens = 1000
        total = input_tokens + output_tokens
        return round((total / 1_000_000) * model.cost_per_1m, 8)

    def route(
        self,
        task_description: str,
        context_length_required: int = 0,
        max_cost_budget: Optional[float] = None,
        strategy: str = "balanced",
    ) -> Optional[Dict]:
        """
        同步路由到最优模型。
        返回模型配置字典 + 预估成本，或 None（无可用模型）。
        """
        categories = self._classify_task(task_description)
        candidates = self._match_models(categories, context_length_required)

        if not candidates:
            candidates = list(self.registry._models.values())

        available = self._filter_available(candidates, max_cost_budget)

        if not available:
            return None

        available = self._sort_by_strategy(available, strategy)
        winner = available[0]

        estimated_cost = self._estimate_cost(winner, context_length_required)

        return {
            "name": winner.name,
            "endpoint": winner.endpoint,
            "api_key": winner.api_key,
            "cost_per_1m": winner.cost_per_1m,
            "tags": winner.tags,
            "context_length": winner.context_length,
            "matched_categories": categories,
            "strategy": strategy,
            "estimated_cost": estimated_cost,
        }

    async def aroute(
        self,
        task_description: str,
        context_length_required: int = 0,
        budget_limit: Optional[float] = None,
        strategy: str = "balanced",
    ) -> Optional[Dict]:
        """
        异步路由到最优模型。
        与 sync route 行为一致，预留 LLM-based classification 的异步扩展点。
        """
        # TODO: 未来可在此接入异步 LLM 分类器
        result = self.route(
            task_description=task_description,
            context_length_required=context_length_required,
            max_cost_budget=budget_limit,
            strategy=strategy,
        )
        return result

    def record_failure(self, model_name: str):
        """记录模型调用失败（供熔断器使用）"""
        cb = get_circuit_breaker(f"llm:{model_name}")
        cb.record_failure()

    def record_success(self, model_name: str):
        """记录模型调用成功"""
        cb = get_circuit_breaker(f"llm:{model_name}")
        cb.record_success()

    def get_stats(self) -> Dict[str, Any]:
        """返回路由统计信息"""
        return self.tracker.get_stats()

    def reset_stats(self):
        """重置统计"""
        self.tracker.reset()

    def get_circuit_status(self) -> Dict[str, Any]:
        """返回所有模型的熔断器状态"""
        status = {}
        for name in self.registry._models:
            cb = get_circuit_breaker(f"llm:{name}")
            status[name] = {
                "state": cb.state.value,
                "failure_count": cb._failure_count,
                "is_open": cb.is_open(),
            }
        return status


# =============================================================================
# MCP Tool Registration
# =============================================================================

def register_llm_routing_tools(mcp: Any):
    """向 FastMCP 实例注册 LLM 路由相关 Tools。"""
    from core.llm.smart_router import ModelRegistry, SmartRouter

    _llm_registry = ModelRegistry()
    _smart_router = SmartRouter(_llm_registry)

    @mcp.tool("llm.route_task")
    def llm_route_task(
        task_description: str,
        context_length: int = 0,
        budget_limit: float = 0.0,
        strategy: str = "balanced",
    ) -> str:
        """
        智能路由：根据任务描述推荐最优 LLM 模型，并返回预估成本。

        Args:
            task_description: 任务描述（如"总结这篇文章"、"优化复杂数据库查询"）
            context_length: 需要的上下文长度（默认 0 表示不限制）
            budget_limit: 预算上限（$/1M tokens），0 表示无限制
            strategy: 路由策略：cost_first | quality_first | balanced

        Returns:
            JSON 字符串，包含 recommended_model、estimated_cost、matched_categories
        """
        try:
            budget = budget_limit if budget_limit > 0 else None
            result = _smart_router.route(
                task_description=task_description,
                context_length_required=context_length,
                max_cost_budget=budget,
                strategy=strategy,
            )
            if result:
                return json.dumps({
                    "success": True,
                    "recommended_model": result["name"],
                    "endpoint": result["endpoint"],
                    "estimated_cost_usd": result["estimated_cost"],
                    "cost_per_1m": result["cost_per_1m"],
                    "context_length": result["context_length"],
                    "matched_categories": result["matched_categories"],
                    "strategy": result["strategy"],
                }, ensure_ascii=False)
            return json.dumps({"success": False, "error": "No available model"}, ensure_ascii=False)
        except Exception as e:
            logger.exception("llm.route_task failed")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool("llm.list_models")
    def llm_list_models() -> str:
        """列出所有已注册模型。"""
        try:
            models = _llm_registry.get_models()
            return json.dumps({"success": True, "models": models}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool("llm.get_stats")
    def llm_get_stats() -> str:
        """获取 LLM 路由调用统计。"""
        try:
            stats = _smart_router.get_stats()
            return json.dumps({"success": True, "stats": stats}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    logger.info("LLM routing MCP tools registered: llm.route_task, llm.list_models, llm.get_stats")
