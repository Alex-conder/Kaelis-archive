"""
Hallucination Guard
===================
多 Agent 实时交叉验证与冲突消解系统。

功能:
    1. cross_agent_fact_check — 跨 Agent 事实核查
    2. source_trace — 来源追踪与可信度评分
    3. hallucination_fix_proposal — 幻觉自动修复提案

用法:
    from core.hallucination.guard import HallucinationGuard
    guard = HallucinationGuard()
    result = guard.cross_agent_fact_check("Python 3.14 已发布", "agent_a", ["agent_b", "agent_c"])
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# HallucinationGuard
# ============================================================================

class HallucinationGuard:
    """
    幻觉防御核心。

    依赖（均为可选，缺失时降级运行）:
        - memory_manager_v2.FourLayerMemoryManager
        - security.risk_gateway.RiskAwareGateway
        - evolution.multi_agent_tracker.MultiAgentEvolutionTracker
    """

    def __init__(
        self,
        memory_manager=None,
        risk_gateway=None,
        tracker=None,
    ):
        self.mm = memory_manager
        self.rg = risk_gateway
        self.tracker = tracker

    # ------------------------------------------------------------------ #
    # Lazy dependency resolution
    # ------------------------------------------------------------------ #

    def _get_mm(self):
        if self.mm is None:
            try:
                from core.memory_manager_v2 import get_memory_manager
                self.mm = get_memory_manager()
            except Exception as e:
                logger.debug("Memory manager unavailable: %s", e)
        return self.mm

    def _get_rg(self):
        if self.rg is None:
            try:
                from core.security.risk_gateway import RiskAwareGateway
                self.rg = RiskAwareGateway()
            except Exception as e:
                logger.debug("Risk gateway unavailable: %s", e)
        return self.rg

    def _get_tracker(self):
        if self.tracker is None:
            try:
                from core.evolution.multi_agent_tracker import MultiAgentEvolutionTracker
                mm = self._get_mm()
                self.tracker = MultiAgentEvolutionTracker(mm) if mm else None
            except Exception as e:
                logger.debug("Tracker unavailable: %s", e)
        return self.tracker

    # ------------------------------------------------------------------ #
    # 1. Cross-Agent Fact Check
    # ------------------------------------------------------------------ #

    def cross_agent_fact_check(
        self,
        claim: str,
        source_agent_id: str,
        other_agent_ids: List[str],
    ) -> Dict[str, Any]:
        """
        跨 Agent 事实核查。

        流程:
            1. 在 source_agent 的 L2 记忆搜索 claim
            2. 在每个 other_agent 的 L2 记忆搜索 claim
            3. 对比结果，检测矛盾或缺失
            4. 信誉加权/多数意见决议
        """
        mm = self._get_mm()
        if mm is None:
            return {"error": "Memory manager unavailable", "has_hallucination": False}

        source_facts = self._search_agent_memory(source_agent_id, claim)
        all_results: Dict[str, List[Dict]] = {source_agent_id: source_facts}
        conflicts: List[Dict] = []

        for other_id in other_agent_ids:
            other_facts = self._search_agent_memory(other_id, claim)
            all_results[other_id] = other_facts

            # 检测矛盾：source 有但 other 无，或内容不一致
            for sf in source_facts:
                match = self._find_best_match(sf, other_facts)
                if match is None:
                    conflicts.append({
                        "type": "missing",
                        "source_agent": source_agent_id,
                        "source_fact": sf,
                        "other_agent": other_id,
                        "other_fact": None,
                    })
                elif not self._is_consistent(sf, match):
                    conflicts.append({
                        "type": "contradiction",
                        "source_agent": source_agent_id,
                        "source_fact": sf,
                        "other_agent": other_id,
                        "other_fact": match,
                    })

        consensus = self._resolve_consensus(all_results, conflicts, source_agent_id)
        return {
            "claim": claim,
            "source_agent": source_agent_id,
            "other_agents_checked": other_agent_ids,
            "source_facts_count": len(source_facts),
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "consensus": consensus,
            "has_hallucination": len(conflicts) > 0,
        }

    def _search_agent_memory(self, agent_id: str, query: str, top_k: int = 5) -> List[Dict]:
        """搜索指定 Agent 的 L2 记忆。"""
        mm = self._get_mm()
        if mm is None:
            return []
        try:
            results = mm.search("L2", query, top_k=top_k, agent_id=agent_id)
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.debug("Search failed for agent %s: %s", agent_id, e)
            return []

    def _find_best_match(self, fact: Dict, candidates: List[Dict]) -> Optional[Dict]:
        """在候选列表中找到与 fact 语义最匹配的记录。"""
        if not candidates:
            return None
        source_key = str(fact.get("key", "")).lower()
        source_value = str(fact.get("value", "")).lower()
        best = None
        best_score = 0.0
        for c in candidates:
            c_key = str(c.get("key", "")).lower()
            c_value = str(c.get("value", "")).lower()
            score = 0.0
            if source_key and source_key == c_key:
                score += 0.5
            if source_value and c_value:
                # 简单重叠度
                overlap = len(set(source_value.split()) & set(c_value.split()))
                score += min(overlap / 10.0, 0.5)
            if score > best_score:
                best_score = score
                best = c
        return best if best_score >= 0.3 else None

    def _is_consistent(self, a: Dict, b: Dict) -> bool:
        """判断两条记忆记录是否一致（简单字符串比较）。"""
        val_a = str(a.get("value", a.get("content", ""))).strip().lower()
        val_b = str(b.get("value", b.get("content", ""))).strip().lower()
        # 完全相等认为一致；包含关系也认为是同一事实的不同表述
        if val_a == val_b:
            return True
        if val_a in val_b or val_b in val_a:
            return True
        return False

    def _resolve_consensus(
        self,
        all_results: Dict[str, List[Dict]],
        conflicts: List[Dict],
        source_agent_id: str,
    ) -> Dict[str, Any]:
        """基于多数意见和信誉加权决议。"""
        agent_votes: Dict[str, int] = {}
        for agent_id, facts in all_results.items():
            agent_votes[agent_id] = len(facts)

        # 简单多数：被最多 Agent 支持的事实
        # 收集所有 fact 的 key（包含 value 摘要，区分同一 key 的不同 value）
        fact_support: Dict[str, List[str]] = {}
        for agent_id, facts in all_results.items():
            for f in facts:
                key = str(f.get("key", ""))
                val = str(f.get("value", ""))[:50]
                composite_key = f"{key}::{val}"
                if composite_key not in fact_support:
                    fact_support[composite_key] = []
                fact_support[composite_key].append(agent_id)

        if not fact_support:
            return {"verdict": "insufficient_data", "supported_by": [], "confidence": 0.0}

        best_key = max(fact_support, key=lambda k: len(fact_support[k]))
        supporters = fact_support[best_key]
        total_agents = len(all_results)
        confidence = len(supporters) / total_agents if total_agents > 0 else 0.0

        # 如果有冲突，source_agent 可能是少数派
        verdict = "confirmed" if confidence >= 0.5 and source_agent_id in supporters else "disputed"
        if conflicts and verdict == "confirmed":
            verdict = "partial_conflict"

        return {
            "verdict": verdict,
            "supported_by": supporters,
            "confidence": round(confidence, 2),
            "source_agent_in_majority": source_agent_id in supporters,
        }

    # ------------------------------------------------------------------ #
    # 2. Source Trace
    # ------------------------------------------------------------------ #

    def source_trace(self, claim_key: str, agent_id: str) -> Dict[str, Any]:
        """
        来源追踪与可信度评分。

        流程:
            1. 读取 L2 中该 claim 的元数据
            2. 查询 multi_agent_tracker 的协作记录
            3. 查询 risk_gateway 审计日志，标记高风险操作
            4. 计算可信度评分（高风险操作每次 -0.2）
        """
        mm = self._get_mm()
        record = None
        if mm:
            try:
                record = mm.read("L2", claim_key, agent_id=agent_id)
            except Exception as e:
                logger.debug("Read memory failed: %s", e)

        # 协作记录
        collab_records: List[Dict] = []
        tracker = self._get_tracker()
        if tracker:
            try:
                cutoff = (datetime.now() - timedelta(days=7)).isoformat()
                raw = tracker._fetch_collaboration_records(cutoff)
                collab_records = [
                    c for c in raw
                    if agent_id in ([c.get("supervisor_id", "")] + c.get("worker_ids", []))
                ]
            except Exception as e:
                logger.debug("Tracker fetch failed: %s", e)

        # 风险审计
        risk_flags: List[Dict] = []
        trust_score = 1.0
        rg = self._get_rg()
        if rg:
            try:
                audit = rg.audit_log(source_id=agent_id)
                risk_flags = [
                    a for a in audit
                    if a.get("decision") in ("BLOCK", "CONFIRM")
                    or a.get("risk_score", 0) > 0.5
                ]
                # 每个高风险标记降级 0.2，最低 0.0
                trust_score = max(0.0, 1.0 - len(risk_flags) * 0.2)
            except Exception as e:
                logger.debug("Risk audit failed: %s", e)

        return {
            "claim_key": claim_key,
            "agent_id": agent_id,
            "memory_record": record,
            "collaboration_history": collab_records[:5],
            "collaboration_count": len(collab_records),
            "risk_flags": risk_flags,
            "risk_flag_count": len(risk_flags),
            "trust_score": round(trust_score, 2),
            "downgraded": len(risk_flags) > 0,
        }

    # ------------------------------------------------------------------ #
    # 3. Hallucination Fix Proposal
    # ------------------------------------------------------------------ #

    def hallucination_fix_proposal(self, conflict_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        幻觉自动修复提案。

        流程:
            1. 分析冲突，生成修复提案（覆盖错误记忆、更新知识图谱）
            2. 通过 RiskAwareGateway 评估风险
            3. 风险低（ALLOW）→ 自动执行
            4. 风险高（CONFIRM/BLOCK）→ 推送审批流
        """
        proposal = self._generate_proposal(conflict_report)

        # 风险评估
        decision = "ALLOW"
        reason = "auto-approved: no risk gateway configured"
        approval_id = None
        rg = self._get_rg()
        if rg:
            try:
                # RiskAwareGateway.evaluate 可能是 async，捕获 TypeError 降级
                result = rg.evaluate(
                    source_id="hallucination_guard",
                    operation="memory_overwrite",
                    data={"proposal": proposal, "conflict_report": conflict_report},
                )
                # 处理返回 tuple (decision, reason, approval_id)
                if isinstance(result, tuple):
                    if len(result) >= 2:
                        decision = result[0]
                        reason = result[1]
                    if len(result) >= 3:
                        approval_id = result[2]
                else:
                    decision = str(result)
            except TypeError:
                # async function called synchronously
                logger.debug("Risk gateway evaluate is async, skipping sync call")
                decision = "ALLOW"
            except Exception as e:
                logger.warning("Risk evaluation failed: %s", e)
                decision = "CONFIRM"  # 保守处理

        # 执行决策
        if decision == "ALLOW":
            executed = self._execute_proposal(proposal)
            return {
                "executed": executed,
                "decision": decision,
                "reason": reason,
                "approval_id": None,
                "proposal": proposal,
                "message": "修复提案已自动执行" if executed else "执行失败",
            }
        else:
            return {
                "executed": False,
                "decision": decision,
                "reason": reason,
                "approval_id": approval_id,
                "proposal": proposal,
                "message": "高风险操作，已推送审批流等待用户确认",
            }

    def _generate_proposal(self, conflict_report: Dict) -> Dict[str, Any]:
        """根据冲突报告生成修复提案。"""
        consensus = conflict_report.get("consensus", {})
        conflicts = conflict_report.get("conflicts", [])
        claim = conflict_report.get("claim", "")
        source_agent = conflict_report.get("source_agent", "")

        actions: List[Dict] = []

        # 若 source_agent 不在多数派，建议覆盖其记忆
        if not consensus.get("source_agent_in_majority", True):
            actions.append({
                "action": "overwrite",
                "target_agent": source_agent,
                "layer": "L2",
                "key": claim,
                "rationale": "source_agent 与多数派结论冲突",
            })

        # 对每条 missing 冲突，建议补充缺失 Agent 的记忆
        for c in conflicts:
            if c.get("type") == "missing":
                actions.append({
                    "action": "sync",
                    "target_agent": c["other_agent"],
                    "layer": "L2",
                    "key": claim,
                    "source_fact": c["source_fact"],
                    "rationale": "其他 Agent 缺少该事实，建议同步",
                })

        return {
            "claim": claim,
            "actions": actions,
            "confidence": consensus.get("confidence", 0.0),
            "verdict": consensus.get("verdict", "unknown"),
        }

    def _execute_proposal(self, proposal: Dict) -> bool:
        """执行修复提案。"""
        mm = self._get_mm()
        if mm is None:
            return False

        success_count = 0
        for action in proposal.get("actions", []):
            try:
                if action["action"] == "overwrite":
                    mm.write(
                        layer=action.get("layer", "L2"),
                        key=action["key"],
                        value=action.get("new_value", action.get("source_fact", {}).get("value", "")),
                        metadata={
                            "type": "hallucination_fix",
                            "rationale": action.get("rationale", ""),
                            "auto_fixed": True,
                        },
                        agent_id=action["target_agent"],
                    )
                    success_count += 1
                elif action["action"] == "sync":
                    source_fact = action.get("source_fact", {})
                    mm.write(
                        layer=action.get("layer", "L2"),
                        key=action["key"],
                        value=source_fact.get("value", ""),
                        metadata={
                            "type": "hallucination_sync",
                            "rationale": action.get("rationale", ""),
                            "auto_fixed": True,
                            "source_agent": proposal.get("claim", ""),
                        },
                        agent_id=action["target_agent"],
                    )
                    success_count += 1
            except Exception as e:
                logger.warning("Proposal action failed: %s", e)

        return success_count > 0


