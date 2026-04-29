"""
每日洞察生成器 — Daily Insight Generator

P17-002 核心模块。

功能：
1. 调用 ProactiveMemoryEngine 获取待推送记忆
2. 读取昨日 L2 事件、技能变更记录
3. 调用 LLM 生成 300 字以内 Markdown 摘要（LLM 不可用时回退到模板）
4. 输出到 data/insights/YYYY-MM-DD.md

用法：
    python scripts/generate_daily_insight.py
    python scripts/generate_daily_insight.py --user-id alice --output-dir ./my_insights
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.memory_proactive import get_proactive_engine, ProactiveMemoryEngine
from core.memory_manager_v2 import get_memory_manager

try:
    from core.skill_manager import get_skill_manager
    SKILL_AVAILABLE = True
except ImportError:
    SKILL_AVAILABLE = False

try:
    from core.llm_client import llm_client
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    llm_client = None

logger = logging.getLogger(__name__)


# ======================================================================
# Prompt 模板
# ======================================================================

SOCIAL_PROMPT = """你是 Kaelis 的 Build in Public 社交媒体助手。
请根据以下开发数据，生成一条 280 字符以内的英文 Twitter/X 推文（适合技术受众）。

要求：
1. 语气热情、真诚，像独立开发者在分享进展。
2. 包含 1-2 个相关 hashtag（如 #BuildInPublic #AI #IndieDev）。
3. 如果有具体数字（bug 修复数、测试通过数、新功能），一定要突出。
4. 不要多余的解释，只输出推文正文。

---

【过去24小时开发数据】
{dev_summary}

---

请只输出推文正文，不超过 280 字符。"""

DAILY_INSIGHT_PROMPT = """你是 Kaelis 的"每日洞察"生成助手。请根据以下信息，为用户生成一段 200-300 字的 Markdown 日报。

要求：
1. 语气亲切、简洁，像一位了解用户的助手在汇报。
2. 分为三个区块：
   - ## 今日推荐回顾（最多 3 条）
   - ## 昨日进化摘要（技能成功率、新增技能等）
   - ## 待办提醒（从记忆中提取的未完成任务或承诺）
3. 如果某项数据为空，直接跳过该区块，不要写"无数据"。
4. 使用 Markdown 格式，适当使用 bullet list 和 **粗体**。

---

【记忆推送】
{memories}

【技能亮点】
{skills}

【昨日事件数】{yesterday_events}

【技能统计】{skill_stats}

---

