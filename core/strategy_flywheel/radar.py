"""
战略雷达扫描模块

技能雷达图 + 行业需求热力图 + 薪资锚点
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 降级策略：内置行业-技能映射模板
FALLBACK_DOMAIN_SKILLS: Dict[str, List[Dict[str, Any]]] = {
    "ai_agent_architect": [
        {"name": "LLM 架构设计", "demand_score": 0.95, "salary_range": "40-80万", "growth_rate": 0.35, "rarity_score": 0.90},
        {"name": "RAG 系统构建", "demand_score": 0.90, "salary_range": "35-70万", "growth_rate": 0.40, "rarity_score": 0.85},
        {"name": "Agent 编排框架", "demand_score": 0.88, "salary_range": "35-70万", "growth_rate": 0.45, "rarity_score": 0.88},
        {"name": "Prompt Engineering", "demand_score": 0.85, "salary_range": "30-60万", "growth_rate": 0.30, "rarity_score": 0.60},
        {"name": "向量数据库", "demand_score": 0.80, "salary_range": "30-55万", "growth_rate": 0.25, "rarity_score": 0.75},
        {"name": "MCP/Function Calling", "demand_score": 0.78, "salary_range": "28-55万", "growth_rate": 0.50, "rarity_score": 0.82},
        {"name": "多模态理解", "demand_score": 0.75, "salary_range": "35-65万", "growth_rate": 0.35, "rarity_score": 0.85},
        {"name": "模型微调", "demand_score": 0.72, "salary_range": "30-60万", "growth_rate": 0.20, "rarity_score": 0.80},
    ],
    "data_scientist": [
        {"name": "机器学习", "demand_score": 0.92, "salary_range": "35-70万", "growth_rate": 0.20, "rarity_score": 0.70},
        {"name": "深度学习", "demand_score": 0.88, "salary_range": "40-80万", "growth_rate": 0.22, "rarity_score": 0.80},
        {"name": "数据工程", "demand_score": 0.85, "salary_range": "30-60万", "growth_rate": 0.18, "rarity_score": 0.55},
        {"name": "SQL/数据查询", "demand_score": 0.80, "salary_range": "25-50万", "growth_rate": 0.10, "rarity_score": 0.30},
        {"name": "数据可视化", "demand_score": 0.75, "salary_range": "25-45万", "growth_rate": 0.15, "rarity_score": 0.40},
    ],
    "fullstack_dev": [
        {"name": "React/Vue", "demand_score": 0.90, "salary_range": "25-50万", "growth_rate": 0.15, "rarity_score": 0.35},
        {"name": "Node.js/Python后端", "demand_score": 0.88, "salary_range": "25-50万", "growth_rate": 0.12, "rarity_score": 0.40},
        {"name": "云原生/DevOps", "demand_score": 0.85, "salary_range": "30-60万", "growth_rate": 0.25, "rarity_score": 0.65},
        {"name": "微服务架构", "demand_score": 0.82, "salary_range": "30-55万", "growth_rate": 0.18, "rarity_score": 0.60},
        {"name": "数据库设计", "demand_score": 0.80, "salary_range": "25-50万", "growth_rate": 0.10, "rarity_score": 0.45},
    ],
}


@dataclass
class SkillRadarResult:
    """技能雷达扫描结果"""
    target_domain: str
    skills: List[Dict[str, Any]] = field(default_factory=list)
    market_heatmap: Dict[str, Any] = field(default_factory=dict)
    recommended_focus: List[str] = field(default_factory=list)
    salary_anchor: Dict[str, Any] = field(default_factory=dict)
    data_source: str = "llm"  # llm | fallback

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_domain": self.target_domain,
            "skills": self.skills,
            "market_heatmap": self.market_heatmap,
            "recommended_focus": self.recommended_focus,
            "salary_anchor": self.salary_anchor,
            "data_source": self.data_source,
        }


class StrategyRadar:
    """
    战略雷达扫描器。

    扫描目标领域的高价值技能、市场需求、薪资水平，
    输出技能雷达图数据与聚焦建议。
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def _normalize_domain(self, domain: str) -> str:
        """将用户输入的领域名归一化为模板 key"""
        domain_lower = domain.lower()
        if any(kw in domain_lower for kw in ["ai agent", "agent", "llm", "大模型", "智能体"]):
            return "ai_agent_architect"
        if any(kw in domain_lower for kw in ["数据科学", "data science", "机器学习", "machine learning"]):
            return "data_scientist"
        if any(kw in domain_lower for kw in ["全栈", "fullstack", "web", "前端", "后端"]):
            return "fullstack_dev"
        return "ai_agent_architect"  # 默认

    def _build_radar_prompt(self, domain: str) -> str:
        return f"""你是一位顶级职业规划顾问。请针对"{domain}"领域进行技能雷达扫描。

请输出严格的 JSON 格式（不要包含 markdown 代码块标记）：
{{
  "skills": [
    {{
      "name": "技能名称",
      "demand_score": 0.0-1.0,
      "salary_range": "年薪范围（万）",
      "growth_rate": 0.0-1.0,
      "rarity_score": 0.0-1.0
    }}
  ],
  "market_heatmap": {{
    "overall_demand": 0.0-1.0,
    "talent_gap": 0.0-1.0,
    "technology_maturity": 0.0-1.0,
    "investment_trend": 0.0-1.0
  }},
  "recommended_focus": ["优先学习的技能1", "技能2", "技能3"],
  "salary_anchor": {{
    "junior": "年薪范围",
    "mid": "年薪范围",
    "senior": "年薪范围",
    "expert": "年薪范围"
  }}
}}

要求：
1. 列出 6-10 个核心技能
2. demand_score 反映市场招聘需求量（1.0=极高）
3. rarity_score 反映人才稀缺度（1.0=极稀缺）
4. growth_rate 反映未来3年增长趋势
"""

    def scan(self, target_domain: str) -> SkillRadarResult:
        """
        扫描目标领域，返回技能雷达图数据。

        优先使用 LLM 生成，LLM 不可用时回退到内置模板。
        """
        # 尝试 LLM 生成
        if self.llm_client:
            try:
                result = self._scan_with_llm(target_domain)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"LLM 雷达扫描失败，回退到模板: {e}")

        # 回退到模板
        return self._scan_with_fallback(target_domain)

    def _scan_with_llm(self, domain: str) -> Optional[SkillRadarResult]:
        prompt = self._build_radar_prompt(domain)
        response = self.llm_client.chat(
            prompt=prompt,
            system_prompt="你是一个专业的职业规划 AI，擅长分析技术领域的技能需求和市场趋势。",
            temperature=0.3,
            json_mode=True,
        )
        data = json.loads(response)
        return SkillRadarResult(
            target_domain=domain,
            skills=data.get("skills", []),
            market_heatmap=data.get("market_heatmap", {}),
            recommended_focus=data.get("recommended_focus", []),
            salary_anchor=data.get("salary_anchor", {}),
            data_source="llm",
        )

    def _scan_with_fallback(self, domain: str) -> SkillRadarResult:
        normalized = self._normalize_domain(domain)
        skills = FALLBACK_DOMAIN_SKILLS.get(normalized, FALLBACK_DOMAIN_SKILLS["ai_agent_architect"])

        # 按 (需求 × 稀缺度) 排序，取 Top 5 作为推荐聚焦
        scored = [
            (s, s["demand_score"] * s["rarity_score"] * (1 + s["growth_rate"]))
            for s in skills
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        recommended = [s[0]["name"] for s in scored[:5]]

        # 市场热力图
        avg_demand = sum(s["demand_score"] for s in skills) / len(skills) if skills else 0.5
        avg_rarity = sum(s["rarity_score"] for s in skills) / len(skills) if skills else 0.5
        avg_growth = sum(s["growth_rate"] for s in skills) / len(skills) if skills else 0.5

        return SkillRadarResult(
            target_domain=domain,
            skills=skills,
            market_heatmap={
                "overall_demand": round(avg_demand, 2),
                "talent_gap": round(avg_rarity, 2),
                "technology_maturity": round(0.5, 2),
                "investment_trend": round(avg_growth, 2),
            },
            recommended_focus=recommended,
            salary_anchor={
                "junior": "15-25万",
                "mid": "25-45万",
                "senior": "45-70万",
                "expert": "70-120万",
            },
            data_source="fallback",
        )
