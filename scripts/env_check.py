#!/usr/bin/env python3
"""
Kaelis 环境检测脚本
输出能力矩阵 JSON，覆盖 FTS5/FAISS/LLM/GPU 检测

Usage:
    python scripts/env_check.py
    python scripts/env_check.py --json > env_report.json
"""

import json
import sqlite3
import sys
import os
import argparse

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_fts5():
    """检测 SQLite FTS5 扩展"""
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        conn.close()
        return True
    except sqlite3.OperationalError:
        return False


def check_faiss():
    """检测 FAISS 向量库"""
    try:
        import faiss
        return faiss.__version__
    except ImportError:
        return None


def check_llm():
    """检测 LLM 客户端"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.llm_client import llm_client
        return llm_client.model if llm_client else None
    except Exception:
        return None


def check_gpu():
    """检测 GPU 可用性"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def check_deepseek_api():
    """检测 DeepSeek API 连通性"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"available": False, "reason": "API key not configured"}
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"available": True, "status": resp.status}
    except Exception as e:
        return {"available": False, "reason": str(e)[:100]}


def check_backend():
    """检测本地后端服务"""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:5000/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"running": True, "status": data.get("status", "unknown")}
    except Exception as e:
        return {"running": False, "reason": str(e)[:100]}


def generate_report():
    """生成完整环境报告"""
    report = {
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
        "checks": {
            "sqlite_fts5": check_fts5(),
            "faiss_version": check_faiss(),
            "llm_model": check_llm(),
            "gpu_available": check_gpu(),
            "deepseek_api": check_deepseek_api(),
            "local_backend": check_backend(),
        },
        "capabilities": {
            "hybrid_search": check_fts5() and check_faiss() is not None,
            "vector_only": check_faiss() is not None,
            "fts_only": check_fts5(),
            "llm_available": check_llm() is not None,
            "offline_capable": check_fts5(),  # SQLite 本地即可离线
            "gpu_accelerated": check_gpu(),
        },
        "recommendations": [],
        "degradation_path": []
    }

    # 生成建议
    if not report["capabilities"]["hybrid_search"]:
        if report["capabilities"]["fts_only"]:
            report["recommendations"].append("FTS5 available but FAISS missing - using keyword-only mode")
            report["degradation_path"].append("FTS5 -> LIKE -> static response")
        else:
            report["recommendations"].append("Neither FTS5 nor FAISS available - falling back to LIKE queries")
            report["degradation_path"].append("LIKE -> static response")
    else:
        report["degradation_path"].append("FAISS+FTS5 Hybrid -> FAISS only -> FTS5 only -> LIKE -> static")

    if not report["capabilities"]["llm_available"]:
        report["recommendations"].append("LLM unavailable - RuleBasedEvaluator will be primary")
        report["degradation_path"].append("HybridEvaluator -> RuleBasedEvaluator -> static pass")

    if not report["checks"]["deepseek_api"]["available"]:
        report["recommendations"].append("DeepSeek API unreachable - running in offline mode")

    if report["checks"]["local_backend"]["running"]:
        report["recommendations"].append("Local backend running at http://localhost:5000")
    else:
        report["recommendations"].append("Local backend not running - start with: python start_server.py")

    return report


def main():
    parser = argparse.ArgumentParser(description="Kaelis Environment Check")
    parser.add_argument("--json", action="store_true", help="Output raw JSON only")
    args = parser.parse_args()

    report = generate_report()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("  Kaelis Environment Check")
        print("=" * 60)
        print()

        print("[System]")
        print(f"  Platform:       {report['platform']}")
        print(f"  Python:         {report['python_version']}")
        print()

        print("[Checks]")
        for name, result in report["checks"].items():
            if isinstance(result, bool):
                icon = "[OK]" if result else "[NG]"
                print(f"  {icon} {name:20s}: {result}")
            elif isinstance(result, dict):
                icon = "[OK]" if result.get("available") or result.get("running") else "[NG]"
                print(f"  {icon} {name:20s}: {result}")
            else:
                icon = "[OK]" if result else "[NG]"
                print(f"  {icon} {name:20s}: {result}")
        print()

        print("[Capabilities]")
        for name, available in report["capabilities"].items():
            icon = "[OK]" if available else "[NG]"
            print(f"  {icon} {name:20s}")
        print()

        if report["recommendations"]:
            print("[Recommendations]")
            for rec in report["recommendations"]:
                print(f"  -> {rec}")
            print()

        if report["degradation_path"]:
            print("[Degradation Path]")
            for path in report["degradation_path"]:
                print(f"  {path}")
            print()

        print("=" * 60)

    # 返回退出码：0 = 至少基础能力可用，1 = 完全不可用
    if report["capabilities"]["offline_capable"]:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
