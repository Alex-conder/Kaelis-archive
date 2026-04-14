#!/usr/bin/env python3
"""
Kaelis 上下文感知建议器 v1.0
监听文件变更，基于文件类型和内容提供智能建议
"""
import sys
import re
from pathlib import Path

# 建议规则库
SUGGESTION_RULES = [
    {
        "pattern": r"api/routes/.*\.py",
        "message": "[API] New route detected. Generate frontend Hook? Run: make idea --frontend-only",
        "priority": "high"
    },
    {
        "pattern": r"web/frontend/src/pages/.*\.tsx",
        "message": "[UI] New page detected. Add route config? Run: make fix --add-route",
        "priority": "high"
    },
    {
        "pattern": r"agent/.*\.py",
        "message": "[AGENT] Agent code detected. Registered in TOOL_REGISTRY? Run: make check --tools",
        "priority": "medium"
    },
    {
        "pattern": r"config/.*\.yaml",
        "message": "[CONFIG] Config modified. Check drift? Run: make drift",
        "priority": "medium"
    },
    {
        "pattern": r"api/models/.*\.py",
        "message": "[MODEL] DB model changed. Generate migration? Run: make migrate --generate",
        "priority": "high"
    },
    {
        "pattern": r"tests/.*\.py",
        "message": "[TEST] Test updated. Run: make test",
        "priority": "low"
    }
]

# 内容触发的建议（基于代码注释）
CONTENT_TRIGGERS = [
    {
        "trigger": r"# TODO: KG",
        "message": "[IDEA] KG TODO detected. Generate KG extract code? Run: make idea --kg-extract",
    },
    {
        "trigger": r"# KAELIS-IDEA",
        "message": "[IDEA] KAELIS-IDEA marker found. Describe your idea and I'll generate implementation.",
    },
    {
        "trigger": r"# BUG:",
        "message": "[BUG] Bug marker detected. Auto-fix? Run: make heal",
    }
]

def analyze_by_path(filepath: str) -> list:
    """基于文件路径匹配建议"""
    suggestions = []
    for rule in SUGGESTION_RULES:
        if re.search(rule["pattern"], filepath):
            suggestions.append({
                "message": rule["message"],
                "priority": rule["priority"]
            })
    return suggestions

def analyze_by_content(filepath: str) -> list:
    """基于文件内容匹配建议"""
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        suggestions = []
        for trigger in CONTENT_TRIGGERS:
            if re.search(trigger["trigger"], content):
                suggestions.append({
                    "message": trigger["message"],
                    "priority": "high"
                })
        return suggestions
    except:
        return []

def format_output(suggestions: list) -> str:
    """格式化输出"""
    if not suggestions:
        return ""
    
    output = []
    for s in suggestions:
        icon = "[HIGH]" if s["priority"] == "high" else "[MED]" if s["priority"] == "medium" else "[LOW]"
        output.append(f"{icon} {s['message']}")
    return "\n".join(output)

def main():
    if len(sys.argv) < 2:
        print("Usage: context_aware_suggester.py <filepath>")
        sys.exit(1)

    filepath = sys.argv[1]
    
    suggestions = analyze_by_path(filepath)
    suggestions.extend(analyze_by_content(filepath))
    
    output = format_output(suggestions)
    if output:
        print(f"\n{'='*60}")
        print(f"[FILE] {filepath}")
        print(f"{'='*60}")
        print(output)
        print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
