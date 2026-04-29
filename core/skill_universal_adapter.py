"""
通用技能纳管引擎 — Universal Skill Adapter

让技能在不同 Agent 框架间自由流动的协议层。
支持：agentskills.io、OpenClaw、Hermes、MCP Tool、自定义 Python。

用法:
    from core.skill_universal_adapter import UniversalSkillAdapter
    adapter = UniversalSkillAdapter()
    skill = adapter.import_skill("~/skills/data_analysis.claw")
    report = adapter.batch_import("~/skills/")
"""

import ast
import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.skill_manager import get_skill_manager

logger = logging.getLogger(__name__)


class SkillFormat(Enum):
    UNKNOWN = "unknown"
    AGENTSKILLS_MD = "agentskills_md"
    OPENCLAW_JSON = "openclaw_json"
    HERMES_MD = "hermes_md"
    MCP_TOOL = "mcp_tool"
    PYTHON_FUNCTION = "python_function"


@dataclass
class CompatibilityReport:
    skill_name: str
    source_format: SkillFormat
    can_register: bool
    warnings: List[str]
    missing_deps: List[str]
    suggested_params: Dict[str, Any]


class UniversalSkillAdapter:
    """
    通用技能适配器：自动识别、转换、注册任意来源的技能。
    """

    def __init__(self):
        self.sm = get_skill_manager()

    # ======================================================================
    # 格式检测
    # ======================================================================

    def detect_format(self, source_path: str) -> SkillFormat:
        """自动识别技能文件格式"""
        p = Path(source_path)
        if not p.exists():
            return SkillFormat.UNKNOWN

        # 文件扩展名判断
        if p.suffix == ".claw":
            return SkillFormat.OPENCLAW_JSON

        if p.suffix == ".py":
            if self._has_skill_decorator(p):
                return SkillFormat.PYTHON_FUNCTION
            return SkillFormat.UNKNOWN

        if p.suffix in (".json", ".yaml", ".yml"):
            return self._detect_json_format(p)

        # Markdown 深度检测
        if p.suffix == ".md":
            return self._detect_md_format(p)

        # 目录检测（MCP Server）
        if p.is_dir() and (p / "package.json").exists():
            return SkillFormat.MCP_TOOL

        return SkillFormat.UNKNOWN

    def _has_skill_decorator(self, py_path: Path) -> bool:
        """检测 Python 文件是否包含 @skill 装饰器"""
        try:
            tree = ast.parse(py_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Name) and dec.id == "skill":
                            return True
        except Exception:
            pass
        return False

    def _detect_json_format(self, p: Path) -> SkillFormat:
        """检测 JSON 内容的格式类型"""
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return SkillFormat.UNKNOWN

        if "name" in data and "task_type" in data and "params" in data:
            return SkillFormat.AGENTSKILLS_MD  # agentskills JSON 格式
        if "commands" in data or "actions" in data:
            return SkillFormat.OPENCLAW_JSON
        return SkillFormat.UNKNOWN

    def _detect_md_format(self, p: Path) -> SkillFormat:
        """检测 Markdown 文件格式类型"""
        text = p.read_text(encoding="utf-8", errors="ignore")
        # agentskills.io 标准
        if "agentskills.io" in text or "## Metadata" in text:
            return SkillFormat.AGENTSKILLS_MD
        # Hermes 风格
        if text.startswith("# SKILL") or "## 技能名称" in text:
            return SkillFormat.HERMES_MD
        return SkillFormat.UNKNOWN

    # ======================================================================
    # 导入转换
    # ======================================================================

    def import_skill(self, source_path: str, format: Optional[SkillFormat] = None) -> Tuple[Dict[str, Any], CompatibilityReport]:
        """
        导入单个技能。
        返回 (skill_dict, compatibility_report)
        """
        fmt = format or self.detect_format(source_path)
        p = Path(source_path)

        if fmt == SkillFormat.UNKNOWN:
            report = CompatibilityReport(
                skill_name=p.name,
                source_format=fmt,
                can_register=False,
                warnings=["无法识别技能格式"],
                missing_deps=[],
                suggested_params={},
            )
            return {}, report

        if fmt == SkillFormat.OPENCLAW_JSON:
            skill, report = self._import_openclaw(p)
        elif fmt == SkillFormat.HERMES_MD:
            skill, report = self._import_hermes(p)
        elif fmt == SkillFormat.AGENTSKILLS_MD:
            skill, report = self._import_agentskills(p)
        elif fmt == SkillFormat.PYTHON_FUNCTION:
            skill, report = self._import_python(p)
        elif fmt == SkillFormat.MCP_TOOL:
            skill, report = self._import_mcp(p)
        else:
            skill, report = {}, CompatibilityReport(
                skill_name=p.name, source_format=fmt,
                can_register=False, warnings=["未支持的格式"],
                missing_deps=[], suggested_params={},
            )

        if report.can_register and skill:
            try:
                self.sm.register_skill(skill)
                logger.info(f"技能已注册: {skill.get('name', 'unknown')} [{fmt.value}]")
            except Exception as e:
                report.can_register = False
                report.warnings.append(f"注册失败: {e}")

        return skill, report

    def batch_import(self, directory: str) -> Dict[str, Any]:
        """
        批量扫描目录，自动纳管所有识别到的技能。
        返回统计报告。
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return {"error": f"目录不存在: {directory}"}

        stats = {
            "total_scanned": 0,
            "recognized": 0,
            "registered": 0,
            "failed": 0,
            "skipped": 0,
            "details": [],
        }

        # 支持的扩展名
        patterns = ["*.md", "*.json", "*.claw", "*.py"]
        files = []
        for pat in patterns:
            files.extend(dir_path.rglob(pat))

        for f in files:
            stats["total_scanned"] += 1
            try:
                skill, report = self.import_skill(str(f))
                if report.source_format == SkillFormat.UNKNOWN:
                    stats["skipped"] += 1
                    continue
                stats["recognized"] += 1
                if report.can_register:
                    stats["registered"] += 1
                else:
                    stats["failed"] += 1
                stats["details"].append({
                    "file": str(f.relative_to(dir_path)),
                    "format": report.source_format.value,
                    "name": report.skill_name,
                    "status": "registered" if report.can_register else "failed",
                    "warnings": report.warnings,
                })
            except Exception as e:
                stats["failed"] += 1
                stats["details"].append({
                    "file": str(f.relative_to(dir_path)),
                    "format": "unknown",
                    "status": "error",
                    "warnings": [str(e)],
                })

        logger.info(f"批量导入完成: {stats['registered']}/{stats['recognized']} 已注册")
        return stats

    # ======================================================================
    # 导出
    # ======================================================================

    def export_skill(self, skill_id: str, target_format: str = "agentskills") -> Optional[Dict[str, Any]]:
        """
        将 Kaelis 技能导出为指定格式。
        当前支持: agentskills
        """
        skill = self.sm.get_skill(skill_id)
        if not skill:
            logger.warning(f"技能不存在: {skill_id}")
            return None

        if target_format == "agentskills":
            return {
                "name": skill.name,
                "task_type": skill.task_type,
                "description": skill.description,
                "params": skill.params,
                "success_rate": skill.success_rate,
                "rating": skill.rating,
                "source": "kaelis_export",
            }

        logger.warning(f"未支持的导出格式: {target_format}")
        return None

    # ======================================================================
    # 各格式具体导入逻辑
    # ======================================================================

    def _import_openclaw(self, p: Path) -> Tuple[Dict[str, Any], CompatibilityReport]:
        """导入 OpenClaw .claw / .json 技能"""
        data = json.loads(p.read_text(encoding="utf-8"))
        name = data.get("name", p.stem)
        skill = {
            "name": name,
            "task_type": data.get("task_type", "general"),
            "description": data.get("description", ""),
            "params": data.get("params", {}),
            "success_rate": data.get("success_rate", 0.5),
            "rating": data.get("rating", 3.0),
            "source": "openclaw_import",
        }
        report = CompatibilityReport(
            skill_name=name,
            source_format=SkillFormat.OPENCLAW_JSON,
            can_register=True,
            warnings=[],
            missing_deps=[],
            suggested_params=skill["params"],
        )
        return skill, report

    def _import_hermes(self, p: Path) -> Tuple[Dict[str, Any], CompatibilityReport]:
        """导入 Hermes SKILL.md"""
        text = p.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        name = p.stem
        description = ""
        params = {}

        # 简单解析 Markdown 标题和描述
        for line in lines:
            if line.startswith("# ") and not description:
                name = line.lstrip("# ").strip()
            elif line.strip() and not description and not line.startswith("#"):
                description = line.strip()
            # 参数行检测
            if "param" in line.lower() or "参数" in line:
                m = re.search(r"`([^`]+)`\s*[:：]\s*(.+)", line)
                if m:
                    params[m.group(1)] = {"type": "string", "description": m.group(2)}

        skill = {
            "name": name,
            "task_type": "general",
            "description": description or f"Imported from Hermes: {p.name}",
            "params": params,
            "success_rate": 0.5,
            "rating": 3.0,
            "source": "hermes_import",
        }
        report = CompatibilityReport(
            skill_name=name,
            source_format=SkillFormat.HERMES_MD,
            can_register=True,
            warnings=["Markdown 参数解析为启发式，建议人工校验"] if not params else [],
            missing_deps=[],
            suggested_params=params,
        )
        return skill, report

    def _import_agentskills(self, p: Path) -> Tuple[Dict[str, Any], CompatibilityReport]:
        """导入 agentskills.io 标准技能"""
        if p.suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            # Markdown 解析
            data = self._parse_agentskills_md(p)

        name = data.get("name", p.stem)
        skill = {
            "name": name,
            "task_type": data.get("task_type", "general"),
            "description": data.get("description", ""),
            "params": data.get("params", {}),
            "success_rate": data.get("success_rate", 0.5),
            "rating": data.get("rating", 3.0),
            "source": "agentskills_import",
        }
        report = CompatibilityReport(
            skill_name=name,
            source_format=SkillFormat.AGENTSKILLS_MD,
            can_register=True,
            warnings=[],
            missing_deps=[],
            suggested_params=skill["params"],
        )
        return skill, report

    def _import_python(self, p: Path) -> Tuple[Dict[str, Any], CompatibilityReport]:
        """导入 Python 函数技能"""
        text = p.read_text(encoding="utf-8")
        tree = ast.parse(text)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name) and dec.id == "skill":
                        name = node.name
                        # 提取参数
                        params = {}
                        for arg in node.args.args:
                            params[arg.arg] = {"type": "auto", "description": ""}
                        skill = {
                            "name": name,
                            "task_type": "general",
                            "description": ast.get_docstring(node) or f"Python function: {name}",
                            "params": params,
                            "source": "python_import",
                            "code_path": str(p),
                        }
                        report = CompatibilityReport(
                            skill_name=name,
                            source_format=SkillFormat.PYTHON_FUNCTION,
                            can_register=True,
                            warnings=["Python 函数技能需确保依赖已安装"],
                            missing_deps=[],
                            suggested_params=params,
                        )
                        return skill, report

        return {}, CompatibilityReport(
            skill_name=p.name, source_format=SkillFormat.PYTHON_FUNCTION,
            can_register=False, warnings=["未找到 @skill 装饰器"],
            missing_deps=[], suggested_params={},
        )

    def _import_mcp(self, p: Path) -> Tuple[Dict[str, Any], CompatibilityReport]:
        """导入 MCP Server 定义"""
        # 读取 package.json 或 mcp.json
        pkg = json.loads((p / "package.json").read_text(encoding="utf-8"))
        name = pkg.get("name", p.name)
        skill = {
            "name": name,
            "task_type": "mcp_tool",
            "description": pkg.get("description", f"MCP Server: {name}"),
            "params": {},
            "source": "mcp_import",
            "server_path": str(p),
        }
        report = CompatibilityReport(
            skill_name=name,
            source_format=SkillFormat.MCP_TOOL,
            can_register=True,
            warnings=["MCP Server 技能需手动配置启动参数"],
            missing_deps=[],
            suggested_params={},
        )
        return skill, report

    # ======================================================================
    # 辅助解析
    # ======================================================================

    def _parse_agentskills_md(self, p: Path) -> Dict[str, Any]:
        """解析 agentskills.io Markdown 格式"""
        text = p.read_text(encoding="utf-8", errors="ignore")
        result = {"name": p.stem, "description": "", "params": {}}

        # 简单解析 ## 区块
        current_section = None
        for line in text.splitlines():
            if line.startswith("## "):
                current_section = line.lstrip("## ").strip().lower()
                continue
            if current_section == "metadata":
                m = re.match(r"-\s*(\w+)\s*[:：]\s*(.+)", line)
                if m:
                    result[m.group(1)] = m.group(2)
            elif current_section in ("description", "desc") and line.strip():
                result["description"] = line.strip()
            elif current_section == "parameters":
                m = re.match(r"-\s*`?([^`:`]+)`?\s*[:：]\s*(.+)", line)
                if m:
                    result["params"][m.group(1).strip()] = {"type": "string", "description": m.group(2)}

        return result
