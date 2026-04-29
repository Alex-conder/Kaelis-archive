"""Tests for core.security.hardware_trust."""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.security.hardware_trust import (
    GPUAttestation,
    GPUAttestationReport,
    TrustedExecutionBridge,
    get_gpu_attestor,
    get_trusted_execution_bridge,
    register_hardware_trust_tools,
)


# ==========================================================================
# GPUAttestationReport
# ==========================================================================

class TestGPUAttestationReport:
    def test_to_dict_truncates_long_quote(self):
        r = GPUAttestationReport(
            gpu_index=0,
            gpu_name="H100",
            cc_mode="on",
            attestation_passed=True,
            quote="a" * 100,
        )
        d = r.to_dict()
        assert d["quote"].endswith("...")
        assert d["cc_mode"] == "on"

    def test_to_dict_short_quote_intact(self):
        r = GPUAttestationReport(
            gpu_index=0,
            gpu_name="A100",
            cc_mode="off",
            attestation_passed=False,
            quote="short",
        )
        d = r.to_dict()
        assert d["quote"] == "short"


# ==========================================================================
# GPUAttestation — Software Fallback
# ==========================================================================

class TestGPUAttestationSoftwareFallback:
    def test_attest_without_nvidia_smi(self):
        with patch("core.security.hardware_trust.NVIDIA_SMI_AVAILABLE", False):
            attestor = GPUAttestation(gpu_index=0)
            report = attestor.attest()
        assert report.simulated is True
        assert report.cc_mode == "simulated"
        assert report.attestation_passed is True
        assert len(report.quote) == 64  # sha256 hex

    def test_software_fallback_with_gpu_info(self):
        attestor = GPUAttestation(gpu_index=0)
        info = {"name": "RTX-4090", "driver_version": "535.104", "vbios_version": "95.02"}
        report = attestor._software_fallback(info)
        assert report.gpu_name == "RTX-4090"
        assert report.driver_version == "535.104"
        assert report.simulated is True


# ==========================================================================
# GPUAttestation — Hardware Path (mocked)
# ==========================================================================

class TestGPUAttestationHardwarePath:
    def test_try_hardware_attestation_success(self):
        attestor = GPUAttestation(gpu_index=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="real_quote_abc")
            report = attestor._try_hardware_attestation(
                {"name": "H100", "driver_version": "535", "vbios_version": "95"}
            )
        assert report is not None
        assert report.simulated is False
        assert report.quote == "real_quote_abc"

    def test_try_hardware_attestation_all_tools_missing(self):
        attestor = GPUAttestation(gpu_index=0)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            report = attestor._try_hardware_attestation({"name": "H100"})
        assert report is None

    def test_is_confidential_computing_available_true(self):
        attestor = GPUAttestation(gpu_index=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="CC status: ON", returncode=0)
            assert attestor.is_confidential_computing_available() is True

    def test_is_confidential_computing_available_false(self):
        attestor = GPUAttestation(gpu_index=0)
        with patch("subprocess.run", side_effect=RuntimeError("no gpu")):
            assert attestor.is_confidential_computing_available() is False

    def test_get_gpu_info_success(self):
        attestor = GPUAttestation(gpu_index=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="H100, 535.104, 95.02\n")
            info = attestor._get_gpu_info()
        assert info["name"] == "H100"
        assert info["driver_version"] == "535.104"

    def test_get_gpu_info_failure(self):
        attestor = GPUAttestation(gpu_index=0)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert attestor._get_gpu_info() is None


# ==========================================================================
# TrustedExecutionBridge
# ==========================================================================

class TestTrustedExecutionBridge:
    def test_run_in_tee_when_available(self):
        with patch.object(GPUAttestation, "is_confidential_computing_available", return_value=True):
            bridge = TrustedExecutionBridge()
            result = bridge.run(lambda: 42)
        assert result["result"] == 42
        assert result["trusted"] is True
        assert result["tee"] is True

    def test_run_without_tee(self):
        with patch.object(GPUAttestation, "is_confidential_computing_available", return_value=False):
            bridge = TrustedExecutionBridge()
            result = bridge.run(lambda: 42)
        assert result["result"] == 42
        assert result["trusted"] is False
        assert result["tee"] is False
        assert "note" in result

    def test_run_function_raises(self):
        with patch.object(GPUAttestation, "is_confidential_computing_available", return_value=False):
            bridge = TrustedExecutionBridge()
            result = bridge.run(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert "error" in result

    def test_get_attestation_report(self):
        with patch.object(GPUAttestation, "is_confidential_computing_available", return_value=False):
            bridge = TrustedExecutionBridge()
            report = bridge.get_attestation_report()
        assert report["gpu_index"] == 0
        assert report["simulated"] is True


# ==========================================================================
# MCP Tools
# ==========================================================================

class TestHardwareTrustMcpTools:
    def test_register_tools(self):
        mock_mcp = MagicMock()
        register_hardware_trust_tools(mock_mcp)
        mock_mcp.tool.assert_any_call("trust.attest_gpu")
        mock_mcp.tool.assert_any_call("trust.get_quote")
        mock_mcp.tool.assert_any_call("trust.check_cc")

    def test_tool_attest_gpu(self):
        # Verify the tool registration path by calling the registered function
        # through a synthetic mcp mock that captures the decorated function
        captured = {}
        def fake_tool(name):
            def decorator(fn):
                captured[name] = fn
                return fn
            return decorator

        mock_mcp = MagicMock()
        mock_mcp.tool = fake_tool
        register_hardware_trust_tools(mock_mcp)

        assert "trust.attest_gpu" in captured
        with patch.object(GPUAttestation, "attest", return_value=GPUAttestationReport(
            gpu_index=0, gpu_name="Sim", cc_mode="simulated", attestation_passed=True, quote="q"
        )):
            out = json.loads(captured["trust.attest_gpu"](0))
        assert out["gpu_name"] == "Sim"


# ==========================================================================
# Singleton
# ==========================================================================

class TestHardwareTrustSingleton:
    def test_get_gpu_attestor_singleton(self):
        a1 = get_gpu_attestor()
        a2 = get_gpu_attestor()
        assert a1 is a2

    def test_get_trusted_execution_bridge_singleton(self):
        b1 = get_trusted_execution_bridge()
        b2 = get_trusted_execution_bridge()
        assert b1 is b2
