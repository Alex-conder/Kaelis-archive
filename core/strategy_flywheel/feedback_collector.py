"""
反馈收集模块

收集用户对飞轮建议的采纳/拒绝反馈，生成周报摘要。
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FeedbackRecord:
    """单条反馈记录"""
    feedback_id: str
    session_id: str
    ring_name: str
    suggestion: str
    action: str  # adopted | rejected | pending
    reason: str
    timestamp: str
    user_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "session_id": self.session_id,
            "ring_name": self.ring_name,
            "suggestion": self.suggestion,
            "action": self.action,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
        }


class FeedbackCollector:
    """
    反馈收集器。

    收集用户对飞轮建议的反馈：
    - 采纳/拒绝记录
    - 原因收集
    - 周报生成
    """

    def __init__(self, user_id: str = "anonymous"):
        self.user_id = user_id

    def submit_feedback(
        self,
        session_id: str,
        ring_name: str,
        suggestion: str,
        action: str,
        reason: str = "",
    ) -> bool:
        """
        提交单条反馈。

        Args:
            session_id: 飞轮会话 ID
            ring_name: 环名称（radar/deconstruct/practice/monetize）
            suggestion: 建议内容
            action: adopted | rejected | pending
            reason: 采纳/拒绝原因
        """
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()

            feedback_id = f"fb_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            record = FeedbackRecord(
                feedback_id=feedback_id,
                session_id=session_id,
                ring_name=ring_name,
                suggestion=suggestion,
                action=action,
                reason=reason,
                timestamp=datetime.now().isoformat(),
                user_id=self.user_id,
            )

            mm.write(
                layer="L2",
                key=f"flywheel:feedback:{feedback_id}",
                value=record.to_dict(),
                metadata={
                    "source": "strategy_flywheel_feedback",
                    "session_id": session_id,
                    "ring": ring_name,
                    "action": action,
                },
                user_id=self.user_id,
            )
            return True
        except Exception as e:
            logger.warning(f"提交反馈失败: {e}")
            return False

    def generate_weekly_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        生成反馈周报。
        """
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()

            # 搜索本周的反馈记录
            results = mm.search(
                layer="L2",
                query="flywheel:feedback",
                top_k=100,
                user_id=self.user_id,
            )

            adopted = []
            rejected = []
            pending = []

            for r in results:
                try:
                    value = r.get("value", {})
                    if isinstance(value, str):
                        value = json.loads(value)
                    ts = value.get("timestamp", "")
                    record_date = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if start_date <= record_date <= end_date:
                        action = value.get("action", "")
                        if action == "adopted":
                            adopted.append(value)
                        elif action == "rejected":
                            rejected.append(value)
                        else:
                            pending.append(value)
                except Exception:
                    continue

            total = len(adopted) + len(rejected) + len(pending)
            adoption_rate = len(adopted) / total if total > 0 else 0

            return {
                "period": f"{start_date.date()} ~ {end_date.date()}",
                "total_feedback": total,
                "adopted": len(adopted),
                "rejected": len(rejected),
                "pending": len(pending),
                "adoption_rate": round(adoption_rate, 2),
                "adopted_items": adopted,
                "rejected_items": rejected,
                "pending_items": pending,
                "insights": self._generate_insights(adopted, rejected),
            }
        except Exception as e:
            logger.warning(f"生成周报失败: {e}")
            return {"error": str(e)}

    def _generate_insights(
        self,
        adopted: List[Dict],
        rejected: List[Dict],
    ) -> List[str]:
        """基于反馈数据生成洞察"""
        insights = []

        if len(adopted) > len(rejected):
            insights.append("✅ 本周建议采纳率较高，策略方向与用户预期一致")
        elif len(rejected) > len(adopted):
            insights.append("⚠️ 本周拒绝率较高，建议检查建议质量或用户目标是否变化")

        # 分析拒绝原因
        rejection_reasons = [r.get("reason", "") for r in rejected if r.get("reason")]
        if rejection_reasons:
            insights.append(f"💡 常见拒绝原因: {', '.join(rejection_reasons[:3])}")

        return insights
