#!/usr/bin/env python3
"""
Kaelis Phase 8 - Runtime API Service
运行时确定性基础设施 - 提供 gRPC/HTTP 接口供外部系统调用

核心能力：
1. ValidateCode - 代码实时校验
2. ValidateEnvironment - 环境契约校验
3. CheckSLO - SLO 运行时校验
4. Health/Metrics - 健康检查和监控指标
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# 尝试导入 FastAPI
try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("[WARN] FastAPI not installed. Using Flask fallback.")
    from flask import Flask, jsonify, request

# 导入现有校验逻辑
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

try:
    from guard_rules import GuardRuleEngine
    GUARD_AVAILABLE = True
except ImportError:
    GUARD_AVAILABLE = False

try:
    from env_contract import EnvironmentContractEngine
    ENV_AVAILABLE = True
except ImportError:
    ENV_AVAILABLE = False

PROJECT_ROOT = Path(__file__).parent.parent.parent

# ============================================================================
# Pydantic 模型定义
# ============================================================================

if FASTAPI_AVAILABLE:
    class FileContext(BaseModel):
        uri: str
        language: str = "python"
        project_path: Optional[str] = None

    class ValidationRequest(BaseModel):
        code: str
        context: FileContext

    class ValidationResult(BaseModel):
        valid: bool
        violations: List[Dict[str, Any]]
        checked_at: str

    class EnvironmentReport(BaseModel):
        overall_score: float
        layer_scores: Dict[str, float]
        issues: List[Dict[str, Any]]
        checked_at: str

    class SLOStatus(BaseModel):
        service: str
        target_availability: float
        actual_availability: float
        target_latency_p95: int
        actual_latency_p95: int
        compliant: bool
        checked_at: str

    class HealthStatus(BaseModel):
        status: str
        version: str
        uptime_seconds: float
        checks: Dict[str, bool]

# ============================================================================
# 运行时服务核心
# ============================================================================

class KaelisRuntimeService:
    """Kaelis 运行时服务核心"""
    
    def __init__(self):
        self.start_time = time.time()
        self.version = "8.0.0"
        self.guard_engine = GuardRuleEngine() if GUARD_AVAILABLE else None
        self.env_engine = EnvironmentContractEngine() if ENV_AVAILABLE else None
    
    def validate_code(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """校验代码是否符合契约"""
        if not self.guard_engine:
            return {
                "valid": False,
                "violations": [{"error": "Guard engine not available"}],
                "checked_at": datetime.now().isoformat()
            }
        
        violations = self.guard_engine.check(code, context)
        
        return {
            "valid": len(violations) == 0,
            "violations": [
                {
                    "level": v.level,
                    "rule": v.rule,
                    "message": v.message,
                    "suggestion": v.suggestion,
                    "line": v.line,
                    "column": v.column
                }
                for v in violations
            ],
            "checked_at": datetime.now().isoformat()
        }
    
    def validate_environment(self) -> Dict[str, Any]:
        """校验环境是否符合契约"""
        if not self.env_engine:
            return {
                "overall_score": 0.0,
                "layer_scores": {},
                "issues": [{"error": "Environment engine not available"}],
                "checked_at": datetime.now().isoformat()
            }
        
        report = self.env_engine.verify_all()
        summary = report.get('summary', {})
        
        return {
            "overall_score": summary.get('overall_score', 0),
            "layer_scores": summary.get('layer_scores', {}),
            "issues": [
                {
                    "layer": r.get('layer'),
                    "check": r.get('check'),
                    "status": r.get('status'),
                    "message": r.get('message')
                }
                for r in report.get('results', [])
                if r.get('status') != 'pass'
            ],
            "checked_at": report.get('timestamp')
        }
    
    def check_slo(self, service: str) -> Dict[str, Any]:
        """检查 SLO 达标情况（模拟/从 Prometheus 拉取）"""
        # 从 slo.yaml 读取目标
        slo_path = PROJECT_ROOT / "config" / "slo.yaml"
        targets = self._load_slo_targets(slo_path, service)
        
        # 模拟从 Prometheus 拉取实际指标
        # 实际实现应调用 Prometheus API
        actual = self._query_metrics(service)
        
        compliant = (
            actual['availability'] >= targets.get('availability', 0.99) and
            actual['latency_p95'] <= targets.get('latency_p95', 1000)
        )
        
        return {
            "service": service,
            "target_availability": targets.get('availability', 0.99),
            "actual_availability": actual['availability'],
            "target_latency_p95": targets.get('latency_p95', 1000),
            "actual_latency_p95": actual['latency_p95'],
            "compliant": compliant,
            "checked_at": datetime.now().isoformat()
        }
    
    def _load_slo_targets(self, slo_path: Path, service: str) -> Dict[str, Any]:
        """加载 SLO 目标"""
        if not slo_path.exists():
            return {"availability": 0.99, "latency_p95": 1000}
        
        try:
            import yaml
            slo = yaml.safe_load(slo_path.read_text(encoding='utf-8'))
            for obj in slo.get('spec', {}).get('objectives', []):
                if obj.get('name') == service:
                    return {
                        "availability": obj.get('indicators', {}).get('availability', {}).get('target', 0.99),
                        "latency_p95": int(obj.get('indicators', {}).get('latency', {}).get('p95', {}).get('target', '1000ms').replace('ms', ''))
                    }
        except:
            pass
        
        return {"availability": 0.99, "latency_p95": 1000}
    
    def _query_metrics(self, service: str) -> Dict[str, float]:
        """查询实际指标（模拟）"""
        # 实际实现应调用 Prometheus API
        # 这里返回模拟数据
        import random
        return {
            "availability": random.uniform(0.98, 0.999),
            "latency_p95": random.randint(50, 2000)
        }
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        uptime = time.time() - self.start_time
        
        return {
            "status": "healthy",
            "version": self.version,
            "uptime_seconds": int(uptime),
            "checks": {
                "guard_engine": self.guard_engine is not None,
                "env_engine": self.env_engine is not None
            }
        }

# ============================================================================
# FastAPI 应用
# ============================================================================

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Kaelis Runtime API",
        description="运行时确定性基础设施",
        version="8.0.0"
    )
    service = KaelisRuntimeService()
    
    @app.post("/v1/validate/code", response_model=ValidationResult)
    async def validate_code_endpoint(request: ValidationRequest):
        """校验代码是否符合契约"""
        result = service.validate_code(request.code, request.context.dict())
        return ValidationResult(**result)
    
    @app.get("/v1/validate/environment", response_model=EnvironmentReport)
    async def validate_environment_endpoint():
        """校验环境是否符合契约"""
        result = service.validate_environment()
        return EnvironmentReport(**result)
    
    @app.get("/v1/slo/{service}", response_model=SLOStatus)
    async def check_slo_endpoint(service_name: str):
        """检查 SLO 达标情况"""
        result = service.check_slo(service_name)
        return SLOStatus(**result)
    
    @app.get("/health", response_model=HealthStatus)
    async def health_endpoint():
        """健康检查"""
        result = service.health_check()
        return HealthStatus(**result)
    
    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus 指标"""
        # 返回模拟的 Prometheus 格式指标
        metrics = f"""
# HELP kaelis_runtime_uptime_seconds Service uptime
# TYPE kaelis_runtime_uptime_seconds counter
kaelis_runtime_uptime_seconds {time.time() - service.start_time}

# HELP kaelis_runtime_health_check Health check status
# TYPE kaelis_runtime_health_check gauge
kaelis_runtime_health_check{{check="guard_engine"}} {1 if service.guard_engine else 0}
kaelis_runtime_health_check{{check="env_engine"}} {1 if service.env_engine else 0}
"""
        return metrics

