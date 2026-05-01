"""
WorkflowEngine — DAG-based workflow definition, parsing, validation and scheduling.

P23-001: Agent Workflow Orchestration Engine
"""

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Data Models
# --------------------------------------------------------------------------- #

@dataclass
class NodeSpec:
    """Workflow node specification."""
    id: str
    type: str  # agent | evaluator | condition | parallel | input | output
    agent: Optional[str] = None
    input_template: Optional[Dict[str, Any]] = None
    depends_on: List[str] = field(default_factory=list)
    retry_count: int = 2
    timeout_seconds: int = 300
    fallback_node: Optional[str] = None
    criteria: Optional[str] = None  # for evaluator / condition
    on_failure: str = "retry"  # retry | fallback | abort | continue
    auto_fix: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "agent": self.agent,
            "input_template": self.input_template,
            "depends_on": self.depends_on,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "fallback_node": self.fallback_node,
            "criteria": self.criteria,
            "on_failure": self.on_failure,
            "auto_fix": self.auto_fix,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeSpec":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class EdgeSpec:
    """Directed edge between two nodes."""
    source: str
    target: str
    condition: Optional[str] = None  # branch condition (for condition nodes)

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "target": self.target, "condition": self.condition}


@dataclass
class WorkflowSpec:
    """Complete workflow specification."""
    name: str
    nodes: List[NodeSpec]
    edges: List[EdgeSpec]
    description: str = ""
    version: str = "1.0"
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "context": self.context,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowSpec":
        nodes = [NodeSpec.from_dict(n) for n in data.get("nodes", [])]
        edges = [EdgeSpec(**e) for e in data.get("edges", [])]
        return cls(
            name=data.get("name", "unnamed"),
            nodes=nodes,
            edges=edges,
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            context=data.get("context", {}),
        )


@dataclass
class NodeResult:
    """Result of a single node execution."""
    node_id: str
    status: str  # pending | running | completed | failed | skipped
    output: Any = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    retries: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "timestamp": self.timestamp,
        }


@dataclass
class WorkflowResult:
    """Result of a complete workflow execution."""
    workflow_name: str
    execution_id: str
    status: str  # COMPLETED | PARTIAL | FAILED
    node_results: Dict[str, NodeResult] = field(default_factory=dict)
    total_duration_ms: Optional[float] = None
    error_summary: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "execution_id": self.execution_id,
            "status": self.status,
            "node_results": {k: v.to_dict() for k, v in self.node_results.items()},
            "total_duration_ms": self.total_duration_ms,
            "error_summary": self.error_summary,
            "context": self.context,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


# --------------------------------------------------------------------------- #
# WorkflowEngine
# --------------------------------------------------------------------------- #

