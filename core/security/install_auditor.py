"""
安装安全审计器 — InstallAuditor

在 Kaelis 首次启动时执行全面安全体检，建立用户信任的第一道闸门。

用法:
    from core.security import InstallAuditor
    auditor = InstallAuditor()
    report = auditor.run_full_audit()
    print(report.to_cli_table())
"""

import json
import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.security.risk_gateway import RiskAwareGateway, RiskAssessment
from core.security.credential_vault import CredentialVault
from core.migration.smart_detector import scan_for_competitors

logger = logging.getLogger(__name__)


@dataclass
class AuditFinding:
    category: str
    level: str  # none, low, medium, high, critical
    title: str
    detail: str
    attack_scenario: str
    fix_suggestion: str
    auto_fixable: bool
    fix_command: Optional[str] = None
    fixed: bool = False


@dataclass
class AuditReport:
    timestamp: str
    overall_level: str
    findings: List[AuditFinding] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall_level": self.overall_level,
            "findings": [
                {
                    "category": f.category,
                    "level": f.level,
                    "title": f.title,
                    "detail": f.detail,
                    "attack_scenario": f.attack_scenario,
                    "fix_suggestion": f.fix_suggestion,
                    "auto_fixable": f.auto_fixable,
                    "fix_command": f.fix_command,
                    "fixed": f.fixed,
                }
                for f in self.findings
            ],
            "stats": self.stats,
        }

    def to_cli_table(self) -> str:
        """生成彩色终端表格"""
        colors = {
            "critical": "\033[91m",  # 红色
            "high": "\033[93m",      # 黄色
            "medium": "\033[94m",    # 蓝色
            "low": "\033[92m",       # 绿色
            "none": "\033[90m",      # 灰色
            "reset": "\033[0m",
        }
        lines = [
            "",
            "╔" + "═" * 78 + "╗",
            "║" + " Kaelis 安装安全审计报告 ".center(78) + "║",
            "╠" + "═" * 78 + "╣",
            f"║ 时间: {self.timestamp:<68} ║",
            f"║ 总体风险: {self.overall_level.upper():<62} ║",
            "╠" + "─" * 78 + "╣",
        ]

        if not self.findings:
            lines.append("║" + " ✅ 未发现安全风险，系统状态良好 ".center(78) + "║")
        else:
            for f in self.findings:
                c = colors.get(f.level, "")
                r = colors["reset"]
                lines.append(f"║ {c}[{f.level.upper():8}]{r} {f.category}: {f.title:<55} ║")
                lines.append(f"║      {f.detail[:72]:<72} ║")
                if f.attack_scenario != "无":
                    lines.append(f"║      ⚠️  攻击场景: {f.attack_scenario[:55]:<55} ║")
                if f.fix_suggestion != "无需修复":
                    fix = f"[AUTO] {f.fix_command}" if f.auto_fixable else f.fix_suggestion
                    lines.append(f"║      💡 修复建议: {fix[:55]:<55} ║")
                lines.append("║" + " " * 78 + "║")

        lines.append("╚" + "═" * 78 + "╝")
        lines.append("")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """生成 Markdown 报告"""
        lines = [
            "# Kaelis 安装安全审计报告",
            f"\n- **审计时间**: {self.timestamp}",
            f"- **总体风险**: {self.overall_level.upper()}",
            f"- **发现问题**: {len(self.findings)} 项",
            "",
        ]
        for f in self.findings:
            icon = "🔴" if f.level == "critical" else "🟠" if f.level == "high" else "🟡" if f.level == "medium" else "🟢"
            lines.append(f"## {icon} [{f.level.upper()}] {f.title}")
            lines.append(f"- **类别**: {f.category}")
            lines.append(f"- **详情**: {f.detail}")
            lines.append(f"- **攻击场景**: {f.attack_scenario}")
            lines.append(f"- **修复建议**: {f.fix_suggestion}")
            if f.auto_fixable and f.fix_command:
                lines.append(f"- **自动修复命令**: `{f.fix_command}`")
            lines.append("")
        return "\n".join(lines)


