"""
职业档案构建模块

辅助用户构建可验证的学习成果档案（GitHub 贡献者档案）。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CredentialItem:
    """单条可验证成果"""
    item_type: str  # project | article | certification | contribution
    title: str
    description: str
    evidence_url: str
    verified_by: str
    date: str
    skills_demonstrated: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_type": self.item_type,
            "title": self.title,
            "description": self.description,
            "evidence_url": self.evidence_url,
            "verified_by": self.verified_by,
            "date": self.date,
            "skills_demonstrated": self.skills_demonstrated,
        }


class CredentialBuilder:
    """
    职业档案构建器。

    基于飞轮学习成果，生成可验证的职业档案：
    - GitHub 开源项目推荐
    - 技术博客选题建议
    - 认证考试规划
    """

    def __init__(self, user_id: str = "anonymous"):
        self.user_id = user_id

    def build_credential_plan(
        self,
        skill_framework: Dict[str, Any],
        practice_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        构建职业档案规划。

        Args:
            skill_framework: 技能框架
            practice_plan: 实践计划

        Returns:
            包含项目、文章、认证计划的完整档案规划
        """
        target_domain = skill_framework.get("target_domain", "技术领域")
        skills = skill_framework.get("recommended_focus", [])
        milestones = practice_plan.get("milestones", [])

        projects = self._suggest_projects(target_domain, skills, milestones)
        articles = self._suggest_articles(target_domain, skills)
        certifications = self._suggest_certifications(target_domain, skills)

        return {
            "target_domain": target_domain,
            "projects": [p.to_dict() for p in projects],
            "articles": [a.to_dict() for a in articles],
            "certifications": [c.to_dict() for c in certifications],
            "timeline": self._build_timeline(projects, articles, certifications),
        }

    def _suggest_projects(
        self,
        domain: str,
        skills: List[str],
        milestones: List[Dict],
    ) -> List[CredentialItem]:
        """建议开源项目"""
        primary_skill = skills[0] if skills else domain
        return [
            CredentialItem(
                item_type="project",
                title=f"{primary_skill} Starter Template",
                description=f"一个开箱即用的 {primary_skill} 项目模板，包含最佳实践配置",
                evidence_url="https://github.com/yourusername/{repo}",
                verified_by="GitHub Stars & Forks",
                date="第4周",
                skills_demonstrated=skills[:2],
            ),
            CredentialItem(
                item_type="project",
                title=f"{domain} 实战项目",
                description=f"完整的 {domain} 应用，解决实际业务问题",
                evidence_url="https://github.com/yourusername/{repo}",
                verified_by="GitHub + 实际用户反馈",
                date="第10周",
                skills_demonstrated=skills,
            ),
        ]

    def _suggest_articles(
        self,
        domain: str,
        skills: List[str],
    ) -> List[CredentialItem]:
        """建议技术博客选题"""
        primary_skill = skills[0] if skills else domain
        return [
            CredentialItem(
                item_type="article",
                title=f"{primary_skill} 入门避坑指南",
                description=f"基于个人学习经验总结的 {primary_skill} 常见误区",
                evidence_url="https://yourblog.com/article1",
                verified_by="阅读量 + 评论互动",
                date="第2周",
                skills_demonstrated=[primary_skill],
            ),
            CredentialItem(
                item_type="article",
                title=f"我用 {primary_skill} 解决了什么问题",
                description="通过一个具体案例展示技能应用",
                evidence_url="https://yourblog.com/article2",
                verified_by="阅读量 + 实际案例验证",
                date="第6周",
                skills_demonstrated=skills[:2],
            ),
            CredentialItem(
                item_type="article",
                title=f"{domain} 从入门到实战：我的 90 天学习路线",
                description="完整的学习复盘和路线图分享",
                evidence_url="https://yourblog.com/article3",
                verified_by="阅读量 + 读者反馈",
                date="第12周",
                skills_demonstrated=skills,
            ),
        ]

    def _suggest_certifications(
        self,
        domain: str,
        skills: List[str],
    ) -> List[CredentialItem]:
        """建议认证考试"""
        # 基于领域推荐认证
        cert_map = {
            "ai_agent_architect": [
                ("AWS Machine Learning Specialty", "云厂商 ML 认证"),
                ("Google Cloud Professional ML Engineer", "GCP ML 工程师认证"),
            ],
            "data_scientist": [
                ("AWS Certified Data Analytics", "数据分析认证"),
                ("TensorFlow Developer Certificate", "TensorFlow 开发者认证"),
            ],
            "fullstack_dev": [
                ("AWS Certified Developer", "云开发认证"),
                ("CKA (Certified Kubernetes Administrator)", "K8s 管理员认证"),
            ],
        }

        domain_key = "ai_agent_architect"  # 默认
        if "数据" in domain or "data" in domain.lower():
            domain_key = "data_scientist"
        elif "全栈" in domain or "web" in domain.lower():
            domain_key = "fullstack_dev"

        certs = cert_map.get(domain_key, cert_map["ai_agent_architect"])
        return [
            CredentialItem(
                item_type="certification",
                title=cert[0],
                description=cert[1],
                evidence_url="https://aws.amazon.com/certification/",
                verified_by="官方认证机构",
                date="第8-12周",
                skills_demonstrated=skills[:2],
            )
            for cert in certs
        ]

    def _build_timeline(
        self,
        projects: List[CredentialItem],
        articles: List[CredentialItem],
        certifications: List[CredentialItem],
    ) -> List[Dict[str, Any]]:
        """构建时间线"""
        timeline = []
        all_items = projects + articles + certifications
        for item in sorted(all_items, key=lambda x: x.date):
            timeline.append({
                "date": item.date,
                "type": item.item_type,
                "title": item.title,
            })
        return timeline

    def generate_github_profile_readme(
        self,
        target_domain: str,
        skills: List[str],
        projects: List[Dict[str, Any]],
    ) -> str:
        """
        生成 GitHub Profile README 模板。
        """
        skill_badges = " ".join([f"`{s}`" for s in skills[:5]])
        project_list = "\n".join([
            f"- [{p.get('title')}]({p.get('evidence_url')}) — {p.get('description', '')}"
            for p in projects
        ])

        return f"""# Hi, I'm Learning {target_domain} 🚀

> 90 天 {target_domain} 学习挑战中...

## 🛠️ Skills
{skill_badges}

## 📊 Learning Progress

| Week | Milestone | Status |
|------|-----------|--------|
| 1-2  | 基础构建   | 🔄 In Progress |
| 3-4  | 最小实践   | ⏳ Planned |
| 5-8  | 项目实战   | ⏳ Planned |
| 9-12 | 优化迭代   | ⏳ Planned |

## 🚀 Projects
{project_list}

## 📝 Latest Articles
<!-- BLOG-POST-LIST:START -->
<!-- BLOG-POST-LIST:END -->

## 📈 GitHub Stats
![Your GitHub stats](https://github-readme-stats.vercel.app/api?username=yourusername&show_icons=true)

---
*Generated by [Kaelis](https://github.com/Alex-conder/Kaelis-archive) Strategy Flywheel*
"""
