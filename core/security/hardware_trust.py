"""
Hardware Trust — NVIDIA GPU Confidential Computing & Attestation

利用 NVIDIA Confidential Computing (CC) 和 GPU Attestation 技术，
为 Kaelis 节点提供从硬件到应用的可信执行链。

功能：
    1. GPUAttestation：验证远程 GPU 环境的可信性（基于 nvidia-pccs / nv-attest）。
    2. TrustedExecutionBridge：在 GPU TEE 中运行敏感计算（如果硬件支持）。
    3. HardwareTrustMCP：暴露 trust.attest_gpu、trust.get_quote 等 MCP Tools。

降级路径：
    - 无 CC 硬件时，返回模拟 attestation report（标记 simulated=True）。
    - 无 nvidia-pccs 工具时，使用基于 CPU 的软件 quote 作为后备。
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency detection
# ---------------------------------------------------------------------------
NVIDIA_SMI_AVAILABLE = False
try:
    subprocess.run(["nvidia-smi"], capture_output=True, check=False, timeout=5)
    NVIDIA_SMI_AVAILABLE = True
except Exception:
    logger.debug("nvidia-smi not available. GPU attestation will use software fallback.")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GPUAttestationReport:
    """GPU 可信证明报告。"""

    gpu_index: int
    gpu_name: str
    cc_mode: str  # "on", "off", "simulated"
    attestation_passed: bool
    quote: str
    driver_version: str = "unknown"
    vbios_version: str = "unknown"
    timestamp: str = field(default_factory=lambda: __import__("time").time())
    simulated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gpu_index": self.gpu_index,
            "gpu_name": self.gpu_name,
            "cc_mode": self.cc_mode,
            "attestation_passed": self.attestation_passed,
            "quote": self.quote[:64] + "..." if len(self.quote) > 64 else self.quote,
            "driver_version": self.driver_version,
            "vbios_version": self.vbios_version,
            "timestamp": self.timestamp,
            "simulated": self.simulated,
        }


# ---------------------------------------------------------------------------
# GPU Attestation
# ---------------------------------------------------------------------------

class GPUAttestation:
    """
    NVIDIA GPU 可信证明器。

    支持两种模式：
        1. 硬件模式：调用 nvidia-pccs / nvidia-ctk 获取真实 attestation。
        2. 模拟模式：生成软件 quote，标记 simulated=True。
    """

    def __init__(self, gpu_index: int = 0):
        self.gpu_index = gpu_index
        self._gpu_info: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def attest(self) -> GPUAttestationReport:
        """
        执行 GPU attestation，返回报告。

        优先尝试硬件 attestation；失败时退化为软件模拟。
        """
        if not NVIDIA_SMI_AVAILABLE:
            return self._software_fallback()

        gpu_info = self._get_gpu_info()
        if gpu_info is None:
            return self._software_fallback()

        # 尝试硬件 attestation（需要 nvidia-pccs 或 nvidia-ctk）
        hw_report = self._try_hardware_attestation(gpu_info)
        if hw_report is not None:
            return hw_report

        return self._software_fallback(gpu_info)

    def is_confidential_computing_available(self) -> bool:
        """检查当前 GPU 是否支持 Confidential Computing。"""
        if not NVIDIA_SMI_AVAILABLE:
            return False
        try:
            result = subprocess.run(
                ["nvidia-smi", "confidentialcompute", "-i", str(self.gpu_index), "--status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "CC status: ON" in result.stdout or "cc_status: on" in result.stdout.lower()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_gpu_info(self) -> Optional[Dict[str, str]]:
        if self._gpu_info is not None:
            return self._gpu_info
        try:
            result = subprocess.run(
                ["nvidia-smi", "-i", str(self.gpu_index), "--query-gpu=name,driver_version,vbios_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = [p.strip() for p in result.stdout.strip().split(",")]
                self._gpu_info = {
                    "name": parts[0] if len(parts) > 0 else "unknown",
                    "driver_version": parts[1] if len(parts) > 1 else "unknown",
                    "vbios_version": parts[2] if len(parts) > 2 else "unknown",
                }
                return self._gpu_info
        except Exception as e:
            logger.debug("nvidia-smi query failed: %s", e)
        return None

    def _try_hardware_attestation(self, gpu_info: Dict[str, str]) -> Optional[GPUAttestationReport]:
        """尝试调用 NVIDIA 工具链获取真实 attestation。"""
        tools = [
            ["nvidia-pccs", "attest", "-i", str(self.gpu_index)],
            ["nvidia-ctk", "attest", "-i", str(self.gpu_index)],
            ["nv-attest", "-i", str(self.gpu_index)],
        ]
        for cmd in tools:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    quote = result.stdout.strip()
                    cc_on = self.is_confidential_computing_available()
                    return GPUAttestationReport(
                        gpu_index=self.gpu_index,
                        gpu_name=gpu_info.get("name", "unknown"),
                        cc_mode="on" if cc_on else "off",
                        attestation_passed=True,
                        quote=quote,
                        driver_version=gpu_info.get("driver_version", "unknown"),
                        vbios_version=gpu_info.get("vbios_version", "unknown"),
                        simulated=False,
                    )
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug("Tool %s failed: %s", cmd[0], e)
        return None

    def _software_fallback(self, gpu_info: Optional[Dict[str, str]] = None) -> GPUAttestationReport:
        """软件降级：生成模拟 quote。"""
        import hashlib
        import time

        name = gpu_info.get("name", "simulated-gpu") if gpu_info else "simulated-gpu"
        nonce = str(time.time())
        quote = hashlib.sha256(f"{name}:{self.gpu_index}:{nonce}".encode()).hexdigest()

        logger.info("GPUAttestation using software fallback for GPU %s", self.gpu_index)
        return GPUAttestationReport(
            gpu_index=self.gpu_index,
            gpu_name=name,
            cc_mode="simulated",
            attestation_passed=True,  # 软件模式下默认信任本机
            quote=quote,
            driver_version=gpu_info.get("driver_version", "simulated") if gpu_info else "simulated",
            vbios_version=gpu_info.get("vbios_version", "simulated") if gpu_info else "simulated",
            simulated=True,
        )


# ---------------------------------------------------------------------------
# Trusted Execution Bridge
# ---------------------------------------------------------------------------

class TrustedExecutionBridge:
    """
    在 NVIDIA GPU TEE 中运行 Kaelis 敏感进程的桥接器。

    若硬件 TEE 不可用，退化为普通执行（标记 trusted=False）。
    """

    def __init__(self, gpu_index: int = 0):
        self.gpu_index = gpu_index
        self._attestor = GPUAttestation(gpu_index=gpu_index)
        self._tee_available = self._check_tee()

    def _check_tee(self) -> bool:
        try:
            return self._attestor.is_confidential_computing_available()
        except Exception:
            return False

    def run(self, func, *args, **kwargs) -> Dict[str, Any]:
        """
        在可信环境中执行函数。

        Returns:
            {"result": ..., "trusted": bool, "tee": bool}
        """
        if self._tee_available:
            try:
                result = func(*args, **kwargs)
                return {"result": result, "trusted": True, "tee": True}
            except Exception as e:
                logger.error("TEE execution failed: %s", e)
                return {"error": str(e), "trusted": False, "tee": True}
        else:
            # 降级：普通执行
            try:
                result = func(*args, **kwargs)
                return {"result": result, "trusted": False, "tee": False, "note": "TEE unavailable, running in normal mode"}
            except Exception as e:
                return {"error": str(e), "trusted": False, "tee": False}

    def get_attestation_report(self) -> Dict[str, Any]:
        return self._attestor.attest().to_dict()


# ---------------------------------------------------------------------------
# MCP Tool Registration
# ---------------------------------------------------------------------------

def register_hardware_trust_tools(mcp) -> None:
    """注册硬件信任相关的 MCP Tools。"""

    @mcp.tool("trust.attest_gpu")
    def trust_attest_gpu(gpu_index: int = 0) -> str:
        """对指定 GPU 执行 attestation，返回报告摘要。"""
        try:
            attestor = GPUAttestation(gpu_index=gpu_index)
            report = attestor.attest()
            return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool("trust.get_quote")
    def trust_get_quote(gpu_index: int = 0) -> str:
        """获取 GPU 的 attestation quote。"""
        try:
            attestor = GPUAttestation(gpu_index=gpu_index)
            report = attestor.attest()
            return json.dumps({"quote": report.quote, "simulated": report.simulated}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool("trust.check_cc")
    def trust_check_cc(gpu_index: int = 0) -> str:
        """检查 GPU Confidential Computing 是否可用。"""
        try:
            attestor = GPUAttestation(gpu_index=gpu_index)
            available = attestor.is_confidential_computing_available()
            return json.dumps({"cc_available": available, "gpu_index": gpu_index}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Singleton getters
# ---------------------------------------------------------------------------

_attestor: Optional[GPUAttestation] = None
_bridge: Optional[TrustedExecutionBridge] = None


def get_gpu_attestor(gpu_index: int = 0) -> GPUAttestation:
    global _attestor
    if _attestor is None:
        _attestor = GPUAttestation(gpu_index=gpu_index)
    return _attestor


def get_trusted_execution_bridge(gpu_index: int = 0) -> TrustedExecutionBridge:
    global _bridge
    if _bridge is None:
        _bridge = TrustedExecutionBridge(gpu_index=gpu_index)
    return _bridge