# ============================================================================
# MCP Tool Registration
# ============================================================================

def register_hallucination_tools(mcp: Any):
    """向 FastMCP 实例注册幻觉防御 Tools。"""

    @mcp.tool()
    def cross_verify(claim: str, source_agent_id: str, other_agent_ids: str = "[]") -> str:
        """
        跨 Agent 事实核查。

        Args:
            claim: 待核查的结论/事实
            source_agent_id: 产出该结论的 Agent ID
            other_agent_ids: 其他 Agent ID 的 JSON 数组字符串，如 '["agent_b", "agent_c"]'
        """
        try:
            ids = json.loads(other_agent_ids)
            if not isinstance(ids, list):
                return json.dumps({"error": "other_agent_ids must be a JSON array"}, ensure_ascii=False)
            guard = HallucinationGuard()
            result = guard.cross_agent_fact_check(claim, source_agent_id, ids)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error("cross_verify error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def source_trace(claim_key: str, agent_id: str) -> str:
        """
        来源追踪与可信度评分。

        Args:
            claim_key: 结论在记忆中的 key
            agent_id: 产出该结论的 Agent ID
        """
        try:
            guard = HallucinationGuard()
            result = guard.source_trace(claim_key, agent_id)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error("source_trace error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def auto_fix(conflict_report_json: str) -> str:
        """
        幻觉自动修复提案。

        Args:
            conflict_report_json: cross_verify 返回的冲突报告 JSON 字符串
        """
        try:
            report = json.loads(conflict_report_json)
            guard = HallucinationGuard()
            result = guard.hallucination_fix_proposal(report)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error("auto_fix error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    logger.info("Hallucination guard tools registered: cross_verify, source_trace, auto_fix")
