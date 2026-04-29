"""
智能环境检测器 — Smart Detector

在 Kaelis 启动时自动扫描磁盘，发现竞品数据并引导迁移。

用法:
    python -c "from core.migration.smart_detector import scan_for_competitors; print(scan_for_competitors())"
"""

import os
import json
import platform
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class CompetitorDataSource:
    name: str          # openclaw | hermes
    type: str          # skills | memory | config
    path: str
    size_bytes: int
    size_human: str
    detected_at: str
    confidence: float  # 0-1，检测置信度


def _human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _get_home() -> Path:
    return Path.home()


def _get_appdata() -> Optional[Path]:
    """获取 Windows AppData 路径"""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata)
    return None


def scan_openclaw() -> List[CompetitorDataSource]:
    """扫描 OpenClaw 数据"""
    results = []
    home = _get_home()
    appdata = _get_appdata()

    candidates = [
        home / ".openclaw",
        home / "openclaw",
    ]
    if appdata:
        candidates.append(appdata / "OpenClaw")
        candidates.append(appdata / "openclaw")

    for candidate in candidates:
        if not candidate.exists():
            continue
        total_size = sum(f.stat().st_size for f in candidate.rglob("*") if f.is_file())
        if total_size == 0:
            continue

        # 判断数据类型
        has_skills = any((candidate / "skills").glob("*")) if (candidate / "skills").exists() else False
        has_memory = (candidate / "memory.json").exists() or (candidate / "history.json").exists()

        data_type = "mixed"
        if has_skills and not has_memory:
            data_type = "skills"
        elif has_memory and not has_skills:
            data_type = "memory"

        results.append(CompetitorDataSource(
            name="openclaw",
            type=data_type,
            path=str(candidate),
            size_bytes=total_size,
            size_human=_human_size(total_size),
            detected_at=datetime.now().isoformat(),
            confidence=0.9 if has_skills or has_memory else 0.5,
        ))

    return results


def scan_hermes() -> List[CompetitorDataSource]:
    """扫描 Hermes 数据"""
    results = []
    home = _get_home()

    candidates = [
        home / "hermes-agent",
        home / ".hermes",
        home / "hermes_memory",
        Path(".") / "hermes_memory",
        Path(".") / ".hermes",
    ]

    for candidate in candidates:
        if not candidate.exists():
            continue
        total_size = sum(f.stat().st_size for f in candidate.rglob("*") if f.is_file())
        if total_size == 0:
            continue

        # Hermes 特征文件
        has_memory_md = any(f.name.endswith(".md") for f in candidate.rglob("*") if f.is_file())
        has_skills_md = (candidate / "SKILLS.md").exists() or any(f.name.startswith("SKILL") for f in candidate.rglob("*.md"))

        data_type = "mixed"
        if has_skills_md and not has_memory_md:
            data_type = "skills"
        elif has_memory_md and not has_skills_md:
            data_type = "memory"

        results.append(CompetitorDataSource(
            name="hermes",
            type=data_type,
            path=str(candidate),
            size_bytes=total_size,
            size_human=_human_size(total_size),
            detected_at=datetime.now().isoformat(),
            confidence=0.85 if has_memory_md else 0.6,
        ))

    return results


def scan_for_competitors() -> List[Dict[str, Any]]:
    """
    扫描所有已知竞品数据源。
    返回可序列化的字典列表，供 API/MCP Tool 使用。
    """
    all_results: List[CompetitorDataSource] = []
    all_results.extend(scan_openclaw())
    all_results.extend(scan_hermes())

    # 按置信度排序
    all_results.sort(key=lambda x: x.confidence, reverse=True)

    return [asdict(r) for r in all_results]


def generate_migration_report(results: List[Dict[str, Any]]) -> str:
    """生成迁移摘要报告"""
    lines = [
        "# Kaelis 迁移检测报告",
        f"\n生成时间: {datetime.now().isoformat()}",
        f"发现数据源: {len(results)} 个\n",
    ]

    for r in results:
        lines.append(f"## {r['name'].upper()} — {r['type']}")
        lines.append(f"- 路径: `{r['path']}`")
        lines.append(f"- 大小: {r['size_human']}")
        lines.append(f"- 置信度: {r['confidence']:.0%}")
        lines.append("")

    if not results:
        lines.append("未发现任何竞品数据。\n")

    lines.append("---")
    lines.append("使用 `kaelis migrate detect` 或 MCP Tool `migrate.detect_and_import` 重新扫描。")
    return "\n".join(lines)
