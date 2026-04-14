#!/usr/bin/env python3
"""
Kaelis 增量架构检查器
实时检测代码变更中的架构违规
"""
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# 遥测文件
TELEMETRY_FILE = Path(".kaelis-telemetry.jsonl")
VIOLATION_LOG = Path(".kaelis-violations.jsonl")

# 轻量级架构规则（实时检查）
INCREMENTAL_RULES = [
    {
        "id": "M0-API-01",
        "name": "Direct jsonify return",
        "pattern": r"return\s+jsonify\s*\(",
        "message": "Should use ResponseModel instead of direct jsonify",
        "severity": "error",
        "fix": "Use standardized response wrapper"
    },
    {
        "id": "M0-IMPORT-01",
        "name": "Import from core directly",
        "pattern": r"from\s+core\s+import",
        "message": "Should import from public API only",
        "severity": "warning",
        "fix": "Import from api.public instead"
    },
    {
        "id": "M0-DB-01",
        "name": "Raw SQL query",
        "pattern": r"(execute|query)\s*\(\s*['\"]\s*(SELECT|INSERT|UPDATE|DELETE)",
        "message": "Should use ORM instead of raw SQL",
        "severity": "error",
        "fix": "Use SQLAlchemy ORM"
    },
    {
        "id": "M0-LOG-01",
        "name": "Print instead of log",
        "pattern": r"^\s*print\s*\(",
        "message": "Should use logger instead of print",
        "severity": "warning",
        "fix": "Use logging.getLogger(__name__)"
    },
    {
        "id": "M0-CONFIG-01",
        "name": "Hardcoded config",
        "pattern": r"(host|port|url)\s*=\s*['\"]\w+",
        "message": "Configuration should be externalized",
        "severity": "warning",
        "fix": "Use config.yaml or environment variables"
    },
    {
        "id": "M0-ERROR-01",
        "name": "Bare except clause",
        "pattern": r"except\s*:",
        "message": "Should catch specific exceptions",
        "severity": "error",
        "fix": "Use 'except SpecificException:'"
    }
]


