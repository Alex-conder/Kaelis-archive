"""
ResponseGenerator - 带记忆上下文的响应生成器

核心职责：
1. 从 Kaelis 四层记忆系统（L0-L3）检索相关上下文
2. 检测记忆冲突并注入 prompt
3. 可选调用外部知识检索（本地文档 / Web / arXiv）
4. 使用 PromptBuilder 组装 prompt
5. 调用 LLM 生成回复
6. 返回结构化结果（含调试信息）

集成点：
- 被 api/routes/kg_flywheel_agent.py 的 _run_general_chat 调用
- 替代原有的硬编码欢迎语，实现真正的记忆增强对话
"""

import asyncio
import json
import logging
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.prompt_builder import BuiltPrompt, MemoryContext, PromptBuilder

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    带四层记忆注入的响应生成器。

    使用示例（同步）：
        rg = ResponseGenerator(user_id="alice")
        result = rg.generate("RAG v3 怎么落地？")
        print(result["reply"])

    使用示例（异步）：
        rg = ResponseGenerator(user_id="alice")
        result = await rg.generate_async("RAG v3 怎么落地？")
    """

    def __init__(
        self,
        user_id: str = "anonymous",
        use_external_knowledge: bool = False,
        use_smart_router: bool = False,
        max_context_tokens: int = 4000,
    ):
        self.user_id = user_id
        self.use_external_knowledge = use_external_knowledge
        self.use_smart_router = use_smart_router
        self.max_context_tokens = max_context_tokens

        # 惰性初始化的依赖（避免模块导入时失败阻断启动）
        self._mm = None
        self._fts = None
        self._conflict_resolver = None
        self._knowledge_retriever = None
        self._llm = None
        self._smart_router = None
        self._prompt_builder = None

    # ------------------------------------------------------------------
    # 依赖懒加载
    # ------------------------------------------------------------------

    @property
    def mm(self):
        if self._mm is None:
            from core.memory_manager_v2 import get_memory_manager
            self._mm = get_memory_manager()
        return self._mm

    @property
    def fts(self):
        if self._fts is None:
            from core.memory_fts import get_fts
            self._fts = get_fts()
        return self._fts

    @property
    def conflict_resolver(self):
        if self._conflict_resolver is None:
            from core.memory_conflict import get_conflict_resolver
            self._conflict_resolver = get_conflict_resolver()
        return self._conflict_resolver

    @property
    def knowledge_retriever(self):
        if self._knowledge_retriever is None:
            from core.knowledge_retriever import KnowledgeRetriever
            self._knowledge_retriever = KnowledgeRetriever()
        return self._knowledge_retriever

    @property
    def llm(self):
        if self._llm is None:
            from core.llm_client import get_llm_client
            self._llm = get_llm_client()
        return self._llm

    @property
    def smart_router(self):
        if self._smart_router is None:
            from core.llm.smart_router import SmartRouter
            self._smart_router = SmartRouter()
        return self._smart_router

    @property
    def prompt_builder(self):
        if self._prompt_builder is None:
            self._prompt_builder = PromptBuilder(max_context_tokens=self.max_context_tokens)
        return self._prompt_builder

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def generate(
        self,
        user_query: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        同步生成回复。
        新版：自动注入可解释性（memory_explanation、trace、safety_check）。
        """
        return self.generate_with_explainability(user_query, session_id, context)

    def generate_with_explainability(
        self,
        user_query: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        带完整可解释性的同步生成。
        返回结果包含 memory_explanation、trace_id、safety_check、safety_audit_id。
        """
        context = context or {}
        trace = context.get("trace")
        trace_engine = context.get("trace_engine")
        start_time = datetime.now()

        try:
            # 1. 检索四层记忆
            identity = self._retrieve_identity()
            active_goals = self._retrieve_active_context()
            episodic = self._retrieve_episodic(user_query)
            semantic = self._retrieve_semantic(user_query)

            # 2. 冲突检测
            conflicts = self._detect_recent_conflicts()

            # 3. 外部知识（可选）
            external = None
            if self.use_external_knowledge:
                external = self._retrieve_external(user_query)

            # 记录记忆检索追踪
            if trace_engine and trace:
                from core.decision_trace import TraceStepType, TraceStatus
                trace_engine.add_step(
                    trace, TraceStepType.MEMORY_RETRIEVAL, status=TraceStatus.COMPLETED,
                    input_data={"query": user_query},
                    output_data={
                        "identity_found": identity is not None,
                        "goals_count": len(active_goals),
                        "episodic_count": len(episodic),
                        "semantic_count": len(semantic),
                        "conflicts_count": len(conflicts),
                        "external_found": external is not None,
                    },
                )

            # 4. 组装 MemoryContext
            mem_ctx = MemoryContext(
                identity=identity,
                active_goals=active_goals,
                episodic_memories=episodic,
                semantic_facts=semantic,
                conflicts=conflicts,
                external_knowledge=external,
                conversation_history=context.get("conversation_history", []),
            )

            # 5. 构建 Prompt
            built = self.prompt_builder.build(
                user_query=user_query,
                memory_context=mem_ctx,
            )

            # 记录 prompt 构建追踪
            if trace_engine and trace:
                from core.decision_trace import TraceStepType, TraceStatus
                trace_engine.add_step(
                    trace, TraceStepType.PROMPT_BUILDING, status=TraceStatus.COMPLETED,
                    input_data={"user_query": user_query, "estimated_tokens": built.estimated_tokens},
                    output_data={
                        "sections_included": built.sections_included,
                        "sections_truncated": built.sections_truncated,
                    },
                )

            # 缓存 prompt 供 inspect API 使用
            try:
                from api.routes.explainability import _last_prompt_cache
                _last_prompt_cache[session_id or "default"] = {
                    "system_prompt": built.system_prompt,
                    "user_prompt": built.user_prompt,
                    "estimated_tokens": built.estimated_tokens,
                    "sections_included": built.sections_included,
                    "sections_truncated": built.sections_truncated,
                    "cached_at": datetime.now().isoformat(),
                }
            except Exception:
                pass

            # 6. 路由模型（可选）
            model_name = None
            if self.use_smart_router and self.smart_router:
                try:
                    route_info = self.smart_router.route(
                        task_description=user_query,
                        strategy="balanced",
                    )
                    if route_info:
                        model_name = route_info.get("name")
                except Exception as e:
                    logger.warning(f"SmartRouter failed: {e}")

            # 7. 调用 LLM
            llm_reply = None
            if self.llm is not None:
                try:
                    llm_reply = self.llm.chat(
                        prompt=built.user_prompt,
                        system_prompt=built.system_prompt,
                        temperature=0.7,
                    )
                except Exception as e:
                    logger.warning(f"LLM call failed: {e}")

            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # 8. 生成记忆可解释性
            memory_explanation = None
            try:
                from core.memory_explain import get_memory_explain_engine
                explain_engine = get_memory_explain_engine()
                memory_explanation = explain_engine.explain_retrieval(
                    query=user_query,
                    user_id=self.user_id,
                    retrieved_memories={"L2": episodic, "L3": semantic},
                    included_sections=built.sections_included,
                    truncated_sections=built.sections_truncated,
                    conflicts=conflicts,
                ).to_dict()
            except Exception as e:
                logger.debug(f"Memory explanation failed: {e}")

            # 9. 宪法安全层审查
            safety_check = None
            try:
                from core.constitutional_layer import get_constitutional_layer
                layer = get_constitutional_layer()
                safety_check = layer.check_output(
                    output=llm_reply or "",
                    context={"domain": "general"},
                    memory_conflicts=len(conflicts),
                ).to_dict()

                # 如果安全层拦截，替换回复
                if safety_check["overall_level"] == "blocked":
                    llm_reply = safety_check.get("refusal_reason", "[内容已被安全层拦截]")
            except Exception as e:
                logger.debug(f"Safety check failed: {e}")

            # 记录 LLM 生成追踪
            if trace_engine and trace:
                from core.decision_trace import TraceStepType, TraceStatus
                trace_engine.add_step(
                    trace, TraceStepType.LLM_GENERATION, status=TraceStatus.COMPLETED,
                    input_data={"model": model_name or "default", "prompt_tokens": built.estimated_tokens},
                    output_data={"reply_length": len(llm_reply) if llm_reply else 0, "elapsed_ms": elapsed_ms},
                )

            # 10. 记录安全审计（Phase 2）
            safety_audit_id = None
            try:
                from core.safety_audit import get_safety_audit_engine
                audit_engine = get_safety_audit_engine()
                safety_audit_id = audit_engine.record_audit(
                    session_id=session_id or "default",
                    user_id=self.user_id,
                    trace_id=trace.trace_id if trace else None,
                    safety_check=safety_check,
                    output_preview=llm_reply[:200] if llm_reply else "",
                    model_used=model_name or getattr(self.llm, "model", "unknown") if self.llm else "none",
                    memory_conflicts=len(conflicts),
                )
            except Exception as e:
                logger.debug(f"Safety audit record skipped: {e}")

            result = {
                "reply": llm_reply or "抱歉，当前 LLM 服务不可用，请稍后重试。",
                "memory_context": {
                    "identity_summary": identity[:200] if identity else None,
                    "goals_count": len(active_goals),
                    "episodic_count": len(episodic),
                    "semantic_count": len(semantic),
                    "conflicts_count": len(conflicts),
                    "has_external": external is not None,
                },
                "conflicts_detected": len(conflicts),
                "model_used": model_name or getattr(self.llm, "model", "unknown") if self.llm else "none",
                "prompt_tokens": built.estimated_tokens,
                "sections_included": built.sections_included,
                "sections_truncated": built.sections_truncated,
                "elapsed_ms": elapsed_ms,
                "error": None,
                "memory_explanation": memory_explanation,
                "safety_check": safety_check,
                "safety_audit_id": safety_audit_id,
            }
            if trace:
                result["trace_id"] = trace.trace_id
            return result

        except Exception as e:
            logger.error(f"Response generation failed: {e}", exc_info=True)
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return {
                "reply": f"抱歉，生成回复时遇到内部错误: {str(e)}",
                "memory_context": {},
                "conflicts_detected": 0,
                "model_used": "none",
                "prompt_tokens": 0,
                "sections_included": [],
                "sections_truncated": [],
                "elapsed_ms": elapsed_ms,
                "error": str(e),
                "memory_explanation": None,
                "safety_check": None,
                "safety_audit_id": None,
            }

    async def generate_async(
        self,
        user_query: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """异步包装（在后台线程中执行同步的 generate）。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate,
            user_query,
            session_id,
            context,
        )

    # ------------------------------------------------------------------
    # 内部检索方法
    # ------------------------------------------------------------------

    def _retrieve_identity(self) -> Optional[str]:
        """检索 L0 身份设定。优先读取用户专属 profile，其次 system_identity。"""
        try:
            # 1. 尝试读取用户专属 profile
            profile = self.mm.read("L0", f"user_profile:{self.user_id}", user_id=self.user_id)
            if profile and profile.get("value"):
                val = profile["value"]
                if isinstance(val, dict):
                    parts = [f"{k}: {v}" for k, v in val.items()]
                    return "\n".join(parts)
                return str(val)
        except Exception as e:
            logger.debug(f"L0 user_profile read failed: {e}")

        try:
            # 2. 回退到系统身份
            sys_id = self.mm.read("L0", "system_identity", user_id="system")
            if sys_id and sys_id.get("value"):
                val = sys_id["value"]
                if isinstance(val, dict):
                    name = val.get("name", "Kaelis")
                    version = val.get("version", "")
                    desc = val.get("description", "")
                    return f"系统身份: {name} {version}\n{desc}".strip()
                return str(val)
        except Exception as e:
            logger.debug(f"L0 system_identity read failed: {e}")

        return None

    def _retrieve_active_context(self) -> List[str]:
        """检索 L1 高重要性活跃记忆（importance >= 0.6）。"""
        goals: List[str] = []
        try:
            # 优先按隐私级别搜索 private（用户自己的）
            memories = self.mm.search_by_privacy_level(
                layer="L1",
                privacy_level="private",
                top_k=10,
                user_id=self.user_id,
            )
            for m in memories:
                if m.get("importance", 0.5) >= 0.6:
                    val = m.get("value", "")
                    if isinstance(val, dict):
                        # 尝试提取有意义的文本
                        text = val.get("content") or val.get("goal") or val.get("description") or str(val)
                    else:
                        text = str(val)
                    if text:
                        goals.append(text)
        except Exception as e:
            logger.debug(f"L1 active context retrieval failed: {e}")
        return goals

    def _retrieve_episodic(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """通过 FTS5 检索 L2 情景记忆。"""
        try:
            results = self.fts.search("L2", query, top_k=top_k)
            # 过滤只保留当前用户的（FTS5 目前不带 user_id 过滤，需要在应用层过滤）
            filtered = [
                r for r in results
                if r.get("metadata", {}).get("_user_id", "anonymous") == self.user_id
                or r.get("user_id", "anonymous") == self.user_id
            ]
            # 如果没有 FTS 结果，回退到 LIKE 搜索
            if not filtered:
                filtered = self.mm.search("L2", query, top_k=top_k, user_id=self.user_id)
            return filtered
        except Exception as e:
            logger.debug(f"L2 episodic retrieval failed: {e}")
            return []

    def _retrieve_semantic(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """通过 FTS5 检索 L3 语义知识（实体），并补充相关关系。"""
        facts: List[Dict[str, Any]] = []
        try:
            # FTS5 搜索实体
            entities = self.fts.search("L3", query, top_k=top_k)
            for e in entities:
                facts.append({
                    "name": e.get("name", ""),
                    "type": e.get("type", "Entity"),
                    "content": e.get("source", ""),
                    "layer": "L3",
                })

            # 补充：查询与这些实体相关的关系（从 SQLite 降级表 kg_relations）
            if entities:
                entity_names = {e.get("name", "") for e in entities if e.get("name")}
                if entity_names:
                    relations = self._query_kg_relations(entity_names, top_k=top_k * 2)
                    for r in relations:
                        facts.append({
                            "name": f"{r['subject']} → {r['object']}",
                            "type": f"关系({r['relation']})",
                            "content": f"{r['subject']} {r['relation']} {r['object']}",
                            "layer": "L3",
                        })
        except Exception as e:
            logger.debug(f"L3 semantic retrieval failed: {e}")
        return facts

    def _query_kg_relations(self, entity_names: set, top_k: int = 10) -> List[Dict[str, str]]:
        """从 SQLite kg_relations 查询与给定实体相关的关系。"""
        relations: List[Dict[str, str]] = []
        try:
            db_path = self.mm._get_db_path("L3")
            placeholders = ",".join("?" * len(entity_names))
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(
                    f"""
                    SELECT source, target, relation, source_text
                    FROM kg_relations
                    WHERE source IN ({placeholders}) OR target IN ({placeholders})
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (*list(entity_names), *list(entity_names), top_k),
                )
                for row in cursor.fetchall():
                    relations.append({
                        "subject": row[0],
                        "object": row[1],
                        "relation": row[2],
                        "source_text": row[3] or "",
                    })
        except Exception as e:
            logger.debug(f"KG relation query failed: {e}")
        return relations

    def _detect_recent_conflicts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """检索最近 N 小时内未解决的记忆冲突。"""
        conflicts: List[Dict[str, Any]] = []
        try:
            # 直接查询 memory_conflicts 表（由 MemoryConflictResolver 维护）
            db_path = Path(self.conflict_resolver.db_path)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT conflict_id, memory_key, memory_layer, version_a, version_b, detected_at
                    FROM memory_conflicts
                    WHERE detected_at > ? AND resolution IS NULL
                    ORDER BY detected_at DESC
                    LIMIT 5
                    """,
                    (cutoff,),
                ).fetchall()

            for r in rows:
                va = json.loads(r["version_a"]) if isinstance(r["version_a"], str) else r["version_a"]
                vb = json.loads(r["version_b"]) if isinstance(r["version_b"], str) else r["version_b"]
                conflicts.append({
                    "conflict_id": r["conflict_id"],
                    "key": r["memory_key"],
                    "layer": r["memory_layer"],
                    "fact_a": va.get("value_preview", str(va))[:150],
                    "fact_b": vb.get("value_preview", str(vb))[:150],
                    "severity": "major" if r["memory_layer"] in ("L0", "L1") else "minor",
                    "detected_at": r["detected_at"],
                })
        except Exception as e:
            logger.debug(f"Conflict detection failed: {e}")
        return conflicts

    def _retrieve_external(self, query: str) -> Optional[str]:
        """调用 KnowledgeRetriever 获取外部知识摘要。"""
        try:
            results = self.knowledge_retriever.search(
                query=query,
                sources=["local"],  # 默认只查本地，避免延迟和网络失败
                top_k=2,
            )
            summary = self.knowledge_retriever.get_search_summary(results)
            return summary if summary else None
        except Exception as e:
            logger.debug(f"External knowledge retrieval failed: {e}")
            return None
