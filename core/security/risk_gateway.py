"""
风险感知网关 — RiskAwareGateway

规则引擎 + 动态评估 + 用户确认的三层审核体系。
"""

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    level: str  # "none", "low", "medium", "high", "critical"
    score: float  # 0.0 - 1.0
    reason: str
    attack_scenario: str
    fix_suggestion: str
    auto_fixable: bool
    fix_command: Optional[str] = None
    requires_approval: bool = False
    approval_id: Optional[str] = None


# 审批队列（内存中；多实例应使用 Redis）
_approval_lock = threading.Lock()
_approval_queue: List[Dict[str, Any]] = []


def submit_for_approval(
    title: str,
    description: str,
    risk: str,
    source: str = "unknown",
    payload: Dict = None,
) -> str:
    """提交一个高风险操作到审批队列，返回 approval_id"""
    item = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "risk": risk,
        "source": source,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
        "resolved_at": None,
        "payload": payload or {},
    }
    with _approval_lock:
        _approval_queue.append(item)
    logger.warning(f"[Approval] 高风险操作已提交审批: {item['id']} | {title}")
    return item["id"]


def get_approval_status(approval_id: str) -> Optional[Dict[str, Any]]:
    with _approval_lock:
        for item in _approval_queue:
            if item["id"] == approval_id:
                return dict(item)
    return None


