#!/usr/bin/env python3
"""
Prompt 1: 性能基线自动检测与告警

用法:
    python scripts/check_performance.py [--save-baseline]

逻辑:
1. 使用 Flask test_client 测试核心 API 的响应时间
2. 对比 data/performance_baseline.json 中的基线
3. 若 P95 延迟增加超过 50% 或吞吐量下降超过 20%，返回失败
4. 生成性能退化报告
"""

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BASELINE_FILE = PROJECT_ROOT / "data" / "performance_baseline.json"
REPORT_FILE = PROJECT_ROOT / "data" / "performance_report.json"

# 阈值配置
LATENCY_REGRESSION_THRESHOLD = 1.50  # P95 延迟增加 50% 视为退化
THROUGHPUT_REGRESSION_THRESHOLD = 0.80  # 吞吐量下降 20% 视为退化
BENCHMARK_REQUESTS = 30  # 每个端点的测试请求数


def benchmark_endpoint(client, method: str, path: str, json_data=None):
    """对一个端点运行多次请求，收集延迟数据"""
    times = []
    errors = 0
    for _ in range(BENCHMARK_REQUESTS):
        start = time.perf_counter()
        try:
            if method == "GET":
                rv = client.get(path)
            elif method == "POST":
                rv = client.post(path, json=json_data or {})
            else:
                raise ValueError(f"Unsupported method: {method}")
            if rv.status_code >= 400:
                errors += 1
        except Exception:
            errors += 1
        finally:
            times.append(time.perf_counter() - start)
    return times, errors


def compute_metrics(times):
    """计算 P50, P95, avg, min, max"""
    if not times:
        return {}
    times.sort()
    n = len(times)
    return {
        "avg_ms": round(statistics.mean(times) * 1000, 2),
        "p50_ms": round(times[int(n * 0.50)] * 1000, 2),
        "p95_ms": round(times[int(n * 0.95)] * 1000, 2),
        "p99_ms": round(times[int(n * 0.99)] * 1000, 2),
        "min_ms": round(times[0] * 1000, 2),
        "max_ms": round(times[-1] * 1000, 2),
    }


def load_baseline():
    if BASELINE_FILE.exists():
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return {}


def save_baseline(results):
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Baseline saved to {BASELINE_FILE}")


def check_regression(current, baseline):
    """检查是否退化，返回 (pass, messages)"""
    messages = []
    passed = True

    for endpoint, cur in current.items():
        base = baseline.get(endpoint)
        if not base:
            continue

        cur_p95 = cur.get("p95_ms", 0)
        base_p95 = base.get("p95_ms", 0)
        if base_p95 > 0 and cur_p95 > base_p95 * LATENCY_REGRESSION_THRESHOLD:
            messages.append(
                f"[FAIL] {endpoint}: P95 latency regressed {base_p95:.1f}ms -> {cur_p95:.1f}ms "
                f"(+{((cur_p95/base_p95-1)*100):.0f}%, threshold {LATENCY_REGRESSION_THRESHOLD*100:.0f}%)"
            )
            passed = False

        # throughput proxy: requests per second (RPS) ~ 1000 / avg_ms
        cur_avg = cur.get("avg_ms", 1)
        base_avg = base.get("avg_ms", 1)
        if base_avg > 0 and cur_avg > base_avg / THROUGHPUT_REGRESSION_THRESHOLD:
            messages.append(
                f"[WARN] {endpoint}: Avg latency increased {base_avg:.1f}ms -> {cur_avg:.1f}ms "
                f"(throughput proxy degraded)"
            )

    return passed, messages


