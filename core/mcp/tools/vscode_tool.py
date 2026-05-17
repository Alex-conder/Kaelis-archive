"""
MCP VSCode 工具 - 允许 Agent 操作本机 VSCode 工作区
Phase 1: MCP 基础工具框架 (Security-hardened)

功能:
  - open_file:   在 VSCode 中打开指定文件
  - write_file:  写入文件内容
  - run_command: 在工作区执行终端命令（带安全过滤）
  - read_file:   读取文件内容
  - list_files:  列出目录中的文件

安全策略 (C0/C2 契约):
  1. 命令白名单/黑名单双层过滤
  2. 路径遍历防护（禁止访问工作区外文件）
  3. 敏感文件访问限制（读取时警告，写入时拒绝）
  4. 工作区边界强制校验

依赖: 本机需安装 `code` 命令（VSCode CLI）
"""
import os
import re
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security Configuration
# ---------------------------------------------------------------------------

# 危险命令黑名单（前缀匹配）
_COMMAND_BLACKLIST = frozenset({
    # 文件破坏类
    "rm", "rmdir", "del", "deltree", "format", "mkfs", "dd", "shred",
    # 系统控制类
    "shutdown", "reboot", "poweroff", "halt", "init", "systemctl",
    # 网络下载/远程执行类
    "curl", "wget", "nc", "netcat", "ncat", "telnet", "ftp", "sftp",
    # PowerShell 高危 cmdlet
    "invoke-expression", "iex", "invoke-webrequest", "iwr",
    "start-process", "new-object", "out-file",
    # Python 高危 one-liner
    "__import__('os').system", "os.system", "subprocess.call",
    "eval(", "exec(", "compile(",
    # 注册表/系统配置
    "reg", "regedit", "sc", "schtasks", "taskkill",
    # 磁盘操作
    "diskpart", "clean", "convert",
})

# 命令白名单（仅允许这些前缀的命令）
_COMMAND_WHITELIST = frozenset({
    # Python 生态
    "python", "python3", "pytest", "pip", "pip3", "flake8", "mypy",
    "black", "isort", "pylint", "coverage", "tox", "poetry", "uv",
    # Node 生态
    "node", "npm", "npx", "yarn", "pnpm", "vitest", "jest", "eslint",
    "prettier", "tsc", "vite", "next",
    # 版本控制
    "git", "gitk",
    # 构建工具
    "cargo", "rustc", "go", "make", "cmake", "mvn", "gradle",
    # 安全查询类
    "echo", "cat", "type", "ls", "dir", "find", "grep", "wc", "head", "tail",
    "pwd", "cd", "mkdir", "touch", "cp", "copy", "mv", "move", "chmod", "chown",
    "which", "where", "whoami", "date", "time", "uname", "ver",
    # IDE
    "code",
    # 测试
    "pytest", "unittest", "test",
})

# 敏感文件模式（glob 风格）
_SENSITIVE_PATTERNS = [
    re.compile(r".*[/\\]\.env.*", re.IGNORECASE),
    re.compile(r".*[/\\]\.ssh[/\\].*", re.IGNORECASE),
    re.compile(r".*[/\\]\.aws[/\\].*", re.IGNORECASE),
    re.compile(r".*[/\\]\.gnupg[/\\].*", re.IGNORECASE),
    re.compile(r".*[/\\]vault\.key.*", re.IGNORECASE),
    re.compile(r".*[/\\]id_rsa.*", re.IGNORECASE),
    re.compile(r".*[/\\]id_ed25519.*", re.IGNORECASE),
    re.compile(r".*[/\\]id_ecdsa.*", re.IGNORECASE),
    re.compile(r".*[/\\]credentials.*", re.IGNORECASE),
    re.compile(r".*[/\\]secret.*", re.IGNORECASE),
    re.compile(r".*[/\\]password.*", re.IGNORECASE),
    re.compile(r".*[/\\]token.*", re.IGNORECASE),
    re.compile(r".*[/\\]api[_-]?key.*", re.IGNORECASE),
    re.compile(r".*[/\\]\.kaelis[/\\]vault.*", re.IGNORECASE),
    re.compile(r".*[/\\]\.kaelis[/\\]config[/\\]ecosystem\.json.*", re.IGNORECASE),
]

# 危险命令子串（任何位置出现即拒绝）
_DANGEROUS_SUBSTRINGS = [
    "> /dev/", "> /sys/", "> /proc/",
    "curl | bash", "curl | sh", "wget | bash", "wget | sh",
    "Invoke-Expression", "IEX", "iex",
    "rm -rf /", "rm -rf \\*", "del /q /s /f \\*",
    "format c:", "format d:", "format e:",
    "mkfs.ext", "mkfs.xfs", "mkfs.btrfs",
    "dd if=/dev/zero of=/dev/sd", "dd if=/dev/zero of=/dev/hd",
]

# 允许的文件扩展名（写入时额外校验）
_SAFE_WRITE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".md", ".txt", ".rst", ".html",
    ".css", ".scss", ".sass", ".less", ".xml", ".sql", ".sh", ".bat",
    ".ps1", ".dockerfile", ".env.example", ".gitignore", ".gitattributes",
    ".lock", ".pipfile", ".editorconfig", ".prettierrc", ".eslintrc",
})


