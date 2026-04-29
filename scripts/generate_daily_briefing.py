#!/usr/bin/env python3
"""
每日智能简报生成器 — Daily Briefing

每天自动生成个性化简报，让用户感知 Kaelis 在后台的"默默努力"。

用法:
    python scripts/generate_daily_briefing.py
    python scripts/generate_daily_briefing.py --user-id alice
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.memory_manager_v2 import get_memory_manager
from core.skill_manager import get_skill_manager


def collect_daily_stats(user_id: str = "anonymous") -> dict:
    """收集过去24小时的统计数据"""
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    stats = {
        "new_memories": 0,
        "chat_sessions": 0,
        "skill_invocations": 0,
        "security_changes": 0,
    }

    try:
        mm = get_memory_manager()
        db_path = mm._get_db_path("L2")
        import sqlite3
        conn = sqlite3.connect(db_path)

        # 新增记忆
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_l2 WHERE user_id = ? AND created_at >= ?",
            (user_id, yesterday_str)
        )
        stats["new_memories"] = cursor.fetchone()[0]

        # 对话次数（简化：统计 chat 来源的记忆）
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_l2 WHERE user_id = ? AND created_at >= ? AND source = 'chat'",
            (user_id, yesterday_str)
        )
        stats["chat_sessions"] = cursor.fetchone()[0]

        conn.close()
    except Exception as e:
        print(f"记忆统计失败: {e}", file=sys.stderr)

    try:
        sm = get_skill_manager()
        skill_stats = sm.get_statistics()
        stats["skill_invocations"] = skill_stats.get("total_invocations", 0)
    except Exception as e:
        print(f"技能统计失败: {e}", file=sys.stderr)

    return stats


def generate_briefing_text(stats: dict, user_id: str = "anonymous") -> str:
    """生成自然语言简报"""
    lines = [
        f"📅 {datetime.now().strftime('%m月%d日')} 简报",
    ]

    if stats["new_memories"] > 0:
        lines.append(f"🧠 昨天新增了 {stats['new_memories']} 条记忆")
    if stats["chat_sessions"] > 0:
        lines.append(f"💬 进行了 {stats['chat_sessions']} 次对话")
    if stats["skill_invocations"] > 0:
        lines.append(f"🛠️ 技能被调用了 {stats['skill_invocations']} 次")

    if stats["new_memories"] == 0 and stats["chat_sessions"] == 0:
        lines.append("🌅 新的一天，开始和 Kaelis 对话吧！")
    else:
        lines.append("✨ Kaelis 正在变得越来越懂你")

    return " | ".join(lines)


def save_briefing(briefing: str, user_id: str = "anonymous") -> Path:
    """保存简报到文件"""
    out_dir = Path("data/insights")
    out_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = out_dir / f"daily_{date_str}.md"
    out_path.write_text(f"# 每日简报 ({date_str})\n\n{briefing}\n", encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Kaelis 每日智能简报")
    parser.add_argument("--user-id", default="anonymous")
    args = parser.parse_args()

    stats = collect_daily_stats(args.user_id)
    briefing = generate_briefing_text(stats, args.user_id)
    out_path = save_briefing(briefing, args.user_id)

    print(briefing)
    print(f"\n已保存: {out_path}")


if __name__ == "__main__":
    main()
