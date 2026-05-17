"""
PromptBuilder - 统一提示词构建器

功能：
1. 将 Kaelis 四层记忆（L0-L3）组装为结构化上下文
2. 冲突检测结果的格式化与注入
3. Token 预算管理与智能截断
4. 输出符合 OpenAI/DeepSeek 兼容格式的 messages 或 prompt 字符串

与现有代码的集成点：
- 被 core/response_generator.py 调用
- 最终通过 core.llm_client.KaelisLLMClient.chat() 发送
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConflictSeverity(Enum):
    """记忆冲突严重程度"""
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


@dataclass
class MemoryContext:
    """用于 Prompt 构建的记忆上下文容器"""
    identity: Optional[str] = None
    active_goals: List[str] = field(default_factory=list)
    episodic_memories: List[Dict[str, Any]] = field(default_factory=list)
    semantic_facts: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    external_knowledge: Optional[str] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class BuiltPrompt:
    """构建后的提示词结构"""
    system_prompt: Optional[str] = None
    user_prompt: str = ""
    estimated_tokens: int = 0
    sections_included: List[str] = field(default_factory=list)
    sections_truncated: List[str] = field(default_factory=list)


class PromptBuilder:
    """
    统一提示词构建器。

    将 MemoryContext 转换为可直接传给 LLM API 的 prompt 结构。
    支持按优先级截断，确保在 token 预算内保留最关键的信息。
    """

    # 各部分的默认优先级（数字越小越优先保留）
    DEFAULT_PRIORITIES = {
        "identity": 1,
        "active_goals": 2,
        "conflicts": 3,
        "semantic_facts": 4,
        "episodic_memories": 5,
        "external_knowledge": 6,
        "conversation_history": 7,
        "user_query": 0,  # 永不截断
        "instructions": 0,  # 永不截断
    }

    # 混合文本平均每个 token 的字符数（中文偏多时取 0.5-0.6）
    CHARS_PER_TOKEN = 0.6

    # 默认系统指令
    DEFAULT_SYSTEM_INSTRUCTION = (
        "你是 Kaelis 智流的内置 AI 助手，拥有四层记忆系统（L0 身份 / L1 活跃目标 / "
        "L2 情景记忆 / L3 语义知识）。你应当诚实、有帮助，并利用从记忆系统中检索到的信息"
        "来提供个性化、连续的认知体验。"
    )

    # 默认生成指令（附加在 user prompt 末尾）
    DEFAULT_INSTRUCTIONS = (
        "请基于以上记忆上下文回答用户问题。\n"
        "规则：\n"
        "1. 如果记忆之间存在冲突，优先遵循 L0 身份设定和 L1 活跃目标，"
        "其次优先使用 L3 语义事实，除非用户明确要求回忆近期事件。\n"
        "2. 如果检索到的信息不足以回答问题，请明确告知用户，不要编造。\n"
        "3. 保持简洁、专业，必要时引用记忆来源。\n"
        "4. 如果检测到记忆冲突（⚠️ 部分），请在回答中简要说明冲突点并给出你的判断。"
    )

    def __init__(
        self,
        max_context_tokens: int = 4000,
        system_instruction: Optional[str] = None,
        priorities: Optional[Dict[str, int]] = None,
    ):
        self.max_context_tokens = max_context_tokens
        self.system_instruction = system_instruction or self.DEFAULT_SYSTEM_INSTRUCTION
        self.priorities = priorities or dict(self.DEFAULT_PRIORITIES)

    def estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数（混合文本）"""
        return max(1, int(len(text) / self.CHARS_PER_TOKEN))

    def build(
        self,
        user_query: str,
        memory_context: MemoryContext,
        custom_system_instruction: Optional[str] = None,
    ) -> BuiltPrompt:
        """
        构建最终 prompt。

        Returns:
            BuiltPrompt: 包含 system_prompt、user_prompt、token 估算和截断信息
        """
        system_prompt = custom_system_instruction or self.system_instruction

        # 1. 生成各文本片段
        sections = self._build_sections(memory_context, user_query)

        # 2. 按优先级排序并截断
        included, truncated, final_text = self._assemble_with_budget(
            sections, system_prompt, user_query
        )

        total_text = f"{system_prompt}\n\n{final_text}"
        estimated = self.estimate_tokens(total_text)

        return BuiltPrompt(
            system_prompt=system_prompt,
            user_prompt=final_text,
            estimated_tokens=estimated,
            sections_included=included,
            sections_truncated=truncated,
        )

    def _build_sections(
        self, ctx: MemoryContext, user_query: str
    ) -> Dict[str, str]:
        """将 MemoryContext 拆分为多个可独立截断的文本片段。"""
        sections: Dict[str, str] = {}

        if ctx.identity:
            sections["identity"] = self._format_identity(ctx.identity)

        if ctx.active_goals:
            sections["active_goals"] = self._format_goals(ctx.active_goals)

        if ctx.conflicts:
            sections["conflicts"] = self._format_conflicts(ctx.conflicts)

        if ctx.semantic_facts:
            sections["semantic_facts"] = self._format_semantic(ctx.semantic_facts)

        if ctx.episodic_memories:
            sections["episodic_memories"] = self._format_episodic(ctx.episodic_memories)

        if ctx.external_knowledge:
            sections["external_knowledge"] = self._format_external(ctx.external_knowledge)

        if ctx.conversation_history:
            sections["conversation_history"] = self._format_history(ctx.conversation_history)

        sections["user_query"] = f"## 用户问题\n{user_query}\n"
        sections["instructions"] = f"## 生成指令\n{self.DEFAULT_INSTRUCTIONS}\n"

        return sections

    def _assemble_with_budget(
        self,
        sections: Dict[str, str],
        system_prompt: str,
        user_query: str,
    ) -> tuple[List[str], List[str], str]:
        """
        按 token 预算组装 prompt。
        策略：先保留高优先级部分，低优先级部分在遇到预算限制时被截断。
        """
        # 计算系统指令的 token 消耗
        system_tokens = self.estimate_tokens(system_prompt)
        # 为用户问题和生成指令预留固定预算（永远保留）
        fixed_sections = ["user_query", "instructions"]
        fixed_text = "\n".join(sections[s] for s in fixed_sections if s in sections)
        fixed_tokens = self.estimate_tokens(fixed_text)

        available = self.max_context_tokens - system_tokens - fixed_tokens
        if available < 0:
            logger.warning(
                "System prompt + fixed sections already exceed max_context_tokens (%d). "
                "Consider increasing limit or shortening system prompt.",
                self.max_context_tokens,
            )
            available = 0

        # 按优先级排序（数字小的优先）
        sorted_sections = sorted(
            [(k, v) for k, v in sections.items() if k not in fixed_sections],
            key=lambda item: self.priorities.get(item[0], 99),
        )

        included: List[str] = []
        truncated: List[str] = []
        current_tokens = 0
        selected_parts: List[str] = []

        for name, text in sorted_sections:
            tokens = self.estimate_tokens(text)
            if current_tokens + tokens <= available:
                selected_parts.append(text)
                included.append(name)
                current_tokens += tokens
            else:
                # 尝试只保留部分内容（简单策略：保留前 N 行）
                truncated_text = self._smart_truncate(text, available - current_tokens)
                if truncated_text:
                    selected_parts.append(truncated_text)
                    included.append(name)
                    truncated.append(name)
                    current_tokens += self.estimate_tokens(truncated_text)
                else:
                    truncated.append(name)

        # 最终组装：高优先级部分在前，然后是固定部分
        all_parts = selected_parts + [sections[s] for s in fixed_sections if s in sections]
        final_text = "\n".join(all_parts)
        return included, truncated, final_text

    def _smart_truncate(self, text: str, max_tokens: int) -> str:
        """在 token 限制内尽量保留文本的前半部分（按行截断）。"""
        if max_tokens <= 0:
            return ""
        max_chars = int(max_tokens * self.CHARS_PER_TOKEN)
        if len(text) <= max_chars:
            return text
        # 按行截断，尽量保留完整行
        lines = text.splitlines(keepends=True)
        result = ""
        for line in lines:
            if len(result) + len(line) <= max_chars:
                result += line
            else:
                break
        if result:
            result += "\n...（内容因长度限制被截断）...\n"
        return result

    # ------------------------------------------------------------------
    # 格式化子方法
    # ------------------------------------------------------------------

    @staticmethod
    def _format_identity(identity: str) -> str:
        return f"## 用户身份与角色设定（L0 Identity）\n{identity}\n"

    @staticmethod
    def _format_goals(goals: List[str]) -> str:
        lines = "\n".join(f"- {g}" for g in goals)
        return f"## 当前活跃目标（L1 Active）\n{lines}\n"

    @staticmethod
    def _format_conflicts(conflicts: List[Dict[str, Any]]) -> str:
        lines = []
        for i, c in enumerate(conflicts, 1):
            severity = c.get("severity", "minor")
            fact_a = c.get("fact_a", "未知")
            fact_b = c.get("fact_b", "未知")
            resolution = c.get("resolution", "")
            line = (
                f"{i}. [严重度: {severity}]\n"
                f"   记忆 A: {fact_a}\n"
                f"   记忆 B: {fact_b}"
            )
            if resolution:
                line += f"\n   建议处理: {resolution}"
            lines.append(line)
        body = "\n".join(lines)
        return f"## ⚠️ 检测到的记忆冲突\n{body}\n"

    @staticmethod
    def _format_episodic(memories: List[Dict[str, Any]]) -> str:
        lines = []
        for m in memories:
            content = m.get("content") or m.get("value", "")
            if isinstance(content, dict):
                content = content.get("content", str(content))
            source = m.get("source", "system")
            created = m.get("created_at", "")
            lines.append(f"- [{source} | {created}] {str(content)[:200]}")
        body = "\n".join(lines)
        return f"## 近期情景记忆（L2 Episodic）\n{body}\n"

    @staticmethod
    def _format_semantic(facts: List[Dict[str, Any]]) -> str:
        lines = []
        for f in facts:
            name = f.get("name") or f.get("key", "")
            ftype = f.get("type", "")
            content = f.get("content") or f.get("value", "")
            if isinstance(content, dict):
                content = content.get("content", str(content))
            if ftype:
                lines.append(f"- [{ftype}] {name}: {str(content)[:200]}")
            else:
                lines.append(f"- {name}: {str(content)[:200]}")
        body = "\n".join(lines)
        return f"## 语义知识（L3 Semantic）\n{body}\n"

    @staticmethod
    def _format_external(knowledge: str) -> str:
        return f"## 外部知识检索结果\n{knowledge}\n"

    @staticmethod
    def _format_history(history: List[Dict[str, str]]) -> str:
        lines = []
        for h in history:
            role = h.get("role", "user")
            content = h.get("content", "")
            lines.append(f"{role}: {content}")
        body = "\n".join(lines)
        return f"## 当前对话历史\n{body}\n"
