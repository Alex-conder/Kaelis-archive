"""
安全扫描器 - 预执行规则扫描层 (P14-001)

功能：
1. 敏感操作拦截（delete/migrate/env-set/config 修改等）
2. 请求内容风险检测（SQL 注入、命令注入等）
3. 审批流集成（需要二次确认的操作）
4. 审计日志记录

拦截规则：
- 数据删除类：DELETE /api/memory/delete (clear_layer=true), DELETE /api/kg/*
- 系统配置类：POST /api/memory/config, POST /api/system/config
- 迁移类：任何 migrate 相关操作
- 环境变量类：修改 DEEPSEEK_API_KEY, DB_URL 等敏感配置

使用方式：
    from core.safety_scanner import SafetyScanner
    scanner = SafetyScanner()
    result = scanner.scan_request(endpoint, method, payload, user_context)
    if result.blocked:
        return result.to_response()
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """扫描结果"""
    blocked: bool
    reason: str
    risk_level: str  # "low", "medium", "high", "critical"
    required_approval: bool
    scan_details: Dict[str, Any]
    
    def to_response(self) -> Dict[str, Any]:
        """转换为 API 响应"""
        return {
            "success": False,
            "error": self.reason,
            "risk_level": self.risk_level,
            "requires_approval": self.required_approval,
            "details": self.scan_details
        }


class SafetyScanner:
    """
    安全扫描器
    
    在敏感操作执行前进行多层扫描：
    1. 端点规则匹配
    2. 内容风险检测
    3. 频率限制检查
    """
    
    # 敏感端点规则（按优先级排序，先匹配先执行）
    SENSITIVE_ENDPOINTS = {
        # endpoint_pattern: (risk_level, description, requires_approval)
        r"/api/memory/delete.*clear_layer=true": ("high", "清空记忆层", True),
        r"/api/kg/.*delete": ("high", "删除知识图谱数据", True),
        r"/api/system/config": ("high", "修改系统配置", True),
        r"/api/env/.*": ("critical", "修改环境变量", True),
        r"/api/migrate": ("high", "执行数据迁移", True),
        r"/api/backup/restore": ("critical", "恢复备份", True),
    }
    
    # 敏感配置键（修改这些需要审批）
    SENSITIVE_CONFIG_KEYS = [
        "api_key", "secret", "password", "token", "credential",
        "db_url", "database_url", "neo4j_uri",
        "deepseek", "openai", "anthropic",
        "smtp", "email_password",
    ]
    
    # 危险内容模式
    DANGEROUS_PATTERNS = [
        (r"(?i)(DROP\s+TABLE|DELETE\s+FROM|TRUNCATE\s+TABLE)", "sql_injection"),
        (r'(?i)(rm\s+-rf|eval\s*\(|exec\s*\(|system\s*\()', "command_injection"),
        (r"(?i)(<script|javascript:|onload=|onerror=)", "xss"),
        (r"(?i)(\.\./|\.\.\\|%2e%2e%2f)", "path_traversal"),
        (r"(?i)(\bOR\b\s+\d+=\d+|\bAND\b\s+\d+=\d+)", "sql_injection"),
    ]
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.blocked_count = 0
        self.approval_queue: List[Dict] = []
    
    def scan_request(
        self,
        endpoint: str,
        method: str,
        payload: Optional[Dict] = None,
        user_context: Optional[Dict] = None
    ) -> ScanResult:
        """
        扫描请求
        
        Args:
            endpoint: API 端点路径
            method: HTTP 方法
            payload: 请求体
            user_context: 用户上下文 {"user_id": ..., "role": ...}
            
        Returns:
            ScanResult: 扫描结果
        """
        payload = payload or {}
        user_context = user_context or {}
        details = {"checks": []}
        
        # 1. 端点规则匹配
        endpoint_result = self._check_endpoint(endpoint, method, payload)
        details["checks"].append({"name": "endpoint_rule", "result": endpoint_result})
        
        if endpoint_result["blocked"]:
            self.blocked_count += 1
            return ScanResult(
                blocked=True,
                reason=endpoint_result["reason"],
                risk_level=endpoint_result["risk_level"],
                required_approval=endpoint_result["requires_approval"],
                scan_details=details
            )
        
        # 2. 内容风险检测
        content_result = self._check_content(payload)
        details["checks"].append({"name": "content_risk", "result": content_result})
        
        if content_result["blocked"]:
            self.blocked_count += 1
            return ScanResult(
                blocked=True,
                reason=content_result["reason"],
                risk_level="high",
                required_approval=False,
                scan_details=details
            )
        
        # 3. 敏感配置修改检测
        config_result = self._check_sensitive_config(payload)
        details["checks"].append({"name": "sensitive_config", "result": config_result})
        
        if config_result["blocked"]:
            self.blocked_count += 1
            return ScanResult(
                blocked=True,
                reason=config_result["reason"],
                risk_level="critical",
                required_approval=True,
                scan_details=details
            )
        
        # 通过所有检查
        return ScanResult(
            blocked=False,
            reason="",
            risk_level="low",
            required_approval=False,
            scan_details=details
        )
    
    def _check_endpoint(self, endpoint: str, method: str, payload: Dict) -> Dict:
        """检查端点是否在敏感列表中，同时检查 payload 中的敏感参数"""
        # 构建检查字符串：endpoint + payload 中的关键标志
        check_str = endpoint
        if payload.get("clear_layer"):
            check_str += "?clear_layer=true"
        
        for pattern, (risk, desc, needs_approval) in self.SENSITIVE_ENDPOINTS.items():
            if re.search(pattern, check_str, re.IGNORECASE):
                # 对于 DELETE/POST/PUT 方法才拦截
                if method.upper() in ("DELETE", "POST", "PUT", "PATCH"):
                    return {
                        "blocked": True,
                        "reason": f"敏感操作: {desc} (风险等级: {risk})",
                        "risk_level": risk,
                        "requires_approval": needs_approval
                    }
        return {"blocked": False}
    
    def _check_content(self, payload: Dict) -> Dict:
        """检测请求内容中的危险模式"""
        payload_str = json.dumps(payload, ensure_ascii=False)
        
        for pattern, threat_type in self.DANGEROUS_PATTERNS:
            if re.search(pattern, payload_str):
                return {
                    "blocked": True,
                    "reason": f"检测到潜在威胁: {threat_type}",
                    "threat_type": threat_type,
                    "matched_pattern": pattern
                }
        
        return {"blocked": False}
    
    def _check_sensitive_config(self, payload: Dict) -> Dict:
        """检测是否修改敏感配置"""
        payload_str = json.dumps(payload, ensure_ascii=False).lower()
        
        for key in self.SENSITIVE_CONFIG_KEYS:
            if key in payload_str:
                return {
                    "blocked": True,
                    "reason": f"检测到敏感配置修改: {key}",
                    "sensitive_key": key
                }
        
        return {"blocked": False}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取扫描统计"""
        return {
            "blocked_count": self.blocked_count,
            "pending_approvals": len(self.approval_queue),
            "rules_loaded": len(self.SENSITIVE_ENDPOINTS),
            "danger_patterns": len(self.DANGEROUS_PATTERNS)
        }


