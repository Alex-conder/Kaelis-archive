"""
Risk-Aware Gateway (Prompt 4)

Three-layer audit pipeline:
1. RuleEngine: whitelist/blacklist pattern matching
2. LLMRiskReviewer: LLM-based dynamic risk assessment
3. ApprovalService: user confirmation with timeout
"""

import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk Decision Enum
# ---------------------------------------------------------------------------

class RiskDecision(str, Enum):
    ALLOW = "ALLOW"
    CONFIRM = "CONFIRM"
    BLOCK = "BLOCK"


# ---------------------------------------------------------------------------
# Rule Engine
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    pattern: str
    action: RiskDecision
    reason: str
    compiled: Any = field(repr=False, default=None)

    def __post_init__(self):
        self.compiled = re.compile(self.pattern, re.IGNORECASE)


class RuleEngine:
    """First-layer rule engine: whitelist/blacklist matching."""

    def __init__(self, rules_path: Optional[str] = None):
        self.rules_path = rules_path or "config/risk_rules.yaml"
        self.whitelist: List[Rule] = []
        self.blacklist: List[Rule] = []
        self._load_rules()

    def _load_rules(self):
        try:
            import yaml
            path = Path(self.rules_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                data = self._default_rules()
        except Exception:
            data = self._default_rules()

        for item in data.get("rule_engine", {}).get("whitelist", []):
            self.whitelist.append(Rule(item["pattern"], RiskDecision.ALLOW, item.get("reason", "")))
        for item in data.get("rule_engine", {}).get("blacklist", []):
            self.blacklist.append(Rule(item["pattern"], RiskDecision.BLOCK, item.get("reason", "")))

    def _default_rules(self) -> Dict[str, Any]:
        return {
            "rule_engine": {
                "whitelist": [
                    {"pattern": "^memory_search$", "action": "ALLOW", "reason": "Read-only"},
                    {"pattern": "^skill_list$", "action": "ALLOW", "reason": "Read-only"},
                ],
                "blacklist": [
                    {"pattern": "rm\\s+-rf", "action": "BLOCK", "reason": "Dangerous deletion"},
                    {"pattern": "eval\\s*\\(", "action": "BLOCK", "reason": "Code execution"},
                ],
            }
        }

    def evaluate(self, operation: str, data: Optional[Dict] = None) -> Optional[tuple]:
        """
        Evaluate against rules. Returns (decision, reason) or None if no rule matches.
        """
        text = operation
        if data:
            try:
                text += " " + json.dumps(data, ensure_ascii=False, default=str)
            except Exception:
                pass

        # Blacklist first (higher priority)
        for rule in self.blacklist:
            if rule.compiled.search(text):
                return RiskDecision.BLOCK, rule.reason

        # Then whitelist
        for rule in self.whitelist:
            if rule.compiled.search(text):
                return RiskDecision.ALLOW, rule.reason

        return None


# ---------------------------------------------------------------------------
# LLM Risk Reviewer
# ---------------------------------------------------------------------------

class LLMRiskReviewer:
    """Second-layer: LLM-based dynamic risk assessment."""

    RISK_LEVEL_MAP = {
        "safe": RiskDecision.ALLOW,
        "low": RiskDecision.ALLOW,
        "medium": RiskDecision.CONFIRM,
        "high": RiskDecision.BLOCK,
        "critical": RiskDecision.BLOCK,
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def evaluate(self, source_id: str, operation: str, data: Optional[Dict] = None) -> tuple:
        """Evaluate risk using LLM or heuristic fallback."""
        if self.llm_client is None:
            # Fallback: heuristic based on operation name and data
            return self._heuristic_evaluate(operation, data)

        prompt = self._build_prompt(source_id, operation, data)
        try:
            response = self.llm_client.complete(prompt, max_tokens=50)
            risk_level = self._parse_risk_level(response)
        except Exception as e:
            logger.warning(f"LLM risk review failed: {e}, using heuristic fallback")
            risk_level = self._heuristic_evaluate(operation, data)[0]

        decision = self.RISK_LEVEL_MAP.get(risk_level, RiskDecision.CONFIRM)
        return decision, f"LLM assessed risk: {risk_level}"

    def evaluate_batch(self, items: List[Dict[str, Any]]) -> List[tuple]:
        """Batch evaluation."""
        return [self.evaluate(item.get("source_id", ""), item["operation"], item.get("data")) for item in items]

    def _heuristic_evaluate(self, operation: str, data: Optional[Dict] = None) -> tuple:
        """Heuristic fallback when LLM is unavailable."""
        text = (operation + " " + json.dumps(data or {}, default=str)).lower()

        critical_patterns = ["delete", "drop", "truncate", "rm -rf", "format", "wipe"]
        for pat in critical_patterns:
            if pat in text:
                return RiskDecision.BLOCK, f"Heuristic: critical keyword '{pat}' detected"

        confirm_patterns = ["write", "update", "modify", "create", "import", "export"]
        for pat in confirm_patterns:
            if pat in text:
                return RiskDecision.CONFIRM, f"Heuristic: modifying keyword '{pat}' detected"

        return RiskDecision.ALLOW, "Heuristic: no risk indicators"

    def _build_prompt(self, source_id: str, operation: str, data: Optional[Dict]) -> str:
        return f"""You are a security risk assessor. Evaluate the following operation and respond with exactly one word: safe, low, medium, high, or critical.

Source: {source_id}
Operation: {operation}
Data: {json.dumps(data or {}, default=str)[:500]}

Risk level:"""

    def _parse_risk_level(self, response: str) -> str:
        text = response.strip().lower()
        for level in ["safe", "low", "medium", "high", "critical"]:
            if level in text:
                return level
        return "medium"


# ---------------------------------------------------------------------------
# Approval Service
# ---------------------------------------------------------------------------

@dataclass
class PendingApproval:
    approval_id: str
    source_id: str
    operation: str
    data: Dict[str, Any]
    requested_at: float
    timeout_seconds: int
    status: str = "pending"  # pending / approved / rejected / timeout
    resolution: Optional[str] = None


class ApprovalService:
    """Third-layer: user confirmation with timeout."""

    def __init__(self, default_timeout: int = 300):
        self.default_timeout = default_timeout
        self._pending: Dict[str, PendingApproval] = {}
        self._trust_cache: Dict[str, RiskDecision] = {}  # "agent_id:operation" -> decision
        self._lock = threading.Lock()

    def request_approval(self, source_id: str, operation: str, data: Optional[Dict] = None) -> PendingApproval:
        """Create a pending approval request."""
        approval_id = f"approval_{uuid.uuid4().hex[:12]}"
        pa = PendingApproval(
            approval_id=approval_id,
            source_id=source_id,
            operation=operation,
            data=data or {},
            requested_at=time.time(),
            timeout_seconds=self.default_timeout,
        )
        with self._lock:
            self._pending[approval_id] = pa
        logger.info(f"Approval requested: {approval_id} for {source_id}/{operation}")
        return pa

    def resolve_approval(self, approval_id: str, decision: str, permanent_trust: bool = False) -> bool:
        """Resolve a pending approval (approved/rejected)."""
        with self._lock:
            pa = self._pending.get(approval_id)
            if pa is None:
                return False
            if pa.status != "pending":
                return False

            pa.status = "approved" if decision == "approved" else "rejected"
            pa.resolution = decision

            if permanent_trust and pa.status == "approved":
                key = f"{pa.source_id}:{pa.operation}"
                self._trust_cache[key] = RiskDecision.ALLOW

            logger.info(f"Approval {approval_id} resolved: {decision}")
            return True

    def check_trust_cache(self, source_id: str, operation: str) -> Optional[RiskDecision]:
        """Check if this agent+operation is permanently trusted."""
        key = f"{source_id}:{operation}"
        return self._trust_cache.get(key)

    def get_pending(self, approval_id: Optional[str] = None, source_id: Optional[str] = None) -> List[PendingApproval]:
        """Get pending approvals, optionally filtered."""
        with self._lock:
            now = time.time()
            results = []
            for pa in list(self._pending.values()):
                if pa.status == "pending" and (now - pa.requested_at) > pa.timeout_seconds:
                    pa.status = "timeout"
                    pa.resolution = "timeout"
                if pa.status != "pending":
                    continue
                if approval_id and pa.approval_id != approval_id:
                    continue
                if source_id and pa.source_id != source_id:
                    continue
                results.append(pa)
            return results

    def audit_log(self, start_time: Optional[float] = None, end_time: Optional[float] = None, source_id: Optional[str] = None) -> List[Dict]:
        """Return audit log of all resolved approvals."""
        with self._lock:
            logs = []
            for pa in self._pending.values():
                if pa.status == "pending":
                    continue
                if start_time and pa.requested_at < start_time:
                    continue
                if end_time and pa.requested_at > end_time:
                    continue
                if source_id and pa.source_id != source_id:
                    continue
                logs.append({
                    "approval_id": pa.approval_id,
                    "source_id": pa.source_id,
                    "operation": pa.operation,
                    "status": pa.status,
                    "resolution": pa.resolution,
                    "requested_at": pa.requested_at,
                })
            return sorted(logs, key=lambda x: x["requested_at"])


# ---------------------------------------------------------------------------
# Risk-Aware Gateway
# ---------------------------------------------------------------------------

class RiskAwareGateway:
    """
    Three-layer risk audit gateway.

    Usage:
        gateway = RiskAwareGateway()
        decision = await gateway.evaluate("agent_1", "api_call", {"endpoint": "/delete"})
    """

    def __init__(self, rules_path: Optional[str] = None, llm_client=None, default_timeout: int = 300):
        self.rule_engine = RuleEngine(rules_path)
        self.llm_reviewer = LLMRiskReviewer(llm_client)
        self.approval_service = ApprovalService(default_timeout)

    async def evaluate(self, source_id: str, operation: str, data: Optional[Dict] = None, context: Optional[Dict] = None) -> tuple:
        """
        Three-layer evaluation pipeline.

        Returns:
            (RiskDecision, reason, approval_id_or_none)
        """
        # Layer 1: Rule Engine
        rule_result = self.rule_engine.evaluate(operation, data)
        if rule_result:
            decision, reason = rule_result
            logger.info(f"RuleEngine: {decision} for {operation} ({reason})")
            return decision, reason, None

        # Layer 2: LLM Reviewer
        llm_decision, llm_reason = self.llm_reviewer.evaluate(source_id, operation, data)
        logger.info(f"LLMReviewer: {llm_decision} for {operation} ({llm_reason})")

        if llm_decision == RiskDecision.ALLOW:
            return RiskDecision.ALLOW, llm_reason, None

        if llm_decision == RiskDecision.BLOCK:
            return RiskDecision.BLOCK, llm_reason, None

        # Layer 3: Approval Service (medium risk)
        # Check trust cache first
        cached = self.approval_service.check_trust_cache(source_id, operation)
        if cached == RiskDecision.ALLOW:
            return RiskDecision.ALLOW, "Permanently trusted", None

        pa = self.approval_service.request_approval(source_id, operation, data)
        return RiskDecision.CONFIRM, f"Pending approval: {pa.approval_id}", pa.approval_id

    def resolve_approval(self, approval_id: str, decision: str, permanent_trust: bool = False) -> bool:
        """Resolve a pending user approval."""
        return self.approval_service.resolve_approval(approval_id, decision, permanent_trust)

    def audit_log(self, start_time: Optional[float] = None, end_time: Optional[float] = None, source_id: Optional[str] = None) -> List[Dict]:
        """Query the audit log."""
        return self.approval_service.audit_log(start_time, end_time, source_id)
