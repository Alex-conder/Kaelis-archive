#!/usr/bin/env python3
"""
Kaelis CLI — 终端交互工具

提供记忆查询、技能管理、每日洞察等子命令，
让开发者无需离开终端即可与 Kaelis 交互。

用法:
    python scripts/cli.py memory search "关键词" --layer L2
    python scripts/cli.py skill list --top 10
    python scripts/cli.py insight --today
    python scripts/cli.py chat "Hello Kaelis"
    python scripts/cli.py status
"""

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

API_BASE = os.environ.get("KAELIS_API_URL", "http://localhost:5000")


def _api_get(endpoint: str) -> Dict[str, Any]:
    import urllib.request
    url = f"{API_BASE}{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"❌ API 错误: {e}", file=sys.stderr)
        sys.exit(1)


def _api_post(endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    import urllib.request
    url = f"{API_BASE}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"❌ API 错误: {e}", file=sys.stderr)
        sys.exit(1)


# ======================================================================
# 子命令: memory
# ======================================================================

def cmd_memory_search(args: argparse.Namespace) -> None:
    query = args.query or "*"
    layer = args.layer or "L2"
    result = _api_post("/api/memory/search", {"layer": layer, "query": query, "top_k": args.limit})
    items = result.get("data", {}).get("results", []) if isinstance(result.get("data"), dict) else result.get("data", [])
    if not items:
        print(f"🔍 未在 {layer} 中找到匹配结果")
        return
    print(f"🧠 {layer} 记忆搜索结果 ({len(items)} 条):\n")
    for i, item in enumerate(items, 1):
        key = item.get("key", "N/A")
        val = item.get("value", "")
        val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
        print(f"  {i}. [{key}]")
        print(textwrap.fill(val_str[:200], width=70, initial_indent="     ", subsequent_indent="     "))
        print()


def cmd_memory_stats(args: argparse.Namespace) -> None:
    result = _api_get("/api/memory/stats")
    layers = result.get("data", {}).get("layers", []) if isinstance(result.get("data"), dict) else []
    print("📊 记忆层级统计:\n")
    for layer in layers:
        name = layer.get("name", "N/A")
        count = layer.get("count", 0)
        health = layer.get("health", "unknown")
        icon = "🟢" if health == "healthy" else "🟡" if health == "degraded" else "🔴"
        print(f"  {icon} {name}: {count} 条")


# ======================================================================
# 子命令: skill
# ======================================================================

def cmd_skill_list(args: argparse.Namespace) -> None:
    result = _api_get("/api/skills")
    skills = result.get("data", []) if isinstance(result.get("data"), list) else result.get("data", {}).get("skills", [])
    if not skills:
        print("📭 技能库为空")
        return
    print(f"🛠️  技能市场 ({len(skills)} 个):\n")
    for i, skill in enumerate(skills[:args.limit], 1):
        name = skill.get("name", "N/A")
        task_type = skill.get("task_type", "unknown")
        rating = skill.get("rating", 0)
        success = skill.get("success_rate", 0)
        print(f"  {i}. {name} [{task_type}] ⭐{rating:.1f} ✅{success:.0%}")


def cmd_skill_best(args: argparse.Namespace) -> None:
    result = _api_get(f"/api/skills/best/{args.task_type}")
    skill = result.get("data")
    if not skill:
        print(f"🔍 未找到 {args.task_type} 类型的最佳技能")
        return
    print(f"🏆 {args.task_type} 最佳技能:\n")
    print(json.dumps(skill, indent=2, ensure_ascii=False))


# ======================================================================
# 子命令: insight
# ======================================================================

def cmd_insight(args: argparse.Namespace) -> None:
    if args.today:
        from scripts.generate_daily_insight import generate_daily_insight
        content = generate_daily_insight(use_llm=False)
        print(content)
    else:
        print("ℹ️ 使用 --today 生成今日洞察")


# ======================================================================
# 子命令: chat
# ======================================================================

def cmd_chat(args: argparse.Namespace) -> None:
    message = args.message
    print(f"👤 You: {message}")
    print("🤖 Kaelis: ", end="", flush=True)
    result = _api_post("/api/kg-flywheel/chat", {"message": message})
    reply = result.get("reply") or result.get("data", {}).get("reply", "(无回复)")
    print(reply)


# ======================================================================
# 子命令: status
# ======================================================================

def cmd_status(args: argparse.Namespace) -> None:
    health = _api_get("/api/health")
    kg_health = _api_get("/api/kg-flywheel/health")
    print("🏥 Kaelis 系统状态\n")
    print(f"  API 服务: {'🟢 健康' if health.get('status') == 'healthy' else '🔴 异常'}")
    print(f"  KG 飞轮:  {'🟢 健康' if kg_health.get('status') == 'healthy' else '🔴 异常'}")
    print(f"  API 地址: {API_BASE}")


# ======================================================================
# 子命令: audit
# ======================================================================

def cmd_audit(args: argparse.Namespace) -> None:
    from core.security.install_auditor import InstallAuditor
    auditor = InstallAuditor()
    report = auditor.run_full_audit()
    if args.markdown:
        print(report.to_markdown())
    else:
        print(report.to_cli_table())
    if not auditor.can_proceed():
        print("\n❌ 发现 CRITICAL 风险，建议修复后再继续使用。")
        sys.exit(1)
    print("\n✅ 审计通过，可以继续使用 Kaelis。")


# ======================================================================
# 子命令: migrate
# ====================================================================== 

def cmd_migrate_detect(args: argparse.Namespace) -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from core.migration.smart_detector import scan_for_competitors
    results = scan_for_competitors()
    if not results:
        print("🔍 未发现竞品数据")
        return
    print(f"🔍 发现 {len(results)} 个竞品数据源:\n")
    for r in results:
        print(f"  📦 {r['name']} @ {r['path']}")
        print(f"     类型: {r['type']} | 大小: {r['size_human']}")


# ======================================================================
# CLI 主入口
# ======================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kaelis",
        description="Kaelis CLI — 与 AI Second Brain 终端交互",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  kaelis memory search "Python" --layer L2 --limit 5
  kaelis skill list --limit 10
  kaelis chat "分析这段代码"
  kaelis status
  kaelis migrate detect
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # memory
    memory_parser = subparsers.add_parser("memory", help="记忆管理")
    memory_sub = memory_parser.add_subparsers(dest="memory_cmd")
    search_p = memory_sub.add_parser("search", help="搜索记忆")
    search_p.add_argument("query", nargs="?", default="*", help="搜索关键词")
    search_p.add_argument("--layer", default="L2", choices=["L0", "L1", "L2", "L3"], help="记忆层级")
    search_p.add_argument("--limit", type=int, default=10, help="返回数量")
    search_p.set_defaults(func=cmd_memory_search)

    stats_p = memory_sub.add_parser("stats", help="记忆统计")
    stats_p.set_defaults(func=cmd_memory_stats)

    # skill
    skill_parser = subparsers.add_parser("skill", help="技能管理")
    skill_sub = skill_parser.add_subparsers(dest="skill_cmd")
    list_p = skill_sub.add_parser("list", help="列出技能")
    list_p.add_argument("--limit", type=int, default=20, help="返回数量")
    list_p.set_defaults(func=cmd_skill_list)

    best_p = skill_sub.add_parser("best", help="获取某类型最佳技能")
    best_p.add_argument("task_type", help="任务类型")
    best_p.set_defaults(func=cmd_skill_best)

    # insight
    insight_parser = subparsers.add_parser("insight", help="每日洞察")
    insight_parser.add_argument("--today", action="store_true", help="生成今日洞察")
    insight_parser.set_defaults(func=cmd_insight)

    # chat
    chat_parser = subparsers.add_parser("chat", help="快速对话")
    chat_parser.add_argument("message", help="消息内容")
    chat_parser.set_defaults(func=cmd_chat)

    # status
    status_parser = subparsers.add_parser("status", help="系统状态")
    status_parser.set_defaults(func=cmd_status)

    # audit
    audit_parser = subparsers.add_parser("audit", help="安装安全审计")
    audit_parser.add_argument("--markdown", action="store_true", help="输出 Markdown 格式报告")
    audit_parser.set_defaults(func=cmd_audit)

    # migrate
    migrate_parser = subparsers.add_parser("migrate", help="数据迁移")
    migrate_sub = migrate_parser.add_subparsers(dest="migrate_cmd")
    detect_p = migrate_sub.add_parser("detect", help="检测竞品数据")
    detect_p.set_defaults(func=cmd_migrate_detect)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