def record_telemetry(event_type: str, data: dict):
    """记录遥测"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "data": data
    }
    with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_violation(violation: dict, filepath: str, line_num: int, line_content: str):
    """记录违规"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "rule_id": violation["id"],
        "rule_name": violation["name"],
        "filepath": filepath,
        "line_num": line_num,
        "line_content": line_content[:100],
        "severity": violation["severity"],
        "fixed_at": None  # 修复时更新
    }
    with open(VIOLATION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_line(line: str, line_num: int, filepath: str) -> List[dict]:
    """检查单行代码"""
    violations = []
    
    for rule in INCREMENTAL_RULES:
        if re.search(rule["pattern"], line, re.IGNORECASE):
            violation = {
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "message": rule["message"],
                "severity": rule["severity"],
                "fix": rule["fix"],
                "line_num": line_num,
                "line_content": line.strip()[:80]
            }
            violations.append(violation)
            
            # 记录到日志
            record_violation(rule, filepath, line_num, line)
    
    return violations


def check_file_incremental(filepath: str, changed_lines: Optional[List[int]] = None) -> List[dict]:
    """
    增量检查文件
    
    Args:
        filepath: 文件路径
        changed_lines: 变更的行号列表，None 表示检查全部
    
    Returns:
        违规列表
    """
    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except Exception as e:
        return []
    
    violations = []
    lines = content.split("\n")
    
    for line_num, line in enumerate(lines, 1):
        # 如果指定了变更行，只检查变更行
        if changed_lines and line_num not in changed_lines:
            continue
        
        line_violations = check_line(line, line_num, filepath)
        violations.extend(line_violations)
    
    return violations


def format_violation(v: dict) -> str:
    """格式化违规输出"""
    icon = "[ERR]" if v["severity"] == "error" else "[WARN]"
    return f"{icon} [{v['rule_id']}] Line {v['line_num']}: {v['message']}"


def print_violations(filepath: str, violations: List[dict]):
    """打印违规信息"""
    if not violations:
        return
    
    print(f"\n[ARCHITECTURE CHECK] {filepath}")
    print("-" * 60)
    
    for v in violations:
        print(format_violation(v))
        print(f"   Code: {v['line_content']}")
        print(f"   Fix:  {v['fix']}")
        print()
    
    error_count = sum(1 for v in violations if v["severity"] == "error")
    warn_count = sum(1 for v in violations if v["severity"] == "warning")
    
    print(f"Found {error_count} errors, {warn_count} warnings")
    print("Run 'make fix' to auto-fix, or 'make check' for full report")
    print("-" * 60)
    
    # 记录遥测
    record_telemetry("incremental_check_violations", {
        "filepath": filepath,
        "error_count": error_count,
        "warn_count": warn_count,
        "rules": [v["rule_id"] for v in violations]
    })


def get_violation_stats(days: int = 7) -> dict:
    """获取违规统计"""
    if not VIOLATION_LOG.exists():
        return {"total": 0, "by_rule": {}, "avg_fix_time": None}
    
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    stats = {
        "total": 0,
        "by_rule": {},
        "fixed": 0,
        "pending": 0,
        "fix_times": []
    }
    
    with open(VIOLATION_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                entry = json.loads(line)
                if entry["timestamp"] < cutoff:
                    continue
                
                stats["total"] += 1
                rule_id = entry["rule_id"]
                
                if rule_id not in stats["by_rule"]:
                    stats["by_rule"][rule_id] = {"count": 0, "fixed": 0}
                stats["by_rule"][rule_id]["count"] += 1
                
                if entry.get("fixed_at"):
                    stats["fixed"] += 1
                    stats["by_rule"][rule_id]["fixed"] += 1
                    
                    # 计算修复时间
                    found_time = datetime.fromisoformat(entry["timestamp"])
                    fix_time = datetime.fromisoformat(entry["fixed_at"])
                    fix_duration = (fix_time - found_time).total_seconds()
                    stats["fix_times"].append(fix_duration)
                else:
                    stats["pending"] += 1
            
            except (json.JSONDecodeError, ValueError):
                continue
    
    # 计算平均修复时间
    if stats["fix_times"]:
        stats["avg_fix_time_seconds"] = sum(stats["fix_times"]) / len(stats["fix_times"])
        stats["avg_fix_time_minutes"] = stats["avg_fix_time_seconds"] / 60
    
    return stats


def print_stats(days: int = 7):
    """打印统计"""
    stats = get_violation_stats(days)
    
    print(f"[ARCHITECTURE VIOLATION STATS] Last {days} days")
    print("=" * 60)
    print(f"Total violations: {stats['total']}")
    print(f"  Fixed: {stats['fixed']}")
    print(f"  Pending: {stats['pending']}")
    
    if stats.get('avg_fix_time_minutes'):
        print(f"\nAverage fix time: {stats['avg_fix_time_minutes']:.1f} minutes")
    
    if stats["by_rule"]:
        print("\nBy rule:")
        for rule_id, rule_stats in sorted(stats["by_rule"].items(), key=lambda x: -x[1]["count"]):
            fixed_pct = rule_stats["fixed"] / rule_stats["count"] * 100 if rule_stats["count"] > 0 else 0
            print(f"  {rule_id}: {rule_stats['count']} ({rule_stats['fixed']} fixed, {fixed_pct:.0f}%)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis Incremental Architecture Check")
    parser.add_argument("filepath", nargs="?", help="File to check")
    parser.add_argument("--lines", help="Changed line numbers (comma-separated)")
    parser.add_argument("--stats", action="store_true", help="Show violation statistics")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    args = parser.parse_args()
    
    if args.stats:
        print_stats(args.days)
        return
    
    if not args.filepath:
        parser.print_help()
        return
    
    # 解析行号
    changed_lines = None
    if args.lines:
        try:
            changed_lines = [int(x.strip()) for x in args.lines.split(",")]
        except ValueError:
            pass
    
    # 检查文件
    violations = check_file_incremental(args.filepath, changed_lines)
    
    if violations:
        print_violations(args.filepath, violations)
        # 返回非零退出码表示发现违规
        import sys
        sys.exit(1 if any(v["severity"] == "error" for v in violations) else 0)
    else:
        print(f"[OK] {args.filepath}: No architecture violations found")


if __name__ == "__main__":
    main()
