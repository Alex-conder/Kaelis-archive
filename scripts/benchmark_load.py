"""
B-3: 性能与可扩展性基准测试

使用 Python concurrent.futures 模拟并发负载，无需额外依赖（locust/k6）。

测试路径：
- 健康检查 (GET /api/auth/health)
- 记忆写入 (POST /api/memory/write)
- 记忆搜索 (POST /api/memory/search)
- 记忆统计 (GET /api/memory/stats)
- 技能列表 (GET /api/skills/)

用法：
    # 先启动后端: python start_server.py
    python scripts/benchmark_load.py --concurrency 50 --duration 30
"""

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

# Windows PowerShell GBK 编码兼容
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests

# 项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

BASE_URL = "http://127.0.0.1:5000"


class LoadTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def health(self) -> float:
        start = time.time()
        r = self.session.get(f"{self.base_url}/api/auth/health", timeout=5)
        r.raise_for_status()
        return time.time() - start

    def memory_write(self) -> float:
        start = time.time()
        # 写入 L0 避免污染 L2 搜索数据集
        r = self.session.post(
            f"{self.base_url}/api/memory/write",
            json={
                "layer": "L0",
                "key": f"benchmark_{int(time.time() * 1000000) % 1000000}",
                "value": {"content": "benchmark test data", "score": 0.85},
                "metadata": {"source": "benchmark", "importance": 0.5},
            },
            timeout=5,
        )
        r.raise_for_status()
        return time.time() - start

    def memory_search(self) -> float:
        start = time.time()
        r = self.session.post(
            f"{self.base_url}/api/memory/search",
            json={"layer": "L2", "query": "benchmark", "top_k": 10},
            timeout=5,
        )
        r.raise_for_status()
        return time.time() - start

    def memory_stats(self) -> float:
        start = time.time()
        r = self.session.get(f"{self.base_url}/api/memory/stats", timeout=5)
        r.raise_for_status()
        return time.time() - start

    def skills_list(self) -> float:
        start = time.time()
        r = self.session.get(f"{self.base_url}/api/skills/?limit=20", timeout=5)
        r.raise_for_status()
        return time.time() - start


def run_benchmark(endpoint_name: str, concurrency: int, duration: int) -> dict:
    """对单个端点运行并发负载测试。"""
    tester = LoadTester()
    method = getattr(tester, endpoint_name)

    results = []
    errors = 0
    start_time = time.time()
    lock = __import__('threading').Lock()

    def worker():
        nonlocal errors
        while time.time() - start_time < duration:
            try:
                lat = method()
                with lock:
                    results.append(lat)
            except Exception:
                with lock:
                    errors += 1

    threads = []
    for _ in range(concurrency):
        t = __import__('threading').Thread(target=worker)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=duration + 10)

    if not results:
        return {"rps": 0, "avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "errors": errors}

    results.sort()
    n = len(results)
    actual_duration = min(time.time() - start_time, duration)
    return {
        "rps": round(n / actual_duration, 2),
        "avg_ms": round(statistics.mean(results) * 1000, 2),
        "p50_ms": round(results[int(n * 0.50)] * 1000, 2),
        "p95_ms": round(results[int(n * 0.95)] * 1000, 2),
        "p99_ms": round(results[int(n * 0.99)] * 1000, 2) if n >= 100 else round(results[-1] * 1000, 2),
        "min_ms": round(results[0] * 1000, 2),
        "max_ms": round(results[-1] * 1000, 2),
        "errors": errors,
        "total_requests": n + errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Kaelis Load Benchmark")
    parser.add_argument("--concurrency", type=int, default=50, help="并发用户数")
    parser.add_argument("--duration", type=int, default=30, help="测试持续时间(秒)")
    parser.add_argument("--url", type=str, default=BASE_URL, help="后端地址")
    args = parser.parse_args()

    print("=" * 60)
    print(f"[BENCH] Kaelis 性能基准测试")
    print(f"   并发: {args.concurrency} | 持续时间: {args.duration}s | 目标: {args.url}")
    print("=" * 60)

    # 先预热
    print("\n[WARMUP] 健康检查...")
    tester = LoadTester(args.url)
    try:
        tester.health()
        print("[OK] 后端连接正常")
    except Exception as e:
        print(f"[FAIL] 无法连接后端: {e}")
        print("   请先启动后端: python start_server.py")
        return

    endpoints = [
        ("health", "健康检查"),
        ("memory_write", "记忆写入"),
        ("memory_search", "记忆搜索"),
        ("memory_stats", "记忆统计"),
        ("skills_list", "技能列表"),
    ]

    report = {}
    for method, label in endpoints:
        print(f"\n[TEST] {label} ({method})...")
        result = run_benchmark(method, args.concurrency, args.duration)
        report[method] = {"label": label, **result}
        print(f"   RPS: {result['rps']:.2f} | Avg: {result['avg_ms']:.1f}ms | P95: {result['p95_ms']:.1f}ms | Errors: {result['errors']}")

    # 保存报告
    report_path = project_root / "docs/PERFORMANCE_BASELINE.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Kaelis 性能基线报告\n\n")
        f.write(f"**测试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**并发用户数**: {args.concurrency}\n")
        f.write(f"**持续时间**: {args.duration}s\n")
        f.write(f"**后端线程数**: {max(4, min(8, (os.cpu_count() or 4)))} (Waitress)\n")
        f.write(f"**SQLite 连接池**: 已启用 (max=8, WAL 模式)\n\n")
        f.write("## 测试结果\n\n")
        f.write("| 端点 | RPS | Avg(ms) | P50(ms) | P95(ms) | P99(ms) | Errors |\n")
        f.write("|------|-----|---------|---------|---------|---------|--------|\n")
        for method, data in report.items():
            f.write(
                f"| {data['label']} | {data['rps']:.2f} | {data['avg_ms']:.1f} | "
                f"{data['p50_ms']:.1f} | {data['p95_ms']:.1f} | {data['p99_ms']:.1f} | {data['errors']} |\n"
            )
        f.write("\n## 结论\n\n")
        # 自动判断 P95 是否 < 200ms
        memory_search_p95 = report.get("memory_search", {}).get("p95_ms", 999)
        if memory_search_p95 < 200:
            f.write(f"✅ **验收通过**: 记忆搜索 P95 延迟 {memory_search_p95:.1f}ms < 200ms\n")
        else:
            f.write(f"⚠️ **需优化**: 记忆搜索 P95 延迟 {memory_search_p95:.1f}ms >= 200ms\n")
            f.write("建议：增加 Waitress 线程数、优化 SQLite 索引、使用 FTS5 全文检索。\n")

    print(f"\n[REPORT] 报告已保存: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
