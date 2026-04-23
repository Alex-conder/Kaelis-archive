"""
Agent Permission Manager
=========================
管理 Agent 对系统资源（工具、记忆、共享空间）的权限。

集成点:
    - core/middleware.py: 在 before_request 中调用 check_request_permission
    - core/mcp/server.py: 在 MCP Tools 中调用 check_agent_permission
    - core/shared_memory_space.py: 底层权限检查委托（可选增强）

权限模型:
    - Agent 身份通过 request header `X-Agent-ID` 或环境变量识别
    - 每个 Agent 有一个 role: system, privileged, standard, restricted
    - 资源有 required_role: system, privileged, standard
    - Role hierarchy: system > privileged > standard > restricted

用法:
    from core.agent_permission_manager import get_agent_permission_manager
    pm = get_agent_permission_manager()
    ok = pm.check_agent_permission(agent_id="agent-1", resource="memory_write", action="write")
"""

import json
import logging
import os
import sqlite3
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = "data"

# ==============================================================================
# Enums & Constants
# ==============================================================================

class AgentRole(str, Enum):
    SYSTEM = "system"         # 系统级 Agent，无限制
    PRIVILEGED = "privileged" # 可信 Agent，可读写记忆、触发进化
    STANDARD = "standard"     # 普通 Agent，只读记忆、有限写入
    RESTRICTED = "restricted" # 受限 Agent，只能读取公开记忆


