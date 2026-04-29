"""
Hermes 数据迁移连接器

功能:
1. 解析 Hermes MEMORY.md 文件，按标题拆分为 L2 记忆条目
2. 读取 SKILL.md 并通过 import_from_agentskills 纳管
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class HermesConnector:
    """Hermes 迁移连接器"""

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        self.memory_entries: List[Dict[str, Any]] = []
        self.skills: List[Dict[str, Any]] = []

    def parse_memory_md(self, md_path: Path) -> List[Dict[str, Any]]:
        """将 Markdown 记忆文件按 # 标题拆分为条目"""
        if not md_path.exists():
            return []

        text = md_path.read_text(encoding="utf-8")
        # 按一级标题拆分
        sections = re.split(r'\n(?=# )', text)
        entries = []

        for section in sections:
            section = section.strip()
            if not section:
                continue
            lines = section.splitlines()
            title = lines[0].lstrip("# ").strip() if lines else "untitled"
            body = "\n".join(lines[1:]).strip()

            entries.append({
                "title": title,
                "content": body,
                "source_file": str(md_path),
            })

        return entries

    def scan_memory(self) -> List[Dict[str, Any]]:
        """扫描所有 Markdown 记忆文件"""
        entries = []
        for md_file in self.source_path.rglob("*.md"):
            if md_file.name.startswith("SKILL"):
                continue  # 技能文件单独处理
            entries.extend(self.parse_memory_md(md_file))

        self.memory_entries = entries
        logger.info(f"Hermes 记忆扫描完成: 发现 {len(entries)} 个条目")
        return entries

    def scan_skills(self) -> List[Dict[str, Any]]:
        """扫描 SKILL.md 等技能文件"""
        skills = []
        for pattern in ["SKILLS.md", "SKILL_*.md", "skill_*.md"]:
            for skill_file in self.source_path.glob(pattern):
                try:
                    text = skill_file.read_text(encoding="utf-8")
                    skills.append({
                        "source_file": str(skill_file),
                        "name": skill_file.stem,
                        "content": text,
                    })
                except Exception as e:
                    logger.warning(f"无法读取技能文件 {skill_file}: {e}")

        self.skills = skills
        return skills

    def import_memory_to_l2(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """导入记忆到 L2"""
        from core.memory_manager_v2 import get_memory_manager

        mm = get_memory_manager()
        entries = self.scan_memory()
        imported = 0

        for i, entry in enumerate(entries):
            try:
                mm.write(
                    layer="L2",
                    key=f"hermes_{entry['title'][:50]}_{i}",
                    value=entry,
                    metadata={"source": "hermes_migration", "migrated": True},
                    user_id=user_id,
                )
                imported += 1
            except Exception as e:
                logger.warning(f"记忆导入失败: {e}")

        return {"total_found": len(entries), "imported": imported}

    def import_skills(self) -> Dict[str, Any]:
        """通过 agentskills 方式导入技能"""
        from core.skill_manager import get_skill_manager

        sm = get_skill_manager()
        skills = self.scan_skills()
        imported = 0

        for s in skills:
            try:
                # 尝试解析 Markdown 中的结构化内容
                lines = s["content"].splitlines()
                name = s["name"]
                description = ""
                params = {}

                for line in lines:
                    if line.startswith("## 描述") or line.startswith("## Description"):
                        continue
                    if line.strip() and not description:
                        description = line.strip()
                    if "param" in line.lower() or "参数" in line:
                        # 简单参数提取
                        pass

                sm.register_skill({
                    "name": name,
                    "task_type": "general",
                    "description": description or f"Imported from Hermes: {name}",
                    "params": params,
                    "source": "hermes_import",
                })
                imported += 1
            except Exception as e:
                logger.error(f"技能导入失败 {s['name']}: {e}")

        return {"total_found": len(skills), "imported": imported}