class InstallAuditor:
    """
    安装安全审计器。
    在首次启动时执行多维安全体检。
    """

    def __init__(self, gateway: Optional[RiskAwareGateway] = None, vault: Optional[CredentialVault] = None):
        self.gateway = gateway or RiskAwareGateway()
        self.vault = vault or CredentialVault()
        self.findings: List[AuditFinding] = []

    def run_full_audit(self) -> AuditReport:
        """执行完整安全审计"""
        self.findings = []

        # 五大维度审计
        self._audit_environment()
        self._audit_competitor_migration()
        self._audit_install_integrity()
        self._audit_network_exposure()
        self._audit_credentials()

        # 自动修复低风险项
        self._apply_auto_fixes()

        # 计算总体风险
        overall = self._calculate_overall_level()
        stats = self._calculate_stats()

        report = AuditReport(
            timestamp=datetime.now().isoformat(),
            overall_level=overall,
            findings=self.findings,
            stats=stats,
        )

        logger.info(f"安装审计完成: {stats['total']} 项发现, 总体风险 {overall}")
        return report

    # ======================================================================
    # 维度1: 环境安全
    # ======================================================================

    def _audit_environment(self) -> None:
        """审计运行环境安全"""
        # 检测高风险目录
        cwd = Path.cwd()
        risky_paths = ["/tmp", "/var/tmp", "/mnt", "/media"]
        for risky in risky_paths:
            if str(cwd).startswith(risky):
                self._add_finding(
                    category="环境安全",
                    level="high",
                    title="在高风险目录运行",
                    detail=f"当前工作目录 {cwd} 位于临时/可移动存储区",
                    attack_scenario="临时目录可能被系统清理或遭受符号链接攻击",
                    fix_suggestion="将 Kaelis 迁移到用户主目录的固定位置（如 ~/Kaelis）",
                    auto_fixable=False,
                )

        # 检测只读文件系统（简化：检查能否写入当前目录）
        try:
            test_file = cwd / ".kaelis_write_test"
            test_file.write_text("test")
            test_file.unlink()
        except OSError:
            self._add_finding(
                category="环境安全",
                level="medium",
                title="当前目录可能为只读",
                detail="无法在当前目录创建文件，可能导致功能异常",
                attack_scenario="只读环境可能阻止安全更新和日志写入",
                fix_suggestion="确保运行目录具有读写权限: chmod 755 <dir>",
                auto_fixable=False,
            )

        # 检测 .env 文件弱口令
        env_file = cwd / ".env"
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8", errors="ignore")
            assessment = self.gateway.assess(content, source=".env")
            if assessment.level != "none":
                self._add_finding(
                    category="环境安全",
                    level=assessment.level,
                    title=".env 文件存在安全风险",
                    detail=assessment.reason,
                    attack_scenario=assessment.attack_scenario,
                    fix_suggestion=assessment.fix_suggestion,
                    auto_fixable=assessment.auto_fixable,
                    fix_command=assessment.fix_command,
                )

    # ======================================================================
    # 维度2: 竞品数据迁移风险
    # ======================================================================

    def _audit_competitor_migration(self) -> None:
        """审计竞品数据迁移风险"""
        competitors = scan_for_competitors()
        if not competitors:
            return

        for comp in competitors:
            # 对竞品路径进行风险扫描
            assessment = self.gateway.assess_file(comp["path"])
            level = assessment.level if assessment.level != "none" else "low"

            self._add_finding(
                category="迁移风险",
                level=level,
                title=f"检测到 {comp['name'].upper()} 遗留数据",
                detail=f"路径: {comp['path']}, 大小: {comp['size_human']}, 类型: {comp['type']}",
                attack_scenario="竞品技能可能包含未审查的代码，导入后可能执行恶意操作",
                fix_suggestion="使用 UniversalSkillAdapter 导入前进行安全扫描，或手动审查每个技能文件",
                auto_fixable=False,
            )

            # 深度扫描技能文件
            comp_path = Path(comp["path"])
            if comp_path.exists():
                for skill_file in comp_path.rglob("*"):
                    if skill_file.is_file() and skill_file.suffix in (".json", ".claw", ".py", ".md"):
                        file_assessment = self.gateway.assess_file(str(skill_file))
                        if file_assessment.level in ("high", "critical"):
                            self._add_finding(
                                category="迁移风险",
                                level=file_assessment.level,
                                title=f"竞品技能文件存在高危风险: {skill_file.name}",
                                detail=file_assessment.reason,
                                attack_scenario=file_assessment.attack_scenario,
                                fix_suggestion=f"立即删除或隔离该文件: {skill_file}",
                                auto_fixable=False,
                            )

    # ======================================================================
    # 维度3: 安装完整性
    # ======================================================================

    def _audit_install_integrity(self) -> None:
        """审计安装完整性"""
        # 检查 requirements.txt 一致性
        req_file = Path("requirements.txt")
        if req_file.exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "check"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    self._add_finding(
                        category="安装完整性",
                        level="medium",
                        title="依赖包存在冲突",
                        detail=result.stdout.strip()[:200] or "pip check 检测到依赖问题",
                        attack_scenario="依赖冲突可能导致安全模块加载失败，留下防御缺口",
                        fix_suggestion="运行 'pip check' 查看详情，并升级/降级冲突包",
                        auto_fixable=False,
                    )
            except Exception as e:
                self._add_finding(
                    category="安装完整性",
                    level="low",
                    title="无法验证依赖完整性",
                    detail=str(e),
                    attack_scenario="无法检测依赖是否存在已知 CVE 漏洞",
                    fix_suggestion="确保网络通畅，或手动运行 pip check",
                    auto_fixable=False,
                )

        # 检查必要系统库
        required_libs = ["sqlite3"]
        for lib in required_libs:
            try:
                __import__(lib)
            except ImportError:
                self._add_finding(
                    category="安装完整性",
                    level="high",
                    title=f"缺少必要系统库: {lib}",
                    detail=f"Python 无法导入 {lib} 模块",
                    attack_scenario="核心功能不可用，可能导致数据存储回退到不安全模式",
                    fix_suggestion=f"安装对应系统包（如 apt install libsqlite3-dev）",
                    auto_fixable=False,
                )

    # ======================================================================
    # 维度4: 网络暴露面
    # ======================================================================

    def _audit_network_exposure(self) -> None:
        """审计网络暴露面"""
        # 检查配置文件中的监听地址
        config_files = ["config/*.json", ".env", "config_memory_safe.json"]
        for pattern in config_files:
            for config_file in Path(".").glob(pattern):
                content = config_file.read_text(encoding="utf-8", errors="ignore")
                if "0.0.0.0" in content:
                    self._add_finding(
                        category="网络暴露",
                        level="medium",
                        title=f"配置文件存在 0.0.0.0 监听: {config_file}",
                        detail="服务监听在所有网络接口，可能暴露给外部网络",
                        attack_scenario="未授权用户可能从局域网或公网访问本地 API",
                        fix_suggestion="将 0.0.0.0 改为 127.0.0.1",
                        auto_fixable=True,
                        fix_command="sed -i 's/0.0.0.0/127.0.0.1/g' " + str(config_file),
                    )

    # ======================================================================
    # 维度5: 凭证安全
    # ======================================================================

    def _audit_credentials(self) -> None:
        """审计凭证安全"""
        # 检查环境变量凭证
        cred_report = self.vault.check_env_credentials()
        for issue in cred_report["issues"]:
            level = issue["risk"]
            if issue["status"] == "missing":
                self._add_finding(
                    category="凭证安全",
                    level=level,
                    title=f"{issue['key']} 未配置",
                    detail=issue["reason"],
                    attack_scenario="无直接安全风险，但相关 AI 功能将不可用",
                    fix_suggestion=f"配置环境变量: export {issue['key']}=your_key_here",
                    auto_fixable=False,
                )
            elif issue["status"] in ("weak", "placeholder"):
                self._add_finding(
                    category="凭证安全",
                    level=level,
                    title=f"{issue['key']} 存在安全风险",
                    detail=issue["reason"],
                    attack_scenario="弱凭证易被暴力破解，泄露后可能导致云服务被恶意使用",
                    fix_suggestion="生成强密码并更新配置，或迁移到 CredentialVault 加密存储",
                    auto_fixable=True,
                    fix_command="python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
                )

        # 检查 .env 中是否有明文 API Key
        env_file = Path(".env")
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                if "API_KEY" in line and "=" in line:
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and len(val) > 10 and not val.startswith("$"):
                        self._add_finding(
                            category="凭证安全",
                            level="medium",
                            title=".env 中存在明文 API Key",
                            detail="API Key 以明文存储在 .env 文件中",
                            attack_scenario=".env 文件可能被意外提交到 Git 或被其他程序读取",
                            fix_suggestion="迁移到 CredentialVault 加密存储，并将 .env 加入 .gitignore",
                            auto_fixable=False,
                        )
                        break

    # ======================================================================
    # 自动修复
    # ======================================================================

    def _apply_auto_fixes(self) -> None:
        """自动修复低风险项"""
        for finding in self.findings:
            if finding.auto_fixable and finding.level in ("low", "medium"):
                if finding.fix_command:
                    try:
                        # 仅执行安全的修复命令
                        if self._is_safe_fix_command(finding.fix_command):
                            subprocess.run(finding.fix_command, shell=True, check=True, timeout=10)
                            finding.fixed = True
                            logger.info(f"自动修复已应用: {finding.title}")
                    except Exception as e:
                        logger.warning(f"自动修复失败: {finding.title} - {e}")

    @staticmethod
    def _is_safe_fix_command(cmd: str) -> bool:
        """判断修复命令是否安全可自动执行"""
        dangerous = ["rm", "dd", "mkfs", "> /dev", ":(){"]
        return not any(d in cmd for d in dangerous)

    # ======================================================================
    # 辅助方法
    # ======================================================================

    def _add_finding(self, **kwargs) -> None:
        self.findings.append(AuditFinding(**kwargs))

    def _calculate_overall_level(self) -> str:
        """计算总体风险等级"""
        levels = [f.level for f in self.findings]
        if "critical" in levels:
            return "critical"
        if "high" in levels:
            return "high"
        if "medium" in levels:
            return "medium"
        if "low" in levels:
            return "low"
        return "none"

    def _calculate_stats(self) -> Dict[str, Any]:
        return {
            "total": len(self.findings),
            "critical": sum(1 for f in self.findings if f.level == "critical"),
            "high": sum(1 for f in self.findings if f.level == "high"),
            "medium": sum(1 for f in self.findings if f.level == "medium"),
            "low": sum(1 for f in self.findings if f.level == "low"),
            "auto_fixed": sum(1 for f in self.findings if f.fixed),
        }

    def can_proceed(self) -> bool:
        """判断是否允许继续启动（无 critical 风险）"""
        return self._calculate_overall_level() != "critical"
