"""
凭证保险库 — CredentialVault

采用 Fernet (AES-128-CBC + HMAC-SHA256) 加密存储敏感凭证。
生产环境建议替换为 HashiCorp Vault 或 AWS Secrets Manager。
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CredentialNotFoundError(Exception):
    """请求凭证不存在时抛出的异常"""
    pass


# Lazy import cryptography to avoid hard dependency at module level
def _get_fernet():
    try:
        from cryptography.fernet import Fernet
        return Fernet
    except ImportError as e:
        raise ImportError(
            "cryptography is required for CredentialVault. "
            "Install it with: pip install cryptography"
        ) from e


class CredentialVault:
    """
    轻量级凭证保险库。
    采用 Fernet 对称加密，自动兼容旧版 XOR 数据。
    """

    def __init__(self, vault_path: Optional[str] = None, master_key_path: Optional[str] = None):
        self.vault_path = Path(vault_path or os.path.expanduser("~/.kaelis/vault.json"))
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self._master_key_path = Path(master_key_path) if master_key_path else None
        self._key = self._derive_key()
        self._cache: Dict[str, Any] = {}
        self._load()

    def _derive_key(self) -> bytes:
        """从环境或文件派生加密密钥（32 字节）"""
        key_env = os.environ.get("KAELIS_VAULT_KEY")
        if key_env:
            return key_env.encode("utf-8")[:32].ljust(32, b"\0")
        if self._master_key_path:
            if self._master_key_path.exists():
                return self._master_key_path.read_bytes()[:32].ljust(32, b"\0")
            # 生成新密钥并保存
            import secrets
            key = secrets.token_bytes(32)
            self._master_key_path.write_bytes(key)
            return key
        # 使用机器特定信息生成稳定密钥（演示/开发环境）
        machine_id = os.environ.get("COMPUTERNAME", "kaelis") + os.environ.get("USER", "default")
        import hashlib
        return hashlib.sha256(machine_id.encode()).digest()

    def _get_fernet(self):
        """基于派生密钥创建 Fernet 实例"""
        Fernet = _get_fernet()
        # Fernet 需要 32 字节 base64-urlsafe 编码的密钥
        urlsafe_key = base64.urlsafe_b64encode(self._key)
        return Fernet(urlsafe_key)

    def _load(self) -> None:
        """加载保险库"""
        if not self.vault_path.exists():
            self._cache = {}
            return
        try:
            data = json.loads(self.vault_path.read_text(encoding="utf-8"))
            self._cache = {k: self._decrypt(v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"保险库加载失败: {e}")
            self._cache = {}

    def _save(self) -> None:
        """保存保险库"""
        data = {k: self._encrypt(v) for k, v in self._cache.items()}
        self.vault_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _encrypt(self, plaintext: str) -> str:
        """Fernet 加密 + Base64"""
        f = self._get_fernet()
        token = f.encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")

    def _decrypt(self, ciphertext: str) -> str:
        """尝试 Fernet 解密，失败则回退到旧版 XOR（兼容迁移）"""
        try:
            f = self._get_fernet()
            decrypted = f.decrypt(ciphertext.encode("ascii"))
            return decrypted.decode("utf-8")
        except Exception:
            # 回退到旧版 XOR（兼容旧数据自动迁移）
            return self._legacy_xor_decrypt(ciphertext)

    def _legacy_xor_decrypt(self, ciphertext: str) -> str:
        """旧版 XOR + Base64 解密（用于向后兼容）"""
        key = self._key
        data = base64.b64decode(ciphertext.encode("ascii"))
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return decrypted.decode("utf-8")

    def set(self, key: str, value: str) -> None:
        """存储凭证"""
        self._cache[key] = value
        self._save()

    def get(self, key: str) -> Optional[str]:
        """获取凭证"""
        return self._cache.get(key)

    def delete(self, key: str) -> None:
        """删除凭证"""
        self._cache.pop(key, None)
        self._save()

    def list_keys(self) -> list:
        """列出所有凭证键（不含值）"""
        return list(self._cache.keys())

    def has_credential(self, key: str) -> bool:
        """检查是否已配置某凭证"""
        return key in self._cache and bool(self._cache[key])

    def store_credential(self, user_id: str, provider: str, credential: str) -> None:
        """存储用户凭证（兼容旧版测试API）"""
        key = f"{user_id}:{provider}"
        self.set(key, credential)

    def retrieve_credential(self, user_id: str, provider: str) -> str:
        """检索用户凭证（兼容旧版测试API）"""
        key = f"{user_id}:{provider}"
        value = self.get(key)
        if value is None:
            self._load()  # 刷新缓存以捕获其他实例的写入
            value = self.get(key)
        if value is None:
            raise CredentialNotFoundError(f"Credential not found for {user_id}/{provider}")
        return value

    def delete_credential(self, user_id: str, provider: str) -> bool:
        """删除用户凭证（兼容旧版测试API）"""
        key = f"{user_id}:{provider}"
        if key not in self._cache:
            return False
        self.delete(key)
        return True

    def list_services(self, user_id: str) -> List[str]:
        """列出某用户的所有服务提供商（兼容旧版测试API）"""
        prefix = f"{user_id}:"
        services = []
        for key in self._cache:
            if key.startswith(prefix):
                services.append(key[len(prefix):])
        return services

    def check_env_credentials(self) -> Dict[str, Any]:
        """
        检查环境变量中的凭证安全性。
        返回问题报告。
        """
        issues = []
        env_vars = ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DB_URL", "SECRET_KEY"]

        for var in env_vars:
            val = os.environ.get(var)
            if not val:
                issues.append({
                    "key": var,
                    "status": "missing",
                    "risk": "medium",
                    "reason": f"{var} 未配置，相关功能不可用",
                })
            elif len(val) < 10:
                issues.append({
                    "key": var,
                    "status": "weak",
                    "risk": "high",
                    "reason": f"{var} 长度过短，可能为弱凭证或占位符",
                })
            elif "default" in val.lower() or "placeholder" in val.lower():
                issues.append({
                    "key": var,
                    "status": "placeholder",
                    "risk": "high",
                    "reason": f"{var} 使用默认值/占位符，存在安全风险",
                })

        return {
            "checked": len(env_vars),
            "issues": issues,
            "secure_count": len(env_vars) - len(issues),
        }


# =============================================================================
# Unified LLM API Key Resolver
# =============================================================================

_LLMAPI_VAULT_INSTANCE: Optional[CredentialVault] = None


def _get_vault_instance() -> CredentialVault:
    global _LLMAPI_VAULT_INSTANCE
    if _LLMAPI_VAULT_INSTANCE is None:
        _LLMAPI_VAULT_INSTANCE = CredentialVault()
    return _LLMAPI_VAULT_INSTANCE


def resolve_llm_api_key(provider_name: str, env_var_name: Optional[str] = None) -> Optional[str]:
    """
    统一解析 LLM API Key。

    查找优先级：
        1. 环境变量（env_var_name 或 {provider_name.upper()}_API_KEY）
        2. CredentialVault（key 为 {provider_name.lower()}_api_key）
        3. 返回 None

    Args:
        provider_name: 提供商名称，如 "deepseek", "openai", "anthropic"
        env_var_name: 显式指定的环境变量名，默认 {PROVIDER}_API_KEY

    Returns:
        API Key 字符串，或 None
    """
    if env_var_name is None:
        env_var_name = f"{provider_name.upper()}_API_KEY"

    # 1. 环境变量优先（向后兼容）
    env_value = os.environ.get(env_var_name)
    if env_value:
        return env_value

    # 2. CredentialVault
    vault_key = f"{provider_name.lower()}_api_key"
    try:
        vault = _get_vault_instance()
        vault_value = vault.get(vault_key)
        if vault_value:
            return vault_value
    except Exception:
        pass

    return None
