"""
Kaelis PR Review Agent
======================
为 Pull Request 提供架构级智能审查。

环境变量:
    GITHUB_TOKEN    - GitHub Personal Access Token
    GITHUB_EVENT_PATH - GitHub Actions 自动提供

用法:
    python scripts/pr_review_agent.py
"""

import json
import logging
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ============================================================================
# GitHub API
# ============================================================================

class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base = "https://api.github.com"

    def _request(self, path: str, method: str = "GET", data: Optional[bytes] = None) -> Any:
        url = f"{self.base}{path}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Kaelis-PR-Review-Agent/1.0",
        }
        if data:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            logger.error("GitHub API error %s: %s", e.code, e.read().decode()[:500])
            raise

    def get_pr_files(self, repo: str, pr_number: int) -> List[Dict]:
        return self._request(f"/repos/{repo}/pulls/{pr_number}/files")

    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        url = f"{self.base}/repos/{repo}/pulls/{pr_number}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3.diff",
                "User-Agent": "Kaelis-PR-Review-Agent/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")

    def post_review_comment(self, repo: str, pr_number: int, body: str, commit_id: str, path: str, line: int) -> Dict:
        return self._request(
            f"/repos/{repo}/pulls/{pr_number}/comments",
            method="POST",
            data=json.dumps({
                "body": body,
                "commit_id": commit_id,
                "path": path,
                "line": line,
                "side": "RIGHT",
            }).encode("utf-8"),
        )

    def post_pr_comment(self, repo: str, pr_number: int, body: str) -> Dict:
        return self._request(
            f"/repos/{repo}/issues/{pr_number}/comments",
            method="POST",
            data=json.dumps({"body": body}).encode("utf-8"),
        )

    def get_pr(self, repo: str, pr_number: int) -> Dict:
        return self._request(f"/repos/{repo}/pulls/{pr_number}")


# ============================================================================
# MCP Memory Search
# ============================================================================

