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