class VSCodeSecurityError(Exception):
    """安全策略违反异常"""
    pass


class VSCodeSecurityGuard:
    """VSCode Tool 安全守卫"""

    @staticmethod
    def check_command(command: str) -> Tuple[bool, str]:
        """
        校验命令是否允许执行。

        策略:
        1. 拒绝包含危险子串的命令
        2. 拒绝黑名单中的命令前缀
        3. 仅允许白名单中的命令前缀（必须匹配开头）
        """
        if not command or not command.strip():
            return False, "Empty command is not allowed"

        cmd_lower = command.lower().strip()

        # 1. 危险子串检查
        for ds in _DANGEROUS_SUBSTRINGS:
            if ds.lower() in cmd_lower:
                return False, f"Command contains dangerous substring: {ds}"

        # 2. 提取命令主词（取第一个 token，去除可能的变量赋值和引号）
        # 例如: "FOO=bar python script.py" -> "python"
        # 例如: "NODE_ENV=production npm run build" -> "npm"
        first_line = cmd_lower.split("\n")[0].strip()
        tokens = first_line.split()
        main_cmd = None
        for tok in tokens:
            # 跳过环境变量赋值 (KEY=value)
            if "=" in tok and not tok.startswith("="):
                continue
            # 去除引号
            clean = tok.strip('"').strip("'")
            if clean:
                main_cmd = clean
                break

        if main_cmd is None:
            return False, "Cannot determine main command"

        # 处理可能的路径前缀，如 "./node_modules/.bin/eslint"
        main_cmd_name = os.path.basename(main_cmd)
        if not main_cmd_name:
            main_cmd_name = main_cmd

        # 2. 黑名单检查
        if main_cmd_name in _COMMAND_BLACKLIST:
            return False, f"Command '{main_cmd_name}' is in blacklist"

        # 3. 白名单检查（主命令或其 basename 必须在白名单中）
        if main_cmd_name not in _COMMAND_WHITELIST and main_cmd not in _COMMAND_WHITELIST:
            return False, (
                f"Command '{main_cmd_name}' is not in whitelist. "
                f"Allowed commands: {sorted(_COMMAND_WHITELIST)}"
            )

        # 4. 额外：检查管道和重定向中的危险命令
        # 分割管道符号: |, ||, &, &&
        pipeline_parts = re.split(r"[|&;]", command)
        for part in pipeline_parts[1:]:  # 跳过第一个（已检查）
            part = part.strip()
            if not part:
                continue
            part_cmd = part.split()[0].strip('"').strip("'")
            part_name = os.path.basename(part_cmd)
            if part_name in _COMMAND_BLACKLIST or part_cmd in _COMMAND_BLACKLIST:
                return False, f"Piped command '{part_name}' is in blacklist"

        return True, "OK"

    @staticmethod
    def check_path(file_path: str, workspace_path: str, operation: str = "read") -> Tuple[bool, str]:
        """
        校验文件路径是否安全。

        策略:
        1. 路径规范化后必须在工作区内（禁止路径遍历）
        2. 敏感文件访问限制
        3. 写入时校验文件扩展名
        """
        if not file_path:
            return False, "Empty path is not allowed"

        # 1. 路径规范化
        abs_workspace = os.path.abspath(workspace_path)
        full_path = os.path.abspath(os.path.join(abs_workspace, file_path))

        # 路径遍历检查：规范化后的路径必须以工作区开头
        try:
            Path(full_path).relative_to(Path(abs_workspace))
        except ValueError:
            return False, f"Path traversal detected: '{file_path}' escapes workspace"

        # 2. 敏感文件检查
        normalized = full_path.replace("\\", "/")
        for pattern in _SENSITIVE_PATTERNS:
            if pattern.match(normalized):
                if operation == "write":
                    return False, f"Writing to sensitive path is prohibited: {file_path}"
                else:
                    # 读取时警告但不阻止（某些场景需要读取配置文件）
                    logger.warning(f"SECURITY: Reading sensitive path {file_path}")

        # 3. 写入时扩展名校验
        if operation == "write":
            ext = os.path.splitext(file_path)[1].lower()
            # 也支持没有扩展名但名字在白名单中的文件
            basename = os.path.basename(file_path).lower()
            if ext not in _SAFE_WRITE_EXTENSIONS and basename not in {
                ".gitignore", ".gitattributes", ".editorconfig",
                ".prettierrc", ".eslintrc", ".babelrc",
                "dockerfile", "makefile", "dockerfile.dev",
            }:
                return False, (
                    f"Writing to file with extension '{ext}' is not allowed. "
                    f"Allowed extensions: {sorted(_SAFE_WRITE_EXTENSIONS)}"
                )

        return True, "OK"


