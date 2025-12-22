"""Tests for git_ops module."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from dev_orchestrator.core.git_ops import GitError, GitOps, GitResult


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
    )

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
    )

    return repo_path


class TestGitOps:
    """Tests for GitOps class."""

    def test_validate_repo_valid(self, temp_git_repo):
        """Test validation of a valid git repository."""
        git_ops = GitOps(temp_git_repo)
        assert git_ops.validate_repo() is True

    def test_validate_repo_invalid(self, tmp_path):
        """Test validation of a non-git directory."""
        git_ops = GitOps(tmp_path)
        assert git_ops.validate_repo() is False

    def test_validate_repo_nonexistent(self, tmp_path):
        """Test validation of a non-existent path."""
        git_ops = GitOps(tmp_path / "nonexistent")
        assert git_ops.validate_repo() is False

    def test_get_current_branch(self, temp_git_repo):
        """Test getting current branch name."""
        git_ops = GitOps(temp_git_repo)
        branch = git_ops.get_current_branch()
        # Could be main or master depending on git config
        assert branch in ["main", "master"]

    def test_branch_exists(self, temp_git_repo):
        """Test checking if branch exists."""
        git_ops = GitOps(temp_git_repo)
        current = git_ops.get_current_branch()
        assert git_ops.branch_exists(current) is True
        assert git_ops.branch_exists("nonexistent-branch") is False

    def test_is_protected_branch(self, temp_git_repo):
        """Test protected branch detection."""
        git_ops = GitOps(temp_git_repo)
        assert git_ops.is_protected_branch("main") is True
        assert git_ops.is_protected_branch("master") is True
        assert git_ops.is_protected_branch("develop") is True
        assert git_ops.is_protected_branch("feature/test") is False

    def test_create_branch(self, temp_git_repo):
        """Test creating a new branch."""
        git_ops = GitOps(temp_git_repo)
        result = git_ops.create_branch("test-branch")
        assert result.success
        assert git_ops.get_current_branch() == "test-branch"

    def test_create_branch_already_exists(self, temp_git_repo):
        """Test creating a branch that already exists."""
        git_ops = GitOps(temp_git_repo)
        git_ops.create_branch("test-branch")
        git_ops.checkout_branch(git_ops.get_default_branch())

        with pytest.raises(GitError, match="already exists"):
            git_ops.create_branch("test-branch")

    def test_create_branch_protected_name(self, temp_git_repo):
        """Test that creating a protected branch is rejected."""
        git_ops = GitOps(temp_git_repo)

        with pytest.raises(GitError, match="protected"):
            git_ops.create_branch("main")

    def test_checkout_branch(self, temp_git_repo):
        """Test checking out an existing branch."""
        git_ops = GitOps(temp_git_repo)
        git_ops.create_branch("feature-branch")
        git_ops.checkout_branch(git_ops.get_default_branch())
        assert git_ops.get_current_branch() != "feature-branch"

        git_ops.checkout_branch("feature-branch")
        assert git_ops.get_current_branch() == "feature-branch"

    def test_checkout_branch_nonexistent(self, temp_git_repo):
        """Test checking out a non-existent branch."""
        git_ops = GitOps(temp_git_repo)

        with pytest.raises(GitError, match="does not exist"):
            git_ops.checkout_branch("nonexistent")

    def test_get_status_clean(self, temp_git_repo):
        """Test getting status of a clean repo."""
        git_ops = GitOps(temp_git_repo)
        status = git_ops.get_status()

        assert status["clean"] is True
        assert status["branch"] in ["main", "master"]

    def test_get_status_with_changes(self, temp_git_repo):
        """Test getting status with uncommitted changes."""
        git_ops = GitOps(temp_git_repo)

        # Create a new file
        (temp_git_repo / "newfile.txt").write_text("content")

        status = git_ops.get_status()
        assert status["clean"] is False
        assert "newfile.txt" in status["files"]["untracked"]

    def test_stage_and_commit(self, temp_git_repo):
        """Test staging and committing files."""
        git_ops = GitOps(temp_git_repo)
        git_ops.create_branch("test-commits")

        # Create and stage a file
        (temp_git_repo / "staged.txt").write_text("staged content")
        git_ops.stage_files(["staged.txt"])

        # Commit
        result = git_ops.commit("Test commit")
        assert result.success

        # Verify clean state
        status = git_ops.get_status()
        assert status["clean"] is True

    def test_commit_on_protected_branch_fails(self, temp_git_repo):
        """Test that commits on protected branches are rejected."""
        git_ops = GitOps(temp_git_repo)

        (temp_git_repo / "test.txt").write_text("content")
        git_ops.stage_files()

        with pytest.raises(GitError, match="protected"):
            git_ops.commit("Should fail")

    def test_get_diff(self, temp_git_repo):
        """Test getting diff of changes."""
        git_ops = GitOps(temp_git_repo)
        git_ops.create_branch("diff-test")

        # Modify existing file
        (temp_git_repo / "README.md").write_text("# Modified\n")

        diff = git_ops.get_diff()
        assert "Modified" in diff or "-# Test Repository" in diff

    def test_get_log(self, temp_git_repo):
        """Test getting commit log."""
        git_ops = GitOps(temp_git_repo)
        commits = git_ops.get_log(count=5)

        assert len(commits) >= 1
        assert commits[0]["message"] == "Initial commit"
        assert "hash" in commits[0]
        assert "author" in commits[0]

    def test_get_file_list(self, temp_git_repo):
        """Test getting list of tracked files."""
        git_ops = GitOps(temp_git_repo)
        files = git_ops.get_file_list()

        assert "README.md" in files

    def test_generate_branch_name(self, temp_git_repo):
        """Test branch name generation."""
        git_ops = GitOps(temp_git_repo)

        name = git_ops.generate_branch_name("Add healthcheck endpoint")
        assert name.startswith("orchestrator/")
        assert "healthcheck" in name or "endpoint" in name

    def test_generate_branch_name_long_goal(self, temp_git_repo):
        """Test branch name generation with long goal."""
        git_ops = GitOps(temp_git_repo)

        long_goal = "This is a very long goal that should be truncated " * 5
        name = git_ops.generate_branch_name(long_goal)

        # Branch name should be reasonable length
        assert len(name) < 100


class TestGitResult:
    """Tests for GitResult dataclass."""

    def test_git_result_success(self):
        """Test GitResult truthiness for success."""
        result = GitResult(
            success=True,
            stdout="output",
            stderr="",
            returncode=0,
            command=["git", "status"],
        )
        assert bool(result) is True

    def test_git_result_failure(self):
        """Test GitResult truthiness for failure."""
        result = GitResult(
            success=False,
            stdout="",
            stderr="error",
            returncode=1,
            command=["git", "status"],
        )
        assert bool(result) is False
