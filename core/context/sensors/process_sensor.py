"""
Process Sensor (Prompt 3)

Monitors running processes and returns top CPU/memory consumers.
"""

import logging
import subprocess
from typing import Any, Dict, List

from core.context.sensor_base import BaseContextSensor

logger = logging.getLogger(__name__)

PSUTIL_AVAILABLE = False
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    logger.warning("psutil not installed. ProcessSensor will use PowerShell fallback.")


SENSITIVE_PATTERNS = ("token", "key", "secret", "password", "credential")


class ProcessSensor(BaseContextSensor):
    """
    Collects top 10 processes by CPU and memory usage.
    Filters sensitive command-line arguments.
    """

    def __init__(self, sensor_id: str = "process", privacy_level: str = "internal"):
        super().__init__(sensor_id, privacy_level)

    def collect(self) -> Dict[str, Any]:
        """Collect process information."""
        processes = []

        if PSUTIL_AVAILABLE:
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "cmdline"]):
                try:
                    info = proc.info
                    processes.append({
                        "pid": info["pid"],
                        "name": info["name"] or "unknown",
                        "cpu_percent": round(info["cpu_percent"] or 0.0, 2),
                        "memory_percent": round(info["memory_percent"] or 0.0, 2),
                        "cmdline": " ".join(info["cmdline"] or []),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            # Fallback: PowerShell on Windows
            try:
                result = subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        "Get-Process | Select-Object Id,ProcessName,CPU,WorkingSet | ConvertTo-Json -Compress",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    for item in data:
                        processes.append({
                            "pid": item.get("Id", 0),
                            "name": item.get("ProcessName", "unknown"),
                            "cpu_percent": round(float(item.get("CPU") or 0), 2),
                            "memory_percent": 0.0,  # Not directly available
                            "cmdline": "",
                        })
            except Exception as e:
                logger.warning(f"PowerShell fallback failed: {e}")

        # Sort by CPU desc, then memory desc, take top 10
        top_cpu = sorted(processes, key=lambda p: p["cpu_percent"], reverse=True)[:10]
        top_mem = sorted(processes, key=lambda p: p["memory_percent"], reverse=True)[:10]

        return {
            "total_processes": len(processes),
            "top_cpu": top_cpu,
            "top_memory": top_mem,
        }

    def filter_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive tokens from process command lines."""
        def _redact_cmdline(cmdline: str) -> str:
            lower = cmdline.lower()
            if any(pat in lower for pat in SENSITIVE_PATTERNS):
                return "<redacted>"
            return cmdline

        filtered_cpu = []
        for proc in data.get("top_cpu", []):
            proc = dict(proc)
            proc["cmdline"] = _redact_cmdline(proc.get("cmdline", ""))
            filtered_cpu.append(proc)

        filtered_mem = []
        for proc in data.get("top_memory", []):
            proc = dict(proc)
            proc["cmdline"] = _redact_cmdline(proc.get("cmdline", ""))
            filtered_mem.append(proc)

        return {
            "total_processes": data.get("total_processes", 0),
            "top_cpu": filtered_cpu,
            "top_memory": filtered_mem,
        }
