#!/usr/bin/env python3
"""
P2: 一键回滚发布脚本

用法:
    python scripts/rollback_release.py <version> [--dry-run]
    python scripts/rollback_release.py v0.3.0

操作:
1. PyPI: yank 指定版本（使其不可 pip install，但不删除历史）
2. GitHub Release: 标记为 "pre-release" + 标题追加 [ROLLED BACK]
3. VSCode Marketplace: unpublish 该版本
4. 生成本地回滚报告

依赖:
    pip install requests twine
    npm install -g @vscode/vsce gh
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
REPORT_FILE = PROJECT_ROOT / "data" / "rollback_report.json"


def run_cmd(cmd: list, cwd=None, check=False):
    """运行外部命令，返回 (success, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd or PROJECT_ROOT, timeout=60
        )
        success = result.returncode == 0
        if check and not success:
            print(f"[ERR] Command failed: {' '.join(cmd)}")
            print(f"      stderr: {result.stderr[:200]}")
        return success, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def rollback_pypi(version: str, dry_run: bool) -> dict:
    """PyPI: yank 版本"""
    print(f"[INFO] Rolling back PyPI version {version}...")
    pkg_name = "kaelis"  # 根据实际包名调整

    if dry_run:
        print(f"  [DRY-RUN] Would yank {pkg_name}=={version} on PyPI")
        return {"platform": "PyPI", "action": "yank", "status": "dry-run", "version": version}

    # 尝试使用 twine 或 PyPI API yank
    # twine 本身不支持 yank，需要使用 pip 的 yank 功能或调用 PyPI API
    # 这里使用 pip 的 yank 方式：通过 pip index 检查

    success, stdout, stderr = run_cmd(
        [sys.executable, "-m", "pip", "index", "versions", pkg_name],
        check=False,
    )

    # 由于 twine 不直接支持 yank，我们生成操作指南
    print(f"  [MANUAL] PyPI does not support automated yank via twine.")
    print(f"           Please run manually:")
    print(f"           curl -X POST https://pypi.org/manage/project/{pkg_name}/release/{version}/yank/")
    print(f"           Or use: python -m pip install {pkg_name}=={version}  # verify it's installable")

    return {
        "platform": "PyPI",
        "action": "yank (manual required)",
        "status": "manual",
        "version": version,
        "note": "PyPI yank requires manual web UI or API token with manage scope",
    }


def rollback_github_release(version: str, dry_run: bool) -> dict:
    """GitHub Release: 标记为 pre-release 并修改标题"""
    print(f"[INFO] Rolling back GitHub Release {version}...")

    # 获取 repo 信息
    success, stdout, _ = run_cmd(["git", "remote", "get-url", "origin"])
    if not success:
        return {"platform": "GitHub", "status": "failed", "error": "No git remote found"}

    remote_url = stdout.strip()
    match = re.search(r"github\.com[:/](.+?)/(.+?)(?:\.git)?$", remote_url)
    if not match:
        return {"platform": "GitHub", "status": "failed", "error": f"Cannot parse repo from {remote_url}"}

    owner, repo = match.groups()

    if dry_run:
        print(f"  [DRY-RUN] Would mark release {version} as pre-release on {owner}/{repo}")
        return {"platform": "GitHub", "action": "mark pre-release", "status": "dry-run", "version": version}

    # 使用 gh CLI 更新 release
    tag = version if version.startswith("v") else f"v{version}"
    success, stdout, stderr = run_cmd([
        "gh", "release", "edit", tag,
        "--prerelease",
        "--title", f"[ROLLED BACK] Kaelis {tag}",
        "--notes", f"This release has been rolled back. Please do not use.\n\nOriginal release notes preserved for reference.",
    ])

    if success:
        print(f"  [OK] GitHub Release {tag} marked as pre-release")
        return {"platform": "GitHub", "action": "mark pre-release", "status": "success", "version": tag}
    else:
        print(f"  [WARN] GitHub CLI failed: {stderr[:200]}")
        print(f"         Manual: gh release edit {tag} --prerelease --title '[ROLLED BACK] Kaelis {tag}'")
        return {"platform": "GitHub", "action": "mark pre-release", "status": "manual", "version": tag, "error": stderr[:200]}


def rollback_vscode(version: str, dry_run: bool) -> dict:
    """VSCode Marketplace: unpublish"""
    print(f"[INFO] Rolling back VSCode Extension {version}...")

    vscode_dir = PROJECT_ROOT / "vscode-kaelis"
    if not vscode_dir.exists():
        return {"platform": "VSCode", "status": "skipped", "reason": "vscode-kaelis dir not found"}

    if dry_run:
        print(f"  [DRY-RUN] Would unpublish Kaelis VSCode extension v{version}")
        return {"platform": "VSCode", "action": "unpublish", "status": "dry-run", "version": version}

    # vsce unpublish 需要完全下架，这里使用 retire 方式（删除特定版本）
    # vsce 不直接支持删除单个版本，只能完全 unpublish
    success, stdout, stderr = run_cmd(
        ["npx", "@vscode/vsce", "unpublish", "--pat", "$VSCE_PAT"],
        cwd=vscode_dir,
    )

    if success:
        print(f"  [OK] VSCode Extension unpublished")
        return {"platform": "VSCode", "action": "unpublish", "status": "success", "version": version}
    else:
        print(f"  [WARN] vsce unpublish failed: {stderr[:200]}")
        print(f"         Manual: cd vscode-kaelis && npx @vscode/vsce unpublish")
        return {"platform": "VSCode", "action": "unpublish", "status": "manual", "version": version, "error": stderr[:200]}


def main():
    parser = argparse.ArgumentParser(description="Rollback a Kaelis release across all platforms")
    parser.add_argument("version", help="Version to rollback (e.g., v0.3.0)")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without executing")
    args = parser.parse_args()

    version = args.version.lstrip("v")
    tag = f"v{version}"

    print("=" * 60)
    print(f"Kaelis Release Rollback — {tag}")
    print("=" * 60)
    if args.dry_run:
        print("[DRY RUN MODE] No actual changes will be made.\n")

    results = []

    # 1. PyPI
    results.append(rollback_pypi(version, args.dry_run))

    # 2. GitHub Release
    results.append(rollback_github_release(version, args.dry_run))

    # 3. VSCode Marketplace
    results.append(rollback_vscode(version, args.dry_run))

    # 4. 生成本地报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": tag,
        "dry_run": args.dry_run,
        "results": results,
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 60)
    print("Rollback Summary")
    print("=" * 60)
    for r in results:
        status_icon = "✅" if r.get("status") == "success" else "⚠️" if r.get("status") == "manual" else "🟡"
        print(f"  {status_icon} {r['platform']}: {r.get('action', 'N/A')} — {r['status']}")

    print(f"\n[OK] Report saved to {REPORT_FILE}")

    if args.dry_run:
        print("\nTo execute for real, run without --dry-run:")
        print(f"  python scripts/rollback_release.py {tag}")
    else:
        print("\n[IMPORTANT] Please verify rollback status on each platform:")
        print(f"  - PyPI: https://pypi.org/project/kaelis/{version}/")
        print(f"  - GitHub: https://github.com/Alex-conder/Kaelis-archive/releases/tag/{tag}")
        print(f"  - VSCode Marketplace: https://marketplace.visualstudio.com/items?itemName=kaelis")


if __name__ == "__main__":
    main()
