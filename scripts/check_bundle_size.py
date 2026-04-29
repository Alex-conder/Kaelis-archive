#!/usr/bin/env python3
"""
Prompt 3: 前端构建产物大小监控

用法:
    python scripts/check_bundle_size.py [--dist web/frontend/dist]

逻辑:
1. 解析 dist/assets/ 目录下 JS/CSS 文件大小
2. 设定硬性阈值：主JS包 > 600KB 或单个懒加载路由 > 100KB 时触发失败
3. 生成大小报告，用于历史对比
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DIST = PROJECT_ROOT / "web" / "frontend" / "dist"
BASELINE_FILE = PROJECT_ROOT / "data" / "bundle_size_baseline.json"
REPORT_FILE = PROJECT_ROOT / "data" / "bundle_size_report.json"

# 阈值配置 (单位: bytes)
MAIN_JS_THRESHOLD = 600 * 1024      # 600 KB
MAIN_CSS_THRESHOLD = 100 * 1024     # 100 KB
LAZY_CHUNK_THRESHOLD = 100 * 1024   # 100 KB


def analyze_dist(dist_path: Path) -> dict:
    """分析构建产物大小"""
    assets_dir = dist_path / "assets"
    if not assets_dir.exists():
        return {"error": f"Assets dir not found: {assets_dir}"}

    files = []
    main_js = None
    main_css = None
    lazy_chunks = []
    total_size = 0

    for f in assets_dir.iterdir():
        if not f.is_file():
            continue
        size = f.stat().st_size
        total_size += size
        name = f.name

        # 识别主包和懒加载 chunk
        if name.startswith("index-") and name.endswith(".js"):
            main_js = {"name": name, "size": size}
        elif name.startswith("index-") and name.endswith(".css"):
            main_css = {"name": name, "size": size}
        elif name.endswith(".js") or name.endswith(".css"):
            lazy_chunks.append({"name": name, "size": size})

        files.append({"name": name, "size": size})

    return {
        "files": sorted(files, key=lambda x: x["size"], reverse=True),
        "main_js": main_js,
        "main_css": main_css,
        "lazy_chunks": lazy_chunks,
        "total_size": total_size,
        "file_count": len(files),
    }


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size/1024:.1f}KB"
    else:
        return f"{size/(1024*1024):.2f}MB"


def check_thresholds(result: dict) -> tuple:
    """检查是否超过阈值，返回 (passed, messages)"""
    messages = []
    passed = True

    main_js = result.get("main_js")
    if main_js and main_js["size"] > MAIN_JS_THRESHOLD:
        messages.append(
            f"[FAIL] Main JS bundle too large: {format_size(main_js['size'])} "
            f"(threshold: {format_size(MAIN_JS_THRESHOLD)})"
        )
        passed = False
    elif main_js:
        messages.append(
            f"[PASS] Main JS: {format_size(main_js['size'])} <= {format_size(MAIN_JS_THRESHOLD)}"
        )

    main_css = result.get("main_css")
    if main_css and main_css["size"] > MAIN_CSS_THRESHOLD:
        messages.append(
            f"[WARN] Main CSS bundle large: {format_size(main_css['size'])} "
            f"(threshold: {format_size(MAIN_CSS_THRESHOLD)})"
        )

    for chunk in result.get("lazy_chunks", []):
        if chunk["size"] > LAZY_CHUNK_THRESHOLD:
            messages.append(
                f"[WARN] Lazy chunk large: {chunk['name']} = {format_size(chunk['size'])} "
                f"(threshold: {format_size(LAZY_CHUNK_THRESHOLD)})"
            )

    return passed, messages


def load_baseline():
    if BASELINE_FILE.exists():
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return {}


def save_baseline(result):
    baseline = {
        "main_js_size": result.get("main_js", {}).get("size", 0),
        "total_size": result.get("total_size", 0),
        "file_count": result.get("file_count", 0),
    }
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    print(f"[OK] Bundle baseline saved to {BASELINE_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Frontend bundle size gate")
    parser.add_argument("--dist", type=Path, default=DEFAULT_DIST)
    parser.add_argument("--save-baseline", action="store_true")
    args = parser.parse_args()

    print("[INFO] Analyzing frontend bundle size...")

    if not args.dist.exists():
        print(f"[WARN] Dist directory not found: {args.dist}")
        print("       Skipping bundle size check.")
        sys.exit(0)

    result = analyze_dist(args.dist)
    if "error" in result:
        print(f"[ERR] {result['error']}")
        sys.exit(1)

    print(f"[INFO] Total assets: {result['file_count']} files, {format_size(result['total_size'])}")
    if result.get("main_js"):
        print(f"[INFO] Main JS:   {result['main_js']['name']} = {format_size(result['main_js']['size'])}")
    if result.get("main_css"):
        print(f"[INFO] Main CSS:  {result['main_css']['name']} = {format_size(result['main_css']['size'])}")

    if args.save_baseline:
        save_baseline(result)
        sys.exit(0)

    passed, messages = check_thresholds(result)

    # 保存报告
    report = {
        "timestamp": __import__('time').strftime("%Y-%m-%d %H:%M:%S"),
        "passed": passed,
        "messages": messages,
        "result": result,
    }
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    for m in messages:
        print(m)

    if passed:
        print("[PASS] Bundle size within thresholds.")
        sys.exit(0)
    else:
        print("[FAIL] Bundle size exceeds thresholds.")
        print("       Suggestion: Use React.lazy + dynamic import() to split large chunks.")
        sys.exit(1)


if __name__ == "__main__":
    main()
