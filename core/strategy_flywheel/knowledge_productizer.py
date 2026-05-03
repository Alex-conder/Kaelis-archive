"""
知识产品化模块

辅助用户将学习成果转化为可出售的知识产品。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeProduct:
    """知识产品定义"""
    product_type: str  # ebook | course | template | tool | community
    title: str
    description: str
    target_audience: str
    content_outline: List[str]
    pricing_suggestion: str
    platform_recommendations: List[str]
    estimated_creation_hours: int
    launch_checklist: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_type": self.product_type,
            "title": self.title,
            "description": self.description,
            "target_audience": self.target_audience,
            "content_outline": self.content_outline,
            "pricing_suggestion": self.pricing_suggestion,
            "platform_recommendations": self.platform_recommendations,
            "estimated_creation_hours": self.estimated_creation_hours,
            "launch_checklist": self.launch_checklist,
        }


class KnowledgeProductizer:
    """
    知识产品化助手。

    基于用户的技能框架和学习成果，建议并设计知识产品。
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def design_products(
        self,
        skill_framework: Dict[str, Any],
        user_level: str = "intermediate",
    ) -> List[KnowledgeProduct]:
        """
        为用户的技能框架设计知识产品。

        Args:
            skill_framework: 技能框架（来自飞轮拆解结果）
            user_level: 用户当前水平

        Returns:
            List[KnowledgeProduct]: 产品建议列表
        """
        target_domain = skill_framework.get("target_domain", "技术领域")
        top_skills = skill_framework.get("recommended_focus", [])
        primary_skill = top_skills[0] if top_skills else target_domain

        # 基于水平选择产品复杂度
        if user_level == "beginner":
            return self._beginner_products(primary_skill, target_domain)
        elif user_level == "advanced":
            return self._advanced_products(primary_skill, target_domain)
        return self._intermediate_products(primary_skill, target_domain)

    def _beginner_products(self, skill: str, domain: str) -> List[KnowledgeProduct]:
        return [
            KnowledgeProduct(
                product_type="template",
                title=f"{skill} 入门速查表",
                description=f"一张图掌握 {skill} 的核心概念和常用命令，适合新手快速上手。",
                target_audience=f"{domain} 初学者",
                content_outline=[
                    "核心概念图解",
                    "常用命令/API 速查",
                    "常见错误排查",
                    "学习资源推荐",
                ],
                pricing_suggestion="免费或 9-19 元（引流产品）",
                platform_recommendations=["小红书", "知乎", "GitHub"],
                estimated_creation_hours=8,
                launch_checklist=[
                    "制作高质量信息图",
                    "发布到 3 个平台收集反馈",
                    "根据反馈迭代",
                ],
            ),
            KnowledgeProduct(
                product_type="ebook",
                title=f"{skill} 7天入门指南",
                description=f"面向零基础的 {skill} 入门电子书，每天 1 小时，7 天掌握基础。",
                target_audience=f"想转行 {domain} 的职场人",
                content_outline=[
                    "Day 1: 环境搭建与初体验",
                    "Day 2-3: 核心概念理解",
                    "Day 4-5: 动手实践",
                    "Day 6: 项目实战",
                    "Day 7: 进阶路线规划",
                ],
                pricing_suggestion="29-49 元",
                platform_recommendations=["小册", "GitBook", "豆瓣阅读"],
                estimated_creation_hours=40,
                launch_checklist=[
                    "完成大纲和样章",
                    "找 3 位目标读者试读",
                    "根据反馈修改",
                    "选择平台发布",
                ],
            ),
        ]

    def _intermediate_products(self, skill: str, domain: str) -> List[KnowledgeProduct]:
        return [
            KnowledgeProduct(
                product_type="course",
                title=f"{skill} 实战训练营",
                description=f"通过 4 个真实项目掌握 {skill}，配有代码 review 和答疑。",
                target_audience=f"有基础想提升的 {domain} 开发者",
                content_outline=[
                    "项目1：最小可用系统",
                    "项目2：性能优化实战",
                    "项目3：边缘案例分析",
                    "项目4：生产环境部署",
                    "附：代码 review 清单",
                ],
                pricing_suggestion="199-499 元",
                platform_recommendations=["知识星球", "极客时间", "网易云课堂"],
                estimated_creation_hours=80,
                launch_checklist=[
                    "录制 1 节试看课程",
                    "搭建学员社群",
                    "设计作业和 review 流程",
                    "早鸟价预售",
                ],
            ),
            KnowledgeProduct(
                product_type="tool",
                title=f"{skill} 开发脚手架",
                description=f"开源的 {skill} 项目模板，包含最佳实践配置和示例代码。",
                target_audience=f"{domain} 开发者",
                content_outline=[
                    "项目结构模板",
                    "配置文件最佳实践",
                    "常用工具链集成",
                    "CI/CD 配置示例",
                    "文档和教程",
                ],
                pricing_suggestion="开源免费 + 赞助/企业版",
                platform_recommendations=["GitHub", "Gitee"],
                estimated_creation_hours=60,
                launch_checklist=[
                    "完成 MVP 模板",
                    "编写详细 README",
                    "录制 5 分钟上手视频",
                    "分享到技术社区",
                ],
            ),
        ]

    def _advanced_products(self, skill: str, domain: str) -> List[KnowledgeProduct]:
        return [
            KnowledgeProduct(
                product_type="community",
                title=f"{skill} 深度研习社",
                description=f"面向 {skill} 专家的高阶交流社群，每月深度主题研讨。",
                target_audience=f"{domain} 高级工程师/架构师",
                content_outline=[
                    "月度主题研讨",
                    "源码共读",
                    "疑难案例会诊",
                    "内推机会共享",
                    "线下聚会",
                ],
                pricing_suggestion="年费 999-1999 元",
                platform_recommendations=["知识星球", "Discord", "微信群"],
                estimated_creation_hours=20,
                launch_checklist=[
                    "邀请 10 位种子成员",
                    "设计社群规则",
                    "策划前 3 个月主题",
                    "持续运营",
                ],
            ),
            KnowledgeProduct(
                product_type="consulting",
                title=f"{skill} 架构咨询服务",
                description=f"为企业提供 {skill} 相关的技术咨询和架构设计服务。",
                target_audience="有技术需求的企业",
                content_outline=[
                    "需求诊断",
                    "架构设计",
                    "实施指导",
                    "团队培训",
                ],
                pricing_suggestion="按小时 500-2000 元 或项目制",
                platform_recommendations=["直接客户", "Toptal", "Arc"],
                estimated_creation_hours=0,
                launch_checklist=[
                    "整理案例集",
                    "建立个人品牌",
                    "获取首批客户推荐",
                ],
            ),
        ]