class ResourceAction(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


ROLE_HIERARCHY = {
    AgentRole.SYSTEM: 4,
    AgentRole.PRIVILEGED: 3,
    AgentRole.STANDARD: 2,
    AgentRole.RESTRICTED: 1,
}

# 默认权限矩阵: {resource: {action: min_role}}
DEFAULT_PERMISSION_MATRIX: Dict[str, Dict[str, AgentRole]] = {
    "memory_read": {
        ResourceAction.READ: AgentRole.RESTRICTED,
    },
    "memory_write": {
        ResourceAction.READ: AgentRole.RESTRICTED,
        ResourceAction.WRITE: AgentRole.STANDARD,
        ResourceAction.DELETE: AgentRole.PRIVILEGED,
    },
    "memory_search": {
        ResourceAction.READ: AgentRole.RESTRICTED,
    },
    "shared_memory": {
        ResourceAction.READ: AgentRole.RESTRICTED,
        ResourceAction.WRITE: AgentRole.STANDARD,
        ResourceAction.DELETE: AgentRole.PRIVILEGED,
        ResourceAction.ADMIN: AgentRole.PRIVILEGED,
    },
    "skill_read": {
        ResourceAction.READ: AgentRole.RESTRICTED,
    },
    "skill_execute": {
        ResourceAction.EXECUTE: AgentRole.STANDARD,
    },
    "evolution_trigger": {
        ResourceAction.EXECUTE: AgentRole.PRIVILEGED,
    },
    "system_config": {
        ResourceAction.READ: AgentRole.PRIVILEGED,
        ResourceAction.WRITE: AgentRole.SYSTEM,
    },
    "audit_log": {
        ResourceAction.READ: AgentRole.PRIVILEGED,
    },
}

# Agent ID 到角色的硬编码映射（生产环境应从数据库或配置服务读取）
DEFAULT_AGENT_ROLES: Dict[str, AgentRole] = {
    "kaelis-core": AgentRole.SYSTEM,
    "kaelis-self-evolve": AgentRole.PRIVILEGED,
    "kaelis-chat": AgentRole.STANDARD,
    "anonymous": AgentRole.RESTRICTED,
}


# ==============================================================================
# AgentPermissionManager
# ==============================================================================

class AgentPermissionManager:
    """
    Agent 权限管理器。

    支持:
        - 基于角色的权限检查
        - 动态权限矩阵配置
        - Agent 注册与角色分配
        - 请求审计日志
    """

    def __init__(self, db_dir: str = DEFAULT_DB_DIR):
        self.db_path = Path(db_dir) / "agent_permissions.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._matrix = {r: dict(a) for r, a in DEFAULT_PERMISSION_MATRIX.items()}
        self._agent_roles: Dict[str, AgentRole] = dict(DEFAULT_AGENT_ROLES)
        self._init_db()
        self._load_from_db()

    # ------------------------------------------------------------------ #
    # DB Initialization
    # ------------------------------------------------------------------ #

    def _init_db(self):
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agent_registry (
                    agent_id    TEXT PRIMARY KEY,
                    role        TEXT NOT NULL CHECK(role IN ('system','privileged','standard','restricted')),
                    name        TEXT,
                    description TEXT,
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL,
                    config      TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS permission_matrix (
                    resource    TEXT NOT NULL,
                    action      TEXT NOT NULL,
                    min_role    TEXT NOT NULL CHECK(min_role IN ('system','privileged','standard','restricted')),
                    updated_at  REAL NOT NULL,
                    PRIMARY KEY (resource, action)
                );

                CREATE TABLE IF NOT EXISTS permission_audit (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id    TEXT NOT NULL,
                    resource    TEXT NOT NULL,
                    action      TEXT NOT NULL,
                    granted     INTEGER NOT NULL,
                    reason      TEXT,
                    context     TEXT DEFAULT '{}',
                    timestamp   REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_agent ON permission_audit(agent_id);
                CREATE INDEX IF NOT EXISTS idx_audit_time ON permission_audit(timestamp);
            """)

    def _load_from_db(self):
        """从数据库加载 Agent 注册信息和权限矩阵。"""
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            # Load agent roles
            rows = conn.execute("SELECT agent_id, role FROM agent_registry").fetchall()
            for agent_id, role in rows:
                try:
                    self._agent_roles[agent_id] = AgentRole(role)
                except ValueError:
                    pass
            # Load permission matrix overrides
            rows = conn.execute("SELECT resource, action, min_role FROM permission_matrix").fetchall()
            for resource, action, min_role in rows:
                if resource not in self._matrix:
                    self._matrix[resource] = {}
                try:
                    self._matrix[resource][action] = AgentRole(min_role)
                except ValueError:
                    pass

    # ------------------------------------------------------------------ #
    # Core Permission API
    # ------------------------------------------------------------------ #

    def check_agent_permission(
        self,
        agent_id: str,
        resource: str,
        action: str = ResourceAction.READ,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        检查 Agent 是否有权限执行某操作。

        Args:
            agent_id: Agent 唯一标识
            resource: 资源名称（如 memory_write, shared_memory）
            action: 操作类型（read/write/delete/execute/admin）
            context: 可选上下文，用于审计

        Returns:
            bool: 是否允许
        """
        role = self._agent_roles.get(agent_id, AgentRole.RESTRICTED)
        role_level = ROLE_HIERARCHY.get(role, 0)

        # 查找资源-操作所需的最小角色
        resource_rules = self._matrix.get(resource, {})
        required_role = resource_rules.get(action)

        if required_role is None:
            # 未定义的规则：默认拒绝（安全优先）
            granted = False
            reason = f"No permission rule defined for {resource}/{action}"
        else:
            required_level = ROLE_HIERARCHY.get(required_role, 0)
            granted = role_level >= required_level
            reason = (
                f"Role {role.value} (level {role_level}) >= required {required_role.value} (level {required_level})"
                if granted
                else f"Role {role.value} (level {role_level}) < required {required_role.value} (level {required_level})"
            )

        # 记录审计日志（异步，不阻塞）
        try:
            self._log_audit(agent_id, resource, action, granted, reason, context)
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")

        return granted

    def require_permission(self, agent_id: str, resource: str, action: str = ResourceAction.READ):
        """权限检查的抛出异常版本。"""
        if not self.check_agent_permission(agent_id, resource, action):
            raise PermissionError(
                f"Agent '{agent_id}' lacks permission for {resource}/{action}"
            )

    # ------------------------------------------------------------------ #
    # Agent Registry
    # ------------------------------------------------------------------ #

    def register_agent(
        self,
        agent_id: str,
        role: AgentRole,
        name: str = "",
        description: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """注册或更新 Agent。"""
        now = time.time()
        self._agent_roles[agent_id] = role
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.execute(
                """
                INSERT INTO agent_registry (agent_id, role, name, description, created_at, updated_at, config)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    role = excluded.role,
                    name = excluded.name,
                    description = excluded.description,
                    updated_at = excluded.updated_at,
                    config = excluded.config
                """,
                (agent_id, role.value, name, description, now, now, json.dumps(config or {}, ensure_ascii=False)),
            )
        logger.info("Registered agent %s with role %s", agent_id, role.value)
        return {"agent_id": agent_id, "role": role.value, "updated_at": now}

    def get_agent_role(self, agent_id: str) -> AgentRole:
        """获取 Agent 的角色。"""
        return self._agent_roles.get(agent_id, AgentRole.RESTRICTED)

    def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有已注册 Agent。"""
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            rows = conn.execute(
                "SELECT agent_id, role, name, description, created_at, updated_at FROM agent_registry ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {
                "agent_id": r[0],
                "role": r[1],
                "name": r[2],
                "description": r[3],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Permission Matrix Management
    # ------------------------------------------------------------------ #

    def set_permission(self, resource: str, action: str, min_role: AgentRole) -> Dict[str, Any]:
        """设置某资源-操作的最小角色要求。"""
        now = time.time()
        if resource not in self._matrix:
            self._matrix[resource] = {}
        self._matrix[resource][action] = min_role
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.execute(
                """
                INSERT INTO permission_matrix (resource, action, min_role, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(resource, action) DO UPDATE SET
                    min_role = excluded.min_role,
                    updated_at = excluded.updated_at
                """,
                (resource, action, min_role.value, now),
            )
        return {"resource": resource, "action": action, "min_role": min_role.value}

    def get_permission_matrix(self) -> Dict[str, Dict[str, str]]:
        """获取当前权限矩阵。"""
        return {
            r: {a: role.value for a, role in actions.items()}
            for r, actions in self._matrix.items()
        }

    # ------------------------------------------------------------------ #
    # Request-level Integration (for Flask middleware)
    # ------------------------------------------------------------------ #

    def check_request_permission(self, request) -> Dict[str, Any]:
        """
        从 Flask request 对象中提取 Agent ID 并检查权限。
        供 middleware.py before_request 调用。
        """
        agent_id = self._extract_agent_id(request)
        # 根据请求路径推断资源类型
        path = request.path or ""
        method = request.method or "GET"

        resource, action = self._infer_resource_action(path, method)
        granted = self.check_agent_permission(agent_id, resource, action, context={"path": path, "method": method})

        return {
            "agent_id": agent_id,
            "resource": resource,
            "action": action,
            "granted": granted,
        }

    def _extract_agent_id(self, request) -> str:
        """从请求中提取 Agent ID。"""
        # 1. Header
        agent_id = request.headers.get("X-Agent-ID", "")
        if agent_id:
            return agent_id
        # 2. Query param
        agent_id = request.args.get("agent_id", "")
        if agent_id:
            return agent_id
        # 3. JSON body (for POST/PUT)
        try:
            data = request.get_json(silent=True) or {}
            agent_id = data.get("agent_id", "")
            if agent_id:
                return agent_id
        except Exception:
            pass
        # 4. 环境变量回退（服务端内部调用）
        agent_id = os.environ.get("KAELIS_AGENT_ID", "")
        if agent_id:
            return agent_id
        # 5. 默认 anonymous
        return "anonymous"

    def _infer_resource_action(self, path: str, method: str) -> Tuple[str, str]:
        """根据请求路径和方法推断资源和操作。"""
        path_lower = path.lower()
        if "/shared-memory" in path_lower:
            resource = "shared_memory"
        elif "/memory" in path_lower:
            resource = "memory_write" if method in ("POST", "PUT", "DELETE") else "memory_read"
        elif "/skill" in path_lower:
            resource = "skill_execute" if method == "POST" else "skill_read"
        elif "/evolve" in path_lower:
            resource = "evolution_trigger"
        elif "/system" in path_lower or "/config" in path_lower:
            resource = "system_config"
        else:
            resource = "memory_read"

        action_map = {
            "GET": ResourceAction.READ,
            "POST": ResourceAction.WRITE,
            "PUT": ResourceAction.WRITE,
            "DELETE": ResourceAction.DELETE,
            "PATCH": ResourceAction.WRITE,
        }
        action = action_map.get(method, ResourceAction.READ)
        return resource, action

    # ------------------------------------------------------------------ #
    # Audit
    # ------------------------------------------------------------------ #

    def _log_audit(
        self,
        agent_id: str,
        resource: str,
        action: str,
        granted: bool,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.execute(
                """
                INSERT INTO permission_audit (agent_id, resource, action, granted, reason, context, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    resource,
                    action,
                    1 if granted else 0,
                    reason,
                    json.dumps(context or {}, ensure_ascii=False),
                    time.time(),
                ),
            )

    def get_audit_log(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100,
        since: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """获取权限审计日志。"""
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            if agent_id:
                rows = conn.execute(
                    """
                    SELECT id, agent_id, resource, action, granted, reason, context, timestamp
                    FROM permission_audit
                    WHERE agent_id = ? AND (? IS NULL OR timestamp >= ?)
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (agent_id, since, since, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, agent_id, resource, action, granted, reason, context, timestamp
                    FROM permission_audit
                    WHERE ? IS NULL OR timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (since, since, limit),
                ).fetchall()
        return [
            {
                "id": r[0],
                "agent_id": r[1],
                "resource": r[2],
                "action": r[3],
                "granted": bool(r[4]),
                "reason": r[5],
                "context": json.loads(r[6]) if r[6] else {},
                "timestamp": r[7],
            }
            for r in rows
        ]


# ==============================================================================
# Singleton
# ==============================================================================

_PERMISSION_MANAGER_INSTANCE: Optional[AgentPermissionManager] = None


def get_agent_permission_manager(db_dir: str = DEFAULT_DB_DIR) -> AgentPermissionManager:
    global _PERMISSION_MANAGER_INSTANCE
    if _PERMISSION_MANAGER_INSTANCE is None:
        _PERMISSION_MANAGER_INSTANCE = AgentPermissionManager(db_dir=db_dir)
    return _PERMISSION_MANAGER_INSTANCE


def reset_agent_permission_manager():
    """测试用：重置单例"""
    global _PERMISSION_MANAGER_INSTANCE
    _PERMISSION_MANAGER_INSTANCE = None
