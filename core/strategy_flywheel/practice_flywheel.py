"""
20/80 实践飞轮 — 刻意练习引擎

将核心知识点转化为可执行的 90 天行动计划，包含每日微练习和项目里程碑。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class DailyTask:
    """每日任务"""
    day: int
    title: str
    description: str
    estimated_minutes: int
    deliverable: str
    skill_tag: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "title": self.title,
            "description": self.description,
            "estimated_minutes": self.estimated_minutes,
            "deliverable": self.deliverable,
            "skill_tag": self.skill_tag,
        }


@dataclass
class Milestone:
    """项目里程碑"""
    phase: str
    week: int
    goal: str
    deliverable: str
    success_criteria: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "week": self.week,
            "goal": self.goal,
            "deliverable": self.deliverable,
            "success_criteria": self.success_criteria,
        }


@dataclass
class PracticePlan:
    """90 天实践计划"""
    target_skill: str
    daily_tasks: List[DailyTask] = field(default_factory=list)
    milestones: List[Milestone] = field(default_factory=list)
    review_schedule: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    total_hours: int = 0
    data_source: str = "llm"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_skill": self.target_skill,
            "daily_tasks": [t.to_dict() for t in self.daily_tasks],
            "milestones": [m.to_dict() for m in self.milestones],
            "review_schedule": self.review_schedule,
            "projects": self.projects,
            "total_hours": self.total_hours,
            "data_source": self.data_source,
        }


class PracticeFlywheel:
    """
    20/80 实践飞轮。

    基于核心技能列表生成 90 天刻意练习计划，
    包含每日微练习、项目里程碑和复习节奏。
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def generate_plan(self, core_skills: List[Dict[str, Any]], target_domain: str = "") -> PracticePlan:
        """
        为核心技能列表生成 90 天实践计划。

        Args:
            core_skills: 核心技能列表，每项包含 name 和 core_20pct
            target_domain: 目标领域名称
        """
        if self.llm_client:
            try:
                result = self._generate_with_llm(core_skills, target_domain)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"LLM 实践计划生成失败，回退到模板: {e}")

        return self._generate_with_fallback(core_skills, target_domain)

    def _generate_with_llm(self, core_skills: List[Dict[str, Any]], target_domain: str) -> Optional[PracticePlan]:
        skills_text = json.dumps(core_skills, ensure_ascii=False, indent=2)
        prompt = f"""你是一位高效学习教练。请基于以下核心技能，设计一个 90 天刻意练习计划。

目标领域: {target_domain}
核心技能:
{skills_text}

请输出严格的 JSON 格式（不要包含 markdown 代码块标记）：
{{
  "milestones": [
    {{
      "phase": "阶段名称（如：基础构建）",
      "week": 1,
      "goal": "阶段目标",
      "deliverable": "可交付成果",
      "success_criteria": ["成功标准1", "标准2"]
    }}
  ],
  "daily_tasks": [
    {{
      "day": 1,
      "title": "任务标题",
      "description": "任务描述（具体可执行）",
      "estimated_minutes": 30,
      "deliverable": "今天必须产出的成果",
      "skill_tag": "相关技能"
    }}
  ],
  "review_schedule": [
    {{"week": 1, "type": "周复盘", "focus": "复盘重点"}}
  ],
  "projects": [
    {{
      "name": "项目名称",
      "description": "项目描述",
      "weeks": "第几周开始",
      "skills_applied": ["技能1", "技能2"]
    }}
  ],
  "total_hours": 120
}}

要求：
1. 每日任务控制在 30-60 分钟，确保可持续性
2. 包含 3-4 个里程碑，每个里程碑有明确的可交付成果
3. 设计 2-3 个实战项目，将所学技能串联应用
4. 每周安排一次复盘
"""
        response = self.llm_client.chat(
            prompt=prompt,
            system_prompt="你是一位专精 20/80 法则的学习教练，擅长设计高密度、可持续的刻意练习计划。",
            temperature=0.4,
            json_mode=True,
        )
        data = json.loads(response)

        daily_tasks = [DailyTask(**t) for t in data.get("daily_tasks", [])]
        milestones = [Milestone(**m) for m in data.get("milestones", [])]

        return PracticePlan(
            target_skill=target_domain,
            daily_tasks=daily_tasks,
            milestones=milestones,
            review_schedule=data.get("review_schedule", []),
            projects=data.get("projects", []),
            total_hours=data.get("total_hours", 0),
            data_source="llm",
        )

    def _generate_with_fallback(self, core_skills: List[Dict[str, Any]], target_domain: str) -> PracticePlan:
        """使用模板生成实践计划"""
        skill_names = [s.get("name", "未知技能") for s in core_skills]
        primary_skill = skill_names[0] if skill_names else target_domain

        milestones = [
            Milestone(
                phase="基础构建",
                week=1,
                goal=f"掌握 {primary_skill} 的核心概念和第一性原理",
                deliverable="完成核心概念笔记，构建知识框架图",
                success_criteria=["能用自己的话解释核心概念", "画出知识框架树"],
            ),
            Milestone(
                phase="最小实践",
                week=4,
                goal="构建第一个可运行的最小系统",
                deliverable=f"完成一个基础的 {primary_skill} Demo",
                success_criteria=["Demo 能独立完成核心功能", "遇到问题时知道去哪里查资料"],
            ),
            Milestone(
                phase="项目实战",
                week=8,
                goal="完成一个完整的实战项目",
                deliverable=f"{primary_skill} 实战项目 + 技术博客",
                success_criteria=["项目代码可运行", "博客获得 3+ 互动"],
            ),
            Milestone(
                phase="优化迭代",
                week=12,
                goal="系统优化，形成个人方法论",
                deliverable="个人知识库 + 优化后的项目",
                success_criteria=["能独立解决 80% 的常见问题", "形成可复用的代码/方法论模板"],
            ),
        ]

        daily_tasks = []
        for day in range(1, 91):
            week = (day - 1) // 7 + 1
            if day % 7 == 0:
                # 每周日复盘
                daily_tasks.append(DailyTask(
                    day=day,
                    title=f"第{week}周复盘",
                    description=f"回顾本周学习的内容，整理错题/卡点，更新知识框架",
                    estimated_minutes=45,
                    deliverable=f"第{week}周复盘笔记",
                    skill_tag="元认知",
                ))
            else:
                task_types = [
                    ("理论学习", f"阅读 {primary_skill} 相关文档/论文，理解核心原理", 30),
                    ("代码实践", f"动手实现 {primary_skill} 的一个功能点", 45),
                    ("项目开发", f"在实战项目中应用 {primary_skill}", 60),
                    ("阅读源码", f"阅读优秀开源项目的 {primary_skill} 实现", 30),
                    ("写作输出", f"写一篇关于 {primary_skill} 的技术博客", 45),
                    ("问题解决", f"尝试解决一个 {primary_skill} 相关的实际问题", 45),
                ]
                task_idx = (day - 1) % len(task_types)
                title, desc, minutes = task_types[task_idx]
                daily_tasks.append(DailyTask(
                    day=day,
                    title=title,
                    description=desc,
                    estimated_minutes=minutes,
                    deliverable=f"{title}产出物",
                    skill_tag=primary_skill,
                ))

        projects = [
            {
                "name": f"{primary_skill} 入门 Demo",
                "description": f"实现一个基础的 {primary_skill} 功能，验证核心概念理解",
                "weeks": "第2-3周",
                "skills_applied": skill_names[:2],
            },
            {
                "name": f"{primary_skill} 实战项目",
                "description": f"结合业务场景，构建一个完整的 {primary_skill} 应用",
                "weeks": "第6-10周",
                "skills_applied": skill_names,
            },
        ]

        review_schedule = [
            {"week": w, "type": "周复盘", "focus": f"回顾第{w}周学习成果，识别卡点"}
            for w in range(1, 13)
        ]
        review_schedule.extend([
            {"week": 4, "type": "月复盘", "focus": "评估里程碑达成情况，调整下月计划"},
            {"week": 8, "type": "月复盘", "focus": "评估项目进度，优化学习策略"},
            {"week": 12, "type": "终期复盘", "focus": "总结 90 天成果，规划下一步"},
        ])

        return PracticePlan(
            target_skill=target_domain,
            daily_tasks=daily_tasks,
            milestones=milestones,
            review_schedule=review_schedule,
            projects=projects,
            total_hours=180,
            data_source="fallback",
        )


