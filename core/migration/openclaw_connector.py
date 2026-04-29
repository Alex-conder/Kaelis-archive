"""
OpenClaw 数据迁移连接器

功能:
1. 扫描 OpenClaw 技能目录
2. 解析 .claw / .json 技能文件
3. 转换为 Kaelis 技能格式并注册
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class OpenClawConnector:
    """OpenClaw 迁移连接器"""

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        self.skills_found: List[Dict[str, Any]] = []
        self.memories_found: List[Dict[str, Any]] = []

    def scan_skills(self) -> List[Dict[str, Any]]:
        """扫描技能文件"""
        skills_dir = self.source_path / "skills"
        if not skills_dir.exists():
            return []

        skills = []
        for file_path in skills_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix in (".json", ".claw"):
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    skills.append({
                        "source_file": str(file_path.relative_to(self.source_path)),
                        "name": data.get("name", file_path.stem),
                        "description": data.get("description", ""),
                        "raw": data,
                    })
                except Exception as e:
                    logger.warning(f"无法解析技能文件 {file_path}: {e}")

        self.skills_found = skills
        logger.info(f"OpenClaw 扫描完成: 发现 {len(skills)} 个技能")
        return skills

    def scan_memory(self) -> List[Dict[str, Any]]:
        """扫描记忆/历史文件"""
        memories = []
        for mem_file in ["memory.json", "history.json", "conversations.json"]:
            fp = self.source_path / mem_file
            if fp.exists():
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        memories.extend(data)
                    else:
                        memories.append(data)
                except Exception as e:
                    logger.warning(f"无法解析记忆文件 {fp}: {e}")

        self.memories_found = memories
        return memories

    def convert_skill(self, raw_skill: Dict[str, Any]) -> Dict[str, Any]:
        """将 OpenClaw 技能转换为 Kaelis 格式"""
        return {
            "name": raw_skill.get("name", "imported_skill"),
            "task_type": raw_skill.get("task_type", "general"),
            "description": raw_skill.get("description", ""),
            "params": raw_skill.get("params", {}),
            "success_rate": raw_skill.get("success_rate", 0.5),
            "rating": raw_skill.get("rating", 3.0),
            "source": "openclaw_import",
            "imported_at": __import__("datetime").datetime.now().isoformat(),
        }

    def import_skills(self) -> Dict[str, Any]:
        """导入技能到 Kaelis 技能市场"""
        from core.skill_manager import get_skill_manager

        sm = get_skill_manager()
        skills = self.scan_skills()
        imported = 0
        failed = 0

        for s in skills:
            try:
                converted = self.convert_skill(s["raw"])
                sm.register_skill(converted)
                imported += 1
            except Exception as e:
                logger.error(f"技能导入失败 {s['name']}: {e}")
                failed += 1

        return {
            "total_found": len(skills),
            "imported": imported,
            "failed": failed,
        }

    def import_memory_to_l2(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """将历史记录导入 L2 情景记忆"""
        from core.memory_manager_v2 import get_memory_manager

        mm = get_memory_manager()
        memories = self.scan_memory()
        imported = 0

        for mem in memories:
            try:
                key = mem.get("id", mem.get("key", f"oc_import_{imported}"))
                mm.write(
                    layer="L2",
                    key=f"openclaw_{key}",
                    value=mem,
                    metadata={"source": "openclaw_migration", "migrated": True},
                    user_id=user_id,
                )
                imported += 1
            except Exception as e:
                logger.warning(f"记忆导入失败: {e}")

        return {"total_found": len(memories), "imported": imported}
