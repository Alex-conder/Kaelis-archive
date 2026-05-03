"""
变现路径生成器

基于技能框架和实践计划，设计3条变现路径并计算收入预估。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MonetizationPath:
    """单条变现路径"""
    path_type: str  # freelance | product | employment | consulting
    title: str
    description: str
    income_forecast: Dict[str, str]  # {month_1: "...", month_6: "...", month_12: "..."}
    startup_cost: str
    timeline: str
    required_skills: List[str]
    risk_level: str  # low | medium | high
    action_steps: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_type": self.path_type,
            "title": self.title,
            "description": self.description,
            "income_forecast": self.income_forecast,
            "startup_cost": self.startup_cost,
            "timeline": self.timeline,
            "required_skills": self.required_skills,
            "risk_level": self.risk_level,
            "action_steps": self.action_steps,
        }


class MonetizationPathGenerator:
    """
    变现路径生成器。

    基于用户的技能框架和实践计划，设计多条变现路径，
    包含收入预估、启动成本和行动步骤。
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def generate_paths(self, skill_framework: Dict[str, Any], target_domain: str = "") -> List[MonetizationPath]:
        """
        基于技能框架生成变现路径。

        Args:
            skill_framework: 包含 skills, knowledge_tree, practice_plan 等
            target_domain: 目标领域
        """
        if self.llm_client:
            try:
                result = self._generate_with_llm(skill_framework, target_domain)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"LLM 变现路径生成失败，回退到模板: {e}")

        return self._generate_with_fallback(skill_framework, target_domain)

    def _generate_with_llm(self, skill_framework: Dict[str, Any], target_domain: str) -> Optional[List[MonetizationPath]]:
        framework_text = json.dumps(skill_framework, ensure_ascii=False, indent=2)
        prompt = f"""你是一位技术变现顾问。请基于以下技能框架，设计 3 条不同的变现路径。

目标领域: {target_domain}
技能框架:
{framework_text}

请输出严格的 JSON 格式（不要包含 markdown 代码块标记）：
{{
  "paths": [
    {{
      "path_type": "freelance|product|employment|consulting",
      "title": "路径标题",
      "description": "路径描述",
      "income_forecast": {{
        "month_1": "第一个月收入预估",
        "month_6": "第六个月收入预估",
        "month_12": "第十二个月收入预估"
      }},
      "startup_cost": "启动成本",
      "timeline": "预计时间线",
      "required_skills": ["技能1", "技能2"],
      "risk_level": "low|medium|high",
      "action_steps": ["第一步", "第二步", "第三步"]
    }}
  ]
}}

要求：
1. 设计 3 条路径，分别覆盖：自由职业/接单、产品/内容、全职/咨询
2. 收入预估要具体（如"第一个月 0-3000，第六个月 8000-15000"）
3. 启动成本要包含时间和金钱
4. 行动步骤要具体到第一周能做什么
"""
        response = self.llm_client.chat(
            prompt=prompt,
            system_prompt="你是一位帮助技术人员将技能变现的实战顾问，擅长设计低门槛、高可行性的变现路径。",
            temperature=0.4,
            json_mode=True,
        )
        data = json.loads(response)
        paths_data = data.get("paths", [])
        return [MonetizationPath(**p) for p in paths_data]

    def _generate_with_fallback(self, skill_framework: Dict[str, Any], target_domain: str) -> List[MonetizationPath]:
        """使用模板生成变现路径"""
        skills = skill_framework.get("skills", [])
        skill_names = [s.get("name", "技术技能") for s in skills[:3]]
        primary_skill = skill_names[0] if skill_names else target_domain

        return [
            MonetizationPath(
                path_type="freelance",
                title=f"{primary_skill} 自由职业接单",
                description=f"在 Upwork、Toptal、程序员客栈等平台承接 {primary_skill} 相关项目，从简单任务开始积累口碑。",
                income_forecast={
                    "month_1": "0-3,000（建立作品集）",
                    "month_6": "5,000-15,000（稳定客户）",
                    "month_12": "15,000-40,000（高价值客户）",
                },
                startup_cost="时间成本：2周准备作品集；金钱成本：0元",
                timeline="1-3个月实现首单，6个月达到稳定收入",
                required_skills=skill_names,
                risk_level="low",
                action_steps=[
                    "第1周：整理 3 个 Demo 项目作为作品集",
                    "第2周：注册 2-3 个接单平台，完善个人资料",
                    "第3周：投递 10 个低价标，获取第一个评价",
                    "第4周：根据反馈优化资料，逐步提高报价",
                ],
            ),
            MonetizationPath(
                path_type="product",
                title=f"{primary_skill} 知识产品化",
                description=f"通过技术博客、开源项目、在线课程、付费社群等方式，将 {primary_skill} 知识产品化，实现被动收入。",
                income_forecast={
                    "month_1": "0-1,000（积累内容）",
                    "month_6": "2,000-8,000（首批付费用户）",
                    "month_12": "10,000-50,000（产品矩阵）",
                },
                startup_cost="时间成本：每周 5-10 小时；金钱成本：0-500元（域名/服务器）",
                timeline="3-6个月积累粉丝，6-12个月实现变现",
                required_skills=skill_names + ["技术写作", "社区运营"],
                risk_level="medium",
                action_steps=[
                    "第1周：选择平台（GitHub/知乎/公众号/YouTube），发布第一篇内容",
                    "第2-4周：每周发布 2 篇高质量内容，建立发布节奏",
                    "第2个月：开源第一个工具/模板，收集用户反馈",
                    "第3个月：基于反馈推出第一个付费产品（小册/课程）",
                ],
            ),
            MonetizationPath(
                path_type="employment",
                title=f"{primary_skill} 高薪职位",
                description=f"瞄准 {primary_skill} 相关的高薪岗位（大厂/独角兽/外企），通过项目经验和开源贡献提升竞争力。",
                income_forecast={
                    "month_1": "0（准备面试）",
                    "month_6": "30,000-60,000（月薪）",
                    "month_12": "40,000-80,000（跳槽/晋升）",
                },
                startup_cost="时间成本：3个月准备；金钱成本：0元",
                timeline="3-6个月准备，1-3个月面试，入职后持续积累",
                required_skills=skill_names,
                risk_level="low",
                action_steps=[
                    "第1个月：完成 2 个实战项目，更新简历和 LinkedIn",
                    "第2个月：开始贡献开源项目，积累 GitHub Green",
                    "第3个月：系统刷题（LeetCode/System Design），模拟面试",
                    "第4个月：投递目标公司，内推优先",
                ],
            ),
        ]
