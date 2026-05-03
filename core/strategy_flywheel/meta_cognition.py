"""
元认知引擎 — 第一性原理拆解

将技能列表拆解为知识框架树，识别20%核心 vs 80%可跳过。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 降级策略：内置知识框架模板
FALLBACK_KNOWLEDGE_TREES: Dict[str, Dict[str, Any]] = {
    "llm_architecture": {
        "root": "LLM 架构设计",
        "branches": [
            {
                "name": "Transformer 核心机制",
                "core": True,
                "children": ["自注意力", "位置编码", "层归一化"],
            },
            {
                "name": "模型架构选型",
                "core": True,
                "children": ["Encoder-only", "Decoder-only", "Encoder-Decoder"],
            },
            {
                "name": "推理优化",
                "core": True,
                "children": ["KV Cache", "量化", " speculative decoding"],
            },
            {
                "name": "分布式训练",
                "core": False,
                "children": ["数据并行", "模型并行", "流水线并行"],
            },
            {
                "name": "模型评估",
                "core": False,
                "children": ["Perplexity", "BLEU", "人工评估"],
            },
        ],
    },
    "rag_system": {
        "root": "RAG 系统构建",
        "branches": [
            {
                "name": "文档解析与分块",
                "core": True,
                "children": ["语义分块", "重叠策略", "多模态解析"],
            },
            {
                "name": "Embedding 与索引",
                "core": True,
                "children": ["向量模型选择", "相似度算法", "索引优化"],
            },
            {
                "name": "检索策略",
                "core": True,
                "children": ["混合检索", "重排序", "查询改写"],
            },
            {
                "name": "生成增强",
                "core": True,
                "children": ["上下文压缩", "引用溯源", "多跳推理"],
            },
            {
                "name": "RAG 评估",
                "core": False,
                "children": ["答案相关性", "检索准确率", "端到端评估"],
            },
        ],
    },
    "agent_orchestration": {
        "root": "Agent 编排框架",
        "branches": [
            {
                "name": "Agent 设计模式",
                "core": True,
                "children": ["ReAct", "Plan-and-Execute", "Multi-Agent"],
            },
            {
                "name": "工具调用",
                "core": True,
                "children": ["Function Calling", "MCP", "Tool Registry"],
            },
            {
                "name": "记忆管理",
                "core": True,
                "children": ["短期记忆", "长期记忆", "向量记忆"],
            },
            {
                "name": "任务规划",
                "core": False,
                "children": ["DAG 规划", "动态重规划", "人机协作"],
            },
            {
                "name": "安全与对齐",
                "core": False,
                "children": ["Prompt 注入防护", "输出审核", "权限控制"],
            },
        ],
    },
}


@dataclass
class DeconstructionResult:
    """第一性原理拆解结果"""
    target_skill: str
    knowledge_tree: Dict[str, Any] = field(default_factory=dict)
    core_20pct: List[str] = field(default_factory=list)
    skippable_80pct: List[str] = field(default_factory=list)
    first_principles: List[str] = field(default_factory=list)
    learning_path: List[str] = field(default_factory=list)
    data_source: str = "llm"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_skill": self.target_skill,
            "knowledge_tree": self.knowledge_tree,
            "core_20pct": self.core_20pct,
            "skippable_80pct": self.skippable_80pct,
            "first_principles": self.first_principles,
            "learning_path": self.learning_path,
            "data_source": self.data_source,
        }


class MetaCognitionEngine:
    """
    元认知引擎。

    对目标技能进行第一性原理拆解，识别核心 20% 知识点和可跳过的 80%，
    输出知识框架树和学习路径。
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def _build_deconstruct_prompt(self, skill: str) -> str:
        return f"""你是一位顶尖的学习策略专家。请对"{skill}"进行第一性原理拆解。

请输出严格的 JSON 格式（不要包含 markdown 代码块标记）：
{{
  "knowledge_tree": {{
    "root": "{skill}",
    "branches": [
      {{
        "name": "知识点模块名称",
        "core": true/false,
        "children": ["子知识点1", "子知识点2"]
      }}
    ]
  }},
  "core_20pct": ["核心知识点1", "核心知识点2", "..."],
  "skippable_80pct": ["可跳过或延后学习的知识点1", "..."],
  "first_principles": ["该技能的第一性原理1", "原理2", "..."],
  "learning_path": ["阶段1：...", "阶段2：...", "阶段3：..."]
}}

要求：
1. core_20pct 必须是最关键的 20% 知识，掌握后能处理 80% 的实际场景
2. skippable_80pct 是可以在需要时查阅而非死记硬背的内容
3. first_principles 是该技能领域不变的本质规律
4. learning_path 是 3-5 个阶段的学习顺序
"""

    def deconstruct(self, target_skill: str) -> DeconstructionResult:
        """
        对目标技能进行第一性原理拆解。

        优先使用 LLM，不可用时回退到内置模板。
        """
        if self.llm_client:
            try:
                result = self._deconstruct_with_llm(target_skill)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"LLM 拆解失败，回退到模板: {e}")

        return self._deconstruct_with_fallback(target_skill)

    def _deconstruct_with_llm(self, skill: str) -> Optional[DeconstructionResult]:
        prompt = self._build_deconstruct_prompt(skill)
        response = self.llm_client.chat(
            prompt=prompt,
            system_prompt="你是一位精通第一性原理学习法的专家，擅长将复杂技能拆解为最小知识单元。",
            temperature=0.3,
            json_mode=True,
        )
        data = json.loads(response)
        return DeconstructionResult(
            target_skill=skill,
            knowledge_tree=data.get("knowledge_tree", {}),
            core_20pct=data.get("core_20pct", []),
            skippable_80pct=data.get("skippable_80pct", []),
            first_principles=data.get("first_principles", []),
            learning_path=data.get("learning_path", []),
            data_source="llm",
        )

    def _deconstruct_with_fallback(self, skill: str) -> DeconstructionResult:
        """使用内置模板回退"""
        skill_lower = skill.lower()

        # 匹配最合适的模板
        template_key = "llm_architecture"
        if any(kw in skill_lower for kw in ["rag", "检索", "向量", "embedding"]):
            template_key = "rag_system"
        elif any(kw in skill_lower for kw in ["agent", "编排", "orchestration", "mcp", "工具"]):
            template_key = "agent_orchestration"

        tree = FALLBACK_KNOWLEDGE_TREES.get(template_key, FALLBACK_KNOWLEDGE_TREES["llm_architecture"])

        # 从模板提取 core 20% 和 skippable 80%
        core = []
        skippable = []
        for branch in tree.get("branches", []):
            if branch.get("core", False):
                core.append(branch["name"])
                core.extend(branch.get("children", [])[:2])  # 前2个子节点
            else:
                skippable.append(branch["name"])
                skippable.extend(branch.get("children", []))

        # 学习路径
        learning_path = [
            f"阶段1：掌握 {skill} 的第一性原理和核心概念",
            f"阶段2：实践核心 20% 知识点，构建最小可用系统",
            f"阶段3：通过项目实战巩固，遇到卡点再补充 80% 细节",
            f"阶段4：系统优化和深度定制",
        ]

        return DeconstructionResult(
            target_skill=skill,
            knowledge_tree=tree,
            core_20pct=core[:5],
            skippable_80pct=skippable[:5],
            first_principles=[
                f"{skill} 的本质是将复杂问题分解为可计算步骤",
                f"所有 {skill} 的优化最终都归结为效率与质量的权衡",
                f"{skill} 的价值在于解决实际问题，而非理论完美",
            ],
            learning_path=learning_path,
            data_source="fallback",
        )