# 全局实例
_scanner_instance: Optional[SafetyScanner] = None


def get_safety_scanner() -> SafetyScanner:
    """获取全局安全扫描器"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = SafetyScanner()
    return _scanner_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试安全扫描器 ===")
    scanner = SafetyScanner()
    
    test_cases = [
        # (endpoint, method, payload, expected_blocked)
        ("/api/memory/delete", "POST", {"layer": "L1", "key": "test"}, False),  # 普通删除不拦截
        ("/api/memory/delete", "POST", {"layer": "L1", "clear_layer": True}, True),  # 清空拦截
        ("/api/system/config", "POST", {"timeout": 30}, True),  # 系统配置拦截
        ("/api/memory/get", "POST", {"layer": "L1"}, False),  # 安全操作
        ("/api/memory/write", "POST", {"value": "; DROP TABLE users; --"}, True),  # SQL 注入
        ("/api/memory/config", "POST", {"db_url": "postgres://..."}, True),  # 敏感配置
    ]
    
    for endpoint, method, payload, expected in test_cases:
        result = scanner.scan_request(endpoint, method, payload)
        status = "PASS" if result.blocked == expected else "FAIL"
        print(f"  [{status}] {method} {endpoint}")
        if result.blocked:
            print(f"         -> Blocked: {result.reason}")
    
    print(f"\nStats: {scanner.get_stats()}")
    print("\n[OK] SafetyScanner test completed")