class RiskAwareGateway:
    """
    三层审核网关：
    1. 规则引擎（静态规则匹配）
    2. 动态评估（启发式评分）
    3. 用户确认（高风险需人工确认）
    """

    # 规则模式: (pattern, risk_level, reason, attack_scenario, fix_suggestion, can_auto, fix_cmd)
    RULES = [
        # 高危命令
        (
            r"rm\s+-rf\s+/",
            "critical",
            "检测到删除根目录命令",
            "恶意技能可销毁整个文件系统",
            "立即删除该技能文件并审查来源",
            False,
            "",
        ),
        (
            r"os\.system\(.*rm",
            "high",
            "检测到通过 os.system 执行删除操作",
            "可执行任意系统命令，导致数据丢失",
            "审查代码逻辑，使用安全的文件删除 API",
            False,
            "",
        ),
        # 敏感文件访问
        (
            r"~\/\.ssh\/id_rsa|~\/\.ssh\/id_ed25519",
            "high",
            "尝试访问 SSH 私钥",
            "私钥泄露可导致服务器被完全控制",
            "禁止技能访问 SSH 目录，使用专用凭证管理",
            False,
            "",
        ),
        (
            r"\.env.*=.*['\"]sk-",
            "high",
            "API Key 以明文形式存储",
            "凭证泄露可导致云服务被恶意使用",
            "迁移到 CredentialVault 加密存储",
            False,
            "",
        ),
        # 网络暴露
        (
            r"0\.0\.0\.0:\d+",
            "medium",
            "服务监听在 0.0.0.0（所有接口）",
            "外部网络可直接访问本地服务",
            "将绑定地址改为 127.0.0.1",
            True,
            "sed -i 's/0.0.0.0/127.0.0.1/g' config",
        ),
        # 弱口令
        (
            r"password\s*=\s*['\"]?(admin|123456|password|default)['\"]?",
            "high",
            "检测到弱口令配置",
            "易被暴力破解，导致未授权访问",
            "生成强密码并更新配置",
            True,
            "python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
        ),
        # 空凭证
        (
            r"API_KEY\s*=\s*['\"]?\s*['\"]?|api_key\s*=\s*['\"]?\s*['\"]?",
            "medium",
            "API Key 未配置（空值或占位符）",
            "相关功能不可用，可能暴露默认行为",
            "配置有效的 API Key 或禁用相关功能",
            False,
            "",
        ),
    ]

    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def assess(self, context: str, source: str = "unknown") -> RiskAssessment:
        """
        评估给定内容的风险等级。
        context: 待审查的文本内容
        source: 内容来源标识
        """
        max_score = 0.0
        matched_reasons = []
        attack_scenarios = []
        fix_suggestions = []
        auto_fixable = False
        fix_cmd = None

        for rule in self.RULES:
            if len(rule) == 6:
                pattern, level, reason, attack, fix, can_auto = rule
                fix_cmd = ""
            else:
                pattern, level, reason, attack, fix, can_auto, fix_cmd = rule
            if re.search(pattern, context, re.IGNORECASE):
                score = self._level_to_score(level)
                if score > max_score:
                    max_score = score
                matched_reasons.append(reason)
                attack_scenarios.append(attack)
                fix_suggestions.append(fix)
                if can_auto:
                    auto_fixable = True
                    fix_cmd = fix_cmd or self._generate_fix_command(pattern, context)

        if not matched_reasons:
            return RiskAssessment(
                level="none",
                score=0.0,
                reason="未发现风险",
                attack_scenario="无",
                fix_suggestion="无需修复",
                auto_fixable=False,
            )

        final_level = self._score_to_level(max_score)

        # K-10: 高风险/关键风险进入审批队列
        requires_approval = final_level in ("high", "critical")
        approval_id = None
        if requires_approval:
            approval_id = submit_for_approval(
                title=f"{source} 存在 {final_level.upper()} 风险",
                description="; ".join(matched_reasons),
                risk=final_level,
                source=source,
                payload={"context": context[:500]},
            )

        result = RiskAssessment(
            level=final_level,
            score=max_score,
            reason="; ".join(matched_reasons),
            attack_scenario="; ".join(attack_scenarios),
            fix_suggestion="; ".join(fix_suggestions),
            auto_fixable=auto_fixable,
            fix_command=fix_cmd,
            requires_approval=requires_approval,
            approval_id=approval_id,
        )

        self.history.append({
            "source": source,
            "level": final_level,
            "score": max_score,
            "reason": result.reason,
            "approval_id": approval_id,
        })
        return result

    def assess_file(self, file_path: str) -> RiskAssessment:
        """评估文件内容风险"""
        p = __import__("pathlib").Path(file_path)
        if not p.exists():
            return RiskAssessment(
                level="none", score=0.0, reason="文件不存在",
                attack_scenario="无", fix_suggestion="无需修复", auto_fixable=False
            )
        if p.is_dir():
            # 对目录进行浅层扫描
            risky_content = []
            for child in p.iterdir():
                if child.is_file() and child.stat().st_size < 1024 * 1024:  # 只扫描 < 1MB 文件
                    try:
                        text = child.read_text(encoding="utf-8", errors="ignore")
                        risky_content.append(text)
                    except Exception:
                        pass
            content = "\n".join(risky_content)
        else:
            content = p.read_text(encoding="utf-8", errors="ignore")
        return self.assess(content, source=str(p))

    def assess_directory(self, dir_path: str, pattern: str = "*") -> List[RiskAssessment]:
        """批量评估目录下的文件"""
        results = []
        p = __import__("pathlib").Path(dir_path)
        if p.exists():
            for f in p.rglob(pattern):
                if f.is_file():
                    results.append(self.assess_file(str(f)))
        return results

    @staticmethod
    def _level_to_score(level: str) -> float:
        mapping = {"none": 0.0, "low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        return mapping.get(level, 0.0)

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 0.9:
            return "critical"
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        if score >= 0.1:
            return "low"
        return "none"

    def _generate_fix_command(self, pattern: str, context: str) -> Optional[str]:
        """根据匹配模式生成修复命令"""
        if "0.0.0.0" in pattern:
            return "sed -i 's/0.0.0.0/127.0.0.1/g' config"
        if "password" in pattern:
            return 'python -c "import secrets; print(secrets.token_urlsafe(32))"'
        return None

    def assess_with_provenance(self, context: str, source: str = "unknown", memory_key: Optional[str] = None) -> RiskAssessment:
        """
        带溯源信息的风险评估

        在基础 assess 之上，查询该内容的污点追溯记录，
        如果来自高风险来源，自动提升风险等级。
        """
        base = self.assess(context, source)

        if memory_key:
            try:
                from core.security.taint_tracker import get_taint_tracker
                tracker = get_taint_tracker()
                provenance = tracker.get_provenance(memory_key)
                if provenance:
                    risky_sources = {"api:untrusted", "web:unknown", "file:unverified"}
                    for p in provenance:
                        if p["source"] in risky_sources:
                            # 提升风险等级
                            new_score = min(base.score + 0.2, 1.0)
                            base.score = new_score
                            base.level = self._score_to_level(new_score)
                            base.reason += f" [溯源警告: 数据来自高风险来源 {p['source']}]"
                            break
            except Exception:
                pass

        return base

    def summary(self) -> Dict[str, Any]:
        """返回历史评估摘要"""
        if not self.history:
            return {"total": 0, "max_level": "none", "critical_count": 0}
        levels = [h["level"] for h in self.history]
        scores = [h["score"] for h in self.history]
        return {
            "total": len(self.history),
            "max_level": max(levels, key=lambda x: self._level_to_score(x)),
            "max_score": max(scores),
            "critical_count": sum(1 for l in levels if l == "critical"),
            "high_count": sum(1 for l in levels if l == "high"),
        }
