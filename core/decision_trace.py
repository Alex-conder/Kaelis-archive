"""
DecisionTraceEngine - 决策链路追踪引擎

对标 Anthropic Extended Thinking / Chain of Thought 的透明推理设计。
为每次 Agent 运行生成结构化、可审计的决策追踪记录。

核心能力：
1. 意图分析追踪（Intent Analysis Trace）
2. 记忆检索追踪（Memory Retrieval Trace）
3. 冲突检测追踪（Conflict Detection Trace）
4. Prompt 构建追踪（Prompt Building Trace）
5. 工具调用追踪（Tool Call Trace）
6. LLM 生成追踪（LLM Generation Trace）
7. 安全审查追踪（Safety Review Trace）

存储：SQLite `decision_traces` 表（JSON 列存储结构化 trace）
"""

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceStepType(Enum):
    """决策步骤类型"""
    INTENT_ANALYSIS = "intent_analysis"
    MEMORY_RETRIEVAL = "memory_retrieval"
    CONFLICT_DETECTION = "conflict_detection"
    PROMPT_BUILDING = "prompt_building"
    TOOL_CALL = "tool_call"
    LLM_GENERATION = "llm_generation"
    SAFETY_REVIEW = "safety_review"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    EXTERNAL_RETRIEVAL = "external_retrieval"


class TraceStatus(Enum):
    """步骤执行状态"""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TraceStep:
    """单个决策步骤"""
    step_type: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: int = 0
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionTrace:
    """完整决策追踪记录"""
    trace_id: str
    session_id: str
    user_id: str
    user_input: str
    final_reply: Optional[str] = None
    agent_state: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    total_duration_ms: int = 0
    steps: List[TraceStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_input": self.user_input,
            "final_reply": self.final_reply,
            "agent_state": self.agent_state,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": self.total_duration_ms,
            "steps": [asdict(s) for s in self.steps],
            "metadata": self.metadata,
        }


