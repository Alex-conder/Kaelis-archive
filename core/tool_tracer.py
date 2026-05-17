"""
ToolTracer - 工具调用追踪引擎

对标 Anthropic Messages API 的 Content Block 架构 + Correlation ID 设计。
为每次工具调用生成结构化追踪记录：
- 工具名称与参数（input）
- 执行结果（output）
- 耗时与错误
- 调用链 ID（correlation_id）
- Pre/Post Hook 审计点

存储：SQLite `tool_call_traces` 表
"""

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolCallTrace:
    """单次工具调用追踪"""
    trace_id: str
    correlation_id: str  # 关联到 DecisionTrace 的 trace_id
    session_id: str
    tool_name: str
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_output: Dict[str, Any] = field(default_factory=dict)
    status: str = "started"  # started / completed / failed
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    duration_ms: int = 0
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


class ToolTracer:
    """
    工具调用追踪引擎。

    使用示例：
        tracer = ToolTracer()
        
        # 方法 1: 上下文管理器（自动记录）
        with tracer.trace_call("extract_triples", correlation_id="trc_xxx", session_id="sess_xxx") as t:
            result = extract_triples(text="...")
            t.tool_output = result
        
        # 方法 2: 装饰器
        @tracer.trace_tool_call(correlation_id="trc_xxx")
        def my_tool(arg):
            return {"result": "ok"}
        
        # 方法 3: 手动记录
        trace = tracer.start_call("query_graph", correlation_id="trc_xxx", session_id="sess_xxx")
        trace.tool_input = {"query": "MATCH ..."}
        result = query_graph(...)
        tracer.complete_call(trace, output=result)
    """

    def __init__(self, db_path: Optional[str] = None):
        import os
        data_dir = os.environ.get("KAELIS_DATA_DIR", "data")
        self.db_path = db_path or str(Path(data_dir) / "kaelis_graph.db")
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []
        self._init_db()

    def _init_db(self):
        """初始化工具调用追踪表"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_call_traces (
                    trace_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_input_json TEXT,
                    tool_output_json TEXT,
                    status TEXT DEFAULT 'started',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_ms INTEGER DEFAULT 0,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_corr 
                ON tool_call_traces(correlation_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_session 
                ON tool_call_traces(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_name 
                ON tool_call_traces(tool_name)
            """)

    def register_pre_hook(self, hook: Callable):
        """注册调用前钩子（权限检查、参数校验等）"""
        self._pre_hooks.append(hook)

    def register_post_hook(self, hook: Callable):
        """注册调用后钩子（审计、结果处理等）"""
        self._post_hooks.append(hook)

    @contextmanager
    def trace_call(
        self,
        tool_name: str,
        correlation_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """上下文管理器：自动追踪工具调用"""
        trace = self.start_call(tool_name, correlation_id, session_id, metadata)
        start_dt = datetime.now()

        try:
            yield trace
            trace.status = "completed"
        except Exception as e:
            trace.status = "failed"
            trace.error = str(e)
            logger.warning(f"[ToolTrace] {tool_name} failed: {e}")
            raise
        finally:
            trace.completed_at = datetime.now().isoformat()
            trace.duration_ms = int(
                (datetime.now() - start_dt).total_seconds() * 1000
            )
            self._persist(trace)
            self._run_post_hooks(trace)

    def trace_tool_call(self, correlation_id: str, session_id: str = ""):
        """装饰器：自动追踪函数调用"""
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                tool_name = func.__name__
                sid = session_id or kwargs.get("session_id", "default")
                with self.trace_call(tool_name, correlation_id, sid) as trace:
                    trace.tool_input = {"args": args, "kwargs": kwargs}
                    result = func(*args, **kwargs)
                    trace.tool_output = result if isinstance(result, dict) else {"result": result}
                    return result
            return wrapper
        return decorator

    def start_call(
        self,
        tool_name: str,
        correlation_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolCallTrace:
        """开始一次工具调用追踪"""
        trace = ToolCallTrace(
            trace_id=f"tct_{uuid.uuid4().hex[:16]}",
            correlation_id=correlation_id,
            session_id=session_id,
            tool_name=tool_name,
            metadata=metadata or {},
        )

        # 运行 Pre-hooks
        for hook in self._pre_hooks:
            try:
                hook(trace)
            except Exception as e:
                logger.warning(f"[ToolTrace] Pre-hook failed: {e}")

        return trace

    def complete_call(
        self,
        trace: ToolCallTrace,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """完成工具调用追踪"""
        trace.completed_at = datetime.now().isoformat()
        if output is not None:
            trace.tool_output = output
        if error is not None:
            trace.status = "failed"
            trace.error = error
        else:
            trace.status = "completed"

        self._persist(trace)
        self._run_post_hooks(trace)

    def _run_post_hooks(self, trace: ToolCallTrace):
        """运行 Post-hooks"""
        for hook in self._post_hooks:
            try:
                hook(trace)
            except Exception as e:
                logger.warning(f"[ToolTrace] Post-hook failed: {e}")

    def _persist(self, trace: ToolCallTrace):
        """持久化到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO tool_call_traces
                    (trace_id, correlation_id, session_id, tool_name,
                     tool_input_json, tool_output_json, status,
                     started_at, completed_at, duration_ms, error,
                     retry_count, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trace.trace_id,
                        trace.correlation_id,
                        trace.session_id,
                        trace.tool_name,
                        json.dumps(trace.tool_input, ensure_ascii=False, default=str),
                        json.dumps(trace.tool_output, ensure_ascii=False, default=str),
                        trace.status,
                        trace.started_at,
                        trace.completed_at,
                        trace.duration_ms,
                        trace.error,
                        trace.retry_count,
                        json.dumps(trace.metadata, ensure_ascii=False, default=str),
                    ),
                )
        except Exception as e:
            logger.error(f"[ToolTrace] Persist failed: {e}")

    def get_traces_by_correlation(
        self, correlation_id: str, limit: int = 50
    ) -> List[ToolCallTrace]:
        """获取同一决策链路下的所有工具调用"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM tool_call_traces
                    WHERE correlation_id = ?
                    ORDER BY started_at ASC
                    LIMIT ?
                    """,
                    (correlation_id, limit),
                ).fetchall()
                return [self._row_to_trace(r) for r in rows]
        except Exception as e:
            logger.error(f"[ToolTrace] get_traces failed: {e}")
            return []

    def get_tool_stats(
        self,
        tool_name: Optional[str] = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """获取工具调用统计"""
        try:
            cutoff = (datetime.now() - __import__("datetime").timedelta(hours=hours)).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                where = "WHERE started_at > ?"
                params = [cutoff]
                if tool_name:
                    where += " AND tool_name = ?"
                    params.append(tool_name)

                total = conn.execute(
                    f"SELECT COUNT(*) as cnt FROM tool_call_traces {where}", params
                ).fetchone()["cnt"]

                failed = conn.execute(
                    f"SELECT COUNT(*) as cnt FROM tool_call_traces {where} AND status = 'failed'",
                    params,
                ).fetchone()["cnt"]

                avg_time = conn.execute(
                    f"SELECT AVG(duration_ms) as avg FROM tool_call_traces {where} AND status = 'completed'",
                    params,
                ).fetchone()["avg"] or 0

                return {
                    "tool_name": tool_name or "all",
                    "period_hours": hours,
                    "total_calls": total,
                    "failed_calls": failed,
                    "success_rate": round((total - failed) / max(total, 1), 3),
                    "avg_duration_ms": round(avg_time, 1),
                }
        except Exception as e:
            logger.error(f"[ToolTrace] get_tool_stats failed: {e}")
            return {}

    def _row_to_trace(self, row: sqlite3.Row) -> ToolCallTrace:
        return ToolCallTrace(
            trace_id=row["trace_id"],
            correlation_id=row["correlation_id"],
            session_id=row["session_id"],
            tool_name=row["tool_name"],
            tool_input=json.loads(row["tool_input_json"]) if row["tool_input_json"] else {},
            tool_output=json.loads(row["tool_output_json"]) if row["tool_output_json"] else {},
            status=row["status"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"] or 0,
            error=row["error"],
            retry_count=row["retry_count"] or 0,
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        )


# ------------------------------------------------------------------
# 单例
# ------------------------------------------------------------------
_tool_tracer_instance: Optional[ToolTracer] = None


def get_tool_tracer() -> ToolTracer:
    """获取工具追踪引擎单例"""
    global _tool_tracer_instance
    if _tool_tracer_instance is None:
        _tool_tracer_instance = ToolTracer()
    return _tool_tracer_instance
