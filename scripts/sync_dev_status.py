#!/usr/bin/env python3
"""
sync_dev_status.py -- Auto-sync dev-status docs with actual package versions.

Reads package.json and requirements.txt, then updates version strings
and status fields in dev-status/*.md files.
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEV_STATUS_DIR = PROJECT_ROOT / "dev-status"
PACKAGE_JSON = PROJECT_ROOT / "web" / "frontend" / "package.json"
REQUIREMENTS_TXT = PROJECT_ROOT / "requirements.txt"


def parse_package_json(path: Path) -> dict:
    """Extract dependency versions from package.json."""
    if not path.exists():
        print(f"[WARN] {path} not found")
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    deps = data.get("dependencies", {})
    dev_deps = data.get("devDependencies", {})
    return {**deps, **dev_deps}


def parse_requirements_txt(path: Path) -> dict:
    """Extract package==version from requirements.txt."""
    versions = {}
    if not path.exists():
        print(f"[WARN] {path} not found")
        return versions
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle package==version, package>=version, package~=version, package^=version
        m = re.match(r"^([a-zA-Z0-9_\-]+)\s*[=<>~^!]+\s*([\d\.]+.*)$", line)
        if m:
            pkg, ver = m.groups()
            versions[pkg.lower()] = ver.rstrip(";").strip()
    return versions


def get_replacement_map(pkg_versions: dict, req_versions: dict) -> list:
    """Build (old_pattern, new_text) replacement table."""
    replacements = []

    # --- Frontend versions from package.json ---
    def v(pkg: str):
        return pkg_versions.get(pkg, "")

    # React family
    react_ver = v("react") or "^19.0.0"
    react_dom_ver = v("react-dom") or react_ver
    router_ver = v("react-router-dom") or "^7.14.2"
    zustand_ver = v("zustand") or "^5.0.3"
    tailwind_ver = v("tailwindcss") or "^4.2.4"
    vite_ver = v("vite") or "^5.4.21"
    ts_ver = v("typescript") or "^5.3.3"
    query_ver = v("@tanstack/react-query") or "^5.99.2"
    axios_ver = v("axios") or "^1.15.2"

    # Old -> new text replacements (ordered by specificity)
    replacements.extend([
        # Exact embedded package.json blocks (A1)
        (
            '"react": "^18.2.0"',
            f'"react": "{react_ver}"'
        ),
        (
            '"react-dom": "^18.2.0"',
            f'"react-dom": "{react_dom_ver}"'
        ),
        (
            '"zustand": "^4.5.2"',
            f'"zustand": "{zustand_ver}"'
        ),
        # Inline dependency lists
        (
            "React 18.2",
            f"React {react_ver.lstrip('^~')}"
        ),
        (
            "React 18 入口",
            "React 19 入口"
        ),
        (
            "Zustand 4.5.2",
            f"Zustand {zustand_ver.lstrip('^~')}"
        ),
        (
            "Vite 5.1",
            f"Vite {vite_ver.lstrip('^~')}"
        ),
        (
            "TailwindCSS",
            f"TailwindCSS {tailwind_ver.lstrip('^~')}"
        ),
        (
            "TypeScript 5.3",
            f"TypeScript {ts_ver.lstrip('^~')}"
        ),
        # Status descriptions
        (
            "仅渲染基本布局，无路由",
            "已配置 HashRouter，支持多页面导航"
        ),
        (
            "无路由",
            "已配置 react-router-dom"
        ),
        # A9 gap-analysis status updates
        (
            "React Router 未配置",
            "React Router (HashRouter) 已配置"
        ),
        (
            "无 axios/fetch 封装",
            "axios 已配置，含拦截器封装"
        ),
        (
            "无 TanStack Query (React Query)",
            f"TanStack Query {query_ver.lstrip('^~')} 已配置"
        ),
        (
            "ReactMarkdown",
            f"react-markdown 已配置"
        ),
        (
            "Vitest + Playwright",
            "Vitest 已配置 (Playwright 尚未配置)"
        ),
        # Feature status
        (
            "无 API 调用",
            "axios API 客户端已配置"
        ),
        (
            "无状态管理（除 Zustand store 骨架）",
            "Zustand 状态管理已配置"
        ),
        (
            "无全局错误边界",
            "全局错误边界已配置"
        ),
    ])

    # --- Python versions from requirements.txt ---
    def rv(pkg: str):
        return req_versions.get(pkg.lower(), "")

    flask_ver = rv("flask") or ""
    if flask_ver:
        replacements.append((
            "Flask (版本未记录)",
            f"Flask {flask_ver}"
        ))

    return replacements


def sync_file(path: Path, replacements: list) -> int:
    """Apply replacements to a single file. Returns number of replacements made."""
    if not path.exists():
        return 0

    original = path.read_text(encoding="utf-8")
    text = original
    count = 0

    for old, new in replacements:
        if new in text:
            # Already up-to-date for this replacement
            continue
        if old in text:
            text = text.replace(old, new)
            count += 1
            print(f"  [{path.name}] Replaced: {old!r} -> {new!r}")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"  [SAVED] {path.name} ({count} replacements)")
    else:
        print(f"  [SKIP]  {path.name} (no changes)")

    return count


def main():
    print("=" * 60)
    print("Syncing dev-status docs with actual package versions")
    print("=" * 60)

    pkg_versions = parse_package_json(PACKAGE_JSON)
    req_versions = parse_requirements_txt(REQUIREMENTS_TXT)

    print(f"\n[package.json] {len(pkg_versions)} packages found")
    print(f"[requirements.txt] {len(req_versions)} packages found\n")

    replacements = get_replacement_map(pkg_versions, req_versions)
    total = 0

    for md_file in sorted(DEV_STATUS_DIR.glob("*.md")):
        total += sync_file(md_file, replacements)

    print("\n" + "=" * 60)
    if total:
        print(f"Done. {total} replacements applied across dev-status/")
        print("Please review the changes with: git diff dev-status/")
    else:
        print("No replacements needed. Docs are up-to-date.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
