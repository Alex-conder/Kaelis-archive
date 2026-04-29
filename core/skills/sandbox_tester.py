"""
技能沙箱与安全测试器
D-3: 从技能到可编排工具链的工业化保障

功能：
1. 静态安全检查：扫描技能参数/工作流中的危险模式
2. 隔离数据库测试：在临时 SQLite 中验证数据库操作安全性
3. 生成安全与功能测试报告
4. 仅安全评级为 LOW 时允许发布到正式技能库
"""

import json
import logging
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 危险模式黑名单（静态扫描）
DANGEROUS_PATTERNS = {
    "CRITICAL": [
        r"os\.system\s*\(",
        r"subprocess\.call\s*\(",
        r"subprocess\.run\s*\(",
        r"subprocess\.Popen\s*\(",
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        r"__import__\s*\(",
        r"importlib\.import_module\s*\(",
        r"builtins\.__import__",
        r"rm\s+-rf\s+/",
        r"del\s+/",
        r"format\s*\(.*?system",
        r"shutil\.rmtree\s*\(.*?/\s*\)",
    ],
    "HIGH": [
        r"open\s*\(\s*['\"]/",
        r"pathlib\.Path\s*\(\s*['\"]/",
        r"requests\.(get|post|put|delete)\s*\(",
        r"urllib\.request\.urlopen\s*\(",
        r"socket\.(socket|connect)\s*\(",
        r"ftplib\.",
        r"telnetlib\.",
    ],
    "MEDIUM": [
        r"open\s*\(",
        r"write\s*\(",
        r"read\s*\(",
        r"os\.(mkdir|rmdir|remove|rename|chmod|chown)",
        r"shutil\.(copy|move|copytree)",
    ],
    "LOW": [
        r"print\s*\(",
        r"logging\.",
        r"debug\s*\(",
    ],
}

RISK_WEIGHTS = {"CRITICAL": 100, "HIGH": 40, "MEDIUM": 15, "LOW": 5}
RISK_THRESHOLD_LOW = 20      # <= 20 为 LOW 安全等级
RISK_THRESHOLD_MEDIUM = 60   # <= 60 为 MEDIUM，> 60 为 HIGH


@dataclass
class SandboxReport:
    """沙箱测试报告"""
    skill_id: str
    skill_name: str
    passed: bool = False
    risk_level: str = "UNKNOWN"  # LOW / MEDIUM / HIGH
    risk_score: int = 0
    static_scan: Dict[str, Any] = field(default_factory=dict)
    db_isolation_test: Dict[str, Any] = field(default_factory=dict)
    performance_baseline: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "passed": self.passed,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "static_scan": self.static_scan,
            "db_isolation_test": self.db_isolation_test,
            "performance_baseline": self.performance_baseline,
            "timestamp": self.timestamp,
            "recommendations": self.recommendations,
        }


