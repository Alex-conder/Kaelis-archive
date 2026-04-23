"""
记忆健康探针 (P10-008)

启动时完整性检查 + 周期性健康检测：
- FTS5 索引一致性
- FAISS 向量存储可用性
- 四层记忆各层读写能力
- LLM 连通性

输出标准化健康报告，供 /api/health 或启动脚本调用。
"""

import json
import logging
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 支持直接运行
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """单项健康检查结果"""
    component: str
    status: str  # "healthy", "degraded", "failed"
    latency_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class MemoryHealthProbe:
    """
    记忆子系统健康探针
    
    使用方式：
        probe = MemoryHealthProbe()
        report = probe.run_all_checks()
        if report["overall"] != "healthy":
            logger.warning("Memory subsystem degraded")
    """
    
    def __init__(self, db_dir: str = "data"):
        self.db_dir = Path(db_dir)
        self.results: List[HealthCheckResult] = []
    
    def run_all_checks(self) -> Dict[str, Any]:
        """运行所有健康检查并返回汇总报告"""
        self.results = []
        
        checks = [
            self.check_sqlite_connectivity,
            self.check_fts5,
            self.check_faiss,
            self.check_four_layer_memory,
            self.check_llm_connectivity,
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                logger.error(f"Health check {check.__name__} crashed: {e}")
                self.results.append(HealthCheckResult(
                    component=check.__name__.replace("check_", ""),
                    status="failed",
                    latency_ms=0.0,
                    message=f"Check crashed: {e}",
                    details={"error": str(e)}
                ))
        
        # 汇总
        overall = "healthy"
        for r in self.results:
            if r.status == "failed":
                overall = "failed"
                break
            elif r.status == "degraded" and overall == "healthy":
                overall = "degraded"
        
        return {
            "overall": overall,
            "timestamp": datetime.now().isoformat(),
            "checks": [asdict(r) for r in self.results],
            "summary": {
                "total": len(self.results),
                "healthy": sum(1 for r in self.results if r.status == "healthy"),
                "degraded": sum(1 for r in self.results if r.status == "degraded"),
                "failed": sum(1 for r in self.results if r.status == "failed"),
            }
        }
    
    def _timed_check(self, name: str, fn) -> HealthCheckResult:
        """执行带计时的检查函数"""
        start = time.perf_counter()
        try:
            status, message, details = fn()
        except Exception as e:
            status, message, details = "failed", str(e), {}
        latency = (time.perf_counter() - start) * 1000
        result = HealthCheckResult(
            component=name,
            status=status,
            latency_ms=round(latency, 2),
            message=message,
            details=details
        )
        self.results.append(result)
        return result
    
    def check_sqlite_connectivity(self):
        """检查 SQLite 数据库连通性"""
        def _check():
            dbs = ["kaelis_dev.db", "kaelis_graph.db"]
            ok_count = 0
            details = {}
            for db_name in dbs:
                db_path = self.db_dir / db_name
                try:
                    with sqlite3.connect(str(db_path)) as conn:
                        cursor = conn.execute("SELECT 1")
                        cursor.fetchone()
                        ok_count += 1
                        details[db_name] = "ok"
                except Exception as e:
                    details[db_name] = f"error: {e}"
            
            if ok_count == len(dbs):
                return "healthy", f"All {len(dbs)} databases accessible", details
            elif ok_count > 0:
                return "degraded", f"{ok_count}/{len(dbs)} databases accessible", details
            else:
                return "failed", "No databases accessible", details
        
        return self._timed_check("sqlite", _check)
    
    def check_fts5(self):
        """检查 FTS5 索引健康状态"""
        def _check():
            db_path = self.db_dir / "kaelis_dev.db"
            with sqlite3.connect(str(db_path)) as conn:
                try:
                    # 确认 FTS5 模块存在
                    cursor = conn.execute("PRAGMA compile_options")
                    options = [r[0] for r in cursor.fetchall()]
                    if "ENABLE_FTS5" not in options:
                        return "failed", "FTS5 not compiled in SQLite", {"compile_options": options[:10]}
                
                    # 检查虚拟表存在性
                    tables = []
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fts_%'"):
                        tables.append(row[0])
                
                    # 简单查询测试
                    for tbl in tables:
                        conn.execute(f"SELECT COUNT(*) FROM {tbl}")
                
                    return "healthy", f"FTS5 ready, tables: {tables}", {"tables": tables}
                except Exception as e:
                    return "failed", f"FTS5 check failed: {e}", {}
        return self._timed_check("fts5", _check)
    
    def check_faiss(self):
        """检查 FAISS 向量库可用性"""
        def _check():
            try:
                import faiss
                version = faiss.__version__ if hasattr(faiss, "__version__") else "unknown"
                
                # 快速功能测试：创建一个小索引
                import numpy as np
                dim = 8
                index = faiss.IndexFlatL2(dim)
                vectors = np.random.random((2, dim)).astype("float32")
                index.add(vectors)
                D, I = index.search(vectors[:1], 1)
                
                return "healthy", f"FAISS {version} functional", {"version": version, "index_test": "ok"}
            except ImportError:
                return "failed", "FAISS not installed", {}
            except Exception as e:
                return "degraded", f"FAISS installed but test failed: {e}", {}
        
        return self._timed_check("faiss", _check)
    
    def check_four_layer_memory(self):
        """检查四层记忆管理器读写"""
        def _check():
            try:
                from core.memory_manager_v2 import FourLayerMemoryManager
                mm = FourLayerMemoryManager(db_dir=str(self.db_dir))
                
                # 测试写入
                test_key = f"health_check_{int(time.time())}"
                ok = mm.write("L0", test_key, {"check": True}, {"source": "health_probe"})
                if not ok:
                    return "failed", "L0 write failed", {}
                
                # 测试读取
                result = mm.read("L0", test_key)
                if result is None:
                    return "failed", "L0 read failed", {}
                
                # 清理
                with sqlite3.connect(str(self.db_dir / "kaelis_dev.db")) as conn:
                    conn.execute("DELETE FROM memory_l0 WHERE key = ?", (test_key,))
                
                    stats = mm.stats()
                    return "healthy", "FourLayerMemoryManager read/write OK", stats
            except ImportError:
                return "failed", "FourLayerMemoryManager not importable", {}
            except Exception as e:
                return "failed", f"FourLayerMemoryManager check failed: {e}", {}
        
        return self._timed_check("four_layer_memory", _check)
    
    def check_llm_connectivity(self):
        """检查 LLM API 连通性"""
        def _check():
            try:
                import os
                import urllib.request
                api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return "degraded", "No API key configured", {}
                
                base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
                req = urllib.request.Request(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    method="GET"
                )
                # 短超时，仅确认网络可达
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        return "healthy", "LLM API reachable", {"provider": "deepseek"}
                    else:
                        return "degraded", f"LLM API returned {resp.status}", {}
            except Exception as e:
                return "degraded", f"LLM API check failed: {e}", {}
        
        return self._timed_check("llm", _check)


def run_startup_health_check(db_dir: str = "data", log_path: Optional[str] = None) -> Dict[str, Any]:
    """
    启动时健康检查入口
    
    返回报告并可选写入日志文件。
    """
    probe = MemoryHealthProbe(db_dir=db_dir)
    report = probe.run_all_checks()
    
    if log_path:
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to write health log: {e}")
    
    # 输出摘要到日志
    summary = report["summary"]
    logger.info(
        f"Startup health check: {report['overall']} "
        f"(H:{summary['healthy']} D:{summary['degraded']} F:{summary['failed']})"
    )
    
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 记忆健康探针测试 ===")
    report = run_startup_health_check()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    overall = report["overall"]
    if overall == "healthy":
        print("\n[OK] All memory subsystems healthy")
    elif overall == "degraded":
        print("\n[NG] Some subsystems degraded")
    else:
        print("\n[NG] Critical failures detected")
