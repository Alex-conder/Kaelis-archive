#!/usr/bin/env python3
"""
Kaelis MCP Standalone Server
==============================
独立的 MCP Server 入口，通过 stdio 传输协议暴露 Kaelis 核心能力。

可作为独立进程启动，供 VSCode Extension、Claude Desktop、Cursor 等 MCP Client 调用。

用法：
    python mcp_standalone.py
    # 或
    python -m mcp_standalone

已注册 Tools:
    - memory_search(layer, query, top_k)
    - memory_write(layer, key, value, metadata)
    - memory_get(layer, key)
    - skill_list(task_type_filter)
    - skill_get(skill_id)
    - daily_insight_generate()
    - proactive_push(context)

已注册 Resources:
    - memory://{layer}/{key}
    - skill://{skill_id}
"""

import os
import sys
import logging
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env 环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("mcp_standalone")


def main():
    """启动独立的 MCP Server（stdio 模式）"""
    logger.info("=" * 60)
    logger.info("Kaelis MCP Standalone Server")
    logger.info("Transport: stdio")
    logger.info("=" * 60)

    # 启动时健康检查
    try:
        from core.memory_health import run_startup_health_check
        health_report = run_startup_health_check(db_dir="data")
        if health_report["overall"] == "failed":
            logger.warning("Memory subsystem health check FAILED - starting in degraded mode")
        else:
            logger.info("Health check passed: %s", health_report["overall"])
    except Exception as e:
        logger.warning("Startup health check skipped: %s", e)

    # 启动 MCP Server
    try:
        from core.mcp.server import create_mcp_server, run_stdio_server
    except ImportError as e:
        logger.error("Failed to import MCP server module: %s", e)
        sys.exit(1)

    mcp = create_mcp_server(name="Kaelis-Standalone")
    if mcp is None:
        logger.error("Failed to create MCP server. Is 'mcp' package installed?")
        sys.exit(1)

    logger.info("MCP Server created successfully")
    logger.info("Tools registered: memory_search, memory_get, memory_write, skill_list, skill_get, daily_insight_generate, proactive_push")
    logger.info("Resources registered: memory://{layer}/{key}, skill://{skill_id}")
    logger.info("Waiting for client connection via stdio...")
    logger.info("-" * 60)

    import anyio
    anyio.run(mcp.run_stdio_async)


if __name__ == "__main__":
    main()