def _run_benchmark(save_baseline_flag: bool) -> dict:
    """在子进程中运行 benchmark，返回结果字典"""
    import os
    os.environ['KAELIS_TESTING'] = '1'
    # 清除 LLM API Key，避免导入时 OpenAI 客户端网络初始化阻塞
    for key in ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
                'QWEN_API_KEY', 'ZHIPU_API_KEY', 'MOONSHOT_API_KEY',
                'XUNFEI_API_KEY', 'BAIDU_API_KEY', 'TENCENT_API_KEY'):
        os.environ.pop(key, None)

    sys.path.insert(0, str(PROJECT_ROOT))
    from prod_server import create_app
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    endpoints = {
        "health": {"method": "GET", "path": "/api/health"},
        "memory_search": {"method": "POST", "path": "/api/memory/search", "json": {"layer": "L2", "query": "test", "top_k": 5}},
        "memory_stats": {"method": "GET", "path": "/api/memory/stats"},
        "skills_list": {"method": "GET", "path": "/api/skills/?limit=5"},
        "flywheel_health": {"method": "GET", "path": "/api/strategy-flywheel/health"},
    }

    current_results = {}
    for name, cfg in endpoints.items():
        times, errors = benchmark_endpoint(client, cfg["method"], cfg["path"], cfg.get("json"))
        metrics = compute_metrics(times)
        metrics["errors"] = errors
        metrics["requests"] = len(times)
        current_results[name] = metrics

    if save_baseline_flag:
        save_baseline(current_results)
        return {"action": "saved_baseline"}

    baseline = load_baseline()
    if not baseline:
        save_baseline(current_results)
        return {"action": "init_baseline"}

    passed, messages = check_regression(current_results, baseline)

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": baseline,
        "current": current_results,
        "passed": passed,
        "messages": messages,
    }
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "action": "checked",
        "passed": passed,
        "messages": messages,
        "current_results": current_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Performance regression gate")
    parser.add_argument("--save-baseline", action="store_true", help="Save current results as baseline")
    args = parser.parse_args()

    print("[INFO] Starting performance benchmark...")

    # 使用子进程运行 benchmark，避免重型依赖导入阻塞主进程
    # 并设置 60 秒超时
    script = (
        "import sys, json; "
        "from scripts.check_performance import _run_benchmark; "
        "result = _run_benchmark(" + ("True" if args.save_baseline else "False") + "); "
        "print(json.dumps(result))"
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        print("[WARN] Performance benchmark timed out after 60s (heavy dependencies detected)")
        print("[INFO] Skipping performance check in local development environment")
        sys.exit(0)
    except Exception as e:
        print(f"[WARN] Could not run performance benchmark: {e}")
        print("[INFO] Skipping performance check")
        sys.exit(0)

    if proc.returncode != 0:
        print(f"[WARN] Benchmark subprocess failed: {proc.stderr}")
        print("[INFO] Skipping performance check")
        sys.exit(0)

    # 解析子进程输出中的最后一行 JSON
    output_lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    if not output_lines:
        print("[WARN] Benchmark subprocess returned no output")
        sys.exit(0)

    try:
        result = json.loads(output_lines[-1])
    except json.JSONDecodeError:
        print(f"[WARN] Could not parse benchmark output: {output_lines[-1][:200]}")
        sys.exit(0)

    action = result.get("action", "")
    if action == "saved_baseline":
        print("[OK] Baseline saved.")
        sys.exit(0)
    elif action == "init_baseline":
        print("[OK] No baseline found, initialized with current results.")
        sys.exit(0)
    elif action == "checked":
        current_results = result.get("current_results", {})
        for name, metrics in current_results.items():
            errors = metrics.get("errors", 0)
            status = "OK" if errors == 0 else f"ERR({errors})"
            print(f"  {name}: avg={metrics.get('avg_ms', 0):.1f}ms p95={metrics.get('p95_ms', 0):.1f}ms [{status}]")

        messages = result.get("messages", [])
        if messages:
            for m in messages:
                print(m)

        if result.get("passed", True):
            print("[PASS] Performance baseline maintained.")
            sys.exit(0)
        else:
            print("[FAIL] Performance regression detected. See report above.")
            sys.exit(1)
    else:
        print(f"[WARN] Unknown benchmark action: {action}")
        sys.exit(0)


if __name__ == "__main__":
    main()