def search_design_docs(query: str, top_k: int = 5) -> List[Dict[str, str]]:
    """通过本地 API 调用 MCP memory_search 查询设计文档。"""
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:5000/api/memory/search",
            data=json.dumps({
                "layer": "L3",
                "query": query,
                "top_k": top_k,
                "agent_id": "kaelis_dev",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success") and data.get("data"):
                return [
                    {
                        "key": item.get("key", ""),
                        "source": item.get("metadata", {}).get("source", "unknown"),
                        "content": str(item.get("value", ""))[:300],
                    }
                    for item in data["data"]
                ]
    except Exception as e:
        logger.warning("Memory search unavailable: %s", e)
    return []


# ============================================================================
# Rule Loader
# ============================================================================

DEFAULT_RULES = [
    {
        "id": "hardcoded_path",
        "type": "regex",
        "name": "硬编码路径",
        "severity": "error",
        "pattern": r'["\']data/[^"\']*["\']|os\.path\.join\([^)]*["\']data["\']',
        "message": "检测到硬编码 `data/` 路径。请使用可注入的 `db_dir` / `db_path` 参数（C1 契约）。",
    },
    {
        "id": "missing_circuit_breaker",
        "type": "regex",
        "name": "缺失熔断器",
        "severity": "warning",
        "pattern": r'def\s+\w+.*request|urllib\.request|requests\.get|requests\.post',
        "exclusion": r'CircuitBreaker|circuit_breaker|with_retry',
        "message": "检测到外部 HTTP 调用但未发现熔断器装饰。建议参考 `core/llm_client.py` 添加 `CircuitBreaker`。",
    },
    {
        "id": "missing_fallback",
        "type": "regex",
        "name": "缺失降级逻辑",
        "severity": "warning",
        "pattern": r'try:.*?except\s*\w+Error:\s*raise',
        "message": "检测到空的 except-raise 模式。根据 C4 契约，应有降级路径（返回默认值 / mock / 缓存）。",
    },
    {
        "id": "layer_violation",
        "type": "import_check",
        "name": "模块分层违规",
        "severity": "error",
        "source_pattern": r'^api/routes/',
        "forbidden_pattern": r'^core/\w+/\w+',
        "message": "api/routes/ 层不应直接导入 core/ 深层模块，应通过 service 层或 facade。",
    },
]


def load_rules(rules_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """从 YAML 文件加载审查规则，未指定时使用默认规则。"""
    if not rules_file:
        # 尝试自动发现项目根目录的 pr_review_rules.yaml
        for candidate in [Path("pr_review_rules.yaml"), Path("../pr_review_rules.yaml"), Path("../../pr_review_rules.yaml")]:
            if candidate.exists():
                rules_file = str(candidate)
                break

    if rules_file and Path(rules_file).exists():
        try:
            data = yaml.safe_load(Path(rules_file).read_text(encoding="utf-8"))
            if data and isinstance(data.get("rules"), list):
                logger.info("Loaded %d rules from %s", len(data["rules"]), rules_file)
                return data["rules"]
        except Exception as e:
            logger.warning("Failed to load rules from %s: %s", rules_file, e)

    logger.info("Using default rules (%d)", len(DEFAULT_RULES))
    return DEFAULT_RULES


# ============================================================================
# Review Rules Engine
# ============================================================================

RULES: List[Dict[str, Any]] = []  # 运行时加载


def analyze_file_diff(path: str, diff_text: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """分析单个文件的 diff，返回违规列表。"""
    violations = []
    added_lines = []

    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])

    added_text = "\n".join(added_lines)

    for rule in rules:
        rule_type = rule.get("type", "regex")

        if rule_type == "regex":
            pattern = rule.get("pattern")
            if not pattern:
                continue
            for match in re.finditer(pattern, added_text, re.DOTALL):
                # 检查排除项
                if rule.get("exclusion"):
                    ctx_start = max(0, match.start() - 200)
                    ctx_end = min(len(added_text), match.end() + 200)
                    context = added_text[ctx_start:ctx_end]
                    if re.search(rule["exclusion"], context):
                        continue

                line_num = added_text[:match.start()].count("\n") + 1
                violations.append({
                    "rule": rule["id"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "line": line_num,
                    "evidence": match.group(0)[:80],
                })

        elif rule_type == "import_check":
            source_pattern = rule.get("source_pattern", "")
            forbidden_pattern = rule.get("forbidden_pattern", "")
            if not source_pattern or not forbidden_pattern:
                continue
            if re.search(source_pattern, path):
                matches = re.findall(r'from\s+([\w.]+)\s+import', added_text)
                for imp in matches:
                    if re.search(forbidden_pattern, imp.replace(".", "/")):
                        violations.append({
                            "rule": rule["id"],
                            "severity": rule["severity"],
                            "message": rule["message"],
                            "evidence": f"from {imp} import ...",
                        })

        elif rule_type == "dependency_check":
            target_pattern = rule.get("target_pattern", "")
            required_param = rule.get("required_param", "")
            if not target_pattern or not required_param:
                continue
            if re.search(target_pattern, added_text):
                required_params = [p.strip() for p in required_param.split("|")]
                has_param = any(re.search(rf'\b{p}\b', added_text) for p in required_params)
                if not has_param:
                    violations.append({
                        "rule": rule["id"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "evidence": "Missing required parameter",
                    })

    return violations


# ============================================================================
# Review Report
# ============================================================================

def generate_review_body(pr_info: Dict, files: List[Dict], all_violations: List[Dict]) -> str:
    lines = [
        "## 🤖 Kaelis Architecture Review",
        "",
        f"**PR**: #{pr_info.get('number')} `{pr_info.get('title')}`",
        f"**Author**: @{pr_info.get('user', {}).get('login', 'unknown')}",
        "",
        "### 审查摘要",
        "",
    ]

    errors = [v for v in all_violations if v.get("severity") == "error"]
    warnings = [v for v in all_violations if v.get("severity") == "warning"]

    lines.append(f"- ❌ Errors: {len(errors)}")
    lines.append(f"- ⚠️ Warnings: {len(warnings)}")
    lines.append("")

    if errors:
        lines.append("### ❌ 架构违规（必须修复）")
        lines.append("")
        for v in errors[:10]:
            lines.append(f"**{v['rule']}**: {v['message']}")
            if "evidence" in v:
                lines.append(f"```\n{v['evidence']}\n```")
            lines.append("")

    if warnings:
        lines.append("### ⚠️ 改进建议")
        lines.append("")
        for v in warnings[:10]:
            lines.append(f"**{v['rule']}**: {v['message']}")
            lines.append("")

    # 查询相关设计文档
    docs = search_design_docs(" ".join(pr_info.get("title", "").split()[:5]))
    if docs:
        lines.append("### 📚 相关设计文档")
        lines.append("")
        for d in docs[:3]:
            lines.append(f"- `{d['source']}`: {d['content'][:100]}...")
        lines.append("")

    lines.append("---")
    lines.append("*本评论由 Kaelis PR Review Agent 自动生成。*")
    return "\n".join(lines)


# ============================================================================
# Main
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis PR Review Agent")
    parser.add_argument("--rules-file", help="Path to pr_review_rules.yaml")
    args = parser.parse_args()

    # 加载规则
    global RULES
    RULES = load_rules(args.rules_file)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN not set")
        sys.exit(1)

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        logger.error("GITHUB_EVENT_PATH not set (must run in GitHub Actions)")
        sys.exit(1)

    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    repo = os.environ.get("GITHUB_REPOSITORY", event.get("repository", {}).get("full_name", ""))
    pr_number = event.get("pull_request", {}).get("number", 0)

    if not repo or not pr_number:
        logger.error("Could not determine repo or PR number")
        sys.exit(1)

    logger.info("Reviewing PR #%d in %s", pr_number, repo)

    gh = GitHubClient(token)
    pr_info = gh.get_pr(repo, pr_number)
    files = gh.get_pr_files(repo, pr_number)

    all_violations = []
    for f in files:
        filename = f.get("filename", "")
        patch = f.get("patch", "")
        if not patch:
            continue
        violations = analyze_file_diff(filename, patch, RULES)
        for v in violations:
            v["file"] = filename
        all_violations.extend(violations)

    body = generate_review_body(pr_info, files, all_violations)

    # 发布总体评论
    try:
        gh.post_pr_comment(repo, pr_number, body)
        logger.info("Posted review comment to PR #%d", pr_number)
    except Exception as e:
        logger.error("Failed to post comment: %s", e)
        sys.exit(1)

    # 如果有错误，设置失败状态（但评论已发布）
    errors = [v for v in all_violations if v.get("severity") == "error"]
    if errors:
        logger.warning("Found %d architecture errors", len(errors))
        sys.exit(1)

    logger.info("Review complete. No architecture errors found.")


if __name__ == "__main__":
    main()
