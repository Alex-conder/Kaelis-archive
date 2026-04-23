"""
工作流引擎监控增强 (P17-004)

为工作流执行提供：
1. 执行时间追踪和 SLA 告警
2. 步骤级别性能分析
3. 失败重试统计
4. Prometheus 指标集成
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowExecutionRecord:
    """工作流执行记录"""
    workflow_id: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "running"  # running, completed, failed, cancelled
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    retry_count: int = 0
    user_id: str = "anonymous"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "steps": self.steps,
            "error": self.error,
            "retry_count": self.retry_count,
            "user_id": self.user_id,
            "metadata": self.metadata
        }


class WorkflowMonitor:
    """
    工作流监控器
    
    跟踪工作流执行的生命周期，记录性能指标。
    """
    
    # SLA 阈值（毫秒）
    SLA_THRESHOLDS = {
        "default": 30000,  # 30s
        "memory_sync": 10000,  # 10s
        "kg_extraction": 300000,  # 5min
        "data_import": 600000,  # 10min
    }
    
    def __init__(self):
        self.active_executions: Dict[str, WorkflowExecutionRecord] = {}
        self.completed_executions: List[WorkflowExecutionRecord] = []
        self.max_history = 1000
    
    def start_execution(
        self,
        workflow_id: str,
        user_id: str = "anonymous",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """开始记录工作流执行"""
        record = WorkflowExecutionRecord(
            workflow_id=workflow_id,
            user_id=user_id,
            metadata=metadata or {}
        )
        self.active_executions[record.execution_id] = record
        
        # Prometheus 指标
        try:
            from core.monitoring.metrics import SYSTEM_METRICS
            SYSTEM_METRICS.active_requests.inc()
        except Exception:
            pass
        
        logger.info(f"Workflow started: {workflow_id} ({record.execution_id})")
        return record.execution_id
    
    def record_step(
        self,
        execution_id: str,
        step_name: str,
        status: str = "success",
        duration_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """记录步骤执行"""
        if execution_id not in self.active_executions:
            return
        
        record = self.active_executions[execution_id]
        step = {
            "name": step_name,
            "status": status,
            "timestamp": time.time(),
            "duration_ms": duration_ms,
            "details": details or {}
        }
        record.steps.append(step)
        
        logger.debug(f"Workflow step: {step_name} [{status}] ({execution_id})")
    
    def complete_execution(
        self,
        execution_id: str,
        status: str = "completed",
        error: Optional[str] = None
    ):
        """完成工作流执行"""
        if execution_id not in self.active_executions:
            return
        
        record = self.active_executions[execution_id]
        record.end_time = time.time()
        record.duration_ms = (record.end_time - record.start_time) * 1000
        record.status = status
        record.error = error
        
        # SLA 检查
        self._check_sla(record)
        
        # 移至历史
        self.completed_executions.append(record)
        if len(self.completed_executions) > self.max_history:
            self.completed_executions = self.completed_executions[-self.max_history:]
        
        del self.active_executions[execution_id]
        
        # Prometheus 指标
        try:
            from core.monitoring.metrics import SYSTEM_METRICS
            SYSTEM_METRICS.active_requests.dec()
        except Exception:
            pass
        
        logger.info(
            f"Workflow {status}: {record.workflow_id} ({execution_id}) "
            f"in {record.duration_ms:.0f}ms"
        )
    
    def _check_sla(self, record: WorkflowExecutionRecord):
        """检查 SLA 是否违规"""
        if record.duration_ms is None:
            return
        
        threshold = self.SLA_THRESHOLDS.get(
            record.workflow_id,
            self.SLA_THRESHOLDS["default"]
        )
        
        if record.duration_ms > threshold:
            logger.warning(
                f"SLA violation: {record.workflow_id} took {record.duration_ms:.0f}ms "
                f"(threshold: {threshold}ms)"
            )
    
    def get_active(self) -> List[Dict[str, Any]]:
        """获取活跃执行列表"""
        return [r.to_dict() for r in self.active_executions.values()]
    
    def get_history(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取历史执行"""
        records = self.completed_executions
        if workflow_id:
            records = [r for r in records if r.workflow_id == workflow_id]
        return [r.to_dict() for r in records[-limit:]]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.completed_executions)
        if total == 0:
            return {"total": 0, "success_rate": 0, "avg_duration_ms": 0}
        
        success = sum(1 for r in self.completed_executions if r.status == "completed")
        durations = [r.duration_ms for r in self.completed_executions if r.duration_ms]
        
        return {
            "total": total,
            "active": len(self.active_executions),
            "success_rate": success / total,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "avg_steps": sum(len(r.steps) for r in self.completed_executions) / total
        }


# 全局监控器
_workflow_monitor: Optional[WorkflowMonitor] = None


def get_workflow_monitor() -> WorkflowMonitor:
    """获取全局工作流监控器"""
    global _workflow_monitor
    if _workflow_monitor is None:
        _workflow_monitor = WorkflowMonitor()
    return _workflow_monitor


def monitored_workflow(workflow_id: str):
    """
    装饰器：自动监控工作流函数
    
    用法：
        @monitored_workflow("memory_sync")
        def sync_memory_task():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_workflow_monitor()
            exec_id = monitor.start_execution(workflow_id)
            
            try:
                monitor.record_step(exec_id, "init", "success")
                result = func(*args, **kwargs)
                monitor.complete_execution(exec_id, "completed")
                return result
            except Exception as e:
                monitor.complete_execution(exec_id, "failed", error=str(e))
                raise
        return wrapper
    return decorator


if __name__ == "__main__":
    import time
    
    monitor = get_workflow_monitor()
    
    # 模拟工作流
    exec_id = monitor.start_execution("test_workflow", user_id="user_1")
    
    monitor.record_step(exec_id, "step_1", "success", 100)
    time.sleep(0.01)
    monitor.record_step(exec_id, "step_2", "success", 200)
    time.sleep(0.01)
    
    monitor.complete_execution(exec_id, "completed")
    
    print(f"Stats: {monitor.get_stats()}")
    print(f"History: {monitor.get_history()}")
    
    print("\n[OK] Workflow monitoring test completed")
