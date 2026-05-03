"""
战略飞轮引擎 — 主编排器

四环串联：雷达扫描 → 第一性原理拆解 → 20/80实践 → 变现路径设计
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.llm_client import get_llm_client
from core.memory_manager_v2 import get_memory_manager

from .radar import StrategyRadar, SkillRadarResult
from .meta_cognition import MetaCognitionEngine, DeconstructionResult
from .practice_flywheel import PracticeFlywheel, PracticePlan, Troubleshooter
from .monetization import MonetizationPathGenerator, MonetizationPath

logger = logging.getLogger(__name__)


class StrategyFlywheelState(Enum):
    """战略飞轮执行状态"""
    IDLE = "idle"
    RADAR_SCANNING = "radar_scanning"
    DECONSTRUCTING = "deconstructing"
    PRACTICING = "practicing"
    MONETIZING = "monetizing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class StrategyFlywheelResponse:
    """战略飞轮响应"""
    reply: str
    session_id: str
    state: StrategyFlywheelState
    data: Dict[str, Any] = field(default_factory=dict)
    ring_results: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[str] = field(default_factory=list)


class FlywheelEngine:
    """
    战略飞轮引擎主编排器。

    管理五步学习策略的完整闭环：
    1. 雷达扫描 — 识别高价值技能和市场机会
    2. 第一性原理拆解 — 将技能拆解为核心 20% + 可跳过 80%
    3. 20/80 实践 — 生成 90 天刻意练习计划
    4. 变现路径 — 设计技能变现方案

    支持 LLM 增强和纯规则降级两种模式。
    """

    def __init__(
        self,
        user_id: str = "anonymous",
        session_id: Optional[str] = None,
        enable_memory: bool = True,
        enable_llm: bool = True,
    ):
        self.user_id = user_id
        self.session_id = session_id or self._generate_session_id()
        self.state = StrategyFlywheelState.IDLE
        self.enable_memory = enable_memory
        self.enable_llm = enable_llm

        # 初始化 LLM 客户端（如果启用）
        self.llm_client = get_llm_client() if enable_llm else None

        # 初始化四环组件
        self.radar = StrategyRadar(llm_client=self.llm_client)
        self.meta = MetaCognitionEngine(llm_client=self.llm_client)
        self.practice = PracticeFlywheel(llm_client=self.llm_client)
        self.monetization = MonetizationPathGenerator(llm_client=self.llm_client)
        self.troubleshooter = Troubleshooter()

    def _generate_session_id(self) -> str:
        return f"sfw{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # ------------------------------------------------------------------ #
    # 公共 API
    # ------------------------------------------------------------------ #

    async def full_cycle(self, target_domain: str) -> StrategyFlywheelResponse:
        """
        执行完整飞轮闭环（四环串联）。

        Args:
            target_domain: 目标领域/职业，如 "AI Agent架构师"

        Returns:
            StrategyFlywheelResponse: 包含完整战略报告
        """
        self.state = StrategyFlywheelState.RADAR_SCANNING
        ring_results = {}
        tool_calls = []
        start_time = time.time()

        try:
            # Ring 1: 雷达扫描
            logger.info(f"[{self.session_id}] Ring 1: 雷达扫描 — {target_domain}")
            radar_result = self.radar.scan(target_domain)
            ring_results["radar"] = radar_result.to_dict()
            tool_calls.append("radar.scan")
            self._write_memory("radar", ring_results["radar"])

            # Ring 2: 第一性原理拆解（对 Top 3 技能）
            self.state = StrategyFlywheelState.DECONSTRUCTING
            logger.info(f"[{self.session_id}] Ring 2: 第一性原理拆解")
            top_skills = radar_result.recommended_focus[:3]
            deconstruction_results = []
            for skill in top_skills:
                decon = self.meta.deconstruct(skill)
                deconstruction_results.append(decon.to_dict())
            ring_results["deconstruction"] = {
                "target_skills": top_skills,
                "results": deconstruction_results,
            }
            tool_calls.append("meta.deconstruct")
            self._write_memory("deconstruction", ring_results["deconstruction"])

            # Ring 3: 20/80 实践计划
            self.state = StrategyFlywheelState.PRACTICING
            logger.info(f"[{self.session_id}] Ring 3: 20/80 实践计划")
            core_skills = []
            for dr in deconstruction_results:
                core_skills.append({
                    "name": dr["target_skill"],
                    "core_20pct": dr.get("core_20pct", []),
                })
            practice_plan = self.practice.generate_plan(core_skills, target_domain)
            ring_results["practice"] = practice_plan.to_dict()
            tool_calls.append("practice.generate_plan")
            self._write_memory("practice", ring_results["practice"])

            # Ring 4: 变现路径
            self.state = StrategyFlywheelState.MONETIZING
            logger.info(f"[{self.session_id}] Ring 4: 变现路径设计")
            skill_framework = {
                "skills": radar_result.skills,
                "recommended_focus": radar_result.recommended_focus,
                "knowledge_trees": [dr.get("knowledge_tree", {}) for dr in deconstruction_results],
                "practice_plan": practice_plan.to_dict(),
            }
            monetization_paths = self.monetization.generate_paths(skill_framework, target_domain)
            ring_results["monetization"] = [p.to_dict() for p in monetization_paths]
            tool_calls.append("monetization.generate_paths")
            self._write_memory("monetization", ring_results["monetization"])

            # 完成
            self.state = StrategyFlywheelState.COMPLETED
            duration = round(time.time() - start_time, 2)
            logger.info(f"[{self.session_id}] 飞轮完成，耗时 {duration}s")

            reply = self._build_summary_reply(target_domain, ring_results)

            return StrategyFlywheelResponse(
                reply=reply,
                session_id=self.session_id,
                state=self.state,
                data={
                    "target_domain": target_domain,
                    "duration_seconds": duration,
                    "llm_used": self.llm_client is not None,
                },
                ring_results=ring_results,
                tool_calls=tool_calls,
            )

        except Exception as e:
            logger.error(f"[{self.session_id}] 飞轮执行错误: {e}", exc_info=True)
            self.state = StrategyFlywheelState.ERROR
            return StrategyFlywheelResponse(
                reply=f"❌ 战略飞轮执行出错: {str(e)}\n\n请检查日志或稍后重试。",
                session_id=self.session_id,
                state=self.state,
                data={"error": str(e), "target_domain": target_domain},
                ring_results=ring_results,
                tool_calls=tool_calls,
            )

    async def scan_only(self, target_domain: str) -> StrategyFlywheelResponse:
        """仅执行雷达扫描环"""
        self.state = StrategyFlywheelState.RADAR_SCANNING
        result = self.radar.scan(target_domain)
        self._write_memory("radar", result.to_dict())
        self.state = StrategyFlywheelState.COMPLETED
        return StrategyFlywheelResponse(
            reply=self._format_radar_reply(result),
            session_id=self.session_id,
            state=self.state,
            data={"target_domain": target_domain},
            ring_results={"radar": result.to_dict()},
            tool_calls=["radar.scan"],
        )

    async def deconstruct_only(self, target_skill: str) -> StrategyFlywheelResponse:
        """仅执行第一性原理拆解环"""
        self.state = StrategyFlywheelState.DECONSTRUCTING
        result = self.meta.deconstruct(target_skill)
        self._write_memory("deconstruction", result.to_dict())
        self.state = StrategyFlywheelState.COMPLETED
        return StrategyFlywheelResponse(
            reply=self._format_deconstruction_reply(result),
            session_id=self.session_id,
            state=self.state,
            data={"target_skill": target_skill},
            ring_results={"deconstruction": result.to_dict()},
            tool_calls=["meta.deconstruct"],
        )

    async def generate_plan_only(self, core_skills: List[Dict[str, Any]], target_domain: str = "") -> StrategyFlywheelResponse:
        """仅生成实践计划"""
        self.state = StrategyFlywheelState.PRACTICING
        result = self.practice.generate_plan(core_skills, target_domain)
        self._write_memory("practice", result.to_dict())
        self.state = StrategyFlywheelState.COMPLETED
        return StrategyFlywheelResponse(
            reply=self._format_practice_reply(result),
            session_id=self.session_id,
            state=self.state,
            data={"target_domain": target_domain},
            ring_results={"practice": result.to_dict()},
            tool_calls=["practice.generate_plan"],
        )

    async def monetize_only(self, skill_framework: Dict[str, Any], target_domain: str = "") -> StrategyFlywheelResponse:
        """仅生成变现路径"""
        self.state = StrategyFlywheelState.MONETIZING
        results = self.monetization.generate_paths(skill_framework, target_domain)
        ring_data = [r.to_dict() for r in results]
        self._write_memory("monetization", ring_data)
        self.state = StrategyFlywheelState.COMPLETED
        return StrategyFlywheelResponse(
            reply=self._format_monetization_reply(results),
            session_id=self.session_id,
            state=self.state,
            data={"target_domain": target_domain},
            ring_results={"monetization": ring_data},
            tool_calls=["monetization.generate_paths"],
        )

    def troubleshoot(self, user_description: str, goal: str = "") -> List[str]:
        """
        卡壳诊断与追问引导。

        Args:
            user_description: 用户描述的卡壳情况
            goal: 用户的总体目标
        """
        stuck_type = self.troubleshooter.diagnose(user_description)
        return self.troubleshooter.guide(stuck_type, {"goal": goal})

    # ------------------------------------------------------------------ #
    # 记忆写入
    # ------------------------------------------------------------------ #

    def _write_memory(self, ring_name: str, data: Any):
        """将飞轮环的执行结果写入 L2 Episodic"""
        if not self.enable_memory:
            return
        try:
            mm = get_memory_manager()
            key = f"flywheel:{self.session_id}:{ring_name}"
            mm.write(
                layer="L2",
                key=key,
                value={
                    "ring": ring_name,
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "timestamp": datetime.now().isoformat(),
                    "data": data,
                },
                metadata={"source": "strategy_flywheel", "ring": ring_name},
                user_id=self.user_id,
            )
        except Exception as e:
            logger.warning(f"记忆写入失败（非阻断）: {e}")

    # ------------------------------------------------------------------ #
    # 格式化输出
    # ------------------------------------------------------------------ #

    def _build_summary_reply(self, target_domain: str, ring_results: Dict[str, Any]) -> str:
        """构建完整飞轮的 Markdown 总结报告"""
        lines = [
            f"# 🎯 {target_domain} — 战略飞轮报告",
            "",
            "---",
            "",
        ]

        # Ring 1
        radar = ring_results.get("radar", {})
        lines.extend([
            "## 📡 Ring 1: 技能雷达扫描",
            "",
            f"**推荐聚焦技能**: {', '.join(radar.get('recommended_focus', []))}",
            "",
            "| 技能 | 需求度 | 稀缺度 | 增长率 | 薪资范围 |",
            "|------|--------|--------|--------|----------|",
        ])
        for skill in radar.get("skills", [])[:5]:
            lines.append(
                f"| {skill.get('name', '-')} | "
                f"{skill.get('demand_score', 0):.0%} | "
                f"{skill.get('rarity_score', 0):.0%} | "
                f"{skill.get('growth_rate', 0):.0%} | "
                f"{skill.get('salary_range', '-')} |"
            )
        lines.append("")

        # Ring 2
        decon = ring_results.get("deconstruction", {})
        lines.extend([
            "## 🔬 Ring 2: 第一性原理拆解",
            "",
        ])
        for dr in decon.get("results", []):
            lines.extend([
                f"### {dr.get('target_skill', '')}",
                "",
                "**核心 20%（必须掌握）**:",
            ])
            for item in dr.get("core_20pct", []):
                lines.append(f"- ✅ {item}")
            lines.append("")
            lines.append("**可跳过 80%（需要时查阅）**:")
            for item in dr.get("skippable_80pct", []):
                lines.append(f"- ⏭️ {item}")
            lines.append("")
            lines.append("**第一性原理**:")
            for principle in dr.get("first_principles", []):
                lines.append(f"> 💡 {principle}")
            lines.append("")

        # Ring 3
        practice = ring_results.get("practice", {})
        lines.extend([
            "## 🏋️ Ring 3: 90 天实践计划",
            "",
            f"**总投入**: 约 {practice.get('total_hours', 0)} 小时",
            "",
            "**里程碑**:",
        ])
        for ms in practice.get("milestones", []):
            lines.append(f"- **第{ms.get('week', '?')}周** — {ms.get('phase', '')}: {ms.get('goal', '')}")
        lines.append("")
        lines.append("**实战项目**:")
        for proj in practice.get("projects", []):
            lines.append(f"- 📦 {proj.get('name', '')}: {proj.get('description', '')}")
        lines.append("")

        # Ring 4
        monetization = ring_results.get("monetization", [])
        lines.extend([
            "## 💰 Ring 4: 变现路径",
            "",
        ])
        for path in monetization:
            lines.extend([
                f"### {path.get('title', '')}",
                "",
                f"{path.get('description', '')}",
                "",
                f"- 🏷️ 类型: {path.get('path_type', '')} | 风险: {path.get('risk_level', '')}",
                f"- 💵 启动成本: {path.get('startup_cost', '')}",
                f"- 📅 时间线: {path.get('timeline', '')}",
                "",
                "**收入预估**:",
            ])
            forecast = path.get("income_forecast", {})
            for k, v in forecast.items():
                lines.append(f"- {k}: {v}")
            lines.append("")
            lines.append("**行动步骤**:")
            for i, step in enumerate(path.get("action_steps", []), 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        lines.extend([
            "---",
            "",
            f"📊 数据来源: {'LLM 增强' if self.llm_client else '规则模板'} | Session: `{self.session_id}`",
        ])

        return "\n".join(lines)

    def _format_radar_reply(self, result: SkillRadarResult) -> str:
        lines = [
            f"# 📡 {result.target_domain} 技能雷达",
            "",
            "**推荐聚焦**:",
        ]
        for skill in result.recommended_focus:
            lines.append(f"- 🎯 {skill}")
        lines.append("")
        lines.append("**Top 技能**:")
        for skill in result.skills[:5]:
            lines.append(
                f"- {skill.get('name')} | 需求 {skill.get('demand_score', 0):.0%} | "
                f"稀缺 {skill.get('rarity_score', 0):.0%} | 增长 {skill.get('growth_rate', 0):.0%} | "
                f"💰 {skill.get('salary_range', '-')}"
            )
        return "\n".join(lines)

    def _format_deconstruction_reply(self, result: DeconstructionResult) -> str:
        lines = [
            f"# 🔬 {result.target_skill} — 第一性原理拆解",
            "",
            "**核心 20%**:",
        ]
        for item in result.core_20pct:
            lines.append(f"- ✅ {item}")
        lines.append("")
        lines.append("**第一性原理**:")
        for p in result.first_principles:
            lines.append(f"> 💡 {p}")
        lines.append("")
        lines.append("**学习路径**:")
        for i, step in enumerate(result.learning_path, 1):
            lines.append(f"{i}. {step}")
        return "\n".join(lines)

    def _format_practice_reply(self, result: PracticePlan) -> str:
        lines = [
            f"# 🏋️ {result.target_skill} — 90 天实践计划",
            "",
            f"**总投入**: 约 {result.total_hours} 小时",
            "",
            "**里程碑**:",
        ]
        for ms in result.milestones:
            lines.append(f"- **第{ms.week}周** — {ms.phase}: {ms.goal}")
        lines.append("")
        lines.append("**本周任务示例**:")
        for task in result.daily_tasks[:7]:
            lines.append(f"- Day {task.day}: {task.title} ({task.estimated_minutes}min) → {task.deliverable}")
        return "\n".join(lines)

    def _format_monetization_reply(self, results: List[MonetizationPath]) -> str:
        lines = ["# 💰 变现路径设计", ""]
        for path in results:
            lines.extend([
                f"## {path.title}",
                "",
                f"{path.description}",
                "",
                f"- 风险: {path.risk_level} | 启动: {path.startup_cost}",
                "",
                "**收入预估**:",
            ])
            for k, v in path.income_forecast.items():
                lines.append(f"- {k}: {v}")
            lines.append("")
        return "\n".join(lines)
