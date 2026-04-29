"""
统一工具注册表与文件安全网关

ToolGateway + ToolRegistry
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.memory_manager_v2 import get_memory_manager
from core.security.exceptions import PermissionDeniedError
from core.security.risk_auditor import RiskAuditor
from core.security.risk_gateway import RiskDecision

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表：统一管理所有 MCP Tools 和内部工具。
    """

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        tool_name: str,
        handler: Callable,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """注册新工具"""
        if tool_name in self._tools:
            logger.warning(f"Tool {tool_name} already registered, overwriting")
        self._tools[tool_name] = {
            "name": tool_name,
            "handler": handler,
            "metadata": metadata or {},
            "registered_at": datetime.now().isoformat(),
        }
        logger.info(f"[ToolRegistry] Registered: {tool_name}")
        return True

    def unregister(self, tool_name: str) -> bool:
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def get(self, tool_name: str) -> Optional[Dict]:
        return self._tools.get(tool_name)

    def discover(self) -> List[Dict]:
        """返回所有已注册工具的元数据清单（不含 handler）"""
        return [
            {
                "name": name,
                "metadata": info["metadata"],
                "registered_at": info["registered_at"],
            }
            for name, info in self._tools.items()
        ]


class ToolGateway:
    """
    工具调用安全网关。

    执行流程：
    1. RiskAuditor 安全审核
    2. 审核通过 → 执行工具调用
    3. 自动将结果写入 L2 Episodic 记忆
    4. 审核拒绝 → 抛出 PermissionDeniedError
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()
        self.auditor = RiskAuditor()

    async def execute(
        self,
        source: str,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict] = None,
    ) -> Any:
        """安全执行工具调用"""
        # 第一层：安全审核
        decision, reason = self.auditor.evaluate(source, tool_name, params)

        if decision == RiskDecision.BLOCK:
            await self._write_memory(source, tool_name, params, None, "blocked", reason)
            raise PermissionDeniedError(f"[{tool_name}] {reason}")

        if decision == RiskDecision.CONFIRM:
            await self._write_memory(source, tool_name, params, None, "pending_confirm", reason)
            raise PermissionDeniedError(f"[{tool_name}] 需人工确认: {reason}")

        # 第二层：执行工具调用
        tool_info = self.registry.get(tool_name)
        if not tool_info:
            raise PermissionDeniedError(f"Tool not found: {tool_name}")

        handler = tool_info["handler"]
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**params)
            else:
                result = handler(**params)
        except Exception as e:
            await self._write_memory(source, tool_name, params, None, "error", str(e))
            raise

        # 第三层：写入 L2 记忆
        await self._write_memory(source, tool_name, params, result, "success", reason)
        return result

    async def _write_memory(
        self,
        source: str,
        tool_name: str,
        params: Dict,
        result: Any,
        status: str,
        reason: str,
    ):
        """将工具执行记录写入 L2 Episodic 记忆"""
        try:
            mm = get_memory_manager()
            mm.write(
                layer="L2",
                key=f"tool_exec:{datetime.now().isoformat()}:{tool_name}",
                value={
                    "source": source,
                    "tool": tool_name,
                    "params": params,
                    "result_preview": str(result)[:500] if result else None,
                    "status": status,
                    "reason": reason,
                },
                metadata={
                    "type": "tool_execution",
                    "agent_id": source,
                    "source": "tool_gateway",
                },
                user_id=source,
            )
        except Exception as e:
            logger.warning(f"Tool memory write failed: {e}")

    def list_tools(self) -> List[Dict]:
        return self.registry.discover()
