"""
OpenClaw 技能/记忆一键迁移工具

P22-004: 自动扫描、安全审核、迁移报告
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.migration.openclaw_connector import OpenClawConnector
from core.security.risk_auditor import RiskAuditor
from core.security.risk_gateway import RiskDecision
from core.skills.sandbox_tester import SkillSandboxTester

logger = logging.getLogger(__name__)

# 标准扫描目录
DEFAULT_SCAN_DIRS = [
    Path.home() / ".openclaw",
    Path("./claw-skills"),
    Path("./.openclaw"),
]


class OpenClawImporter:
    """
    OpenClaw 一键迁移导入器。

    流程：扫描 → 安全审核 → 沙箱测试 → 导入 → 报告
    """

    def __init__(self, source_path: Optional[str] = None):
        self.source_path = Path(source_path) if source_path else None
        self.connector = OpenClawConnector(str(self.source_path)) if self.source_path else None
        self.risk_auditor = RiskAuditor()
        self.sandbox = SkillSandboxTester()
        self.report: Dict[str, Any] = {
            "skills": {"scanned": 0, "passed": 0, "blocked": 0, "needs_review": 0, "items": []},
            "memories": {"scanned": 0, "imported": 0, "failed": 0, "items": []},
        }

    def scan_openclaw_skills(self) -> List[Dict[str, Any]]:
        """自动扫描标准目录中的 OpenClaw 技能"""
        all_skills = []
        scanned_dirs = []

        # 如果指定了 source_path，优先扫描
        if self.connector:
            skills = self.connector.scan_skills()
            all_skills.extend(skills)
            scanned_dirs.append(str(self.source_path))

        # 扫描默认目录
        for scan_dir in DEFAULT_SCAN_DIRS:
            if scan_dir.exists() and scan_dir.is_dir():
                try:
                    conn = OpenClawConnector(str(scan_dir))
                    skills = conn.scan_skills()
                    all_skills.extend(skills)
                    scanned_dirs.append(str(scan_dir))
                except Exception as e:
                    logger.warning(f"扫描目录失败 {scan_dir}: {e}")

        logger.info(f"OpenClaw 扫描完成: 目录 {scanned_dirs}, 技能 {len(all_skills)} 个")
        return all_skills

    def _security_review(self, skill_data: Dict[str, Any]) -> Dict[str, Any]:
        """对技能进行安全审核和沙箱测试"""
        name = skill_data.get("name", "unknown")
        raw = skill_data.get("raw", {})

        # 1. RiskAuditor 静态审核
        decision, reason = self.risk_auditor.evaluate(
            source="openclaw_migration",
            tool_name=name,
            params=raw,
        )

        if decision == RiskDecision.BLOCK:
            return {
                "name": name,
                "status": "blocked",
                "reason": reason,
                "risk_level": "HIGH",
            }

        # 2. 沙箱测试
        sandbox_report = self.sandbox.test_skill(raw)
        if sandbox_report.risk_level in ("HIGH", "CRITICAL"):
            return {
                "name": name,
                "status": "blocked",
                "reason": f"Sandbox detected {sandbox_report.risk_level} risk",
                "risk_level": sandbox_report.risk_level,
                "issues": [i["pattern"] for i in sandbox_report.static_scan.get("issues", [])],
            }

        if decision == RiskDecision.CONFIRM:
            return {
                "name": name,
                "status": "needs_review",
                "reason": reason,
                "risk_level": "MEDIUM",
            }

        return {
            "name": name,
            "status": "passed",
            "reason": "Security checks passed",
            "risk_level": sandbox_report.risk_level,
        }

    def import_skill(self, skill_path: str) -> Dict[str, Any]:
        """
        导入单个 OpenClaw 技能。

        路径可以是目录或具体的 .json/.claw 文件。
        """
        path = Path(skill_path)
        if not path.exists():
            return {"success": False, "error": f"Path not found: {skill_path}"}

        # 如果是目录，使用 connector 扫描
        if path.is_dir():
            self.connector = OpenClawConnector(str(path))
            skills = self.connector.scan_skills()
        else:
            # 单个文件
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                skills = [{"source_file": str(path), "name": data.get("name", path.stem), "description": data.get("description", ""), "raw": data}]
            except Exception as e:
                return {"success": False, "error": str(e)}

        results = []
        for skill_info in skills:
            review = self._security_review(skill_info)
            item = {
                "name": skill_info["name"],
                "source_file": skill_info.get("source_file", ""),
                **review,
            }

            if review["status"] == "passed":
                try:
                    converted = self.connector.convert_skill(skill_info["raw"]) if self.connector else skill_info["raw"]
                    from core.skill_manager import get_skill_manager
                    sm = get_skill_manager()
                    sm.register_skill(converted)
                    item["imported"] = True
                except Exception as e:
                    item["imported"] = False
                    item["error"] = str(e)
            else:
                item["imported"] = False

            results.append(item)
            self.report["skills"]["items"].append(item)

        self._update_report_counts()
        return {"success": True, "results": results}

    def import_memory(self, memory_path: str) -> Dict[str, Any]:
        """导入 OpenClaw 记忆文件到 L2 Episodic 记忆"""
        path = Path(memory_path)
        if not path.exists():
            return {"success": False, "error": f"Path not found: {memory_path}"}

        if self.connector is None:
            self.connector = OpenClawImporter._connector_for_path(path)

        try:
            result = self.connector.import_memory_to_l2(user_id="anonymous")
            self.report["memories"]["scanned"] += result.get("total_found", 0)
            self.report["memories"]["imported"] += result.get("imported", 0)
            self.report["memories"]["failed"] += result.get("total_found", 0) - result.get("imported", 0)
            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _connector_for_path(path: Path) -> OpenClawConnector:
        """根据文件路径推断合适的 source_path"""
        if path.is_dir():
            return OpenClawConnector(str(path))
        # 对于单个文件，使用其父目录
        return OpenClawConnector(str(path.parent))

    def run_migration(self, directory: Optional[str] = None) -> Dict[str, Any]:
        """
        执行完整迁移：扫描所有技能 → 安全审核 → 导入 → 生成报告
        """
        if directory:
            self.source_path = Path(directory)
            self.connector = OpenClawConnector(str(self.source_path))

        # 扫描技能
        skills = self.scan_openclaw_skills()
        self.report["skills"]["scanned"] = len(skills)

        # 逐个审核和导入
        for skill_info in skills:
            review = self._security_review(skill_info)
            item = {
                "name": skill_info["name"],
                "source_file": skill_info.get("source_file", ""),
                **review,
            }

            if review["status"] == "passed":
                try:
                    converted = self.connector.convert_skill(skill_info["raw"])
                    from core.skill_manager import get_skill_manager
                    sm = get_skill_manager()
                    sm.register_skill(converted)
                    item["imported"] = True
                except Exception as e:
                    item["imported"] = False
                    item["error"] = str(e)
            else:
                item["imported"] = False

            self.report["skills"]["items"].append(item)

        # 记忆迁移
        if self.connector:
            mem_result = self.connector.import_memory_to_l2()
            self.report["memories"]["scanned"] = mem_result.get("total_found", 0)
            self.report["memories"]["imported"] = mem_result.get("imported", 0)

        self._update_report_counts()
        logger.info(f"OpenClaw migration report: {self.report['skills']}")
        return dict(self.report)

    def _update_report_counts(self):
        """更新报告计数"""
        items = self.report["skills"]["items"]
        self.report["skills"]["passed"] = sum(1 for i in items if i["status"] == "passed" and i.get("imported"))
        self.report["skills"]["blocked"] = sum(1 for i in items if i["status"] == "blocked")
        self.report["skills"]["needs_review"] = sum(1 for i in items if i["status"] == "needs_review")

    def get_report(self) -> Dict[str, Any]:
        """获取当前迁移报告"""
        return dict(self.report)
