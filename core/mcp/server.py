"""
Kaelis MCP Server

将 Kaelis 核心能力暴露为 MCP Tools 和 Resources，
供 Claude Desktop、Cursor 等支持 MCP 的客户端调用。

传输方式：stdio（默认，兼容 Claude Desktop）

已注册 Tools:
    基础记忆:
    - memory_search(layer, query, top_k)
    - memory_write(layer, key, value, metadata)
    - memory_get(layer, key)
    共享记忆空间 (Sprint 5-7):
    - memory_remember(space_id, key, value, tags, metadata, ttl_seconds)
    - memory_recall(space_id, query, top_k, exact_key, tags)
    - memory_forget(space_id, key, reason)
    - memory_evolve(space_id, task_type, focus_keys)
    - memory_subscribe(space_id, tags, query_pattern)
    技能与洞察:
    - skill_list(task_type_filter)
    - skill_get(skill_id)
    - daily_insight_generate()

已注册 Resources:
    - memory://{layer}/{key}
    - skill://{skill_id}

用法：
    python -m core.mcp.server
    # 或
    python core/mcp/server.py
"""

import json
import logging
import sys
from typing import Any, Dict, List, Optional

# 确保项目根目录在路径中
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ======================================================================
# Lazy imports (避免在模块导入时初始化全局单例)
# ======================================================================

def _get_mm():
    from core.memory_manager_v2 import get_memory_manager
    return get_memory_manager()


def _get_fts():
    from core.memory_fts import get_fts
    return get_fts()


def _get_sm():
    from core.skill_manager import get_skill_manager
    return get_skill_manager()


def _get_proactive():
    from core.memory_proactive import get_proactive_engine
    return get_proactive_engine()


def _get_sms():
    from core.shared_memory_space import get_shared_memory_space
    return get_shared_memory_space()


def _get_evolution():
    from core.self_evolving import get_evolution_engine
    return get_evolution_engine()


def _get_agent_registry():
    from core.agent_registry import AgentRegistry
    from core.security.credential_vault import CredentialVault
    mm = _get_mm()
    vault = CredentialVault()
    return AgentRegistry(mm, vault)


def _get_sensor_registry():
    from core.context.sensor_base import SensorRegistry
    from core.context.sensors import FileChangeSensor, ProcessSensor
    registry = SensorRegistry()
    registry.register(FileChangeSensor())
    registry.register(ProcessSensor())
    return registry


def _get_pubsub():
    from core.semantic_pubsub import get_pubsub_engine
    return get_pubsub_engine()


# ======================================================================
# FastMCP Server
# ======================================================================

