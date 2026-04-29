#!/usr/bin/env python3
"""
开发者年度回顾生成器 — Developer Year in Review

生成个人年度开发回顾报告，帮助用户感知与 AI 协作的"复利效应"。

用法:
    python scripts/generate_developer_yearly.py
    python scripts/generate_developer_yearly.py --year 2025 --output ./my_report.md
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.memory_manager_v2 import get_memory_manager


def collect_stats(days: int = 365) -> dict:
    """收集过去 N 天的开发统计数据"""
    mm = get_memory_manager()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    stats = {
        "total_chats": 0,
        "total_memories": 0,
        "top_skills": [],
        "monthly_growth": [],
        "top_searched": [],
    }

    try:
        # 统计 L2 事件
        db_path = mm._get_db_path("L2")
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT key, value, metadata, created_at FROM memory_l2 WHERE created_at >= ?",
            (cutoff,)
        )
        rows = cursor.fetchall()
        conn.close()

        chats = 0
        memories = 0
        skill_refs = Counter()
        search_queries = Counter()

        for row in rows:
            key, val_str, meta_str, created_at = row
            try:
                val = json.loads(val_str) if val_str else {}
                meta = json.loads(meta_str) if meta_str else {}
            except Exception:
                val = {}
                meta = {}

            source = meta.get("source", "")
            if source == "chat":
                chats += 1
            else:
                memories += 1

            # 技能引用统计
            if isinstance(val, dict) and "skill" in str(val).lower():
                skill_name = val.get("name", val.get("skill", "unknown"))
                skill_refs[skill_name] += 1

            # 搜索查询统计（简单启发式）
            if "search" in key.lower() or "query" in key.lower():
                search_queries[key] += 1

        stats["total_chats"] = chats
        stats["total_memories"] = memories
        stats["top_skills"] = skill_refs.most_common(5)
        stats["top_searched"] = search_queries.most_common(3)

        # 按月统计记忆增长
        monthly = Counter()
        for row in rows:
            created_at = row[3]
            if created_at:
                month = created_at[:7]  # YYYY-MM
                monthly[month] += 1
        stats["monthly_growth"] = sorted(monthly.items())

    except Exception as e:
        print(f"统计收集部分失败: {e}", file=sys.stderr)

    return stats


def generate_report(stats: dict, year: int) -> str:
    """生成 Markdown 格式年度回顾报告"""
    now = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# 🌊 Kaelis 开发者年度回顾 — {year}",
        f"\n> 生成于 {now} | 你的 AI 第二大脑，陪你走过的又一年",
        "",
        "---",
        "",
        "## 📊 数字概览",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 总对话次数 | {stats['total_chats']} |",
        f"| 总记忆条数 | {stats['total_memories']} |",
        f"| 活跃技能数 | {len(stats['top_skills'])} |",
        "",
    ]

    if stats["monthly_growth"]:
        lines.extend([
            "## 📈 记忆增长曲线",
            "",
        ])
        for month, count in stats["monthly_growth"]:
            bar = "█" * min(count // 5 + 1, 20)
            lines.append(f"- **{month}**: {bar} ({count} 条)")
        lines.append("")

    if stats["top_skills"]:
        lines.extend([
            "## 🛠️ 最常用技能 Top 5",
            "",
        ])
        for i, (skill, count) in enumerate(stats["top_skills"], 1):
            lines.append(f"{i}. **{skill}** — 使用 {count} 次")
        lines.append("")

    if stats["top_searched"]:
        lines.extend([
            "## 🔍 最常被回忆的记忆",
            "",
        ])
        for i, (query, count) in enumerate(stats["top_searched"], 1):
            lines.append(f"{i}. `{query}` — 被检索 {count} 次")
        lines.append("")

    # 年度寄语
    lines.extend([
        "---",
        "",
        "## 💌 年度寄语",
        "",
        f"> 这一年，你与 Kaelis 共同积累了 **{stats['total_memories']}** 条记忆，",
        f"> 进行了 **{stats['total_chats']}** 次对话。",
        "> 每一次对话，都在让 AI 更懂你。",
        "> 继续构建属于你的认知飞轮 🚀",
        "",
        "*—— Kaelis 智流*",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Kaelis 开发者年度回顾生成器")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="年度")
    parser.add_argument("--days", type=int, default=365, help="回顾天数")
    parser.add_argument("--output", default="data/insights", help="输出目录")
    args = parser.parse_args()

    print(f"🔄 正在收集 {args.days} 天的开发数据...")
    stats = collect_stats(days=args.days)

    print(f"📊 数据收集完成: {stats['total_chats']} 次对话, {stats['total_memories']} 条记忆")

    report = generate_report(stats, args.year)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"dev_yearly_{args.year}.md"
    out_path.write_text(report, encoding="utf-8")

    print(f"\n📝 年度回顾已生成: {out_path}")
    print(f"   总对话: {stats['total_chats']}")
    print(f"   总记忆: {stats['total_memories']}")
    print(f"   活跃技能: {len(stats['top_skills'])}")


if __name__ == "__main__":
    main()
