"""
MCP VSCode 工具 - 允许 Agent 操作本机 VSCode 工作区
Phase 1: MCP 基础工具框架

功能:
  - open_file:   在 VSCode 中打开指定文件
  - write_file:  写入文件内容
  - run_command: 在工作区执行终端命令

依赖: 本机需安装 `code` 命令（VSCode CLI）
"""
import os
import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class VSCodeTool:
    """VSCode 远程操作工具"""

    def __init__(self, workspace_path: str = "."):
        self.workspace_path = os.path.abspath(workspace_path)

    def open_file(self, file_path: str, line: int = 1) -> Dict[str, Any]:
        """在 VSCode 中打开指定文件到指定行"""
        try:
            full_path = os.path.join(self.workspace_path, file_path)
            cmd = ["code", "--goto", f"{full_path}:{line}"]
            subprocess.run(cmd, check=True, capture_output=True)
            return {"success": True, "action": "open_file", "file": file_path, "line": line}
        except FileNotFoundError:
            logger.error("VSCode CLI (`code`) not found. Please install it: https://code.visualstudio.com/docs/editor/command-line")
            return {"success": False, "error": "VSCode CLI (`code`) not found"}
        except Exception as e:
            logger.error(f"VSCode open_file failed: {e}")
            return {"success": False, "error": str(e)}

    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """写入文件内容（自动创建目录）"""
        try:
            full_path = os.path.join(self.workspace_path, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "success": True,
                "action": "write_file",
                "file": file_path,
                "bytes_written": len(content.encode("utf-8")),
            }
        except Exception as e:
            logger.error(f"VSCode write_file failed: {e}")
            return {"success": False, "error": str(e)}

    def run_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """在工作区目录执行终端命令"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.workspace_path,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "action": "run_command",
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            logger.error(f"VSCode run_command failed: {e}")
            return {"success": False, "error": str(e)}


def get_vscode_tool(workspace_path: str = ".") -> VSCodeTool:
    return VSCodeTool(workspace_path)
