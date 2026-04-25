"""
Kaelis Mesh Authorization
==========================
跨节点授权管理：JWT 签发/验证、权限授予/撤销。

用法:
    from core.mesh.authorization import AuthorizationManager, get_authorization_manager
    auth = get_authorization_manager()
    token = auth.create_token("issuer_kni", "subject_kni", [{"resource_type": "memory", "resource_id": "L1", "actions": ["read"]}])
    payload = auth.verify_token(token)
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import jwt

from core.mesh.identity import get_node_identity
from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)

# ============================================================================
# Config
# ============================================================================

JWT_ALGORITHM = "EdDSA"
PERMISSIONS_KEY = "mesh_permissions"


# ============================================================================
# Authorization Manager
# ============================================================================

class AuthorizationManager:
    """
    跨节点授权管理器。

    - 使用节点 Ed25519 密钥对签发/验证 JWT
    - 权限记录存储在 L0 Identity 层
    """

    def __init__(self):
        self._identity = get_node_identity()

    # ------------------------------------------------------------------ #
    # JWT
    # ------------------------------------------------------------------ #

    def create_token(
        self,
        issuer_kni: str,
        subject_kni: str,
        permissions: List[Dict[str, Any]],
        ttl_hours: int = 24,
    ) -> str:
        """
        签发授权 JWT。

        Args:
            issuer_kni: 签发者 KNI（必须是本节点）
            subject_kni: 被授权者 KNI
            permissions: 权限列表，每项包含 resource_type, resource_id, actions
            ttl_hours: 有效期（小时）

        Returns:
            JWT 字符串
        """
        if issuer_kni != self._identity.kni:
            raise ValueError("Only local node can issue tokens")

        now = datetime.now(timezone.utc)
        payload = {
            "iss": issuer_kni,
            "sub": subject_kni,
            "permissions": permissions,
            "iat": now,
            "exp": now + timedelta(hours=ttl_hours),
            "jti": f"{issuer_kni}:{subject_kni}:{int(time.time())}",
        }

        # EdDSA 需要 private_key 对象
        token = jwt.encode(
            payload,
            key=self._identity._private_key,
            algorithm=JWT_ALGORITHM,
        )
        logger.info("Token issued: issuer=%s subject=%s perms=%d", issuer_kni, subject_kni, len(permissions))
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        验证 JWT 并返回 payload。

        如果 token 是本节点签发的，使用本地公钥验证；
        如果是远程节点签发的，需要其公钥（当前版本仅支持本地验证）。
        """
        try:
            # 先不验证签名，提取 issuer
            unverified = jwt.decode(token, options={"verify_signature": False}, algorithms=[JWT_ALGORITHM])
            issuer = unverified.get("iss", "")

            if issuer == self._identity.kni:
                # 本节点签发：用本地公钥验证
                payload = jwt.decode(
                    token,
                    key=self._identity._public_key,
                    algorithms=[JWT_ALGORITHM],
                )
                return payload
            else:
                # TODO: 从网络/缓存获取远程节点公钥
                logger.warning("Cannot verify token from remote issuer %s: public key not cached", issuer)
                return None

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token: %s", e)
            return None

    # ------------------------------------------------------------------ #
    # Permission Registry
    # ------------------------------------------------------------------ #

    def grant_permission(
        self,
        requester_kni: str,
        resource_type: str,
        resource_id: str,
        actions: List[str],
    ) -> str:
        """
        用户审批后记录授权到 L0。

        Returns:
            permission_id
        """
        perm_id = f"perm_{requester_kni}_{resource_type}_{resource_id}_{int(time.time())}"
        record = {
            "id": perm_id,
            "requester_kni": requester_kni,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "actions": actions,
            "granted_at": datetime.now(timezone.utc).isoformat(),
            "granted_by": self._identity.kni,
        }

        try:
            mm = get_memory_manager()
            # 读取现有权限列表
            existing = mm.read(layer="L0", key=PERMISSIONS_KEY, user_id="system")
            perms = []
            if existing and isinstance(existing.get("value"), list):
                perms = existing["value"]

            perms.append(record)

            mm.write(
                layer="L0",
                key=PERMISSIONS_KEY,
                value=perms,
                metadata={"type": "mesh_permissions", "source": "core.mesh.authorization"},
                user_id="system",
                agent_id="kaelis_self",
            )
            logger.info("Permission granted: %s -> %s/%s [%s]", requester_kni, resource_type, resource_id, ",".join(actions))
            return perm_id

        except Exception as e:
            logger.error("Failed to grant permission: %s", e)
            raise

    def revoke_permission(self, permission_id: str) -> bool:
        """撤销指定权限。"""
        try:
            mm = get_memory_manager()
            existing = mm.read(layer="L0", key=PERMISSIONS_KEY, user_id="system")
            if not existing or not isinstance(existing.get("value"), list):
                return False

            perms = existing["value"]
            new_perms = [p for p in perms if p.get("id") != permission_id]
            if len(new_perms) == len(perms):
                return False  # not found

            mm.write(
                layer="L0",
                key=PERMISSIONS_KEY,
                value=new_perms,
                metadata={"type": "mesh_permissions", "source": "core.mesh.authorization"},
                user_id="system",
                agent_id="kaelis_self",
            )
            logger.info("Permission revoked: %s", permission_id)
            return True

        except Exception as e:
            logger.error("Failed to revoke permission: %s", e)
            return False

    def list_permissions(self, requester_kni: Optional[str] = None) -> List[Dict]:
        """列出所有授权记录，可按要求者 KNI 过滤。"""
        try:
            mm = get_memory_manager()
            existing = mm.read(layer="L0", key=PERMISSIONS_KEY, user_id="system")
            if not existing or not isinstance(existing.get("value"), list):
                return []

            perms = existing["value"]
            if requester_kni:
                perms = [p for p in perms if p.get("requester_kni") == requester_kni]
            return perms

        except Exception as e:
            logger.error("Failed to list permissions: %s", e)
            return []

    def check_permission(
        self,
        requester_kni: str,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> bool:
        """检查请求者是否有指定资源的操作权限。"""
        perms = self.list_permissions(requester_kni)
        for p in perms:
            if p.get("resource_type") == resource_type and p.get("resource_id") == resource_id:
                if action in p.get("actions", []):
                    return True
        return False


# ============================================================================
# Singleton
# ============================================================================

_AuthInstance: Optional[AuthorizationManager] = None


def get_authorization_manager() -> AuthorizationManager:
    """获取全局授权管理器单例。"""
    global _AuthInstance
    if _AuthInstance is None:
        _AuthInstance = AuthorizationManager()
    return _AuthInstance