class Troubleshooter:
    """
    卡壳追问引导器。

    当用户在实践中遇到卡点时，通过追问引导用户找到突破口。
    """

    TROUBLESHOOTING_TEMPLATES = {
        "concept_stuck": [
            "你能否用一句话向一个10岁小孩解释这个概念的核心？",
            "这个概念和你已经熟悉的哪个知识最相似？它们的区别是什么？",
            "如果跳过这个概念，你现在的项目还能继续吗？如果不能，卡住的具体是哪一步？",
        ],
        "code_stuck": [
            "你的代码目前报什么错？请把完整错误信息贴出来。",
            "如果你只能改一行代码，你会改哪里？为什么？",
            "这个功能的输入和输出分别是什么？你能用3个具体例子说明吗？",
            "你有没有尝试把问题分解成更小的子问题？最小的那个子问题是什么？",
        ],
        "motivation_stuck": [
            "你今天学习的这个知识点，和你最初的目标（{goal}）有什么直接联系？",
            "如果明天是世界末日，你今天学的这个技能能帮你做什么？",
            "你能想象一个场景，掌握这个技能后你解决了什么具体问题？",
        ],
        "direction_stuck": [
            "你现在的能力和目标岗位要求之间，差距最大的三个点是什么？",
            "如果给你三个月时间，你最想先解决哪个具体问题？",
            "你有没有找到一个已经达成目标的人？他的路径和你的有什么不一样？",
        ],
    }

    def guide(self, stuck_type: str, context: Dict[str, Any]) -> List[str]:
        """
        根据卡壳类型生成追问列表。

        Args:
            stuck_type: concept_stuck | code_stuck | motivation_stuck | direction_stuck
            context: 包含 goal 等上下文信息
        """
        templates = self.TROUBLESHOOTING_TEMPLATES.get(stuck_type, self.TROUBLESHOOTING_TEMPLATES["concept_stuck"])
        goal = context.get("goal", "达成目标")
        return [t.format(goal=goal) for t in templates]

    def diagnose(self, user_description: str) -> str:
        """
        根据用户描述诊断卡壳类型。
        """
        desc_lower = user_description.lower()
        if any(kw in desc_lower for kw in ["报错", "错误", "exception", "error", "bug", "运行", "代码"]):
            return "code_stuck"
        if any(kw in desc_lower for kw in ["不懂", "不理解", "概念", "什么意思", "原理"]):
            return "concept_stuck"
        if any(kw in desc_lower for kw in ["不想学", "没动力", "坚持", "懒", "放弃"]):
            return "motivation_stuck"
        if any(kw in desc_lower for kw in ["方向", "迷茫", "不知道", "选哪个", "怎么开始"]):
            return "direction_stuck"
        return "concept_stuck"  # 默认