class VSCodeTool:
    """VSCode 远程操作工具（安全增强版）"""

    def __init__(self, workspace_path: str = "."):
        self.workspace_path = os.path.abspath(workspace_path)
        self.guard = VSCodeSecurityGuard()

    def _safe_path(self, file_path: str, operation: str = "read") -> Tuple[bool, str]:
        """内部路径安全校验"""
        return self.guard.check_path(file_path, self.workspace_path, operation)

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def open_file(self, file_path: str, line: int = 1) -> Dict[str, Any]:
        """在 VSCode 中打开指定文件到指定行"""
        try:
            ok, msg = self._safe_path(file_path, "read")
            if not ok:
                return {"success": False, "error": msg}

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
            ok, msg = self._safe_path(file_path, "write")
            if not ok:
                return {"success": False, "error": msg}

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
        """在工作区目录执行终端命令（带安全过滤）"""
        try:
            ok, msg = self.guard.check_command(command)
            if not ok:
                logger.warning(f"SECURITY: Blocked command '{command}': {msg}")
                return {"success": False, "error": msg, "blocked": True}

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

    def read_file(self, file_path: str) -> Dict[str, Any]:
        """读取文件内容"""
        try:
            ok, msg = self._safe_path(file_path, "read")
            if not ok:
                return {"success": False, "error": msg}

            full_path = os.path.join(self.workspace_path, file_path)
            if not os.path.exists(full_path):
                return {"success": False, "error": f"File not found: {file_path}"}
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "success": True,
                "action": "read_file",
                "file": file_path,
                "content": content,
                "lines": content.count("\n") + 1,
            }
        except Exception as e:
            logger.error(f"VSCode read_file failed: {e}")
            return {"success": False, "error": str(e)}

    def list_files(self, directory: str = ".", pattern: str = "*") -> Dict[str, Any]:
        """列出目录中的文件"""
        try:
            ok, msg = self._safe_path(directory, "read")
            if not ok:
                return {"success": False, "error": msg}

            target_dir = Path(self.workspace_path) / directory
            if not target_dir.exists():
                return {"success": False, "error": f"Directory not found: {directory}"}
            files = sorted([str(p.relative_to(self.workspace_path)).replace("\\", "/")
                           for p in target_dir.rglob(pattern) if p.is_file()])[:200]
            return {
                "success": True,
                "action": "list_files",
                "directory": directory,
                "pattern": pattern,
                "count": len(files),
                "files": files,
            }
        except Exception as e:
            logger.error(f"VSCode list_files failed: {e}")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Git Operations (Security-hardened)
    # ------------------------------------------------------------------ #

    def _run_git(self, args: list, timeout: int = 30) -> Dict[str, Any]:
        """Run a git subcommand with safety checks."""
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                cwd=self.workspace_path,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Git command timed out after {timeout}s"}
        except Exception as e:
            logger.error(f"Git command failed: {e}")
            return {"success": False, "error": str(e)}

    def git_status(self) -> Dict[str, Any]:
        """Show git working tree status."""
        result = self._run_git(["status", "--short", "--branch"])
        result["action"] = "git_status"
        # Parse status into structured data
        if result["success"]:
            files = []
            branch = ""
            for line in result["stdout"].splitlines():
                if line.startswith("##"):
                    branch = line[3:].strip()
                elif len(line) >= 2:
                    files.append({
                        "status": line[:2].strip(),
                        "path": line[3:].strip(),
                    })
            result["branch"] = branch
            result["files"] = files
            result["count"] = len(files)
        return result

    def git_diff(self, file_path: Optional[str] = None, staged: bool = False) -> Dict[str, Any]:
        """
        Show git diff.

        Args:
            file_path: Optional specific file to diff.
            staged: Show diff for staged changes.
        """
        args = ["diff"]
        if staged:
            args.append("--staged")
        if file_path:
            ok, msg = self._safe_path(file_path, "read")
            if not ok:
                return {"success": False, "error": msg}
            args.append(file_path)
        result = self._run_git(args)
        result["action"] = "git_diff"
        return result

    def git_commit(self, message: str, allow_empty: bool = False) -> Dict[str, Any]:
        """
        Commit staged changes.

        Security guards:
        - Rejects empty messages
        - Rejects messages containing shell metacharacters
        - Rejects --amend, --no-edit, --fixup flags injected via message
        """
        if not message or not message.strip():
            return {"success": False, "error": "Commit message is required"}

        msg = message.strip()

        # Prevent shell injection via commit message
        dangerous = {";", "&", "|", "<", ">", "`", "$", "(", ")", "\n"}
        for ch in dangerous:
            if ch in msg:
                return {"success": False, "error": f"Commit message contains forbidden character: {ch!r}"}

        # Prevent flag injection
        flag_injection = {"--amend", "--no-edit", "--fixup", "--squash", "--reuse-message", "--reedit-message"}
        lower_msg = msg.lower()
        for flag in flag_injection:
            if flag in lower_msg:
                return {"success": False, "error": f"Commit message contains forbidden flag: {flag}"}

        args = ["commit", "-m", msg]
        if allow_empty:
            args.append("--allow-empty")

        result = self._run_git(args)
        result["action"] = "git_commit"
        return result


def get_vscode_tool(workspace_path: str = ".") -> VSCodeTool:
    return VSCodeTool(workspace_path)
