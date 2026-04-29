"""
Notifier — 轻量通知/审批管道

P3 安全执行通道的适配层：将 ToolGateway 的审批需求
转发为可插拔的通知后端（WebSocket / 日志 / 回调）。
"""

import logging
import asyncio
import inspect
from enum import Enum
from typing import Callable, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    WEBSOCKET = "websocket"
    LOG = "log"
    CALLBACK = "callback"


@dataclass
class ApprovalRequest:
    request_id: str
    source_agent: str
    tool_name: str
    params: dict
    risk_level: str          # low / medium / high / critical
    reason: str
    context: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    timeout_seconds: int = 300
    status: str = "pending"  # pending / approved / denied / timeout


class Notifier:
    """轻量通知/审批中心。"""

    def __init__(self):
        self._handlers: List[Callable] = []
        self._pending: dict[str, ApprovalRequest] = {}
        self._callbacks: dict[str, Callable] = {}
        self.channel = NotificationChannel.LOG

    def set_channel(self, channel: NotificationChannel):
        self.channel = channel

    def register_handler(self, handler: Callable):
        self._handlers.append(handler)

    async def request_approval(
        self,
        source_agent: str,
        tool_name: str,
        params: dict,
        risk_level: str,
        reason: str,
        context: str = "",
        timeout: int = 300,
    ) -> str:
        req_id = f"appr-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hash(tool_name) & 0xFFFFFF:06x}"
        req = ApprovalRequest(
            request_id=req_id,
            source_agent=source_agent,
            tool_name=tool_name,
            params=params,
            risk_level=risk_level,
            reason=reason,
            context=context,
            timeout_seconds=timeout,
        )
        self._pending[req_id] = req

        payload = {
            "type": "approval_request",
            "request_id": req_id,
            "source_agent": source_agent,
            "tool_name": tool_name,
            "params": params,
            "risk_level": risk_level,
            "reason": reason,
            "context": context,
            "timeout": timeout,
            "timestamp": req.created_at.isoformat(),
        }

        if self.channel == NotificationChannel.LOG:
            logger.info(f"[APPROVAL] {req_id} | {source_agent} → {tool_name} | risk={risk_level} | reason={reason}")
        elif self.channel == NotificationChannel.WEBSOCKET:
            for h in self._handlers:
                try:
                    if inspect.iscoroutinefunction(h):
                        await h(payload)
                    else:
                        h(payload)
                except Exception as e:
                    logger.warning(f"WS handler error: {e}")
        else:
            for h in self._handlers:
                try:
                    h(payload)
                except Exception:
                    pass

        return req_id

    async def resolve(self, request_id: str, approved: bool) -> bool:
        req = self._pending.get(request_id)
        if not req:
            return False
        req.status = "approved" if approved else "denied"
        cb = self._callbacks.pop(request_id, None)
        if cb:
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(approved)
                else:
                    cb(approved)
            except Exception as e:
                logger.warning(f"Approval callback error: {e}")
        return True

    def on_resolved(self, request_id: str, callback: Callable):
        self._callbacks[request_id] = callback

    def get_pending(self) -> List[ApprovalRequest]:
        return list(self._pending.values())

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._pending.get(request_id)