请直接输出 Markdown，不要加任何解释性前缀。"""


# ======================================================================
# 数据收集
# ======================================================================

def collect_memories(engine: ProactiveMemoryEngine, user_id: str = "anonymous") -> Dict[str, Any]:
    """收集主动推送记忆"""
    bundle = engine.generate_push_bundle(user_id=user_id)
    all_mems = bundle.all_memories()
    return {
        "time_based": [m.to_dict() for m in bundle.time_based],
        "context_related": [m.to_dict() for m in bundle.context_related],
        "forgetting_curve": [m.to_dict() for m in bundle.forgetting_curve],
        "all": [m.to_dict() for m in all_mems],
    }


def collect_yesterday_events(user_id: str = "anonymous") -> List[Dict[str, Any]]:
    """读取昨日 L2 事件"""
    try:
        mm = get_memory_manager()
        yesterday = datetime.now() - timedelta(days=1)
        date_start = yesterday.strftime("%Y-%m-%d")
        date_end = (yesterday + timedelta(days=1)).strftime("%Y-%m-%d")

        db_path = mm._get_db_path("L2")
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT key, value, metadata, source, created_at "
            "FROM memory_l2 WHERE user_id = ? AND created_at >= ? AND created_at < ? "
            "ORDER BY created_at DESC LIMIT 20",
            (user_id, date_start, date_end)
        )
        rows = []
        for row in cursor.fetchall():
            rows.append({
                "key": row[0],
                "value": json.loads(row[1]),
                "metadata": json.loads(row[2]) if row[2] else {},
                "source": row[3],
                "created_at": row[4],
            })
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"Failed to collect yesterday events: {e}")
        return []


def collect_skill_stats() -> Dict[str, Any]:
    """读取技能统计"""
    if not SKILL_AVAILABLE:
        return {"available": False}
    try:
        sm = get_skill_manager()
        return sm.get_statistics()
    except Exception as e:
        logger.warning(f"Failed to collect skill stats: {e}")
        return {"available": False, "error": str(e)}


def collect_skill_highlights(days: int = 1) -> List[Dict[str, Any]]:
    """读取近期技能亮点"""
    try:
        engine = get_proactive_engine()
        highlights = engine.get_skill_evolution_highlights(days=days, limit=5)
        return [h.to_dict() for h in highlights]
    except Exception as e:
        logger.warning(f"Failed to collect skill highlights: {e}")
        return []


# ======================================================================
# 内容生成
# ======================================================================

def _format_memories_for_llm(memories: List[Dict[str, Any]]) -> str:
    """将记忆格式化为 LLM 可读的文本"""
    if not memories:
        return "（无推荐记忆）"
    lines = []
    for m in memories[:5]:
        reason = m.get("reason", "")
        val = m.get("value")
        val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
        lines.append(f"- [{m['layer']}] {m['key']}: {val_str[:120]} ({reason})")
    return "\n".join(lines)


def _format_skills_for_llm(skills: List[Dict[str, Any]]) -> str:
    """将技能格式化为 LLM 可读的文本"""
    if not skills:
        return "（无技能亮点）"
    lines = []
    for s in skills[:5]:
        lines.append(
            f"- {s['name']} ({s['task_type']}): "
            f"成功率 {s['success_rate']:.0%}, 评分 {s['rating']:.1f}, "
            f"使用 {s['usage_count']} 次"
        )
    return "\n".join(lines)


def _extract_todos_from_memories(memories: List[Dict[str, Any]]) -> List[str]:
    """从记忆内容中简单提取待办项（基于关键词）"""
    todo_keywords = ["待办", "TODO", "todo", "需要", "必须", "别忘了", "记得"]
    todos = []
    for m in memories:
        val = m.get("value")
        text = json.dumps(val, ensure_ascii=False) if val else ""
        for kw in todo_keywords:
            if kw in text:
                # 提取包含关键词的那句话
                for sentence in text.split("。"):
                    if kw in sentence:
                        todos.append(sentence.strip() + "。")
                        break
                break
    # 去重
    seen = set()
    unique = []
    for t in todos:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:5]


def generate_with_llm(
    memories: List[Dict[str, Any]],
    skills: List[Dict[str, Any]],
    yesterday_events: int = 0,
    skill_stats: Dict[str, Any] = None,
    llm_client_instance=None,
) -> str:
    """使用 LLM 生成洞察摘要"""
    if skill_stats is None:
        skill_stats = {}

    prompt = DAILY_INSIGHT_PROMPT.format(
        memories=_format_memories_for_llm(memories),
        skills=_format_skills_for_llm(skills),
        yesterday_events=yesterday_events,
        skill_stats=json.dumps(skill_stats, ensure_ascii=False, indent=2),
    )

    client = llm_client_instance or llm_client
    if client is None:
        raise RuntimeError("LLM client not available")

    try:
        response = client.chat(
            prompt=prompt,
            system_prompt="你是一个简洁、亲切的日报生成助手。只输出 Markdown，不添加任何前缀说明。",
            temperature=0.7,
            max_tokens=800,
        )
        return str(response).strip()
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise


def generate_template(
    memories: List[Dict[str, Any]],
    skills: List[Dict[str, Any]],
    yesterday_events: int = 0,
    skill_stats: Dict[str, Any] = None,
) -> str:
    """LLM 不可用时，使用模板生成洞察"""
    lines = [f"# Kaelis 每日洞察 — {datetime.now().strftime('%Y-%m-%d')}", ""]

    # 今日推荐回顾
    if memories:
        lines.append("## 今日推荐回顾")
        for m in memories[:3]:
            reason = m.get("reason", "")
            val = m.get("value")
            val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
            lines.append(f"- **{m['key']}** ({m['layer']}): {val_str[:100]}")
            if reason:
                lines.append(f"  *原因：{reason}*")
        lines.append("")

    # 昨日进化摘要
    if skills or (skill_stats and skill_stats.get("total")):
        lines.append("## 昨日进化摘要")
        if yesterday_events > 0:
            lines.append(f"- 昨日共记录 **{yesterday_events}** 条系统事件")
        if skill_stats and skill_stats.get("total"):
            lines.append(
                f"- 当前技能库共 **{skill_stats['total']}** 个技能，"
                f"整体成功率 **{skill_stats.get('overall_success_rate', 0):.0%}**"
            )
        for s in skills[:3]:
            lines.append(
                f"- **{s['name']}**: 成功率 {s['success_rate']:.0%}, "
                f"评分 {s['rating']:.1f} ({s.get('improvement', '')})"
            )
        lines.append("")

    # 待办提醒
    todos = _extract_todos_from_memories(memories)
    if todos:
        lines.append("## 待办提醒")
        for t in todos[:3]:
            lines.append(f"- [ ] {t}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by Kaelis at {datetime.now().isoformat()}*")
    return "\n".join(lines)


# ======================================================================
# 主流程
# ======================================================================

def generate_daily_insight(
    user_id: str = "anonymous",
    output_dir: str = "data/insights",
    llm_client_instance=None,
    use_llm: bool = True,
) -> str:
    """
    生成每日洞察并写入文件。

    Args:
        user_id: 用户 ID
        output_dir: 输出目录
        llm_client_instance: 可选的 LLM 客户端实例
        use_llm: 是否尝试使用 LLM（False 则强制使用模板）

    Returns:
        生成的 Markdown 内容
    """
    # 收集数据
    engine = get_proactive_engine()
    mem_data = collect_memories(engine, user_id=user_id)
    memories = mem_data["all"]

    yesterday_events = collect_yesterday_events(user_id=user_id)
    skill_stats = collect_skill_stats()
    skill_highlights = collect_skill_highlights(days=1)

    # 生成内容
    if use_llm and (llm_client_instance or llm_client):
        try:
            content = generate_with_llm(
                memories=memories,
                skills=skill_highlights,
                yesterday_events=len(yesterday_events),
                skill_stats=skill_stats,
                llm_client_instance=llm_client_instance,
            )
        except Exception as e:
            logger.warning(f"LLM generation failed, falling back to template: {e}")
            content = generate_template(
                memories=memories,
                skills=skill_highlights,
                yesterday_events=len(yesterday_events),
                skill_stats=skill_stats,
            )
    else:
        content = generate_template(
            memories=memories,
            skills=skill_highlights,
            yesterday_events=len(yesterday_events),
            skill_stats=skill_stats,
        )

    # 写入文件
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_path = out_path / f"{date_str}.md"
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"Daily insight written to {file_path}")

    return content


# ======================================================================
# CLI
# ======================================================================

def generate_social_post(
    dev_summary: str,
    llm_client_instance=None,
) -> str:
    """使用 LLM 生成社交媒体推文草稿"""
    prompt = SOCIAL_PROMPT.format(dev_summary=dev_summary)
    client = llm_client_instance or llm_client
    if client is None:
        # 回退：基于模板生成
        lines = [
            f"Shipped some cool updates to Kaelis today! 🚀",
            f"{dev_summary[:120]}...",
            "Building the AI that remembers.",
            "#BuildInPublic #AI",
        ]
        return "\n".join(lines)
    try:
        response = client.chat(
            prompt=prompt,
            system_prompt="你是一个精通 Twitter/X 的开发者营销助手。只输出推文，不加任何前缀。",
            temperature=0.8,
            max_tokens=200,
        )
        text = str(response).strip()
        # 简单截断到 280 字符
        if len(text) > 280:
            text = text[:277] + "..."
        return text
    except Exception as e:
        logger.error(f"Social post generation failed: {e}")
        return f"🚀 Building Kaelis — the AI that remembers, understands, and evolves. {dev_summary[:100]} #BuildInPublic #AI"


def collect_dev_summary(user_id: str = "anonymous") -> str:
    """收集过去24小时的开发摘要，用于社交媒体"""
    parts = []
    # 技能统计
    stats = collect_skill_stats()
    if stats and stats.get("total"):
        parts.append(f"Skills: {stats['total']} total, {stats.get('overall_success_rate', 0):.0%} success rate")
    # 昨日事件数
    events = collect_yesterday_events(user_id=user_id)
    if events:
        parts.append(f"Events: {len(events)} recorded in L2 memory")
    # 技能亮点
    highlights = collect_skill_highlights(days=1)
    if highlights:
        top = highlights[0]
        parts.append(f"Top skill: {top['name']} ({top['success_rate']:.0%} success)")
    return "; ".join(parts) if parts else "Making steady progress on the AI Second Brain."


def main():
    parser = argparse.ArgumentParser(description="Kaelis 每日洞察生成器")
    parser.add_argument("--user-id", default="anonymous", help="用户 ID")
    parser.add_argument("--output-dir", default="data/insights", help="输出目录")
    parser.add_argument("--no-llm", action="store_true", help="强制使用模板，不调用 LLM")
    parser.add_argument("--verbose", action="store_true", help="详细日志")
    parser.add_argument("--social", action="store_true", help="同时生成社交媒体推文草稿")
    parser.add_argument("--social-only", action="store_true", help="仅生成社交媒体推文")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    if args.social_only:
        dev_summary = collect_dev_summary(user_id=args.user_id)
        tweet = generate_social_post(dev_summary, llm_client_instance=None if not args.no_llm else None)
        out_path = Path(args.output_dir).parent / "social"
        out_path.mkdir(parents=True, exist_ok=True)
        tweet_path = out_path / f"tweet_draft_{datetime.now().strftime('%Y-%m-%d')}.md"
        tweet_path.write_text(f"# Tweet Draft ({datetime.now().strftime('%Y-%m-%d')})\n\n{tweet}\n", encoding="utf-8")
        print(tweet)
        logger.info(f"Tweet draft saved to {tweet_path}")
        return

    content = generate_daily_insight(
        user_id=args.user_id,
        output_dir=args.output_dir,
        use_llm=not args.no_llm,
    )
    print(content)

    if args.social:
        dev_summary = collect_dev_summary(user_id=args.user_id)
        tweet = generate_social_post(dev_summary, llm_client_instance=None if not args.no_llm else None)
        out_path = Path(args.output_dir).parent / "social"
        out_path.mkdir(parents=True, exist_ok=True)
        tweet_path = out_path / f"tweet_draft_{datetime.now().strftime('%Y-%m-%d')}.md"
        tweet_path.write_text(f"# Tweet Draft ({datetime.now().strftime('%Y-%m-%d')})\n\n{tweet}\n", encoding="utf-8")
        print(f"\n---\n🐦 Tweet Draft:\n{tweet}\n")
        logger.info(f"Tweet draft saved to {tweet_path}")


if __name__ == "__main__":
    main()
