"""
Kaelis Node Identity
====================
去中心化身份管理：Ed25519 密钥对、KNI (Kaelis Node ID)、签名验证。

用法:
    from core.mesh.identity import NodeIdentity, get_node_identity
    ni = get_node_identity()
    print(ni.kni)
    sig = ni.sign_message(b"hello")
    assert ni.verify_signature(b"hello", sig, ni.kni)
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import base58
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# 导入记忆管理器
from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)

# ============================================================================
# Paths & Constants
# ============================================================================

KEYS_DIR = Path("data/keys")
IDENTITY_KEY_FILE = KEYS_DIR / "node_identity.key"
MASTER_KEY_ENV = "KAELIS_MASTER_KEY"
DEFAULT_MASTER_KEY = "kaelis-default-master-key-change-me"
KDF_ITERATIONS = 100_000


# ============================================================================
# Key Derivation
# ============================================================================

def _derive_key(password: bytes, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 派生 256-bit 密钥。"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password)


# ============================================================================
# Node Identity
# ============================================================================

class NodeIdentity:
    """
    Kaelis 节点身份。

    Attributes:
        kni: Kaelis Node ID（公钥 SHA3-256 前 12 字节 base58 编码）
        public_key_bytes: 原始公钥字节（32 字节）
        display_name: 节点显示名称
        capabilities: 能力列表
        version: Kaelis 版本
        endpoint_url: 节点服务端点
    """

    def __init__(self):
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._public_key: Optional[Ed25519PublicKey] = None
        self.kni: Optional[str] = None
        self.public_key_bytes: Optional[bytes] = None

        # 元数据（从 L0 加载或默认）
        self.display_name: str = "Kaelis Node"
        self.capabilities: List[str] = []
        self.version: str = "1.0.0"
        self.endpoint_url: str = ""

        self._load_or_create()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def _load_or_create(self):
        """加载现有身份或创建新身份。"""
        KEYS_DIR.mkdir(parents=True, exist_ok=True)

        if IDENTITY_KEY_FILE.exists():
            self._load_identity()
        else:
            self._create_identity()

        self._load_metadata()

    def _create_identity(self):
        """生成新的 Ed25519 密钥对并加密存储。"""
        logger.info("Creating new node identity...")
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        public_bytes = public_key.public_bytes_raw()
        private_bytes = private_key.private_bytes_raw()

        # KNI = SHA3-256(pub)[:12] base58
        kni = self._compute_kni(public_bytes)

        # 加密私钥
        encrypted = self._encrypt_private_key(private_bytes)

        # 存储
        key_data = {
            "kni": kni,
            "public_key": public_bytes.hex(),
            "encrypted_private_key": encrypted.hex(),
            "format": "ed25519+aes256gcm",
        }
        IDENTITY_KEY_FILE.write_text(json.dumps(key_data, indent=2), encoding="utf-8")
        IDENTITY_KEY_FILE.chmod(0o600)

        self._private_key = private_key
        self._public_key = public_key
        self.public_key_bytes = public_bytes
        self.kni = kni

        logger.info("Node identity created: KNI=%s", kni)

    def _load_identity(self):
        """从文件加载身份。"""
        key_data = json.loads(IDENTITY_KEY_FILE.read_text(encoding="utf-8"))
        self.kni = key_data["kni"]
        self.public_key_bytes = bytes.fromhex(key_data["public_key"])

        # 恢复公钥
        self._public_key = Ed25519PublicKey.from_public_bytes(self.public_key_bytes)

        # 解密私钥
        encrypted = bytes.fromhex(key_data["encrypted_private_key"])
        private_bytes = self._decrypt_private_key(encrypted)
        self._private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)

        logger.info("Node identity loaded: KNI=%s", self.kni)

    # ------------------------------------------------------------------ #
    # Crypto
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_kni(public_key_bytes: bytes) -> str:
        """计算 KNI。"""
        digest = hashlib.sha3_256(public_key_bytes).digest()
        return base58.b58encode(digest[:12]).decode("ascii")

    def _get_master_password(self) -> bytes:
        """获取主密钥（环境变量或默认值）。"""
        key = os.environ.get(MASTER_KEY_ENV, DEFAULT_MASTER_KEY)
        return key.encode("utf-8")

    def _encrypt_private_key(self, private_bytes: bytes) -> bytes:
        """AES-256-GCM 加密私钥。"""
        password = self._get_master_password()
        salt = os.urandom(16)
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, private_bytes, None)
        return salt + nonce + ciphertext

    def _decrypt_private_key(self, encrypted: bytes) -> bytes:
        """AES-256-GCM 解密私钥。"""
        password = self._get_master_password()
        salt = encrypted[:16]
        nonce = encrypted[16:28]
        ciphertext = encrypted[28:]
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    # ------------------------------------------------------------------ #
    # Sign / Verify
    # ------------------------------------------------------------------ #

    def sign_message(self, message: bytes) -> bytes:
        """使用节点私钥签名消息。"""
        if not self._private_key:
            raise RuntimeError("Private key not loaded")
        return self._private_key.sign(message)

    def verify_signature(self, message: bytes, signature: bytes, kni: str) -> bool:
        """
        验证签名。

        如果 kni 是本节点，使用本地公钥验证；
        否则需要外部提供公钥（未来从网络获取）。
        """
        if kni == self.kni:
            if not self._public_key:
                return False
            try:
                self._public_key.verify(signature, message)
                return True
            except Exception:
                return False
        # TODO: 从网络/缓存获取远程节点公钥
        logger.warning("Cannot verify signature for remote KNI %s: public key not cached", kni)
        return False

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    def _load_metadata(self):
        """从 L0 Identity 层加载元数据。"""
        try:
            mm = get_memory_manager()
            data = mm.read(layer="L0", key="node_identity", user_id="system")
            if data and isinstance(data.get("value"), dict):
                meta = data["value"]
                self.display_name = meta.get("display_name", self.display_name)
                self.capabilities = meta.get("capabilities", self.capabilities)
                self.version = meta.get("version", self.version)
                self.endpoint_url = meta.get("endpoint_url", self.endpoint_url)
        except Exception as e:
            logger.warning("Failed to load metadata from L0: %s", e)

    def save_metadata(self) -> bool:
        """保存元数据到 L0 Identity 层。"""
        try:
            mm = get_memory_manager()
            meta = {
                "display_name": self.display_name,
                "capabilities": self.capabilities,
                "version": self.version,
                "endpoint_url": self.endpoint_url,
                "kni": self.kni,
            }
            return mm.write(
                layer="L0",
                key="node_identity",
                value=meta,
                metadata={"type": "node_identity", "source": "core.mesh.identity"},
                user_id="system",
                agent_id="kaelis_self",
            )
        except Exception as e:
            logger.error("Failed to save metadata: %s", e)
            return False

    def get_signed_metadata(self) -> Dict:
        """返回带签名的元数据（用于分享给其他节点）。"""
        meta = {
            "display_name": self.display_name,
            "capabilities": self.capabilities,
            "version": self.version,
            "endpoint_url": self.endpoint_url,
            "kni": self.kni,
            "public_key": self.public_key_bytes.hex() if self.public_key_bytes else None,
        }
        payload = json.dumps(meta, sort_keys=True).encode("utf-8")
        signature = self.sign_message(payload)
        meta["signature"] = signature.hex()
        return meta

    @staticmethod
    def verify_signed_metadata(signed_meta: Dict) -> bool:
        """验证其他节点分享的签名元数据。"""
        sig_hex = signed_meta.pop("signature", None)
        pub_hex = signed_meta.get("public_key")
        if not sig_hex or not pub_hex:
            return False

        try:
            pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
            payload = json.dumps(signed_meta, sort_keys=True).encode("utf-8")
            pub_key.verify(bytes.fromhex(sig_hex), payload)
            return True
        except Exception:
            return False


# ============================================================================
# Singleton
# ============================================================================

_IdentityInstance: Optional[NodeIdentity] = None


def get_node_identity() -> NodeIdentity:
    """获取全局单例节点身份。"""
    global _IdentityInstance
    if _IdentityInstance is None:
        _IdentityInstance = NodeIdentity()
    return _IdentityInstance


def reset_identity_instance():
    """测试用：重置单例。"""
    global _IdentityInstance
    _IdentityInstance = None


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kaelis Node Identity")
    parser.add_argument("--show", action="store_true", help="Show node identity")
    parser.add_argument("--sign", type=str, help="Sign a message")
    parser.add_argument("--save-meta", action="store_true", help="Save metadata to L0")
    parser.add_argument("--name", type=str, help="Set display name")
    parser.add_argument("--endpoint", type=str, help="Set endpoint URL")
    args = parser.parse_args()

    ni = get_node_identity()

    if args.name:
        ni.display_name = args.name
    if args.endpoint:
        ni.endpoint_url = args.endpoint
    if args.save_meta or args.name or args.endpoint:
        ni.save_metadata()
        print(f"Metadata saved: name={ni.display_name}, endpoint={ni.endpoint_url}")

    if args.show or not any([args.sign, args.save_meta, args.name, args.endpoint]):
        print(f"KNI: {ni.kni}")
        print(f"Display Name: {ni.display_name}")
        print(f"Version: {ni.version}")
        print(f"Capabilities: {ni.capabilities}")
        print(f"Endpoint: {ni.endpoint_url}")
        print(f"Public Key: {ni.public_key_bytes.hex()[:32]}...")

    if args.sign:
        sig = ni.sign_message(args.sign.encode("utf-8"))
        print(f"Signature: {sig.hex()}")
        print(f"Verify: {ni.verify_signature(args.sign.encode('utf-8'), sig, ni.kni)}")