class DecisionTraceEngine:
    """
    决策链路追踪引擎。

    使用示例：
        engine = DecisionTraceEngine()
        trace = engine.start_trace(session_id="abc", user_id="alice", user_input="...")
        
        with engine.step(trace, TraceStepType.INTENT_ANALYSIS) as step:
            step.input_data = {"text": user_input}
            intent, confidence = analyze_intent(user_input)
            step.output_data = {"intent": intent, "confidence": confidence}
        
        engine.complete_trace(trace, reply="...")
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(Path("data/kaelis_graph.db").resolve())
        self._init_db()

    def _init_db(self):
        """初始化追踪表（幂等）"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_traces (
                    trace_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT DEFAULT 'anonymous',
                    user_input TEXT,
                    final_reply TEXT,
                    agent_state TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    total_duration_ms INTEGER DEFAULT 0,
                    steps_json TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trace_session 
                ON decision_traces(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trace_user 
                ON decision_traces(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trace_started 
                ON decision_traces(started_at)
            """)

    def start_trace(
        self,
        session_id: str,
        user_id: str = "anonymous",
        user_input: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionTrace:
        """开始一个新的决策追踪"""
        trace = DecisionTrace(
            trace_id=f"trc_{uuid.uuid4().hex[:16]}",
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
            started_at=datetime.now().isoformat(),
            metadata=metadata or {},
        )
        logger.debug(f"[Trace] Started {trace.trace_id} for session {session_id}")
        return trace

    @contextmanager
    def step(
        self,
        trace: DecisionTrace,
        step_type: TraceStepType,
        input_data: Optional[Dict[str, Any]] = None,
    ):
        """
        上下文管理器：自动记录步骤开始和结束。

        使用示例：
            with engine.step(trace, TraceStepType.MEMORY_RETRIEVAL, {"query": q}) as s:
                results = retrieve_memories(q)
                s.output_data = {"count": len(results), "top_result": results[0]}
        """
        step_obj = TraceStep(
            step_type=step_type.value,
            status=TraceStatus.STARTED.value,
            started_at=datetime.now().isoformat(),
            input_data=input_data or {},
        )
        trace.steps.append(step_obj)
        start_ts = datetime.now()

        try:
            yield step_obj
            step_obj.status = TraceStatus.COMPLETED.value
        except Exception as e:
            step_obj.status = TraceStatus.FAILED.value
            step_obj.error = str(e)
            logger.warning(f"[Trace] Step {step_type.value} failed: {e}")
            raise
        finally:
            step_obj.completed_at = datetime.now().isoformat()
            step_obj.duration_ms = int(
                (datetime.now() - start_ts).total_seconds() * 1000
            )

    def add_step(
        self,
        trace: DecisionTrace,
        step_type: TraceStepType,
        status: TraceStatus,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceStep:
        """手动添加一个已完成步骤（用于无法使用上下文管理器的场景）"""
        now = datetime.now().isoformat()
        step = TraceStep(
            step_type=step_type.value,
            status=status.value,
            started_at=now,
            completed_at=now,
            duration_ms=duration_ms,
            input_data=input_data or {},
            output_data=output_data or {},
            error=error,
            metadata=metadata or {},
        )
        trace.steps.append(step)
        return step

    def complete_trace(
        self,
        trace: DecisionTrace,
        final_reply: Optional[str] = None,
        agent_state: Optional[str] = None,
    ):
        """完成追踪并持久化到数据库"""
        trace.completed_at = datetime.now().isoformat()
        trace.final_reply = final_reply
        trace.agent_state = agent_state

        start_dt = datetime.fromisoformat(trace.started_at)
        trace.total_duration_ms = int(
            (datetime.now() - start_dt).total_seconds() * 1000
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO decision_traces
                    (trace_id, session_id, user_id, user_input, final_reply,
                     agent_state, started_at, completed_at, total_duration_ms,
                     steps_json, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trace.trace_id,
                        trace.session_id,
                        trace.user_id,
                        trace.user_input,
                        trace.final_reply,
                        trace.agent_state,
                        trace.started_at,
                        trace.completed_at,
                        trace.total_duration_ms,
                        json.dumps(trace.to_dict()["steps"], ensure_ascii=False, default=str),
                        json.dumps(trace.metadata, ensure_ascii=False, default=str),
                    ),
                )
            logger.info(
                f"[Trace] Completed {trace.trace_id} in {trace.total_duration_ms}ms, "
                f"{len(trace.steps)} steps"
            )
        except Exception as e:
            logger.error(f"[Trace] Failed to persist trace: {e}")

    def get_trace(self, trace_id: str) -> Optional[DecisionTrace]:
        """根据 ID 获取追踪记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM decision_traces WHERE trace_id = ?",
                    (trace_id,),
                ).fetchone()
                if not row:
                    return None
                return self._row_to_trace(row)
        except Exception as e:
            logger.error(f"[Trace] get_trace failed: {e}")
            return None

    def list_traces(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DecisionTrace]:
        """列出追踪记录"""
        try:
            conditions = []
            params = []
            if session_id:
                conditions.append("session_id = ?")
                params.append(session_id)
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)

            where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"""
                SELECT * FROM decision_traces
                {where_sql}
                ORDER BY started_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_trace(r) for r in rows]
        except Exception as e:
            logger.error(f"[Trace] list_traces failed: {e}")
            return []

    def _row_to_trace(self, row: sqlite3.Row) -> DecisionTrace:
        """将数据库行转换为 DecisionTrace"""
        steps = json.loads(row["steps_json"]) if row["steps_json"] else []
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        return DecisionTrace(
            trace_id=row["trace_id"],
            session_id=row["session_id"],
            user_id=row["user_id"],
            user_input=row["user_input"] or "",
            final_reply=row["final_reply"],
            agent_state=row["agent_state"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            total_duration_ms=row["total_duration_ms"] or 0,
            steps=[TraceStep(**s) for s in steps],
            metadata=metadata,
        )

    def get_trace_summary(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """获取追踪摘要（轻量级）"""
        trace = self.get_trace(trace_id)
        if not trace:
            return None
        return {
            "trace_id": trace.trace_id,
            "session_id": trace.session_id,
            "user_id": trace.user_id,
            "user_input": trace.user_input[:200] if trace.user_input else "",
            "final_reply": trace.final_reply[:200] if trace.final_reply else "",
            "agent_state": trace.agent_state,
            "started_at": trace.started_at,
            "completed_at": trace.completed_at,
            "total_duration_ms": trace.total_duration_ms,
            "step_count": len(trace.steps),
            "step_summary": [
                {
                    "type": s.step_type,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                }
                for s in trace.steps
            ],
        }


# ------------------------------------------------------------------
# 单例（线程安全）
# ------------------------------------------------------------------
_trace_engine_instance: Optional[DecisionTraceEngine] = None
_trace_engine_lock = threading.Lock()


def get_trace_engine() -> DecisionTraceEngine:
    """获取决策追踪引擎单例（线程安全）"""
    global _trace_engine_instance
    if _trace_engine_instance is None:
        with _trace_engine_lock:
            if _trace_engine_instance is None:
                _trace_engine_instance = DecisionTraceEngine()
    return _trace_engine_instance
