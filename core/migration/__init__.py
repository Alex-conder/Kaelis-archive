"""
Kaelis 数据迁移模块

支持从竞品（OpenClaw、Hermes 等）导入技能和记忆数据。
"""

from .smart_detector import scan_for_competitors, CompetitorDataSource
from .openclaw_connector import OpenClawConnector
from .hermes_connector import HermesConnector

__all__ = [
    "scan_for_competitors",
    "CompetitorDataSource",
    "OpenClawConnector",
    "HermesConnector",
]
