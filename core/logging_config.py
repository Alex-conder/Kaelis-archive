#!/usr/bin/env python3
"""
Kaelis 统一日志配置
Fixer D2: 消除多处重复调用 logging.basicConfig 导致的配置混乱
"""

import logging
import sys


def init_logging(level: int = logging.INFO) -> None:
    """初始化全局统一的日志格式与级别"""
    # 仅在尚未配置根处理器时执行，避免重复覆盖
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(handler)
