"""
VSCode Tool Git Operations Tests
验证 git_status / git_diff / git_commit 的安全策略
C1 契约: 测试环境隔离 /tmp_path
"""

import os
import pytest
import subprocess

from core.mcp.tools.vscode_tool import VSCodeTool


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary Git repository."""
    repo = tmp_path / "git_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), check=True, capture_output=True)
    return str(repo)


@pytest.fixture
def tool(git_repo):
    return VSCodeTool(git_repo)


class TestGitStatus:
    def test_git_status_clean(self, tool):
        result = tool.git_status()
        assert result["success"] is True
        assert "branch" in result
        assert result["count"] == 0

    def test_git_status_with_untracked(self, tool, git_repo):
        with open(os.path.join(git_repo, "new.py"), "w") as f:
            f.write("print('hello')")
        result = tool.git_status()
        assert result["success"] is True
        assert result["count"] == 1
        assert result["files"][0]["path"] == "new.py"


class TestGitDiff:
    def test_git_diff_empty(self, tool):
        result = tool.git_diff()
        assert result["success"] is True
        # No changes = empty diff

    def test_git_diff_with_changes(self, tool, git_repo):
        file_path = os.path.join(git_repo, "README.md")
        with open(file_path, "w") as f:
            f.write("# Hello")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=git_repo, check=True, capture_output=True)

        with open(file_path, "w") as f:
            f.write("# Hello World")
        result = tool.git_diff("README.md")
        assert result["success"] is True
        assert "Hello World" in result["stdout"]

    def test_git_diff_staged(self, tool, git_repo):
        file_path = os.path.join(git_repo, " staged.txt")
        with open(file_path, "w") as f:
            f.write("staged")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        result = tool.git_diff(staged=True)
        assert result["success"] is True
        assert "staged" in result["stdout"]

    def test_git_diff_path_traversal_blocked(self, tool):
        result = tool.git_diff("../secret.txt")
        assert result["success"] is False
        assert "path traversal" in result["error"].lower()


class TestGitCommit:
    def test_git_commit_success(self, tool, git_repo):
        with open(os.path.join(git_repo, "a.py"), "w") as f:
            f.write("x = 1")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        result = tool.git_commit("Add a.py")
        assert result["success"] is True

    def test_git_commit_empty_message_blocked(self, tool):
        result = tool.git_commit("")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_git_commit_shell_injection_blocked(self, tool):
        result = tool.git_commit("msg; rm -rf /")
        assert result["success"] is False
        assert "forbidden character" in result["error"].lower()

    def test_git_commit_flag_injection_blocked(self, tool):
        result = tool.git_commit("msg --amend")
        assert result["success"] is False
        assert "forbidden flag" in result["error"].lower()

    def test_git_commit_no_changes(self, tool, git_repo):
        # Clean repo with nothing staged
        result = tool.git_commit("Nothing to commit")
        assert result["success"] is False  # git commit fails with nothing staged