else:
    # Flask 回退实现
    app = Flask(__name__)
    service = KaelisRuntimeService()
    
    @app.route('/v1/validate/code', methods=['POST'])
    def validate_code_endpoint():
        data = request.json
        result = service.validate_code(data.get('code', ''), data.get('context', {}))
        return jsonify(result)
    
    @app.route('/v1/validate/environment', methods=['GET'])
    def validate_environment_endpoint():
        result = service.validate_environment()
        return jsonify(result)
    
    @app.route('/v1/slo/<service_name>', methods=['GET'])
    def check_slo_endpoint(service_name):
        result = service.check_slo(service_name)
        return jsonify(result)
    
    @app.route('/health', methods=['GET'])
    def health_endpoint():
        result = service.health_check()
        return jsonify(result)
    
    @app.route('/metrics', methods=['GET'])
    def metrics_endpoint():
        metrics = f"""
# HELP kaelis_runtime_uptime_seconds Service uptime
kaelis_runtime_uptime_seconds {time.time() - service.start_time}
"""
        return metrics

# ============================================================================
# 主入口
# ============================================================================

def main():
    """启动 Runtime API 服务"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kaelis Runtime API Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host address')
    parser.add_argument('--port', type=int, default=5001, help='Port number')
    parser.add_argument('--reload', action='store_true', help='Auto-reload (dev mode)')
    
    args = parser.parse_args()
    
    print(f"🚀 Kaelis Runtime API v8.0.0")
    print(f"   Mode: {'FastAPI' if FASTAPI_AVAILABLE else 'Flask'}")
    print(f"   Address: http://{args.host}:{args.port}")
    print(f"   Endpoints:")
    print(f"     POST /v1/validate/code")
    print(f"     GET  /v1/validate/environment")
    print(f"     GET  /v1/slo/{{service}}")
    print(f"     GET  /health")
    print(f"     GET  /metrics")
    
    if FASTAPI_AVAILABLE:
        import uvicorn
        uvicorn.run(
            "services.kaelis_runtime.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload
        )
    else:
        app.run(host=args.host, port=args.port, debug=args.reload)

if __name__ == '__main__':
    main()