class WorkflowEngine:
    """
    DAG workflow engine.

    Supports:
    - YAML/JSON parsing
    - Cycle detection
    - Topological sorting
    - Parallel execution of independent nodes
    - Variable passing via input templates
    - Condition branching
    - Retry and fallback handling
    """

    def __init__(self):
        self._executions: Dict[str, WorkflowResult] = {}

    # ------------------------------------------------------------------ #
    # Parsing
    # ------------------------------------------------------------------ #

    def parse(self, file_path: str) -> WorkflowSpec:
        """Parse a workflow from YAML or JSON file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml") and YAML_AVAILABLE:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)

        return WorkflowSpec.from_dict(data)

    def parse_json(self, json_str: str) -> WorkflowSpec:
        """Parse a workflow from JSON string."""
        data = json.loads(json_str)
        return WorkflowSpec.from_dict(data)

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate(self, spec: WorkflowSpec) -> List[str]:
        """
        Validate a workflow spec.
        Returns a list of error messages (empty if valid).
        """
        errors = []
        node_ids = {n.id for n in spec.nodes}

        # Check for duplicate node IDs
        seen_ids: Set[str] = set()
        for node in spec.nodes:
            if node.id in seen_ids:
                errors.append(f"Duplicate node ID: {node.id}")
            seen_ids.add(node.id)

        # Check edge references
        for edge in spec.edges:
            if edge.source not in node_ids:
                errors.append(f"Edge references unknown source node: {edge.source}")
            if edge.target not in node_ids:
                errors.append(f"Edge references unknown target node: {edge.target}")

        # Check depends_on references
        for node in spec.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    errors.append(f"Node '{node.id}' depends_on unknown node: {dep}")

        # Check fallback_node references
        for node in spec.nodes:
            if node.fallback_node and node.fallback_node not in node_ids:
                errors.append(f"Node '{node.id}' fallback_node unknown: {node.fallback_node}")

        # Cycle detection
        cycle = self._detect_cycle(spec)
        if cycle:
            errors.append(f"Cycle detected in workflow: {' -> '.join(cycle)}")

        # Check for orphaned nodes (no edges and not input/output)
        edge_nodes = set()
        for edge in spec.edges:
            edge_nodes.add(edge.source)
            edge_nodes.add(edge.target)
        for node in spec.nodes:
            if node.id not in edge_nodes and node.type not in ("input", "output"):
                errors.append(f"Node '{node.id}' is orphaned (no edges)")

        return errors

    def _detect_cycle(self, spec: WorkflowSpec) -> Optional[List[str]]:
        """Detect cycles using DFS. Returns the cycle path if found."""
        adj: Dict[str, List[str]] = {n.id: [] for n in spec.nodes}
        for edge in spec.edges:
            adj[edge.source].append(edge.target)
        # Also include depends_on
        for node in spec.nodes:
            for dep in node.depends_on:
                if dep not in adj:
                    adj[dep] = []
                if node.id not in adj[dep]:
                    adj[dep].append(node.id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in adj}
        parent = {}

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            color[node] = GRAY
            path.append(node)
            for neighbor in adj.get(node, []):
                if color[neighbor] == GRAY:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
                if color[neighbor] == WHITE:
                    result = dfs(neighbor, path)
                    if result:
                        return result
            path.pop()
            color[node] = BLACK
            return None

        for nid in list(adj.keys()):
            if color[nid] == WHITE:
                cycle = dfs(nid, [])
                if cycle:
                    return cycle
        return None

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #

    async def execute(
        self,
        spec: WorkflowSpec,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """
        Execute a workflow spec asynchronously.

        Execution strategy:
        1. Build dependency graph (edges + depends_on)
        2. Topological sort for ordering
        3. Execute ready nodes in parallel (asyncio.gather)
        4. Pass outputs to downstream nodes via template rendering
        5. Handle retries and fallbacks
        """
        execution_id = f"wfexec_{uuid.uuid4().hex[:10]}"
        merged_context = {**(spec.context or {}), **(context or {})}

        result = WorkflowResult(
            workflow_name=spec.name,
            execution_id=execution_id,
            status="running",
            context=merged_context,
        )
        self._executions[execution_id] = result

        # Build adjacency and in-degree
        adj, in_degree = self._build_graph(spec)
        node_map = {n.id: n for n in spec.nodes}
        ready = [nid for nid, deg in in_degree.items() if deg == 0]

        # Initialize node results
        for nid in node_map:
            result.node_results[nid] = NodeResult(node_id=nid, status="pending")

        try:
            while ready:
                # Execute ready nodes in parallel
                batch = ready[:]
                ready = []

                await asyncio.gather(
                    *[self._execute_node_with_retry(nid, node_map[nid], result, merged_context) for nid in batch]
                )

                # Update downstream nodes
                for nid in batch:
                    for downstream in adj.get(nid, []):
                        in_degree[downstream] -= 1
                        if in_degree[downstream] == 0:
                            ready.append(downstream)

            # Determine final status
            failed = [r for r in result.node_results.values() if r.status == "failed"]
            if failed:
                if len(failed) == len(spec.nodes):
                    result.status = "FAILED"
                else:
                    result.status = "PARTIAL"
                result.error_summary = [f"{r.node_id}: {r.error}" for r in failed]
            else:
                result.status = "COMPLETED"

        except Exception as e:
            logger.exception(f"Workflow execution failed: {e}")
            result.status = "FAILED"
            result.error_summary.append(str(e))

        finally:
            result.end_time = time.time()
            result.total_duration_ms = (result.end_time - result.start_time) * 1000

        return result

    def _build_graph(self, spec: WorkflowSpec) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
        """Build adjacency list and in-degree from edges + depends_on."""
        adj: Dict[str, List[str]] = {n.id: [] for n in spec.nodes}
        in_degree: Dict[str, int] = {n.id: 0 for n in spec.nodes}

        for edge in spec.edges:
            adj[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        for node in spec.nodes:
            for dep in node.depends_on:
                if dep in adj and node.id not in adj[dep]:
                    adj[dep].append(node.id)
                    in_degree[node.id] += 1

        return adj, in_degree

    async def _execute_node_with_retry(
        self,
        node_id: str,
        node: NodeSpec,
        result: WorkflowResult,
        context: Dict[str, Any],
    ) -> None:
        """Execute a single node with retry logic."""
        node_result = result.node_results[node_id]
        node_result.status = "running"
        start = time.time()

        last_error = None
        for attempt in range(node.retry_count + 1):
            try:
                output = await self._execute_node(node, result, context)
                node_result.output = output
                node_result.status = "completed"
                node_result.retries = attempt
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Node {node_id} attempt {attempt + 1} failed: {e}")
                if attempt < node.retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))  # exponential-ish backoff
                else:
                    # All retries exhausted
                    if node.fallback_node:
                        logger.info(f"Node {node_id} falling back to {node.fallback_node}")
                        try:
                            fallback_output = await self._execute_fallback(node, result, context)
                            node_result.output = fallback_output
                            node_result.status = "completed"
                            node_result.retries = node.retry_count
                        except Exception as fallback_err:
                            node_result.status = "failed"
                            node_result.error = f"{last_error} | fallback failed: {fallback_err}"
                    else:
                        node_result.status = "failed"
                        node_result.error = last_error

        node_result.duration_ms = (time.time() - start) * 1000

    async def _execute_node(
        self,
        node: NodeSpec,
        result: WorkflowResult,
        context: Dict[str, Any],
    ) -> Any:
        """
        Execute a single node. To be overridden by subclasses.
        Base implementation provides simulation for testing.
        """
        # Render input template with upstream outputs + context
        inputs = self._render_inputs(node, result, context)

        if node.type == "condition":
            return self._evaluate_condition(node, inputs, result)

        if node.type == "parallel":
            # Parallel node: execute sub-workflow or gather multiple tasks
            return {"parallel_input": inputs, "status": "gathered"}

        if node.type == "input":
            return inputs

        if node.type == "output":
            return inputs

        # Default: agent / evaluator simulation
        await asyncio.sleep(0.01)  # simulate async work
        return {"node_type": node.type, "agent": node.agent, "inputs": inputs}

    async def _execute_fallback(
        self,
        node: NodeSpec,
        result: WorkflowResult,
        context: Dict[str, Any],
    ) -> Any:
        """Execute fallback node. Base implementation returns a placeholder."""
        return {"fallback": True, "original_node": node.id}

    def _render_inputs(
        self,
        node: NodeSpec,
        result: WorkflowResult,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Render input template by substituting upstream outputs and context variables."""
        template = node.input_template or {}
        rendered = {}

        for key, value in template.items():
            if isinstance(value, str):
                rendered[key] = self._render_template_string(value, result, context)
            else:
                rendered[key] = value

        # Merge with context overrides
        rendered.update({k: v for k, v in context.items() if k not in rendered})
        return rendered

    def _render_template_string(
        self,
        template: str,
        result: WorkflowResult,
        context: Dict[str, Any],
    ) -> Any:
        """Render a template string by substituting variables."""
        # Pattern: {{node_id.output_key}} or {{context_key}}
        pattern = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")

        def replacer(match: re.Match) -> str:
            var_path = match.group(1).strip()
            parts = var_path.split(".")

            # Check context first
            if len(parts) == 1 and parts[0] in context:
                val = context[parts[0]]
                return str(val) if val is not None else ""

            # Check upstream node outputs: node_id.output_key
            if len(parts) >= 2:
                node_id = parts[0]
                output_key = ".".join(parts[1:])
                upstream = result.node_results.get(node_id)
                if upstream and upstream.output:
                    output = upstream.output
                    if isinstance(output, dict):
                        # Traverse nested keys
                        current = output
                        for part in parts[1:]:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                return match.group(0)  # leave unchanged
                        return str(current) if current is not None else ""
                    else:
                        return str(output)

            return match.group(0)  # leave unchanged if not found

        # If the entire string is a single variable reference, return the raw value
        full_match = pattern.fullmatch(template)
        if full_match:
            var_path = full_match.group(1).strip()
            parts = var_path.split(".")
            if len(parts) >= 2:
                node_id = parts[0]
                upstream = result.node_results.get(node_id)
                if upstream and upstream.output:
                    output = upstream.output
                    if isinstance(output, dict) and len(parts) > 1:
                        current = output
                        for part in parts[1:]:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                break
                        else:
                            return current
                    return output
            elif len(parts) == 1 and parts[0] in context:
                return context[parts[0]]

        return pattern.sub(replacer, template)

    def _evaluate_condition(
        self,
        node: NodeSpec,
        inputs: Dict[str, Any],
        result: WorkflowResult,
    ) -> Dict[str, Any]:
        """Evaluate a condition node. Returns branch selection info."""
        criteria = node.criteria or "true"
        try:
            eval_locals = dict(inputs)
            # Flatten upstream outputs so nested keys become top-level variables
            for nid, nr in result.node_results.items():
                if nr.status == "completed" and nr.output is not None:
                    if isinstance(nr.output, dict):
                        for k, v in nr.output.items():
                            if k not in eval_locals:
                                eval_locals[k] = v
                    else:
                        if nid not in eval_locals:
                            eval_locals[nid] = nr.output
            passed = bool(eval(criteria, {"__builtins__": {}}, eval_locals))
            return {"passed": passed, "criteria": criteria, "inputs": inputs}
        except Exception as e:
            logger.warning(f"Condition evaluation failed for node {node.id}: {e}")
            return {"passed": False, "criteria": criteria, "error": str(e), "inputs": inputs}

    def get_execution(self, execution_id: str) -> Optional[WorkflowResult]:
        """Get a workflow execution result by ID."""
        return self._executions.get(execution_id)

    def list_executions(self) -> List[Dict[str, Any]]:
        """List all execution results."""
        return [r.to_dict() for r in self._executions.values()]
