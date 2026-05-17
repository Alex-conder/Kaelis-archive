"""
Pipeline 流程编排引擎

实现配置驱动的知识图谱构建闭环。
用户可通过 YAML/JSON 配置定义流程步骤，
系统按顺序执行，支持条件分支、并行执行、失败降级。

示例配置：
    pipeline:
      name: "kg_build_v2"
      steps:
        - id: extract
          type: extract
          extractor: oneke
          input: text
          output: triples
          fallback: mock
        
        - id: store_neo4j
          type: store
          storage: neo4j
          input: triples
          condition: "len(triples) > 0"
        
        - id: store_nebula
          type: store
          storage: nebula
          input: triples
          condition: "len(triples) > 0"
          on_error: skip
        
        - id: query_validate
          type: query
          storage: neo4j
          query: "MATCH (n) RETURN count(n) as total"
          output: stats
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from core.plugins import get_plugin_registry

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(Enum):
    EXTRACT = "extract"
    STORE = "store"
    QUERY = "query"
    TRANSFORM = "transform"
    CUSTOM = "custom"


@dataclass
class PipelineStep:
    """流程步骤定义"""
    id: str
    type: StepType
    input: str = "text"           # 输入上下文 key
    output: str = ""              # 输出上下文 key
    extractor: str = ""           # EXTRACT 步骤专用
    storage: str = ""             # STORE/QUERY 步骤专用
    query: str = ""               # QUERY 步骤专用
    condition: str = ""           # 执行条件（Python 表达式）
    on_error: str = "fail"        # 错误处理：fail / skip / retry
    fallback: str = ""            # 降级策略（如 extractor fallback）
    max_retries: int = 0
    timeout: int = 30
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """步骤执行结果"""
    step_id: str
    status: StepStatus
    data: Any = None
    error: Optional[str] = None
    elapsed_ms: int = 0
    retries: int = 0


@dataclass
class PipelineResult:
    """流程执行结果"""
    pipeline_name: str
    success: bool
    context: Dict[str, Any]
    steps: List[StepResult]
    total_elapsed_ms: int = 0


class PipelineEngine:
    """
    流程编排引擎。

    职责：
    1. 解析 PipelineStep 列表
    2. 按顺序执行每一步
    3. 管理执行上下文（context）
    4. 处理条件判断、错误降级、超时控制
    """

    def __init__(self, steps: List[PipelineStep], name: str = "default"):
        self.name = name
        self.steps = steps
        self.registry = get_plugin_registry()

    def run(self, initial_context: Dict[str, Any]) -> PipelineResult:
        """
        执行完整流程。

        Args:
            initial_context: 初始上下文，例如 {"text": "...", "schema": {...}}

        Returns:
            PipelineResult
        """
        context = dict(initial_context)
        step_results: List[StepResult] = []
        overall_start = time.time()

        for step in self.steps:
            result = self._execute_step(step, context)
            step_results.append(result)

            if result.status == StepStatus.SUCCESS and step.output:
                context[step.output] = result.data

            # 严重错误时中断流程
            if result.status == StepStatus.FAILED and step.on_error == "fail":
                logger.error(f"Pipeline [{self.name}] interrupted at step '{step.id}': {result.error}")
                break

        total_elapsed = int((time.time() - overall_start) * 1000)
        success = all(r.status in (StepStatus.SUCCESS, StepStatus.SKIPPED) for r in step_results)

        return PipelineResult(
            pipeline_name=self.name,
            success=success,
            context=context,
            steps=step_results,
            total_elapsed_ms=total_elapsed
        )

    def _execute_step(self, step: PipelineStep, context: Dict[str, Any]) -> StepResult:
        """执行单个步骤"""
        start = time.time()

        # 1. 条件判断
        if step.condition:
            try:
                condition_met = eval(step.condition, {"__builtins__": {}}, context)
                if not condition_met:
                    logger.debug(f"Step '{step.id}' skipped by condition")
                    return StepResult(step_id=step.id, status=StepStatus.SKIPPED, elapsed_ms=0)
            except Exception as e:
                logger.warning(f"Step '{step.id}' condition eval failed: {e}")
                # 条件判断失败时保守执行（不跳过）

        # 2. 执行
        retries = 0
        last_error = None

        while retries <= step.max_retries:
            try:
                data = self._dispatch_step(step, context)
                elapsed = int((time.time() - start) * 1000)
                return StepResult(step_id=step.id, status=StepStatus.SUCCESS, data=data, elapsed_ms=elapsed, retries=retries)
            except Exception as e:
                last_error = str(e)
                retries += 1
                logger.warning(f"Step '{step.id}' attempt {retries} failed: {e}")
                if retries <= step.max_retries:
                    time.sleep(0.5 * retries)

        # 3. 错误处理
        elapsed = int((time.time() - start) * 1000)
        if step.on_error == "skip":
            logger.info(f"Step '{step.id}' failed, skipping as configured")
            return StepResult(step_id=step.id, status=StepStatus.SKIPPED, error=last_error, elapsed_ms=elapsed, retries=retries)

        return StepResult(step_id=step.id, status=StepStatus.FAILED, error=last_error, elapsed_ms=elapsed, retries=retries)

    def _dispatch_step(self, step: PipelineStep, context: Dict[str, Any]) -> Any:
        """根据步骤类型分发到具体处理器"""
        if step.type == StepType.EXTRACT:
            return self._handle_extract(step, context)
        elif step.type == StepType.STORE:
            return self._handle_store(step, context)
        elif step.type == StepType.QUERY:
            return self._handle_query(step, context)
        elif step.type == StepType.TRANSFORM:
            return self._handle_transform(step, context)
        elif step.type == StepType.CUSTOM:
            return self._handle_custom(step, context)
        else:
            raise ValueError(f"Unknown step type: {step.type}")

    def _handle_extract(self, step: PipelineStep, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """处理抽取步骤"""
        text = context.get(step.input, "")
        schema = context.get("schema")

        extractor = self.registry.get_extractor(step.extractor)
        if extractor is None or not extractor.available:
            # 尝试 fallback
            if step.fallback:
                logger.info(f"Extractor '{step.extractor}' unavailable, fallback to '{step.fallback}'")
                extractor = self.registry.get_extractor(step.fallback)
            if extractor is None or not extractor.available:
                raise RuntimeError(f"No available extractor (tried: {step.extractor}, fallback: {step.fallback})")

        return extractor.extract(text, schema=schema)

    def _handle_store(self, step: PipelineStep, context: Dict[str, Any]) -> Dict[str, int]:
        """处理存储步骤"""
        triples = context.get(step.input, [])
        if not isinstance(triples, list):
            raise ValueError(f"Store step input '{step.input}' must be a list of triples")

        storage = self.registry.get_storage(step.storage)
        if storage is None:
            raise RuntimeError(f"Storage '{step.storage}' not found")
        if not storage.available:
            raise RuntimeError(f"Storage '{step.storage}' not available")

        inserted = 0
        failed = 0
        for t in triples:
            if storage.upsert_triple(t):
                inserted += 1
            else:
                failed += 1

        return {"inserted": inserted, "failed": failed}

    def _handle_query(self, step: PipelineStep, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """处理查询步骤"""
        storage = self.registry.get_storage(step.storage)
        if storage is None or not storage.available:
            raise RuntimeError(f"Storage '{step.storage}' not available for query")

        query = step.query
        # 支持简单的模板替换，例如 {{total}} -> context['total']
        for key, val in context.items():
            if isinstance(val, str):
                query = query.replace(f"{{{{{key}}}}}", val)

        return storage.execute(query)

    def _handle_transform(self, step: PipelineStep, context: Dict[str, Any]) -> Any:
        """处理转换步骤（执行用户提供的 lambda 或函数）"""
        transform_fn = step.params.get("fn")
        if transform_fn and callable(transform_fn):
            return transform_fn(context)
        # 默认返回输入数据
        return context.get(step.input)

    def _handle_custom(self, step: PipelineStep, context: Dict[str, Any]) -> Any:
        """处理自定义步骤"""
        custom_fn = step.params.get("handler")
        if custom_fn and callable(custom_fn):
            return custom_fn(step, context)
        raise ValueError(f"Custom step '{step.id}' requires a callable handler in params")


# ------------------------------------------------------------------
# 预设流程模板
# ------------------------------------------------------------------

def create_default_pipeline() -> PipelineEngine:
    """创建默认的知识图谱构建流程"""
    steps = [
        PipelineStep(
            id="extract",
            type=StepType.EXTRACT,
            extractor="oneke",
            input="text",
            output="triples",
            fallback="llm",
            on_error="fail"
        ),
        PipelineStep(
            id="store_primary",
            type=StepType.STORE,
            storage="neo4j",
            input="triples",
            condition="len(triples) > 0",
            on_error="fail"
        ),
        PipelineStep(
            id="store_secondary",
            type=StepType.STORE,
            storage="nebula",
            input="triples",
            condition="len(triples) > 0",
            on_error="skip"  # Nebula 为补充存储，失败不阻断
        ),
        PipelineStep(
            id="validate",
            type=StepType.QUERY,
            storage="neo4j",
            query="MATCH (n) RETURN count(n) as total",
            output="stats",
            on_error="skip"
        ),
    ]
    return PipelineEngine(steps, name="kg_build_default")


def create_extraction_only_pipeline(extractor: str = "llm") -> PipelineEngine:
    """创建仅抽取流程（不写入存储）"""
    steps = [
        PipelineStep(
            id="extract",
            type=StepType.EXTRACT,
            extractor=extractor,
            input="text",
            output="triples",
            fallback="mock"
        ),
    ]
    return PipelineEngine(steps, name=f"extract_only_{extractor}")
