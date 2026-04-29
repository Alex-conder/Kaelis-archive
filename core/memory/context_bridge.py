"""
内存上下文桥接器 — Context Bridge

将工具执行结果与当前对话上下文关联，写入 L2 Episodic 记忆。
"""

import logging
from datetime import datetime
from typing import Any, Dict

from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)


def bridge_tool_execution(
    source_agent: str,
    tool_name: str,
    params: Dict[str, Any],
    result: Any,
    context: str = "",
) -> bool:
    """
    记录工具执行到 L2 记忆，关联当前对话上下文。

    Args:
        source_agent: 调用来源 Agent ID
        tool_name: 工具名称
        params: 调用参数
        result: 执行结果（会被截断到 500 字符）
        context: 当前对话上下文描述
    """
    try:
        mm = get_memory_manager()
        mm.write(
            layer="L2",
            key=f"tool_exec:{datetime.now().isoformat()}:{tool_name}",
            value={
                "source_agent": source_agent,
                "tool": tool_name,
                "params": params,
                "result_preview": str(result)[:500] if result else None,
                "context": context,
                "timestamp": datetime.now().isoformat(),
            },
            metadata={
                "type": "tool_execution",
                "event_type": "tool_exec",
                "agent_id": source_agent,
                "source": "context_bridge",
            },
            user_id=source_agent,
        )
        return True
    except Exception as e:
        logger.warning(f"Context bridge memory write failed: {e}")
        return False
