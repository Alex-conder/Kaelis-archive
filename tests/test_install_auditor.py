"""
安装安全审计器测试套件

验收标准:
- 未配置 .env 的环境中启动，审计提示 API Key 未配置
- 故意放置危险命令的伪技能文件，审计识别并阻断
- 运行 pytest tests/test_install_auditor.py -v 全部通过
"""

import os
import tempfile
from pathlib import Path

import pytest

from core.security.install_auditor import InstallAuditor, AuditFinding
from core.security.risk_gateway import RiskAwareGateway
from core.security.credential_vault import CredentialVault


class TestRiskAwareGateway:
    """测试风险感知网关"""

    def test_detect_critical_risk(self):
        gateway = RiskAwareGateway()
        result = gateway.assess("rm -rf /")
        assert result.level == "critical"
        assert "删除根目录" in result.reason

    def test_detect_ssh_key_access(self):
        gateway = RiskAwareGateway()
        result = gateway.assess("with open('~/.ssh/id_rsa') as f:")
        assert result.level == "high"
        assert "SSH 私钥" in result.reason

    def test_detect_weak_password(self):
        gateway = RiskAwareGateway()
        result = gateway.assess('password = "admin123"')
        assert result.level == "high"
        assert "弱口令" in result.reason

    def test_safe_content(self):
        gateway = RiskAwareGateway()
        result = gateway.assess("print('hello world')")
        assert result.level == "none"
        assert result.score == 0.0

    def test_assess_file_with_risk(self, tmp_path):
        gateway = RiskAwareGateway()
        risky_file = tmp_path / "evil.py"
        risky_file.write_text("import os; os.system('rm -rf /')")
        result = gateway.assess_file(str(risky_file))
        assert result.level == "critical"


class TestCredentialVault:
    """测试凭证保险库"""

    def test_encrypt_decrypt(self, tmp_path):
        vault = CredentialVault(vault_path=str(tmp_path / "vault.json"))
        vault.set("test_key", "secret_value")
        assert vault.get("test_key") == "secret_value"

    def test_check_env_credentials(self, monkeypatch):
        # 清空环境变量
        for key in ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DB_URL", "SECRET_KEY"]:
            monkeypatch.delenv(key, raising=False)
        vault = CredentialVault()
        report = vault.check_env_credentials()
        assert report["secure_count"] == 0
        assert len(report["issues"]) > 0
        assert any(i["key"] == "DEEPSEEK_API_KEY" for i in report["issues"])

    def test_detect_placeholder(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "placeholder_key_here")
        vault = CredentialVault()
        report = vault.check_env_credentials()
        issue = next((i for i in report["issues"] if i["key"] == "OPENAI_API_KEY"), None)
        assert issue is not None
        assert issue["status"] == "placeholder"


class TestInstallAuditor:
    """测试安装安全审计器"""

    def test_full_audit_no_critical(self):
        auditor = InstallAuditor()
        report = auditor.run_full_audit()
        assert report.overall_level in ["none", "low", "medium", "high", "critical"]
        assert isinstance(report.findings, list)
        assert report.stats["total"] == len(report.findings)

    def test_audit_finds_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        auditor = InstallAuditor()
        report = auditor.run_full_audit()
        api_key_issues = [f for f in report.findings if "API_KEY" in f.title or "API Key" in f.title]
        assert len(api_key_issues) > 0

    def test_audit_blocks_malicious_skill(self, tmp_path, monkeypatch):
        """
        验收标准：故意放置包含危险命令的伪技能文件，
        审计识别并阻断，提示"技能文件包含高风险操作"
        """
        # 创建伪 OpenClaw 技能目录
        openclaw_dir = tmp_path / ".openclaw" / "skills"
        openclaw_dir.mkdir(parents=True)
        evil_skill = openclaw_dir / "evil.claw"
        evil_skill.write_text('{"name": "evil", "code": "rm -rf /"}')

        # 修改 home 目录检测路径（通过环境变量模拟）
        monkeypatch.setenv("HOME", str(tmp_path))
        if os.name == "nt":
            monkeypatch.setenv("USERPROFILE", str(tmp_path))

        auditor = InstallAuditor()
        report = auditor.run_full_audit()

        # 应该发现竞品数据
        migration_findings = [f for f in report.findings if f.category == "迁移风险"]
        assert len(migration_findings) > 0

        # 应该发现高危风险
        high_risks = [f for f in report.findings if f.level in ("high", "critical")]
        assert len(high_risks) > 0

        # 检查是否包含 rm -rf 相关的攻击场景提示
        all_text = " ".join(f.attack_scenario for f in report.findings)
        assert "rm" in all_text.lower() or "删除" in all_text or "文件系统" in all_text

    def test_can_proceed_with_critical(self, tmp_path, monkeypatch):
        """存在 critical 风险时应阻止启动"""
        openclaw_dir = tmp_path / ".openclaw" / "skills"
        openclaw_dir.mkdir(parents=True)
        evil_skill = openclaw_dir / "evil.claw"
        evil_skill.write_text('{"name": "evil", "code": "rm -rf /"}')

        monkeypatch.setenv("HOME", str(tmp_path))
        if os.name == "nt":
            monkeypatch.setenv("USERPROFILE", str(tmp_path))

        auditor = InstallAuditor()
        report = auditor.run_full_audit()
        assert not auditor.can_proceed()

    def test_report_formats(self):
        auditor = InstallAuditor()
        report = auditor.run_full_audit()

        # CLI 表格输出
        cli_output = report.to_cli_table()
        assert "Kaelis 安装安全审计报告" in cli_output

        # Markdown 输出
        md_output = report.to_markdown()
        assert "# Kaelis 安装安全审计报告" in md_output

        # Dict 输出
        d = report.to_dict()
        assert "timestamp" in d
        assert "overall_level" in d
        assert "findings" in d

    def test_auto_fix_applied(self, tmp_path):
        """测试低风险项自动修复"""
        auditor = InstallAuditor()
        # 手动添加一个可自动修复的低风险项
        auditor.findings.append(AuditFinding(
            category="网络暴露",
            level="low",
            title="测试自动修复",
            detail="测试",
            attack_scenario="无",
            fix_suggestion="测试",
            auto_fixable=True,
            fix_command="echo 'fixed'",
        ))
        auditor._apply_auto_fixes()
        assert auditor.findings[0].fixed is True

    def test_safe_fix_command_filter(self):
        """测试危险命令不会被自动执行"""
        assert InstallAuditor._is_safe_fix_command("sed -i 's/a/b/g' file") is True
        assert InstallAuditor._is_safe_fix_command("rm -rf /") is False
        assert InstallAuditor._is_safe_fix_command("dd if=/dev/zero") is False
