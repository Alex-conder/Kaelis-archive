"""
Credential Vault (Prompt 1)

AES-256 encrypted credential storage for user API keys and service tokens.
Each user's credentials are stored under data/vault/{user_id}/.
"""

import logging
import os
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class CredentialNotFoundError(Exception):
    """Raised when a requested credential does not exist or cannot be decrypted."""
    pass


# Try cryptography first, fallback to base64-only with warning
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    Fernet = None  # type: ignore
    logger.warning("cryptography not installed. CredentialVault will store credentials in base64 (not secure).")


class CredentialVault:
    """
    Secure credential vault using AES-256 (Fernet) encryption.

    Usage:
        vault = CredentialVault()
        vault.store_credential("user_1", "openai", "sk-xxx")
        key = vault.retrieve_credential("user_1", "openai")
    """

    def __init__(self, master_key_path: str = "data/keys/master.key", vault_dir: str = "data/vault"):
        self.master_key_path = Path(master_key_path)
        self.master_key_path.parent.mkdir(parents=True, exist_ok=True)
        self.vault_dir = Path(vault_dir)
        self._cipher = self._load_or_create_cipher()
        logger.info("CredentialVault initialized")

    def _load_or_create_cipher(self):
        """Load existing master key or generate a new one."""
        if self.master_key_path.exists():
            key = self.master_key_path.read_bytes()
            if CRYPTO_AVAILABLE:
                return Fernet(key)
            else:
                return _FallbackCipher(key)

        # Generate new key
        if CRYPTO_AVAILABLE:
            key = Fernet.generate_key()
            cipher = Fernet(key)
        else:
            key = os.urandom(32)
            cipher = _FallbackCipher(key)
        self.master_key_path.write_bytes(key)
        logger.info(f"Generated new master key at {self.master_key_path}")
        return cipher

    def _vault_dir(self, user_id: str) -> Path:
        """Return the vault directory for a user."""
        vault_dir = self.vault_dir / user_id
        vault_dir.mkdir(parents=True, exist_ok=True)
        return vault_dir

    def _file_path(self, user_id: str, service_name: str) -> Path:
        """Return the encrypted credential file path."""
        safe_service = "".join(c for c in service_name if c.isalnum() or c in "_-").rstrip()
        if not safe_service:
            safe_service = "unknown"
        return self._vault_dir(user_id) / f"{safe_service}.enc"

    def store_credential(self, user_id: str, service_name: str, api_key: str) -> None:
        """Encrypt and store a credential."""
        file_path = self._file_path(user_id, service_name)
        data = api_key.encode("utf-8")
        encrypted = self._cipher.encrypt(data)
        file_path.write_bytes(encrypted)
        logger.info(f"Stored credential for user={user_id} service={service_name}")

    def retrieve_credential(self, user_id: str, service_name: str) -> str:
        """Decrypt and return a credential. Raises CredentialNotFoundError on failure."""
        file_path = self._file_path(user_id, service_name)
        if not file_path.exists():
            raise CredentialNotFoundError(f"No credential found for {user_id}/{service_name}")
        try:
            encrypted = file_path.read_bytes()
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode("utf-8")
        except Exception as e:
            raise CredentialNotFoundError(f"Failed to decrypt credential for {user_id}/{service_name}: {e}")

    def delete_credential(self, user_id: str, service_name: str) -> bool:
        """Delete a stored credential. Returns True if deleted, False if not found."""
        file_path = self._file_path(user_id, service_name)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted credential for user={user_id} service={service_name}")
            return True
        return False

    def list_services(self, user_id: str) -> List[str]:
        """List all stored service names for a user."""
        vault_dir = self._vault_dir(user_id)
        if not vault_dir.exists():
            return []
        services = []
        for f in vault_dir.iterdir():
            if f.suffix == ".enc" and f.is_file():
                services.append(f.stem)
        return sorted(services)


class _FallbackCipher:
    """Fallback cipher when cryptography is not installed (base64 only, NOT secure)."""

    def __init__(self, key: bytes):
        self.key = key

    def encrypt(self, data: bytes) -> bytes:
        import base64
        return base64.b64encode(data)

    def decrypt(self, data: bytes) -> bytes:
        import base64
        return base64.b64decode(data)
