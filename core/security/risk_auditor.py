"""
风险审计器 — RiskAuditor

对工具调用进行安全审核。
"""

import logging
from typing import Any, Dict

from core.security.risk_gateway import RiskDecision

logger = logging.getLogger(__name__)

# 高危工具黑名单
DANGEROUS_TOOLS = {"file.delete", "file.rm", "os.system", "eval", "exec"}

# 敏感参数关键词
SENSITIVE_PARAMS = {"password", "secret", "token", "api_key", "private_key"}


class RiskAuditor:
    """
    工具调用风险审计器。
    对 source + tool_name + params 进行静态规则审核。
    """

    def evaluate(self, source: str, tool_name: str, params: Dict[str, Any]) -> tuple:
        """
        评估工具调用风险。
        返回 (decision, reason):
        - decision: RiskDecision.ALLOW / RiskDecision.BLOCK / RiskDecision.CONFIRM
        - reason: 审核原因说明
        """
        tool_lower = tool_name.lower()

        # 1. 高危工具检查
        if tool_lower in DANGEROUS_TOOLS:
            return (RiskDecision.CONFIRM, f"{tool_name} 属于高危工具，需人工确认")

        # 2. 敏感参数检查
        param_str = str(params).lower()
        for keyword in SENSITIVE_PARAMS:
            if keyword in param_str:
                return (RiskDecision.CONFIRM, f"参数包含敏感关键词: {keyword}")

        # 3. 文件删除检查
        if "delete" in tool_lower or "remove" in tool_lower:
            return (RiskDecision.CONFIRM, "删除操作需确认")

        # 4. 来源黑名单（可选扩展）
        if source.startswith("untrusted_"):
            return (RiskDecision.BLOCK, f"来源 {source} 不受信任")

        return (RiskDecision.ALLOW, "通过安全审核")
