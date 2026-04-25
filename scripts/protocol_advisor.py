"""
Protocol Evolution Advisor
==========================
监控外部协议变化（MCP、A2A、OpenAI Agent SDK），评估对 Kaelis 的影响。

用法:
    python scripts/protocol_advisor.py [--output report.md]
"""

import argparse
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Windows console UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ============================================================================
# Config
# ============================================================================

PROTOCOLS = {
    "mcp": {
        "name": "Model Context Protocol (MCP)",
        "repo": "modelcontextprotocol/specification",
        "current_version_file": ".protocol_versions/mcp.json",
        "relevance": "core/mcp/server.py, core/mcp/client.py",
    },
    "a2a": {
        "name": "Anthropic A2A Protocol",
        "repo": "anthropics/anthropic-cookbook",  # A2A 尚无独立仓库，先监控 cookbook
        "current_version_file": ".protocol_versions/a2a.json",
        "relevance": "api/routes/agent.py, core/agent_registry.py",
    },
    "openai_agents": {
        "name": "OpenAI Agents SDK",
        "repo": "openai/openai-python",
        "current_version_file": ".protocol_versions/openai_agents.json",
        "relevance": "core/llm_client.py, core/strategy_selector.py",
    },
}

VERSIONS_DIR = PROJECT_ROOT / ".protocol_versions"


# ============================================================================
# GitHub API Helpers
# ============================================================================

def github_api(url: str) -> Optional[Dict]:
    """调用 GitHub API，自动处理 rate limit。"""
    token = os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Kaelis-ProtocolAdvisor/1.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("GitHub API failed for %s: %s", url, e)
        return None


def fetch_latest_release(repo: str) -> Optional[Dict]:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    data = github_api(url)
    if data:
        return {
            "version": data.get("tag_name", "unknown"),
            "published_at": data.get("published_at", ""),
            "body": data.get("body", "")[:2000],
            "url": data.get("html_url", ""),
        }
    return None


def fetch_tags(repo: str, limit: int = 5) -> List[str]:
    url = f"https://api.github.com/repos/{repo}/tags?per_page={limit}"
    data = github_api(url)
    if data:
        return [t["name"] for t in data]
    return []


# ============================================================================
# Version Persistence
# ============================================================================

def load_recorded_version(protocol_id: str) -> Optional[Dict]:
    path = VERSIONS_DIR / f"{protocol_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_recorded_version(protocol_id: str, version: str, details: Dict):
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = VERSIONS_DIR / f"{protocol_id}.json"
    record = {
        "protocol": protocol_id,
        "version": version,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "details": details,
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


# ============================================================================
# Impact Analysis
# ============================================================================

def analyze_impact(protocol_id: str, changelog: str, current_version: str, new_version: str) -> Dict[str, Any]:
    """基于 changelog 内容做简单的关键词影响评估。"""
    text = changelog.lower()

    # 紧迫性关键词
    critical_keywords = ["security", "cve", "vulnerability", "breaking change", "deprecated", "removed"]
    high_keywords = ["new feature", "improvement", "performance", "stable"]

    critical_hits = [kw for kw in critical_keywords if kw in text]
    high_hits = [kw for kw in high_keywords if kw in text]

    if critical_hits:
        urgency = "high"
        reason = f"发现关键关键词: {', '.join(critical_hits)}"
    elif high_hits:
        urgency = "medium"
        reason = f"发现重要更新: {', '.join(high_hits)}"
    else:
        urgency = "low"
        reason = "常规维护更新，未发现明显影响"

    return {
        "current_version": current_version or "unknown",
        "latest_version": new_version,
        "urgency": urgency,
        "reason": reason,
        "keywords_found": critical_hits + high_hits,
    }


# ============================================================================
# Report
# ============================================================================

def generate_report() -> Dict[str, Any]:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocols": [],
    }

    for pid, cfg in PROTOCOLS.items():
        logger.info("Checking %s (%s)...", cfg["name"], cfg["repo"])
        latest = fetch_latest_release(cfg["repo"])
        recorded = load_recorded_version(pid)

        if not latest:
            report["protocols"].append({
                "id": pid,
                "name": cfg["name"],
                "repo": cfg["repo"],
                "relevance": cfg["relevance"],
                "status": "check_failed",
                "reason": "Unable to fetch from GitHub API",
            })
            continue

        current_ver = recorded["version"] if recorded else None
        is_new = current_ver != latest["version"]

        impact = analyze_impact(pid, latest["body"], current_ver, latest["version"])

        entry = {
            "id": pid,
            "name": cfg["name"],
            "repo": cfg["repo"],
            "relevance": cfg["relevance"],
            "current_version": current_ver or "unknown",
            "latest_version": latest["version"],
            "published_at": latest["published_at"],
            "is_new": is_new,
            "impact": impact,
            "release_url": latest["url"],
            "changelog_preview": latest["body"][:500],
        }
        report["protocols"].append(entry)

        if is_new:
            logger.warning("[%s] NEW VERSION: %s -> %s (urgency: %s)", pid, current_ver, latest["version"], impact["urgency"])
            save_recorded_version(pid, latest["version"], latest)
        else:
            logger.info("[%s] Up to date: %s", pid, current_ver)

    return report


def format_markdown(report: Dict) -> str:
    lines = [
        "# Protocol Evolution Advisory Report",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
    ]

    new_count = sum(1 for p in report["protocols"] if p.get("is_new"))
    high_urgency = sum(1 for p in report["protocols"] if p.get("impact", {}).get("urgency") == "high")

    lines.append(f"- Protocols monitored: {len(report['protocols'])}")
    lines.append(f"- New versions found: {new_count}")
    lines.append(f"- High urgency items: {high_urgency}")
    lines.append("")

    for p in report["protocols"]:
        lines.append(f"## {p['name']}")
        lines.append("")
        lines.append(f"- **Repository**: `{p['repo']}`")
        lines.append(f"- **Kaelis Relevance**: {p.get('relevance', 'N/A')}")
        lines.append(f"- **Current**: `{p.get('current_version', 'unknown')}`")
        lines.append(f"- **Latest**: `{p.get('latest_version', 'unknown')}`")
        lines.append(f"- **Status**: {'🆕 New version available' if p.get('is_new') else '✅ Up to date'}")
        if "impact" in p:
            impact = p["impact"]
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(impact["urgency"], "⚪")
            lines.append(f"- **Urgency**: {emoji} {impact['urgency'].upper()}")
            lines.append(f"- **Assessment**: {impact['reason']}")
        if p.get("release_url"):
            lines.append(f"- **Release Notes**: {p['release_url']}")
        lines.append("")

    lines.append("---")
    lines.append("*Report generated by `scripts/protocol_advisor.py`.*")
    return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Kaelis Protocol Evolution Advisor")
    parser.add_argument("--output", "-o", help="Output markdown report path")
    args = parser.parse_args()

    report = generate_report()
    md = format_markdown(report)
    print(md)

    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        logger.info("Report saved to %s", args.output)


if __name__ == "__main__":
    main()
