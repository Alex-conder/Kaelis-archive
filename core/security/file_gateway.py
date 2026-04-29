"""
文件操作安全网关 — FileGateway

三层审计管道：规则引擎 -> LLM评估 -> 用户确认
所有核心模块的文件操作必须通过此网关。
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.security.risk_gateway import ApprovalService, RiskDecision

logger = logging.getLogger(__name__)

# 危险操作黑名单
DANGEROUS_OPERATIONS = {"delete", "rm", "rmdir", "chmod", "chown", "mv", "move", "replace"}

# 受保护目录（不允许操作）
PROTECTED_PATHS = {
    "/", "C:\\", "C:/", "/usr", "/bin", "/sbin", "/lib", "/lib64",
    "/etc", "/sys", "/proc", "/dev", "/boot", "/var/log",
    os.path.expanduser("~/.ssh"), os.path.expanduser("~/.gnupg"),
    os.path.expanduser("~/AppData/Roaming"),
}

# 危险文件扩展名
DANGEROUS_EXTENSIONS = {".exe", ".dll", ".so", ".dylib", ".sys", ".bat", ".cmd", ".sh"}

# 允许操作的文件类型
ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".html", ".css"}


class FileOperationType(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    RENAME = "rename"
    COPY = "copy"
    LIST = "list"


@dataclass
class FileOperationRequest:
    """标准化文件操作请求"""
    source: str                          # 请求来源模块/Agent
    operation: FileOperationType         # 操作类型
    file_path: str                       # 目标文件路径
    content: Optional[str] = None        # 写入内容（可选）
    destination: Optional[str] = None    # 重命名/复制目标（可选）
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileOperationResult:
    """文件操作结果"""
    approved: bool
    decision: RiskDecision
    reason: str
    approval_id: Optional[str] = None
    executed: bool = False
    result: Any = None


class FileGateway:
    """
    文件操作安全网关。

    三层审计管道：
    1. 规则引擎（静态规则匹配）
    2. LLM评估（启发式风险评分）
    3. 用户确认（高风险操作需人工审批）
    """

    def __init__(self):
        self.approval_service = ApprovalService(default_timeout=300)
        self._audit_log: List[Dict] = []
        self.allowed_directories: List[str] = []  # 白名单目录

    # ------------------------------------------------------------------ #
    # 第一层：规则引擎
    # ------------------------------------------------------------------ #

    def _rule_engine(self, req: FileOperationRequest) -> tuple:
        """
        规则引擎评估。
        返回 (decision, reason) 或 (None, None) 表示需要进入下一层。
        """
        path = Path(req.file_path).resolve()

        # 1. 路径规范化检查（防止路径遍历）
        try:
            path.resolve()
        except Exception:
            return (RiskDecision.BLOCK, "非法路径格式")

        # 2. 受保护目录检查
        for protected in PROTECTED_PATHS:
            try:
                if path == Path(protected).resolve() or path.is_relative_to(Path(protected).resolve()):
                    return (RiskDecision.BLOCK, f"路径受保护: {protected}")
            except Exception:
                continue

        # 3. 危险操作检查
        op_name = req.operation.value
        if op_name in DANGEROUS_OPERATIONS:
            return (RiskDecision.CONFIRM, f"{op_name} 属于高危操作，需人工确认")

        # 4. 危险扩展名检查
        if path.suffix.lower() in DANGEROUS_EXTENSIONS:
            return (RiskDecision.BLOCK, f"危险文件类型: {path.suffix}")

        # 5. 允许扩展名白名单（write/delete 时更严格）
        if req.operation in (FileOperationType.WRITE, FileOperationType.DELETE):
            if path.suffix.lower() not in ALLOWED_EXTENSIONS and path.suffix != "":
                return (RiskDecision.CONFIRM, f"非标准文件类型操作: {path.suffix}")

        # 规则引擎通过，进入下一层
        return (None, None)

    # ------------------------------------------------------------------ #
    # 第二层：LLM评估（启发式，无需真实LLM）
    # ------------------------------------------------------------------ #

    def _llm_review(self, req: FileOperationRequest) -> tuple:
        """
        启发式风险评估。
        返回 (decision, reason)。
        """
        op = req.operation.value
        path_str = req.file_path.lower()

        # 删除大文件（> 10MB）需要确认
        if req.operation == FileOperationType.DELETE:
            try:
                size = Path(req.file_path).stat().st_size
                if size > 10 * 1024 * 1024:
                    return (RiskDecision.CONFIRM, f"删除大文件 ({size / 1024 / 1024:.1f} MB)，需确认")
            except Exception:
                pass

        # 批量删除（通配符）
        if "*" in req.file_path or "?" in req.file_path:
            return (RiskDecision.CONFIRM, "通配符操作可能影响多个文件")

        # 覆盖已有文件
        if req.operation == FileOperationType.WRITE and Path(req.file_path).exists():
            return (RiskDecision.CONFIRM, "覆盖已有文件")

        # 敏感关键词
        sensitive_keywords = ["password", "secret", "token", "key", "credential", "vault"]
        if any(kw in path_str for kw in sensitive_keywords):
            return (RiskDecision.CONFIRM, "路径包含敏感关键词")

        # 默认允许
        return (RiskDecision.ALLOW, "通过启发式评估")

    # ------------------------------------------------------------------ #
    # 第三层：用户确认
    # ------------------------------------------------------------------ #

    def _request_user_confirmation(self, req: FileOperationRequest, reason: str) -> str:
        """提交审批请求，返回 approval_id"""
        pa = self.approval_service.request_approval(
            agent_id=req.source,
            operation=f"{req.operation.value}:{req.file_path}",
            context={
                "source": req.source,
                "operation": req.operation.value,
                "file_path": req.file_path,
                "reason": reason,
                "content_preview": req.content[:200] if req.content else None,
            },
        )
        return pa.approval_id

    # ------------------------------------------------------------------ #
    # 公开 API
    # ------------------------------------------------------------------ #

    def evaluate(self, req: FileOperationRequest) -> FileOperationResult:
        """
        评估文件操作请求，返回审批结果。
        调用方需根据 result.approved 决定是否执行实际操作。
        """
        # 0.5 层：目录白名单检查（非只写操作）
        whitelist_result = self._check_directory_whitelist(req.file_path, req.operation)
        if whitelist_result:
            decision, reason = whitelist_result
        else:
            # 第一层：规则引擎
            decision, reason = self._rule_engine(req)

            # 第二层：LLM评估（规则引擎未决时）
            if decision is None:
                decision, reason = self._llm_review(req)

        # 第三层：用户确认（CONFIRM 决策）
        approval_id = None
        if decision == RiskDecision.CONFIRM:
            approval_id = self._request_user_confirmation(req, reason)
            self._audit_log.append({
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "source": req.source,
                "operation": req.operation.value,
                "file_path": req.file_path,
                "decision": decision.value,
                "reason": reason,
                "approval_id": approval_id,
                "status": "pending",
            })
            return FileOperationResult(
                approved=False,
                decision=decision,
                reason=reason,
                approval_id=approval_id,
            )

        # BLOCK 直接拒绝
        if decision == RiskDecision.BLOCK:
            self._audit_log.append({
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "source": req.source,
                "operation": req.operation.value,
                "file_path": req.file_path,
                "decision": decision.value,
                "reason": reason,
                "status": "blocked",
            })
            return FileOperationResult(
                approved=False,
                decision=decision,
                reason=reason,
            )

        # ALLOW 直接通过
        self._audit_log.append({
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "source": req.source,
            "operation": req.operation.value,
            "file_path": req.file_path,
            "decision": decision.value,
            "reason": reason,
            "status": "allowed",
        })
        return FileOperationResult(
            approved=True,
            decision=decision,
            reason=reason,
        )

    def resolve(self, approval_id: str, resolution: str) -> bool:
        """解析审批请求（approved / rejected）"""
        ok = self.approval_service.resolve_approval(approval_id, resolution)
        if ok:
            for entry in self._audit_log:
                if entry.get("approval_id") == approval_id:
                    entry["status"] = resolution
        return ok

    def get_pending(self) -> List[Dict]:
        """获取所有待审批的文件操作"""
        pending = self.approval_service.get_pending()
        return [
            {
                "approval_id": p.approval_id,
                "source": p.context.get("source"),
                "operation": p.context.get("operation"),
                "file_path": p.context.get("file_path"),
                "reason": p.context.get("reason"),
                "status": p.status,
            }
            for p in pending
        ]

    def audit_log(self) -> List[Dict]:
        """返回完整审计日志"""
        return list(self._audit_log)

    # ------------------------------------------------------------------ #
    # 目录白名单管理
    # ------------------------------------------------------------------ #

    def add_allowed_directory(self, path: str) -> bool:
        """添加授权目录"""
        resolved = Path(path).resolve().as_posix()
        if resolved not in self.allowed_directories:
            self.allowed_directories.append(resolved)
        return True

    def remove_allowed_directory(self, path: str) -> bool:
        """移除授权目录"""
        resolved = Path(path).resolve().as_posix()
        if resolved in self.allowed_directories:
            self.allowed_directories.remove(resolved)
            return True
        return False

    def _check_directory_whitelist(self, file_path: str, operation: FileOperationType) -> Optional[tuple]:
        """检查目录白名单权限。返回 (decision, reason) 或 None"""
        if operation == FileOperationType.READ:
            return None  # 读取操作不受白名单限制
        if not self.allowed_directories:
            return None  # 未设置白名单时不限制

        target = Path(file_path).resolve().as_posix()
        for allowed in self.allowed_directories:
            if target == allowed or target.startswith(allowed + "/"):
                return None
        return (RiskDecision.BLOCK, f"路径不在授权目录白名单内: {file_path}")

    # ------------------------------------------------------------------ #
    # 便捷方法：封装常用文件操作
    # ------------------------------------------------------------------ #

    def read_file(self, source: str, file_path: str) -> FileOperationResult:
        req = FileOperationRequest(source=source, operation=FileOperationType.READ, file_path=file_path)
        return self.evaluate(req)

    def write_file(self, source: str, file_path: str, content: str) -> FileOperationResult:
        req = FileOperationRequest(source=source, operation=FileOperationType.WRITE, file_path=file_path, content=content)
        return self.evaluate(req)

    def delete_file(self, source: str, file_path: str) -> FileOperationResult:
        req = FileOperationRequest(source=source, operation=FileOperationType.DELETE, file_path=file_path)
        return self.evaluate(req)