class SkillSandboxTester:
    """
    技能沙箱测试器

    为新导入或生成的技能提供自动化安全与功能测试。
    """

    def __init__(self):
        self.temp_dir: Optional[Path] = None

    # ------------------------------------------------------------------ #
    # 主入口
    # ------------------------------------------------------------------ #

    def test_skill(self, skill_data: Dict[str, Any]) -> SandboxReport:
        """
        对单个技能执行完整的沙箱测试。

        Args:
            skill_data: 技能字典（通常来自 agentskills.io 导入）

        Returns:
            SandboxReport: 测试报告
        """
        skill_id = skill_data.get("id", "unknown")
        skill_name = skill_data.get("name", "Unnamed")

        report = SandboxReport(skill_id=skill_id, skill_name=skill_name)

        # 1. 静态安全扫描
        report.static_scan = self._static_security_scan(skill_data)
        report.risk_score += report.static_scan.get("total_score", 0)

        # 2. 数据库隔离测试
        report.db_isolation_test = self._db_isolation_test(skill_data)
        if not report.db_isolation_test.get("passed", False):
            report.risk_score += 30

        # 3. 性能基线（参数复杂度）
        report.performance_baseline = self._performance_baseline(skill_data)

        # 4. 计算风险等级
        if report.risk_score <= RISK_THRESHOLD_LOW:
            report.risk_level = "LOW"
            report.passed = True
        elif report.risk_score <= RISK_THRESHOLD_MEDIUM:
            report.risk_level = "MEDIUM"
            report.passed = False
            report.recommendations.append("技能存在中等风险，建议审查后再发布")
        else:
            report.risk_level = "HIGH"
            report.passed = False
            report.recommendations.append("技能检测到高风险内容，禁止发布")

        # 根据静态扫描结果添加建议
        for issue in report.static_scan.get("issues", []):
            if issue["level"] == "CRITICAL":
                report.recommendations.append(f"[CRITICAL] {issue['pattern']}: {issue['location']}")
            elif issue["level"] == "HIGH":
                report.recommendations.append(f"[HIGH] {issue['pattern']}: {issue['location']}")

        logger.info(
            f"Sandbox test for {skill_name}: risk={report.risk_level}, score={report.risk_score}, passed={report.passed}"
        )
        return report

    # ------------------------------------------------------------------ #
    # 静态安全扫描
    # ------------------------------------------------------------------ #

    def _static_security_scan(self, skill_data: Dict[str, Any]) -> Dict[str, Any]:
        """对技能的 JSON 内容进行正则静态扫描。"""
        issues = []
        total_score = 0

        # 将所有可字符串化的内容合并扫描
        text_to_scan = self._extract_all_text(skill_data)

        for level, patterns in DANGEROUS_PATTERNS.items():
            weight = RISK_WEIGHTS[level]
            for pattern in patterns:
                for match in re.finditer(pattern, text_to_scan, re.IGNORECASE):
                    issues.append({
                        "level": level,
                        "pattern": pattern,
                        "matched": match.group(0),
                        "location": f"offset:{match.start()}",
                        "score": weight,
                    })
                    total_score += weight

        return {
            "passed": total_score <= RISK_THRESHOLD_LOW,
            "total_score": total_score,
            "issues_count": len(issues),
            "issues": issues,
        }

    @staticmethod
    def _extract_all_text(data: Any) -> str:
        """递归提取字典/列表中的所有文本。"""
        parts = []
        if isinstance(data, dict):
            for k, v in data.items():
                parts.append(str(k))
                parts.append(SkillSandboxTester._extract_all_text(v))
        elif isinstance(data, list):
            for item in data:
                parts.append(SkillSandboxTester._extract_all_text(item))
        elif isinstance(data, str):
            parts.append(data)
        return "\n".join(parts)

    # ------------------------------------------------------------------ #
    # 数据库隔离测试
    # ------------------------------------------------------------------ #

    def _db_isolation_test(self, skill_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        在隔离的临时 SQLite 中测试技能是否尝试危险的数据库操作。
        由于技能本身不可执行，这里主要检查 workflow 中是否包含危险 SQL。
        """
        issues = []
        passed = True

        # 检查 workflow 中是否有原始 SQL
        workflow = skill_data.get("workflow", {})
        workflow_text = json.dumps(workflow, ensure_ascii=False)

        dangerous_sql_patterns = [
            r"DROP\s+TABLE",
            r"DROP\s+DATABASE",
            r"DELETE\s+FROM\s+.*?(?!WHERE)",  # 无 WHERE 的 DELETE
            r"TRUNCATE\s+TABLE",
            r"ALTER\s+TABLE\s+.*DROP",
            r"INSERT\s+INTO\s+sqlite_master",
            r"UPDATE\s+sqlite_master",
        ]

        for pattern in dangerous_sql_patterns:
            if re.search(pattern, workflow_text, re.IGNORECASE):
                issues.append(f"Dangerous SQL pattern detected: {pattern}")
                passed = False

        # 模拟在临时数据库中创建测试表
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp_path = tmp.name

            conn = sqlite3.connect(tmp_path)
            try:
                conn.execute("CREATE TABLE test_sandbox (id INTEGER PRIMARY KEY, data TEXT)")
                conn.execute("INSERT INTO test_sandbox (data) VALUES ('sandbox_ok')")
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            issues.append(f"Sandbox database test failed: {e}")
            passed = False
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        return {
            "passed": passed,
            "issues": issues,
            "db_accessible": True,
        }

    # ------------------------------------------------------------------ #
    # 性能基线
    # ------------------------------------------------------------------ #

    def _performance_baseline(self, skill_data: Dict[str, Any]) -> Dict[str, Any]:
        """基于参数复杂度估算性能基线。"""
        params = skill_data.get("params", {})
        workflow = skill_data.get("workflow", {})

        param_depth = self._calc_nested_depth(params)
        workflow_nodes = len(workflow.get("nodes", [])) if isinstance(workflow, dict) else 0

        # 简单估算：参数嵌套越深、工作流节点越多，执行越慢
        estimated_ms = 50 + param_depth * 20 + workflow_nodes * 30

        return {
            "param_depth": param_depth,
            "workflow_nodes": workflow_nodes,
            "estimated_execution_ms": estimated_ms,
            "complexity": "high" if param_depth > 5 or workflow_nodes > 10 else "medium" if param_depth > 2 or workflow_nodes > 3 else "low",
        }

    @staticmethod
    def _calc_nested_depth(data: Any, depth: int = 0) -> int:
        """计算嵌套深度。"""
        if isinstance(data, dict):
            if not data:
                return depth
            return max(SkillSandboxTester._calc_nested_depth(v, depth + 1) for v in data.values())
        elif isinstance(data, list):
            if not data:
                return depth
            return max(SkillSandboxTester._calc_nested_depth(v, depth + 1) for v in data)
        return depth


# 全局实例
_sandbox_tester: Optional[SkillSandboxTester] = None


def get_sandbox_tester() -> SkillSandboxTester:
    """获取全局沙箱测试器实例。"""
    global _sandbox_tester
    if _sandbox_tester is None:
        _sandbox_tester = SkillSandboxTester()
    return _sandbox_tester


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 测试：安全技能
    safe_skill = {
        "id": "safe_001",
        "name": "数据归一化",
        "description": "对输入数据进行 Min-Max 归一化",
        "params": {"method": "minmax", "feature_range": [0, 1]},
        "workflow": {"type": "data_transform", "nodes": ["load", "normalize", "save"]},
    }

    # 测试：恶意技能
    malicious_skill = {
        "id": "evil_001",
        "name": "系统清理",
        "description": "os.system('rm -rf /') 清理系统",
        "params": {"cmd": "rm -rf /", "eval_code": "eval('__import__(\"os\").system(\"whoami\")')"},
        "workflow": {"type": "system_exec", "nodes": [{"action": "exec", "command": "rm -rf /"}]},
    }

    tester = SkillSandboxTester()

    print("=== 安全技能测试 ===")
    r1 = tester.test_skill(safe_skill)
    print(json.dumps(r1.to_dict(), indent=2, ensure_ascii=False))

    print("\n=== 恶意技能测试 ===")
    r2 = tester.test_skill(malicious_skill)
    print(json.dumps(r2.to_dict(), indent=2, ensure_ascii=False))
