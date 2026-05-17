"""
Redis 客户端包装器
Phase 2: 可选依赖，为 Mesh/Swarm/RAG 提供分布式缓存

环境变量:
  REDIS_HOST (默认 localhost)
  REDIS_PORT (默认 6379)
  REDIS_DB   (默认 0)
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("redis-py not installed, RedisClient will operate in no-op mode")


class RedisClient:
    """Redis 客户端（带降级保护）"""

    def __init__(self):
        self._client: Optional['redis.Redis'] = None  # type: ignore[name-defined]
        if REDIS_AVAILABLE:
            try:
                host = os.getenv("REDIS_HOST", "localhost")
                port = int(os.getenv("REDIS_PORT", "6379"))
                db = int(os.getenv("REDIS_DB", "0"))
                self._client = redis.Redis(
                    host=host, port=port, db=db, decode_responses=True, socket_connect_timeout=2
                )
                self._client.ping()
                logger.info(f"[Redis] Connected to {host}:{port}/{db}")
            except Exception as e:
                logger.warning(f"[Redis] Connection failed: {e}")
                self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> Optional[str]:
        if self._client:
            try:
                return self._client.get(key)
            except Exception:
                pass
        return None

    def set(self, key: str, value: str, expire: int = 3600) -> None:
        if self._client:
            try:
                self._client.setex(key, expire, value)
            except Exception:
                pass

    def delete(self, key: str) -> None:
        if self._client:
            try:
                self._client.delete(key)
            except Exception:
                pass

    def hget(self, name: str, key: str) -> Optional[str]:
        if self._client:
            try:
                return self._client.hget(name, key)
            except Exception:
                pass
        return None

    def hset(self, name: str, key: str, value: str) -> None:
        if self._client:
            try:
                self._client.hset(name, key=value)
            except Exception:
                pass


def get_redis_client() -> RedisClient:
    return RedisClient()
