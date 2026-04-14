#!/usr/bin/env python3
"""
Kaelis 韧性上下文 (Resilience Context)
提供系统环境的"韧性快照"，融合内部认知信号与外部环境信号
"""
import os
import sys
import psutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class ResilienceSnapshot:
    """韧性快照"""
    timestamp: str
    system: Dict[str, Any]  # CPU, 内存, 磁盘
    services: Dict[str, Any]  # Neo4j, Python, 等依赖服务
    cognitive: Dict[str, Any]  # 认知负载状态
    overall_health: str  # healthy, degraded, critical
    confidence: float  # 快照置信度 0-1

class ResilienceContext:
    """韧性上下文管理器"""
    
    def __init__(self):
        self.snapshot_history = []
        self.max_history = 100
    
    def capture(self) -> ResilienceSnapshot:
        """捕获当前韧性快照"""
        # 系统资源
        system = self._capture_system()
        
        # 服务健康
        services = self._capture_services()
        
        # 认知负载
        cognitive = self._capture_cognitive()
        
        # 整体健康评估
        overall_health = self._assess_health(system, services, cognitive)
        
        # 快照置信度（基于数据完整性）
        confidence = self._calculate_confidence(system, services)
        
        snapshot = ResilienceSnapshot(
            timestamp=datetime.now().isoformat(),
            system=system,
            services=services,
            cognitive=cognitive,
            overall_health=overall_health,
            confidence=confidence
        )
        
        # 保存历史
        self.snapshot_history.append(asdict(snapshot))
        if len(self.snapshot_history) > self.max_history:
            self.snapshot_history.pop(0)
        
        return snapshot
    
    def _capture_system(self) -> Dict[str, Any]:
        """捕获系统资源状态"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
                "network_io": psutil.net_io_counters()._asdict() if hasattr(psutil.net_io_counters(), '_asdict') else str(psutil.net_io_counters()),
                "status": "healthy" if psutil.cpu_percent(interval=0.1) < 80 else "stressed"
            }
        except Exception as e:
            return {"error": str(e), "status": "unknown"}
    
    def _capture_services(self) -> Dict[str, Any]:
        """捕获关键服务状态"""
        services = {}
        
        # Neo4j 状态
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=neo4j", "--format", "{{.Status}}"],
                capture_output=True, text=True, timeout=5
            )
            services["neo4j"] = {
                "running": "Up" in result.stdout,
                "status": "healthy" if "Up" in result.stdout else "down",
                "response_time_ms": self._check_neo4j_response()
            }
        except Exception as e:
            services["neo4j"] = {"running": False, "status": "unknown", "error": str(e)}
        
        # Python 环境
        try:
            services["python"] = {
                "version": sys.version,
                "executable": sys.executable,
                "status": "healthy"
            }
        except Exception as e:
            services["python"] = {"status": "error", "error": str(e)}
        
        # 文件系统可写性
        try:
            test_file = Path(".resilience_test")
            test_file.write_text("test")
            test_file.unlink()
            services["filesystem"] = {"writable": True, "status": "healthy"}
        except Exception as e:
            services["filesystem"] = {"writable": False, "status": "error", "error": str(e)}
        
        return services
    
    def _check_neo4j_response(self) -> Optional[int]:
        """检查 Neo4j 响应时间"""
        try:
            import time
            start = time.time()
            result = subprocess.run(
                ["docker", "exec", "neo4j", "cypher-shell", "-u", "neo4j", "-p", "password", "RETURN 1"],
                capture_output=True, timeout=5
            )
            elapsed = int((time.time() - start) * 1000)
            return elapsed if result.returncode == 0 else None
        except:
            return None
    
    def _capture_cognitive(self) -> Dict[str, Any]:
        """捕获认知负载状态"""
        # 基于遥测数据分析认知状态
        try:
            telemetry_file = Path(".kaelis-telemetry.jsonl")
            if not telemetry_file.exists():
                return {"status": "no_data"}
            
            # 读取最近的事件
            recent_events = []
            with open(telemetry_file, "r") as f:
                lines = f.readlines()[-100:]  # 最近100条
                for line in lines:
                    try:
                        event = json.loads(line.strip())
                        recent_events.append(event)
                    except:
                        continue
            
            # 分析认知指标
            error_count = sum(1 for e in recent_events if "error" in e.get("event", ""))
            recovery_count = sum(1 for e in recent_events if "heal" in e.get("event", ""))
            
            # 计算认知压力指数
            cognitive_load = min(error_count / 10, 1.0)  # 0-1
            
            return {
                "recent_events": len(recent_events),
                "error_count": error_count,
                "recovery_count": recovery_count,
                "cognitive_load": cognitive_load,
                "status": "stressed" if cognitive_load > 0.5 else "healthy"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _assess_health(self, system: Dict, services: Dict, cognitive: Dict) -> str:
        """评估整体健康状态"""
        issues = 0
        
        # 系统问题
        if system.get("cpu_percent", 0) > 90:
            issues += 2
        elif system.get("cpu_percent", 0) > 70:
            issues += 1
        
        if system.get("memory_percent", 0) > 90:
            issues += 2
        elif system.get("memory_percent", 0) > 80:
            issues += 1
        
        # 服务问题
        for svc, status in services.items():
            if isinstance(status, dict) and status.get("status") != "healthy":
                issues += 1
        
        # 认知问题
        if cognitive.get("cognitive_load", 0) > 0.7:
            issues += 2
        elif cognitive.get("cognitive_load", 0) > 0.4:
            issues += 1
        
        if issues >= 4:
            return "critical"
        elif issues >= 2:
            return "degraded"
        else:
            return "healthy"
    
    def _calculate_confidence(self, system: Dict, services: Dict) -> float:
        """计算快照置信度"""
        confidence = 1.0
        
        # 系统数据完整性
        if "error" in system:
            confidence -= 0.3
        
        # 服务检查完整性
        for svc, status in services.items():
            if isinstance(status, dict) and "error" in status:
                confidence -= 0.1
        
        return max(confidence, 0.0)
    
    def get_trend(self, metric: str, minutes: int = 5) -> Dict[str, Any]:
        """获取指标趋势"""
        cutoff = datetime.now().timestamp() - (minutes * 60)
        relevant = [
            s for s in self.snapshot_history
            if datetime.fromisoformat(s["timestamp"]).timestamp() > cutoff
        ]
        
        if not relevant:
            return {"trend": "unknown", "data_points": 0}
        
        # 简化趋势分析
        values = []
        for s in relevant:
            if metric == "cpu":
                values.append(s["system"].get("cpu_percent", 0))
            elif metric == "memory":
                values.append(s["system"].get("memory_percent", 0))
        
        if len(values) < 2:
            return {"trend": "insufficient_data", "data_points": len(values)}
        
        # 简单线性趋势
        first_half = sum(values[:len(values)//2]) / max(len(values)//2, 1)
        second_half = sum(values[len(values)//2:]) / max(len(values) - len(values)//2, 1)
        
        if second_half > first_half * 1.2:
            trend = "increasing"
        elif second_half < first_half * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "current": values[-1],
            "average": sum(values) / len(values),
            "data_points": len(values)
        }
    
    def should_intervene(self) -> tuple[bool, str]:
        """判断是否需要系统干预"""
        snapshot = self.capture()
        
        if snapshot.overall_health == "critical":
            return True, "critical_health"
        
        if snapshot.overall_health == "degraded":
            # 检查趋势
            cpu_trend = self.get_trend("cpu")
            if cpu_trend.get("trend") == "increasing":
                return True, "degrading_trend"
        
        return False, "healthy"


# 全局实例
_resilience_context = None

def get_resilience_context() -> ResilienceContext:
    """获取全局韧性上下文实例"""
    global _resilience_context
    if _resilience_context is None:
        _resilience_context = ResilienceContext()
    return _resilience_context


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Resilience Context")
    parser.add_argument("--capture", action="store_true", help="Capture snapshot")
    parser.add_argument("--trend", help="Get trend for metric (cpu/memory)")
    parser.add_argument("--check", action="store_true", help="Check if intervention needed")
    args = parser.parse_args()
    
    ctx = get_resilience_context()
    
    if args.capture:
        snapshot = ctx.capture()
        print(json.dumps(asdict(snapshot), indent=2, default=str))
    
    elif args.trend:
        trend = ctx.get_trend(args.trend)
        print(json.dumps(trend, indent=2))
    
    elif args.check:
        should, reason = ctx.should_intervene()
        print(f"Intervention needed: {should}")
        print(f"Reason: {reason}")
    
    else:
        # 默认输出当前状态
        snapshot = ctx.capture()
        print(f"Overall Health: {snapshot.overall_health}")
        print(f"Confidence: {snapshot.confidence:.1%}")
        print(f"System: CPU {snapshot.system.get('cpu_percent', 'N/A')}%, "
              f"Memory {snapshot.system.get('memory_percent', 'N/A')}%")
        services_str = ", ".join([f"{k}={v.get('status', 'unknown')}" for k, v in snapshot.services.items()])
        print(f"Services: {services_str}")
