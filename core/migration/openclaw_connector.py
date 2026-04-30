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

    @staticmethod
    def _parse_md_sections(text: str, section_names: set) -> Dict[str, str]:
        """从 Markdown 文本中提取指定的二级标题内容"""
        import re
        sections: Dict[str, str] = {}
        targets = {name.lower() for name in section_names}
        pattern = re.compile(r"^##\s+(.+?)\s*\n(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
        for match in pattern.finditer(text):
            heading = match.group(1).strip().lower()
            content = match.group(2).strip()
            if heading in targets:
                sections[heading] = content
        return sections

    def scan_agent_md(self) -> List[Dict[str, Any]]:
        """扫描并解析 OpenClaw agent.md 自然语言协议文件"""
        agent_files = list(self.source_path.rglob("agent.md"))
        results = []
        for fp in agent_files:
            try:
                text = fp.read_text(encoding="utf-8")
                sections = self._parse_md_sections(text, {"role", "capabilities", "constraints"})
                results.append({
                    "source_file": str(fp.relative_to(self.source_path)),
                    "role": sections.get("role", ""),
                    "capabilities": sections.get("capabilities", ""),
                    "constraints": sections.get("constraints", ""),
                    "raw": text,
                })
            except Exception as e:
                logger.warning(f"无法解析 agent.md {fp}: {e}")
        logger.info(f"OpenClaw agent.md 扫描完成: 发现 {len(results)} 个协议文件")
        return results

    def scan_soul_md(self) -> List[Dict[str, Any]]:
        """扫描并解析 OpenClaw soul.md 人格文件"""
        soul_files = list(self.source_path.rglob("soul.md"))
        results = []
        for fp in soul_files:
            try:
                text = fp.read_text(encoding="utf-8")
                sections = self._parse_md_sections(text, {"personality", "tone", "values", "identity", "behavior"})
                results.append({
                    "source_file": str(fp.relative_to(self.source_path)),
                    "personality": sections.get("personality", ""),
                    "tone": sections.get("tone", ""),
                    "values": sections.get("values", ""),
                    "identity": sections.get("identity", ""),
                    "behavior": sections.get("behavior", ""),
                    "raw": text,
                })
            except Exception as e:
                logger.warning(f"无法解析 soul.md {fp}: {e}")
        logger.info(f"OpenClaw soul.md 扫描完成: 发现 {len(results)} 个人格文件")
        return results

    def convert_context_engine(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """将 ContextEngine 插件数据迁移为 Kaelis L2 情景记忆格式"""
        from datetime import datetime
        now = datetime.now().isoformat()
        record_id = context_data.get("id") or context_data.get("session_id") or context_data.get("key", "unknown")
        return {
            "key": f"context_engine_{record_id}",
            "value": {
                "memory_type": "episodic",
                "subtype": "context_engine",
                "timestamp": context_data.get("timestamp", context_data.get("created_at", now)),
                "content": context_data.get("content", context_data),
                "session_id": context_data.get("session_id"),
                "plugin_version": context_data.get("version"),
            },
            "metadata": {
                "source": "context_engine_migration",
                "migrated": True,
                "original_plugin": context_data.get("plugin", "context_engine"),
            },
        }

    def run_full_migration(self, target_user_id: str) -> Dict[str, Any]:
        """一键执行 OpenClaw 全量迁移：扫描 → 转换 → 导入 → 报告"""
        from datetime import datetime
        from core.memory_manager_v2 import get_memory_manager

        start_time = datetime.now().isoformat()

        # 1. 扫描所有数据源
        skills = self.scan_skills()
        memories = self.scan_memory()
        agents = self.scan_agent_md()
        souls = self.scan_soul_md()

        # 2. 导入技能
        skill_report = self.import_skills()

        # 3. 导入历史记忆
        memory_report = self.import_memory_to_l2(user_id=target_user_id)

        # 4. 扫描并迁移 ContextEngine 数据
        context_files = []
        for pattern in ["context_engine.json", "context.json"]:
            fp = self.source_path / pattern
            if fp.exists():
                context_files.append(fp)
            context_files.extend(self.source_path.rglob(pattern))

        seen = set()
        unique_context_files = []
        for fp in context_files:
            rp = str(fp.resolve())
            if rp not in seen:
                seen.add(rp)
                unique_context_files.append(fp)

        mm = get_memory_manager()
        context_imported = 0
        context_failed = 0
        for fp in unique_context_files:
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else [data]
                for entry in entries:
                    converted = self.convert_context_engine(entry)
                    mm.write(
                        layer="L2",
                        key=converted["key"],
                        value=converted["value"],
                        metadata=converted["metadata"],
                        user_id=target_user_id,
                    )
                    context_imported += 1
            except Exception as e:
                logger.warning(f"ContextEngine 迁移失败 {fp}: {e}")
                context_failed += 1

        end_time = datetime.now().isoformat()

        report = {
            "target_user_id": target_user_id,
            "started_at": start_time,
            "completed_at": end_time,
            "scan": {
                "skills_found": len(skills),
                "memories_found": len(memories),
                "agent_md_found": len(agents),
                "soul_md_found": len(souls),
                "context_engine_files": len(unique_context_files),
            },
            "import": {
                "skills": skill_report,
                "memories": memory_report,
                "context_engine": {
                    "imported": context_imported,
                    "failed": context_failed,
                },
            },
            "details": {
                "skills": skills,
                "memories": memories,
                "agents": agents,
                "souls": souls,
            },
        }
        logger.info(f"OpenClaw 全量迁移完成: {report['scan']}")
        return report
