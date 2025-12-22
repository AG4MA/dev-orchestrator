"""Git operations module using subprocess for transparency and control.

Safety guarantees:
- Never force push
- Never delete branches without explicit confirmation
- Never operate directly on main/master
- All operations are logged
"""

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import get_config
from .run_context import RunContext


class GitError(Exception):
    """Exception for git operation failures."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


@dataclass
class GitResult:
    """Result of a git command execution."""

    success: bool
    stdout: str
    stderr: str
    returncode: int
    command: list[str]

    def __bool__(self) -> bool:
        return self.success


class GitOps:
    """Safe git operations for target repository management."""

    # Protected branches that should never be directly modified
    PROTECTED_BRANCHES = {"main", "master", "develop", "production"}

    def __init__(self, repo_path: Path, context: RunContext | None = None):
        """Initialize git operations for a repository.

        Args:
            repo_path: Path to the target repository
            context: Optional run context for logging
        """
        self.repo_path = Path(repo_path).resolve()
        self.context = context
        self.config = get_config()

    def _run_git(
        self,
        args: list[str],
        check: bool = True,
        capture_output: bool = True,
    ) -> GitResult:
        """Execute a git command safely.

        Args:
            args: Git command arguments (without 'git' prefix)
            check: Raise exception on non-zero exit
            capture_output: Capture stdout/stderr

        Returns:
            GitResult with command output
        """
        cmd = [self.config.git_executable] + args

        # Log the command
        if self.context:
            self.context.log("DEBUG", f"Git command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=capture_output,
                text=True,
                timeout=120,  # 2 minute timeout
            )

            git_result = GitResult(
                success=result.returncode == 0,
                stdout=result.stdout.strip() if result.stdout else "",
                stderr=result.stderr.strip() if result.stderr else "",
                returncode=result.returncode,
                command=cmd,
            )

            if check and not git_result.success:
                raise GitError(
                    f"Git command failed: {' '.join(args)}\n{git_result.stderr}",
                    returncode=result.returncode,
                    stderr=git_result.stderr,
                )

            return git_result

        except subprocess.TimeoutExpired as e:
            raise GitError(f"Git command timed out: {' '.join(args)}") from e

    def validate_repo(self) -> bool:
        """Check if the path is a valid git repository."""
        if not self.repo_path.exists():
            return False

        result = self._run_git(["rev-parse", "--git-dir"], check=False)
        return result.success

    def get_current_branch(self) -> str:
        """Get the current branch name."""
        result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout

    def get_default_branch(self) -> str:
        """Detect the default branch (main or master)."""
        # Try to get from remote
        result = self._run_git(
            ["symbolic-ref", "refs/remotes/origin/HEAD"],
            check=False,
        )
        if result.success:
            # Returns something like refs/remotes/origin/main
            return result.stdout.split("/")[-1]

        # Fallback: check if main or master exists
        for branch in ["main", "master"]:
            result = self._run_git(["rev-parse", "--verify", branch], check=False)
            if result.success:
                return branch

        return self.config.default_branch

    def is_protected_branch(self, branch: str) -> bool:
        """Check if a branch is protected."""
        return branch in self.PROTECTED_BRANCHES

    def branch_exists(self, branch: str) -> bool:
        """Check if a branch exists locally."""
        result = self._run_git(["rev-parse", "--verify", branch], check=False)
        return result.success

    def create_branch(self, branch_name: str, base_branch: str | None = None) -> GitResult:
        """Create a new branch from base branch.

        Safety: Will not create branches that would overwrite protected branches.
        """
        if self.is_protected_branch(branch_name):
            raise GitError(f"Cannot create branch with protected name: {branch_name}")

        if self.branch_exists(branch_name):
            raise GitError(f"Branch already exists: {branch_name}")

        base = base_branch or self.get_default_branch()

        # Ensure we're starting from a clean state
        self._run_git(["checkout", base])
        self._run_git(["pull", "--ff-only"], check=False)  # Try to pull, but don't fail

        result = self._run_git(["checkout", "-b", branch_name])

        if self.context:
            self.context.log("INFO", f"Created branch: {branch_name} from {base}")
            self.context.branch_name = branch_name

        return result

    def checkout_branch(self, branch_name: str) -> GitResult:
        """Checkout an existing branch."""
        if not self.branch_exists(branch_name):
            raise GitError(f"Branch does not exist: {branch_name}")

        return self._run_git(["checkout", branch_name])

    def get_status(self) -> dict[str, Any]:
        """Get repository status."""
        result = self._run_git(["status", "--porcelain"])

        files = {"modified": [], "added": [], "deleted": [], "untracked": []}
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            status = line[:2]
            filepath = line[3:]

            if status[0] == "M" or status[1] == "M":
                files["modified"].append(filepath)
            elif status[0] == "A":
                files["added"].append(filepath)
            elif status[0] == "D" or status[1] == "D":
                files["deleted"].append(filepath)
            elif status[0] == "?":
                files["untracked"].append(filepath)

        return {
            "branch": self.get_current_branch(),
            "files": files,
            "clean": not any(files.values()),
        }

    def stage_files(self, files: list[str] | None = None) -> GitResult:
        """Stage files for commit.

        Args:
            files: List of files to stage, or None for all changes
        """
        if files:
            return self._run_git(["add"] + files)
        return self._run_git(["add", "-A"])

    def commit(self, message: str, allow_empty: bool = False) -> GitResult:
        """Create a commit with the staged changes.

        Safety: Refuses to commit on protected branches.
        """
        current_branch = self.get_current_branch()
        if self.is_protected_branch(current_branch):
            raise GitError(f"Cannot commit directly to protected branch: {current_branch}")

        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")

        result = self._run_git(args, check=False)

        if result.success and self.context:
            self.context.log("INFO", f"Created commit: {message[:50]}...")

        return result

    def get_diff(self, staged: bool = False, file_path: str | None = None) -> str:
        """Get diff of changes.

        Args:
            staged: Get staged changes instead of unstaged
            file_path: Specific file to diff
        """
        args = ["diff"]
        if staged:
            args.append("--staged")
        if file_path:
            args.extend(["--", file_path])

        result = self._run_git(args)
        return result.stdout

    def get_log(self, count: int = 10, branch: str | None = None) -> list[dict[str, str]]:
        """Get recent commit log.

        Args:
            count: Number of commits to retrieve
            branch: Branch to get log from (default: current)
        """
        format_str = "%H|%an|%ae|%ad|%s"
        args = ["log", f"-{count}", f"--format={format_str}", "--date=iso"]
        if branch:
            args.append(branch)

        result = self._run_git(args)

        commits = []
        for line in result.stdout.splitlines():
            if "|" in line:
                parts = line.split("|", 4)
                if len(parts) == 5:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    })

        return commits

    def get_file_list(self, branch: str | None = None) -> list[str]:
        """Get list of all tracked files."""
        args = ["ls-tree", "-r", "--name-only", branch or "HEAD"]
        result = self._run_git(args)
        return result.stdout.splitlines()

    def read_file(self, file_path: str, ref: str = "HEAD") -> str:
        """Read file content at a specific ref."""
        result = self._run_git(["show", f"{ref}:{file_path}"])
        return result.stdout

    def generate_branch_name(self, goal: str) -> str:
        """Generate a deterministic branch name from goal.

        Format: {prefix}/{date}/{slug}
        """
        # Create slug from goal
        slug = goal.lower()
        # Keep only alphanumeric and spaces
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        # Replace spaces with dashes, limit length
        slug = "-".join(slug.split())[:40]

        date = datetime.now().strftime("%Y%m%d")

        return f"{self.config.branch_prefix}/{date}/{slug}"


def clone_repo(url: str, target_path: Path, context: RunContext | None = None) -> GitOps:
    """Clone a repository to a target path.

    Args:
        url: Git repository URL
        target_path: Local path to clone to
        context: Optional run context for logging

    Returns:
        GitOps instance for the cloned repo
    """
    config = get_config()

    if target_path.exists():
        raise GitError(f"Target path already exists: {target_path}")

    cmd = [config.git_executable, "clone", url, str(target_path)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for clone
        )

        if result.returncode != 0:
            raise GitError(f"Clone failed: {result.stderr}")

        if context:
            context.log("INFO", f"Cloned repository to {target_path}")

        return GitOps(target_path, context)

    except subprocess.TimeoutExpired as e:
        raise GitError("Clone operation timed out") from e
