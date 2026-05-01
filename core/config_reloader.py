"""
配置热重载模块

监听 .env 文件变化，自动重新加载环境变量并刷新运行时组件。

用法:
    from core.config_reloader import start_env_watcher, reload_env_config
    start_env_watcher(".env")  # 启动后台监听
    reload_env_config()         # 手动触发重载
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

_ENV_WATCHER_THREAD: Optional[object] = None


def _parse_env_file(filepath: str) -> dict:
    """解析 .env 文件，返回键值对字典"""
    result = {}
    path = Path(filepath)
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            result[key] = value
    return result


def reload_env_config(env_file: str = ".env") -> bool:
    """
    重新加载 .env 文件并更新 os.environ，然后刷新运行时组件。

    Returns:
        True if reloaded successfully
    """
    env_path = Path(env_file)
    if not env_path.exists():
        logger.warning("Env file not found: %s", env_path.absolute())
        return False

    logger.info("Reloading env config from %s", env_path.absolute())
    new_vars = _parse_env_file(str(env_path))

    updated = []
    for key, value in new_vars.items():
        old = os.environ.get(key)
        if old != value:
            os.environ[key] = value
            updated.append(key)

    if not updated:
        logger.info("No env changes detected")
        return True

    logger.info("Updated %d env variables: %s", len(updated), ", ".join(updated))

    # 刷新 LLM 客户端单例
    try:
        from core.llm_client import reset_llm_client
        reset_llm_client()
    except Exception as e:
        logger.warning("Failed to reset llm_client: %s", e)

    # 刷新 ProviderRegistry（通过重新创建全局实例）
    try:
        from core.llm_providers import registry
        # ProviderRegistry 在创建时读取环境变量，无法直接刷新。
        # 这里通过模块属性通知使用者重新创建实例。
        registry._ENV_RELOADED_AT = time.time()
        logger.info("ProviderRegistry marked for refresh")
    except Exception as e:
        logger.warning("Failed to mark ProviderRegistry refresh: %s", e)

    # 刷新 SmartRouter / ModelRegistry
    try:
        from core.llm.smart_router import ModelRegistry
        # ModelRegistry 支持从环境变量重新加载预置模型
        # 用户自定义模型已通过 SQLite 持久化，无需刷新
        _new_registry = ModelRegistry()
        logger.info("ModelRegistry refreshed with %d models", len(_new_registry._models))
    except Exception as e:
        logger.warning("Failed to refresh ModelRegistry: %s", e)

    return True


def start_env_watcher(
    env_file: str = ".env",
    interval: float = 3.0,
    on_reload: Optional[Callable[[], None]] = None,
) -> None:
    """
    启动后台线程轮询 .env 文件变化，变化时自动调用 reload_env_config。

    Args:
        env_file: 要监听的 .env 文件路径
        interval: 轮询间隔（秒）
        on_reload: 可选的回调函数，在重载成功后调用
    """
    import threading

    env_path = Path(env_file)
    last_mtime: Optional[float] = None
    if env_path.exists():
        last_mtime = env_path.stat().st_mtime

    def _watch_loop():
        nonlocal last_mtime
        while True:
            time.sleep(interval)
            try:
                if not env_path.exists():
                    continue
                current_mtime = env_path.stat().st_mtime
                if last_mtime is None or current_mtime > last_mtime:
                    last_mtime = current_mtime
                    success = reload_env_config(str(env_path))
                    if success and on_reload:
                        try:
                            on_reload()
                        except Exception as cb_err:
                            logger.warning("Reload callback error: %s", cb_err)
            except Exception as e:
                logger.debug("Env watcher error: %s", e)

    global _ENV_WATCHER_THREAD
    if _ENV_WATCHER_THREAD is not None and _ENV_WATCHER_THREAD.is_alive():
        logger.info("Env watcher already running")
        return

    t = threading.Thread(target=_watch_loop, daemon=True, name="env-watcher")
    t.start()
    _ENV_WATCHER_THREAD = t
    logger.info("Started env watcher for %s (interval=%ss)", env_path.absolute(), interval)
