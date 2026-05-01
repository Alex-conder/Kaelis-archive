"""
Message Encryptor — End-to-end encryption for cross-device messages.

Uses AES-256-GCM with a key derived from the user's master credential.
The encryption key is cached in memory and never persisted plaintext.
"""

import base64
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MessageEncryptor:
    """
    Encrypt/decrypt cross-device messages using AES-256-GCM.

    Key derivation:
    1. Retrieve user's master credential from CredentialVault
    2. HKDF-SHA256 to derive a 32-byte AES key
    3. Cache derived key in memory (never stored to disk)
    """

    def __init__(self):
        self._cached_key: Optional[bytes] = None

    def _get_key(self) -> Optional[bytes]:
        """Derive or retrieve the encryption key."""
        if self._cached_key:
            return self._cached_key

        try:
            # Try to derive from CredentialVault master password
            from core.security.credential_vault import CredentialVault
            vault = CredentialVault()
            master = vault.get_credential("user", "master_password")
            if master:
                self._cached_key = self._derive_key(master)
                return self._cached_key
        except Exception as e:
            logger.debug("CredentialVault key derivation failed: %s", e)

        # Fallback: derive from node identity private key (deterministic per node)
        try:
            from core.mesh.identity import get_node_identity
            nid = get_node_identity()
            if nid._private_key:
                raw = nid._private_key.private_bytes_raw()
                self._cached_key = self._derive_key(raw.hex())
                return self._cached_key
        except Exception as e:
            logger.debug("Identity key derivation failed: %s", e)

        logger.warning("No encryption key available; messages will be sent unencrypted")
        return None

    def _derive_key(self, secret: str) -> bytes:
        """Derive a 32-byte AES key from a secret string using HKDF."""
        try:
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashes
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"kaelis_message_v1",
                info=b"cross-device-sync",
            )
            return hkdf.derive(secret.encode("utf-8"))
        except Exception:
            # Fallback simple derivation if cryptography HKDF fails
            import hashlib
            return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"),
                                       b"kaelis_message_v1", 100000, 32)

    # ------------------------------------------------------------------ #
    # Encrypt / Decrypt
    # ------------------------------------------------------------------ #

    def encrypt(self, plaintext: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Encrypt a message payload.

        Returns:
            {"ciphertext": base64, "nonce": base64, "tag": base64}
            or None if encryption fails.
        """
        key = self._get_key()
        if not key:
            return None

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = os.urandom(12)
            aesgcm = AESGCM(key)
            data = json.dumps(plaintext, default=str).encode("utf-8")
            ct = aesgcm.encrypt(nonce, data, None)
            # AES-GCM appends 16-byte auth tag to ciphertext
            ciphertext = ct[:-16]
            tag = ct[-16:]
            return {
                "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "tag": base64.b64encode(tag).decode("ascii"),
            }
        except Exception as e:
            logger.warning("Encryption failed: %s", e)
            return None

    def decrypt(self, envelope: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Decrypt a message envelope."""
        key = self._get_key()
        if not key:
            return None

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = base64.b64decode(envelope["nonce"])
            ciphertext = base64.b64decode(envelope["ciphertext"])
            tag = base64.b64decode(envelope["tag"])
            aesgcm = AESGCM(key)
            # Reconstruct: ciphertext + tag
            ct_with_tag = ciphertext + tag
            data = aesgcm.decrypt(nonce, ct_with_tag, None)
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            logger.warning("Decryption failed: %s", e)
            return None

    def is_available(self) -> bool:
        return self._get_key() is not None


# ============================================================================
# Singleton
# ============================================================================

_EncryptorInstance: Optional[MessageEncryptor] = None


def get_message_encryptor() -> MessageEncryptor:
    global _EncryptorInstance
    if _EncryptorInstance is None:
        _EncryptorInstance = MessageEncryptor()
    return _EncryptorInstance