def create_mcp_server(name: str = "Kaelis") -> Any:
    """
    创建并配置 Kaelis MCP Server。
    返回 FastMCP 实例（如果 mcp 可用），否则返回 None。
    """
    try:
        from mcp.server import FastMCP
    except ImportError:
        logger.error("mcp package not installed. Run: pip install mcp")
        return None

    mcp = FastMCP(name, instructions="Kaelis 记忆中枢与技能进化引擎。提供记忆读写、全文搜索、技能管理、共享记忆空间和每日洞察生成能力。")

    # ------------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------------ #

    @mcp.tool()
    def memory_search(layer: str, query: str, top_k: int = 5, agent_id: str = "") -> str:
        """
        搜索记忆（支持 L1/L2/L3）。
        优先使用 FTS5，回退到 LIKE 匹配。
        agent_id 为空字符串时不过滤 Agent。
        """
        try:
            if layer.upper() not in ("L1", "L2", "L3"):
                return json.dumps({"error": f"Unsupported layer: {layer}"}, ensure_ascii=False)

            # 先尝试 FTS
            fts = _get_fts()
            results = fts.search(layer, query, top_k)
            method = "fts5"

            # FTS 无结果时回退 LIKE
            if not results and layer.upper() in ("L1", "L2"):
                mm = _get_mm()
                aid = agent_id if agent_id else None
                results = mm.search(layer, query, top_k, agent_id=aid)
                method = "like"

            return json.dumps({
                "success": True,
                "method": method,
                "count": len(results),
                "results": results,
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"memory_search error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def memory_get(layer: str, key: str, agent_id: str = "") -> str:
        """读取指定层和 key 的记忆。agent_id 为空字符串时不过滤 Agent。"""
        try:
            mm = _get_mm()
            aid = agent_id if agent_id else None
            result = mm.read(layer, key, agent_id=aid)
            if result is None:
                return json.dumps({"found": False}, ensure_ascii=False)
            return json.dumps({"found": True, "data": result}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"memory_get error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def memory_write(layer: str, key: str, value: str, metadata: str = "{}", agent_id: str = "kaelis_self") -> str:
        """
        写入记忆。value 为 JSON 字符串，metadata 为可选 JSON 字符串。
        agent_id 默认为 kaelis_self（Kaelis 自身操作）。
        """
        try:
            parsed_value = json.loads(value)
            parsed_meta = json.loads(metadata) if metadata else {}
            mm = _get_mm()
            ok = mm.write(layer, key, parsed_value, metadata=parsed_meta, agent_id=agent_id)
            return json.dumps({"success": ok}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"memory_write error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def skill_list(task_type_filter: str = "") -> str:
        """列出技能，可传入 task_type 过滤。"""
        try:
            sm = _get_sm()
            skills = sm.list_skills(task_type=task_type_filter or None, sort_by="rating")
            data = [
                {
                    "id": s.id,
                    "name": s.name,
                    "task_type": s.task_type,
                    "rating": s.rating,
                    "success_rate": s.success_rate,
                    "usage_count": s.usage_count,
                    "source": s.source,
                }
                for s in skills
            ]
            return json.dumps({"count": len(data), "skills": data}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"skill_list error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def skill_get(skill_id: str) -> str:
        """获取单个技能的详细信息。"""
        try:
            sm = _get_sm()
            skill = sm.storage.get(skill_id)
            if skill is None:
                return json.dumps({"found": False}, ensure_ascii=False)
            return json.dumps({"found": True, "skill": skill.to_dict()}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"skill_get error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def daily_insight_generate() -> str:
        """生成每日洞察报告（Markdown 格式）。"""
        try:
            from scripts.generate_daily_insight import generate_daily_insight
            content = generate_daily_insight(use_llm=False)
            return json.dumps({"success": True, "content": content}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"daily_insight_generate error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def proactive_push(context: str = "") -> str:
        """获取主动记忆推送包。"""
        try:
            engine = _get_proactive()
            bundle = engine.generate_push_bundle(context=context)
            return json.dumps({"success": True, "bundle": bundle.to_dict()}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"proactive_push error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def _format_push_message(memories: List[Dict[str, Any]]) -> str:
        """将记忆列表格式化为推送文本。"""
        if not memories:
            return ""
        lines = ["💡 Kaelis 记忆推送:"]
        for i, m in enumerate(memories[:5], 1):
            reason = m.get("reason", "相关记忆")
            value = m.get("value", "")
            if isinstance(value, dict):
                summary = value.get("summary", value.get("decision", str(value)[:80]))
            else:
                summary = str(value)[:80]
            lines.append(f"  {i}. [{reason}] {summary}")
        return "\n".join(lines)

    @mcp.tool()
    def context_aware_push(current_context: str = "", user_id: str = "default", limit: int = 5) -> str:
        """
        基于当前对话上下文，推送相关记忆。
        供浏览器扩展或 Claude 轮询调用。
        """
        try:
            engine = _get_proactive()
            bundle = engine.generate_push_bundle(context=current_context, user_id=user_id)
            memories = [m.to_dict() for m in bundle.all_memories()[:limit]]
            push_text = _format_push_message(memories) if memories else ""
            return json.dumps({
                "has_memories": len(memories) > 0,
                "push_message": push_text,
                "memories": memories,
                "suggested_action": "copy_to_clipboard" if memories else "none"
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"context_aware_push error: {e}")
            return json.dumps({
                "has_memories": False,
                "push_message": "",
                "memories": [],
                "suggested_action": "none",
                "error": str(e)
            }, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Shared Memory Space Tools (Sprint 5-7)
    # ------------------------------------------------------------------ #

    @mcp.tool()
    def memory_remember(
        space_id: str,
        key: str,
        value: str,
        tags: str = "[]",
        metadata: str = "{}",
        ttl_seconds: int = 0,
        user_id: str = "anonymous",
    ) -> str:
        """
        在共享记忆空间中保存一条记忆。如果 key 已存在则覆盖（版本号自动递增）。
        value 为 JSON 字符串；tags 和 metadata 也为 JSON 字符串。
        """
        try:
            sms = _get_sms()
            parsed_value = json.loads(value)
            parsed_tags = json.loads(tags) if tags else []
            parsed_meta = json.loads(metadata) if metadata else {}
            ttl = ttl_seconds if ttl_seconds > 0 else None
            result = sms.write_memory(
                space_id=space_id,
                key=key,
                value=parsed_value,
                user_id=user_id,
                tags=parsed_tags,
                metadata=parsed_meta,
                ttl_seconds=ttl,
            )
            return json.dumps({"success": True, "data": result}, ensure_ascii=False, default=str)
        except PermissionError as e:
            return json.dumps({"success": False, "error": "permission_denied", "message": str(e)}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"memory_remember error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def memory_recall(
        space_id: str,
        query: str,
        top_k: int = 10,
        exact_key: bool = False,
        tags: str = "[]",
        user_id: str = "anonymous",
    ) -> str:
        """
        在共享记忆空间中搜索/回忆记忆。
        exact_key=true 时精确匹配 key；否则使用 FTS5/LIKE 搜索。
        tags 为 JSON 字符串数组，用于过滤（预留，当前仅记录）。
        """
        try:
            sms = _get_sms()
            results = sms.search_memory(
                space_id=space_id,
                query=query,
                user_id=user_id,
                top_k=top_k,
                exact_key=exact_key,
            )
            return json.dumps({
                "success": True,
                "count": len(results),
                "results": results,
            }, ensure_ascii=False, default=str)
        except PermissionError as e:
            return json.dumps({"success": False, "error": "permission_denied", "message": str(e)}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"memory_recall error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def memory_forget(
        space_id: str,
        key: str,
        reason: str = "",
        user_id: str = "anonymous",
    ) -> str:
        """
        从共享记忆空间中删除一条记忆。记录删除原因到审计日志。
        需要 writer 权限（删除自己的）或 admin 权限（删除任何）。
        """
        try:
            sms = _get_sms()
            ok = sms.delete_memory(space_id=space_id, key=key, user_id=user_id, reason=reason)
            return json.dumps({"success": ok, "message": f"Memory '{key}' deleted"}, ensure_ascii=False)
        except PermissionError as e:
            return json.dumps({"success": False, "error": "permission_denied", "message": str(e)}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"memory_forget error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def memory_evolve(
        space_id: str,
        task_type: str = "",
        focus_keys: str = "[]",
        user_id: str = "anonymous",
    ) -> str:
        """
        触发自我进化引擎，对共享空间内的特定记忆进行迭代优化。
        focus_keys 为 JSON 字符串数组，指定要进化的记忆 key。
        如果 focus_keys 为空，则对整个空间触发一般性进化。
        需要 admin 或 owner 权限。
        """
        try:
            sms = _get_sms()
            # Verify permission
            if not sms._check_permission(space_id, user_id, "admin"):
                return json.dumps({"success": False, "error": "permission_denied", "message": "Admin permission required"}, ensure_ascii=False)

            parsed_keys = json.loads(focus_keys) if focus_keys else []
            engine = _get_evolution()

            evolved = []
            for key in parsed_keys:
                try:
                    mem = sms.read_memory(space_id, key, user_id=user_id)
                    # Trigger a lightweight evolution on this memory
                    # Wrap in a simple execution function
                    def _exec(params):
                        return {"result": mem["value"], "confidence": 0.5}

                    from core.self_evolving import TaskExpectation
                    expectation = TaskExpectation(
                        criteria="Improve clarity and completeness of shared memory",
                        evaluation_method="rule",
                        target_confidence=0.7,
                        max_iterations=2,
                    )
                    record = engine.evolve(
                        execution_id=f"shared-{space_id}-{key}-{int(time.time())}",
                        task_type=task_type or "memory_enhancement",
                        initial_params={"value": mem["value"]},
                        expectation=expectation,
                        execution_func=_exec,
                    )
                    evolved.append({
                        "key": key,
                        "status": record.status,
                        "best_confidence": record.best_confidence,
                    })
                except Exception as inner_e:
                    evolved.append({"key": key, "status": "error", "error": str(inner_e)})

            return json.dumps({"success": True, "evolved": evolved}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"memory_evolve error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def memory_subscribe(
        space_id: str,
        tags: str = "[]",
        query_pattern: str = "",
        similarity_threshold: float = 0.8,
        user_id: str = "anonymous",
    ) -> str:
        """
        订阅共享记忆空间的变更通知 (Sprint 7 D10)。
        当匹配 tags 或 query_pattern 的记忆被写入/修改时，会收到通知。
        使用语义发布-订阅引擎实现真正的订阅匹配。
        需要 reader 权限。
        """
        try:
            sms = _get_sms()
            if not sms._check_permission(space_id, user_id, "reader"):
                return json.dumps({"success": False, "error": "permission_denied", "message": "Reader permission required"}, ensure_ascii=False)

            parsed_tags = json.loads(tags) if tags else []
            pubsub = _get_pubsub()
            sub_id = pubsub.subscribe(
                space_id=space_id,
                tags=parsed_tags,
                query_pattern=query_pattern,
                similarity_threshold=similarity_threshold,
            )
            return json.dumps({
                "success": True,
                "subscription_id": sub_id,
                "space_id": space_id,
                "tags": parsed_tags,
                "query_pattern": query_pattern,
                "similarity_threshold": similarity_threshold,
                "polling_endpoint": f"/api/pubsub/subscriptions/{sub_id}/history",
                "note": "Subscription is active. Use the polling endpoint to retrieve delivery history.",
            }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"memory_subscribe error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Context Sensor Tools (Prompt 3)
    # ------------------------------------------------------------------ #

    @mcp.tool()
    def context_sensor_list() -> str:
        """List all registered context sensors."""
        try:
            import json
            registry = _get_sensor_registry()
            sensors = registry.list_sensors()
            return json.dumps({"success": True, "sensors": sensors}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"context_sensor_list error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def context_sensor_trigger(sensor_id: str) -> str:
        """Force-trigger a sensor snapshot."""
        try:
            import json
            registry = _get_sensor_registry()
            snapshot = registry.trigger(sensor_id)
            if snapshot is None:
                return json.dumps({"success": False, "error": "Sensor not found"}, ensure_ascii=False)
            return json.dumps({"success": True, "snapshot": snapshot.to_dict()}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"context_sensor_trigger error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def context_snapshot_diff(sensor_id: str) -> str:
        """Get a diff snapshot from a sensor (returns None if no change)."""
        try:
            import json
            registry = _get_sensor_registry()
            snapshot = registry.diff(sensor_id)
            if snapshot is None:
                return json.dumps({"success": True, "changed": False}, ensure_ascii=False)
            return json.dumps({"success": True, "changed": True, "snapshot": snapshot.to_dict()}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"context_snapshot_diff error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Agent Registry Tools (Prompt 1)
    # ------------------------------------------------------------------ #

    @mcp.tool()
    def agent_register(
        agent_name: str,
        agent_type: str,
        service_name: str,
        capabilities: str = "[]",
        endpoint: str = "",
        user_id: str = "anonymous",
    ) -> str:
        """Register a new agent. capabilities is a JSON string array."""
        try:
            import json
            registry = _get_agent_registry()
            caps = json.loads(capabilities) if capabilities else []
            agent_id = registry.register(
                user_id=user_id,
                agent_name=agent_name,
                agent_type=agent_type,
                service_name=service_name,
                capabilities=caps,
                endpoint=endpoint or None,
            )
            return json.dumps({"success": True, "agent_id": agent_id}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"agent_register error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def agent_list(user_id: str = "anonymous") -> str:
        """List all registered agents for a user."""
        try:
            import json
            registry = _get_agent_registry()
            agents = registry.list_agents(user_id)
            return json.dumps({"success": True, "count": len(agents), "agents": agents}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"agent_list error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Risk Gateway Tools (Prompt 4)
    # ------------------------------------------------------------------ #

    @mcp.tool()
    def risk_audit_query(start_time: str = "", end_time: str = "", source_id: str = "") -> str:
        """Query risk audit log by time range and/or source_id."""
        try:
            from core.security.risk_gateway import RiskAwareGateway
            gateway = RiskAwareGateway()
            st = float(start_time) if start_time else None
            et = float(end_time) if end_time else None
            sid = source_id if source_id else None
            logs = gateway.audit_log(start_time=st, end_time=et, source_id=sid)
            return json.dumps({"success": True, "count": len(logs), "logs": logs}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"risk_audit_query error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def risk_threshold_adjust(rule_name: str, threshold: str = "") -> str:
        """Placeholder for adjusting risk thresholds. Currently records the request."""
        try:
            return json.dumps({"success": True, "message": f"Threshold adjustment for '{rule_name}' recorded."}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"risk_threshold_adjust error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    async def agent_call_api(agent_id: str, service_name: str, endpoint: str, params: str = "{}") -> str:
        """
        Call a user API through the secure proxy.
        Automatically retrieves the API key from the credential vault.
        """
        try:
            import json
            from core.security.api_proxy import APIProxy
            from core.security.credential_vault import CredentialVault
            from core.security.risk_gateway import RiskAwareGateway
            parsed_params = json.loads(params) if params else {}
            proxy = APIProxy(vault=CredentialVault(), gateway=RiskAwareGateway())
            # user_id is inferred from agent context; here we use a default for MCP
            result = await proxy.call_user_api(
                agent_id=agent_id,
                user_id="anonymous",
                service_name=service_name,
                endpoint=endpoint,
                params=parsed_params,
            )
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"agent_call_api error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Multi-Agent Evolution Tools (Prompt 6)
    # ------------------------------------------------------------------ #

    @mcp.tool()
    def evolution_analyze_bottleneck(days: int = 7) -> str:
        """Analyze multi-agent collaboration bottlenecks."""
        try:
            import json
            from core.evolution.multi_agent_tracker import MultiAgentEvolutionTracker
            tracker = MultiAgentEvolutionTracker(memory_manager=_get_mm())
            bottlenecks = tracker.analyze_bottleneck(days=days)
            return json.dumps({"success": True, "bottlenecks": bottlenecks}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"evolution_analyze_bottleneck error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def evolution_export_trajectory(days: int = 30, output_path: str = "data/rl_trajectories/exported.jsonl") -> str:
        """Export collaboration records as RL trajectories."""
        try:
            import json
            from core.evolution.multi_agent_tracker import MultiAgentEvolutionTracker
            tracker = MultiAgentEvolutionTracker(memory_manager=_get_mm())
            count = tracker.export_rl_trajectory(output_path=output_path, days=days)
            return json.dumps({"success": True, "exported": count, "path": output_path}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"evolution_export_trajectory error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def agent_unregister(agent_id: str) -> str:
        """Unregister an agent by ID."""
        try:
            import json
            registry = _get_agent_registry()
            ok = registry.unregister(agent_id)
            return json.dumps({"success": ok, "message": f"Agent {agent_id} unregistered" if ok else "Agent not found"}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"agent_unregister error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Resources
    # ------------------------------------------------------------------ #

    @mcp.resource("memory://{layer}/{key}")
    def memory_resource(layer: str, key: str) -> str:
        """记忆资源：memory://L1/my_key"""
        try:
            mm = _get_mm()
            result = mm.read(layer, key)
            if result is None:
                return "Memory not found"
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return f"Error: {e}"

    @mcp.resource("skill://{skill_id}")
    def skill_resource(skill_id: str) -> str:
        """技能资源：skill://my_skill_id"""
        try:
            sm = _get_sm()
            skill = sm.storage.get(skill_id)
            if skill is None:
                return "Skill not found"
            return json.dumps(skill.to_dict(), ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return f"Error: {e}"

    # Register Mesh tools (Project Mesh)
    try:
        from core.mcp.mesh_tools import register_mesh_tools
        register_mesh_tools(mcp)
    except Exception as e:
        logger.warning("Failed to register mesh tools: %s", e)

    # Register Hallucination Guard tools
    try:
        from core.hallucination.guard import register_hallucination_tools
        register_hallucination_tools(mcp)
    except Exception as e:
        logger.warning("Failed to register hallucination guard tools: %s", e)

    # Register NVIDIA NIM integration tools
    try:
        from core.integrations.nvidia_nim_manager import NIMRegistry
        _register_nim_tools(mcp)
    except Exception as e:
        logger.warning("Failed to register NIM tools: %s", e)

    # Register Physical Sensor tools
    try:
        from core.context.sensors.physical_sensor import get_physical_sensor_registry
        _register_physical_sensor_tools(mcp)
    except Exception as e:
        logger.warning("Failed to register physical sensor tools: %s", e)

    # Register Hardware Trust tools
    try:
        from core.security.hardware_trust import register_hardware_trust_tools
        register_hardware_trust_tools(mcp)
    except Exception as e:
        logger.warning("Failed to register hardware trust tools: %s", e)

    # ------------------------------------------------------------------ #
    # File Operations (Secure Gateway + Semantic Index)
    # ------------------------------------------------------------------ #
    try:
        from core.security.file_gateway import FileGateway, FileOperationRequest, FileOperationType
        from core.context.sensors.file_sensor import FileIndexer

        _file_gateway = FileGateway()
        _file_indexer = FileIndexer()

        @mcp.tool("file.secure_operation")
        def file_secure_operation(
            source: str,
            operation: str,
            file_path: str,
            content: str = "",
            destination: str = "",
        ) -> str:
            """
            安全文件操作网关。所有文件操作必须经过此工具。
            operation: read | write | delete | rename | copy | list
            返回审批结果，调用方需根据 approved 字段决定是否执行实际操作。
            """
            try:
                op_map = {
                    "read": FileOperationType.READ,
                    "write": FileOperationType.WRITE,
                    "delete": FileOperationType.DELETE,
                    "rename": FileOperationType.RENAME,
                    "copy": FileOperationType.COPY,
                    "list": FileOperationType.LIST,
                }
                op_type = op_map.get(operation.lower())
                if not op_type:
                    return json.dumps({"error": f"Unknown operation: {operation}"}, ensure_ascii=False)

                req = FileOperationRequest(
                    source=source,
                    operation=op_type,
                    file_path=file_path,
                    content=content or None,
                    destination=destination or None,
                )
                result = _file_gateway.evaluate(req)
                return json.dumps({
                    "approved": result.approved,
                    "decision": result.decision.value,
                    "reason": result.reason,
                    "approval_id": result.approval_id,
                }, ensure_ascii=False)
            except Exception as e:
                logger.error(f"file.secure_operation error: {e}")
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("file.semantic_search")
        def file_semantic_search(query: str, top_k: int = 5) -> str:
            """
            基于自然语言搜索已索引的本地文件。
            示例: query="关于GDPR合规的文件"
            """
            try:
                results = _file_indexer.semantic_search(query, top_k=top_k)
                return json.dumps({
                    "success": True,
                    "count": len(results),
                    "results": results,
                }, ensure_ascii=False, default=str)
            except Exception as e:
                logger.error(f"file.semantic_search error: {e}")
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("file.index_directory")
        def file_index_directory(root_path: str, recursive: bool = True) -> str:
            """扫描目录并为文件建立语义索引。"""
            try:
                stats = _file_indexer.index_directory(root_path, recursive=recursive)
                return json.dumps({"success": True, "stats": stats}, ensure_ascii=False, default=str)
            except Exception as e:
                logger.error(f"file.index_directory error: {e}")
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        logger.info("[MCP] File gateway + indexer tools registered")
    except Exception as e:
        logger.warning("Failed to register file tools: %s", e)

    # ------------------------------------------------------------------ #
    # Tool Gateway + LLM Router (Prompt 1 & 2)
    # ------------------------------------------------------------------ #
    try:
        from core.tools.universal_tool_registry import ToolGateway, ToolRegistry
        from core.llm.smart_router import ModelRegistry, SmartRouter

        _tool_gateway = ToolGateway()
        _llm_registry = ModelRegistry()
        _smart_router = SmartRouter(_llm_registry)

        @mcp.tool("tool.list")
        def tool_list() -> str:
            """返回已注册工具清单"""
            try:
                tools = _tool_gateway.list_tools()
                return json.dumps({"success": True, "tools": tools}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("tool.call")
        def tool_call(source: str, tool_name: str, params: str = "{}") -> str:
            """通过 ToolGateway 安全调用任意工具"""
            try:
                import asyncio
                parsed = json.loads(params) if params else {}
                result = asyncio.run(_tool_gateway.execute(source, tool_name, parsed))
                return json.dumps({"success": True, "result": result}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("tool.register_external")
        def tool_register_external(name: str, endpoint: str, metadata: str = "{}") -> str:
            """注册外部 MCP Tool"""
            try:
                meta = json.loads(metadata) if metadata else {}
                meta["endpoint"] = endpoint
                def external_handler(**kwargs):
                    return {"status": "delegated", "tool": name, "params": kwargs}
                _tool_gateway.registry.register(name, external_handler, meta)
                return json.dumps({"success": True, "registered": name}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("file.add_allowed_dir")
        def file_add_allowed_dir(path: str) -> str:
            """授权目录到文件网关白名单"""
            try:
                from core.security.file_gateway import FileGateway
                fg = FileGateway()
                fg.add_allowed_directory(path)
                return json.dumps({"success": True, "allowed": fg.allowed_directories}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("file.remove_allowed_dir")
        def file_remove_allowed_dir(path: str) -> str:
            """撤销目录授权"""
            try:
                from core.security.file_gateway import FileGateway
                fg = FileGateway()
                fg.remove_allowed_directory(path)
                return json.dumps({"success": True, "allowed": fg.allowed_directories}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("file.list_allowed_dirs")
        def file_list_allowed_dirs() -> str:
            """列出文件网关所有已授权目录"""
            try:
                from core.security.file_gateway import FileGateway
                fg = FileGateway()
                return json.dumps({"success": True, "allowed": fg.allowed_directories}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("llm.register_model")
        def llm_register_model(
            name: str,
            endpoint: str,
            api_key: str,
            cost_per_1m: float,
            tags: str = "",
            context_length: int = 4096,
        ) -> str:
            """注册新模型到 SmartRouter"""
            try:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                _llm_registry.add_model(name, endpoint, api_key, cost_per_1m, tag_list, context_length)
                return json.dumps({"success": True, "registered": name}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("llm.optimize_request")
        def llm_optimize_request(task_description: str, strategy: str = "balanced") -> str:
            """根据任务描述返回推荐模型"""
            try:
                result = _smart_router.route(task_description, strategy=strategy)
                if result:
                    return json.dumps({"success": True, "recommendation": result}, ensure_ascii=False)
                return json.dumps({"success": False, "error": "No available model"}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        @mcp.tool("llm.call_with_routing")
        def llm_call_with_routing(task_description: str, prompt: str, strategy: str = "balanced") -> str:
            """自动路由并调用模型（返回推荐结果，实际调用由调用方执行）"""
            try:
                result = _smart_router.route(task_description, strategy=strategy)
                if result:
                    return json.dumps({
                        "success": True,
                        "selected_model": result["name"],
                        "endpoint": result["endpoint"],
                        "estimated_cost_per_1m": result["cost_per_1m"],
                        "prompt": prompt,
                    }, ensure_ascii=False)
                return json.dumps({"success": False, "error": "No available model"}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

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
                task_description: 任务描述
                context_length: 需要的上下文长度
                budget_limit: 预算上限（$/1M tokens），0 表示无限制
                strategy: cost_first | quality_first | balanced
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
                        "estimated_cost_usd": result.get("estimated_cost"),
                        "cost_per_1m": result["cost_per_1m"],
                        "context_length": result["context_length"],
                        "matched_categories": result["matched_categories"],
                        "strategy": result["strategy"],
                    }, ensure_ascii=False)
                return json.dumps({"success": False, "error": "No available model"}, ensure_ascii=False)
            except Exception as e:
                logger.error(f"llm.route_task error: {e}")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("llm.get_stats")
        def llm_get_stats() -> str:
            """获取 LLM 路由调用统计。"""
            try:
                stats = _smart_router.get_stats()
                return json.dumps({"success": True, "stats": stats}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        logger.info("[MCP] Tool gateway + LLM router tools registered")
    except Exception as e:
        logger.warning("Failed to register tool/llm tools: %s", e)

    # ------------------------------------------------------------------ #
    # Agent Swarm Tools (P22)
    # ------------------------------------------------------------------ #
    try:
        from core.agent_swarm.labor_market import get_labor_market
        from core.agent_swarm.task_delegator import get_task_delegator, TaskStatus

        _labor_market = get_labor_market()
        _task_delegator = get_task_delegator()

        @mcp.tool("agent.create_subagent")
        def agent_create_subagent(
            name: str,
            description: str = "",
            capabilities: str = "[]",
            tools: str = "[]",
            system_prompt: str = "",
            max_tokens: int = 4096,
        ) -> str:
            """动态创建 Subagent。capabilities 和 tools 为 JSON 字符串数组。"""
            try:
                caps = json.loads(capabilities) if capabilities else []
                tool_list = json.loads(tools) if tools else []
                agent = _labor_market.add_dynamic_subagent(
                    name=name,
                    description=description,
                    capabilities=caps,
                    tools=tool_list,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                )
                return json.dumps({"success": True, "agent": agent.spec.name}, ensure_ascii=False)
            except ValueError as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
            except Exception as e:
                logger.exception("agent.create_subagent failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("agent.list_subagents")
        def agent_list_subagents() -> str:
            """列出所有 Subagent（fixed + dynamic）。"""
            try:
                agents = _labor_market.list_subagents()
                return json.dumps({"success": True, "count": len(agents), "agents": agents}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("agent.remove_subagent")
        def agent_remove_subagent(name: str) -> str:
            """移除 dynamic Subagent（fixed 不可移除）。"""
            try:
                ok = _labor_market.remove_subagent(name)
                return json.dumps({"success": ok, "removed": name if ok else None}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("task.delegate")
        def task_delegate(
            description: str,
            subagent_name: str = "",
            context: str = "",
            timeout: int = 300,
        ) -> str:
            """委托任务给 Subagent。subagent_name 为空时自动匹配。"""
            try:
                import asyncio as _asyncio
                record = _asyncio.run(_task_delegator.delegate(
                    description=description,
                    subagent_name=subagent_name or None,
                    context=context,
                    timeout=timeout,
                ))
                return json.dumps({
                    "success": True,
                    "task_id": record.task_id,
                    "status": record.status.value,
                    "subagent": record.subagent_name,
                    "result": record.result,
                }, ensure_ascii=False, default=str)
            except Exception as e:
                logger.exception("task.delegate failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("task.status")
        def task_status(task_id: str) -> str:
            """查询任务状态。"""
            try:
                status = _task_delegator.get_status(task_id)
                if status:
                    return json.dumps({"success": True, "status": status}, ensure_ascii=False, default=str)
                return json.dumps({"success": False, "error": "Task not found"}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("task.cancel")
        def task_cancel(task_id: str) -> str:
            """取消执行中的任务。"""
            try:
                import asyncio as _asyncio
                ok = _asyncio.run(_task_delegator.cancel(task_id))
                return json.dumps({"success": ok, "cancelled": ok}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        logger.info("[MCP] Agent swarm tools registered")
    except Exception as e:
        logger.warning("Failed to register agent swarm tools: %s", e)

    # ------------------------------------------------------------------ #
    # A2A Protocol Tools (P22-003)
    # ------------------------------------------------------------------ #
    try:
        from core.protocol.a2a_adapter import A2AAdapter

        _a2a_adapter = A2AAdapter()

        @mcp.tool("a2a.register_external")
        def a2a_register_external(card_url: str) -> str:
            """通过 URL 注册外部 A2A Agent 到 Kaelis。"""
            try:
                card = _a2a_adapter.discover_external_agents(card_url)
                if not card:
                    return json.dumps({"success": False, "error": "Failed to fetch agent card"}, ensure_ascii=False)
                agent_id = _a2a_adapter.from_agent_card(card)
                if agent_id:
                    return json.dumps({"success": True, "agent_id": agent_id}, ensure_ascii=False)
                return json.dumps({"success": False, "error": "Failed to register agent"}, ensure_ascii=False)
            except Exception as e:
                logger.exception("a2a.register_external failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("a2a.send_task")
        def a2a_send_task(target_url: str, task_json: str = "{}") -> str:
            """向外部 A2A Agent 发送任务。"""
            try:
                task = json.loads(task_json) if task_json else {}
                result = _a2a_adapter.send_task(target_url, task)
                return json.dumps({"success": True, "result": result}, ensure_ascii=False, default=str)
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        logger.info("[MCP] A2A protocol tools registered")
    except Exception as e:
        logger.warning("Failed to register A2A tools: %s", e)

    # ------------------------------------------------------------------ #
    # Strategy Flywheel Tools
    # ------------------------------------------------------------------ #
    try:
        from core.strategy_flywheel import FlywheelEngine

        @mcp.tool("flywheel.scan")
        def flywheel_scan(target_domain: str, user_id: str = "anonymous") -> str:
            """雷达扫描：分析目标领域的技能需求和市场趋势。"""
            try:
                import asyncio
                engine = FlywheelEngine(user_id=user_id, enable_memory=True)
                response = asyncio.run(engine.scan_only(target_domain))
                return json.dumps({
                    "success": True,
                    "reply": response.reply,
                    "session_id": response.session_id,
                    "ring_results": response.ring_results,
                }, ensure_ascii=False)
            except Exception as e:
                logger.exception("flywheel.scan failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("flywheel.deconstruct")
        def flywheel_deconstruct(target_skill: str, user_id: str = "anonymous") -> str:
            """第一性原理拆解：将技能拆解为核心20%和可跳过80%。"""
            try:
                import asyncio
                engine = FlywheelEngine(user_id=user_id, enable_memory=True)
                response = asyncio.run(engine.deconstruct_only(target_skill))
                return json.dumps({
                    "success": True,
                    "reply": response.reply,
                    "session_id": response.session_id,
                    "ring_results": response.ring_results,
                }, ensure_ascii=False)
            except Exception as e:
                logger.exception("flywheel.deconstruct failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("flywheel.generate_plan")
        def flywheel_generate_plan(
            target_domain: str,
            core_skills_json: str = "[]",
            user_id: str = "anonymous",
        ) -> str:
            """生成90天实践计划。core_skills_json 为 JSON 字符串。"""
            try:
                import asyncio
                core_skills = json.loads(core_skills_json) if core_skills_json else []
                engine = FlywheelEngine(user_id=user_id, enable_memory=True)
                response = asyncio.run(engine.generate_plan_only(core_skills, target_domain))
                return json.dumps({
                    "success": True,
                    "reply": response.reply,
                    "session_id": response.session_id,
                    "ring_results": response.ring_results,
                }, ensure_ascii=False)
            except Exception as e:
                logger.exception("flywheel.generate_plan failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("flywheel.monetize")
        def flywheel_monetize(
            target_domain: str,
            skill_framework_json: str = "{}",
            user_id: str = "anonymous",
        ) -> str:
            """设计变现路径。skill_framework_json 为 JSON 字符串。"""
            try:
                import asyncio
                skill_framework = json.loads(skill_framework_json) if skill_framework_json else {}
                engine = FlywheelEngine(user_id=user_id, enable_memory=True)
                response = asyncio.run(engine.monetize_only(skill_framework, target_domain))
                return json.dumps({
                    "success": True,
                    "reply": response.reply,
                    "session_id": response.session_id,
                    "ring_results": response.ring_results,
                }, ensure_ascii=False)
            except Exception as e:
                logger.exception("flywheel.monetize failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("flywheel.full_cycle")
        def flywheel_full_cycle(target_domain: str, user_id: str = "anonymous") -> str:
            """执行完整战略飞轮闭环：雷达扫描→拆解→实践→变现。"""
            try:
                import asyncio
                engine = FlywheelEngine(user_id=user_id, enable_memory=True)
                response = asyncio.run(engine.full_cycle(target_domain))
                return json.dumps({
                    "success": True,
                    "reply": response.reply,
                    "session_id": response.session_id,
                    "state": response.state.value,
                    "data": response.data,
                    "ring_results": response.ring_results,
                    "tool_calls": response.tool_calls,
                }, ensure_ascii=False)
            except Exception as e:
                logger.exception("flywheel.full_cycle failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        @mcp.tool("flywheel.troubleshoot")
        def flywheel_troubleshoot(description: str, goal: str = "", user_id: str = "anonymous") -> str:
            """卡壳诊断：根据用户描述生成追问引导。"""
            try:
                engine = FlywheelEngine(user_id=user_id)
                questions = engine.troubleshoot(description, goal)
                stuck_type = engine.troubleshooter.diagnose(description)
                return json.dumps({
                    "success": True,
                    "stuck_type": stuck_type,
                    "questions": questions,
                }, ensure_ascii=False)
            except Exception as e:
                logger.exception("flywheel.troubleshoot failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        logger.info("[MCP] Strategy Flywheel tools registered")
    except Exception as e:
        logger.warning("Failed to register Strategy Flywheel tools: %s", e)

    # ------------------------------------------------------------------ #
    # OpenClaw Migration Tool (P22-004)
    # ------------------------------------------------------------------ #
    try:
        from core.migration.openclaw_importer import OpenClawImporter

        @mcp.tool("migration.import_openclaw")
        def migration_import_openclaw(directory: str = "") -> str:
            """导入 OpenClaw 技能和记忆。directory 为空时扫描默认目录。"""
            try:
                importer = OpenClawImporter(source_path=directory or None)
                report = importer.run_migration(directory=directory or None)
                return json.dumps({"success": True, "report": report}, ensure_ascii=False, default=str)
            except Exception as e:
                logger.exception("migration.import_openclaw failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        logger.info("[MCP] OpenClaw migration tool registered")
    except Exception as e:
        logger.warning("Failed to register OpenClaw migration tool: %s", e)

    # ------------------------------------------------------------------ #
    # Sandbox Tester Tool (P22-005)
    # ------------------------------------------------------------------ #
    try:
        from core.skills.sandbox_tester import SkillSandboxTester

        @mcp.tool("skill.test_in_sandbox")
        def skill_test_in_sandbox(skill_json: str = "{}") -> str:
            """在沙箱中测试技能安全性。skill_json 为技能 JSON 字符串。"""
            try:
                skill = json.loads(skill_json) if skill_json else {}
                tester = SkillSandboxTester()
                report = tester.test_skill(skill)
                return json.dumps({
                    "success": True,
                    "passed": report.passed,
                    "risk_level": report.risk_level,
                    "risk_score": report.risk_score,
                    "recommendations": report.recommendations,
                }, ensure_ascii=False)
            except Exception as e:
                logger.exception("skill.test_in_sandbox failed")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        logger.info("[MCP] Sandbox tester tool registered")
    except Exception as e:
        logger.warning("Failed to register sandbox tester tool: %s", e)

    return mcp


# ======================================================================
# NIM Tools registration
# ======================================================================

def _register_nim_tools(mcp):
    from core.integrations.nvidia_nim_manager import get_nim_registry

    @mcp.tool("nim.discover")
    def nim_discover(base_url: str = "http://localhost") -> str:
        """Discover local NVIDIA NIM services."""
        try:
            reg = get_nim_registry()
            services = reg.discover_nim_services(base_url=base_url)
            return json.dumps({"services": services}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool("nim.register")
    def nim_register(url: str, model_type: str = "unknown") -> str:
        """Register a NIM endpoint as a Kaelis Agent."""
        try:
            reg = get_nim_registry()
            profile = reg.register_nim_as_agent(url, model_type=model_type)
            return json.dumps({"agent_id": profile.agent_id, "online": profile.is_online}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool("nim.list")
    def nim_list() -> str:
        """List all registered NIM agents."""
        try:
            reg = get_nim_registry()
            return json.dumps({"agents": reg.list_agents()}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool("nim.call")
    def nim_call(agent_id: str, payload: str = '{}') -> str:
        """Proxy a chat-completion call to a registered NIM agent."""
        try:
            reg = get_nim_registry()
            parsed = json.loads(payload)
            result = reg.proxy_nim_call(agent_id, parsed)
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


# ======================================================================
# Physical Sensor Tools registration
# ======================================================================

def _register_physical_sensor_tools(mcp):
    from core.context.sensors.physical_sensor import (
        get_physical_sensor_registry,
        IsaacSimSensor,
        OmniverseSensor,
    )

    @mcp.tool("physical_sensor.list")
    def physical_sensor_list() -> str:
        """List registered physical sensors."""
        try:
            reg = get_physical_sensor_registry()
            return json.dumps({"sensors": reg.list_sensors()}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool("physical_sensor.collect")
    def physical_sensor_collect(name: str = "all") -> str:
        """Collect data from all or a specific physical sensor."""
        try:
            reg = get_physical_sensor_registry()
            if name == "all":
                data = reg.collect_all()
            else:
                sensor = reg._sensors.get(name)
                if sensor is None:
                    return json.dumps({"error": f"Sensor {name} not found"}, ensure_ascii=False)
                data = {name: sensor.collect()}
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool("physical_sensor.register_isaac")
    def physical_sensor_register_isaac(name: str, prim_path: str = "/World/robot") -> str:
        """Register an Isaac Sim sensor."""
        try:
            reg = get_physical_sensor_registry()
            reg.register(name, IsaacSimSensor(robot_prim_path=prim_path))
            return json.dumps({"registered": name, "type": "IsaacSimSensor"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool("physical_sensor.register_omniverse")
    def physical_sensor_register_omniverse(name: str, usd_path: str = "") -> str:
        """Register an Omniverse sensor."""
        try:
            reg = get_physical_sensor_registry()
            reg.register(name, OmniverseSensor(usd_path=usd_path or None))
            return json.dumps({"registered": name, "type": "OmniverseSensor"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


# ======================================================================
# Entry points
# ======================================================================

def run_stdio_server():
    """启动 stdio 传输的 MCP Server"""
    import anyio
    mcp = create_mcp_server()
    if mcp is None:
        sys.exit(1)
    anyio.run(mcp.run_stdio_async)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    run_stdio_server()


if __name__ == "__main__":
    main()
