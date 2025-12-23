"""Async executor with multi-agent workflow.

Coordinates LangChain agents through LangGraph workflow.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..agents.base_agent import AgentOutput, AgentState, FileChange
from ..agents.workflow import AgentWorkflow
from ..core.config import get_config
from ..core.git_ops import GitOps
from ..core.llm_config import check_llm_available
from ..core.run_context import RunContext, RunStatus


class AgentExecutor:
    """Executor that coordinates multi-agent workflow."""

    def __init__(self, context: RunContext):
        """Initialize executor.

        Args:
            context: Run context for this execution
        """
        self.context = context
        self.config = get_config()
        self.git_ops: GitOps | None = None
        self.workflow: AgentWorkflow | None = None
        self.final_state: AgentState | None = None
        self.modified_files: list[str] = []

    def setup(self) -> None:
        """Set up executor for a run."""
        self.context.ensure_run_dir()
        self.context.log("INFO", "Setting up agent executor...")

        # Check LLM availability
        available, message = check_llm_available()
        if not available:
            raise ValueError(f"LLM not available: {message}")
        self.context.log("INFO", f"LLM: {message}")

        # Validate repo
        if not self.context.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.context.repo_path}")

        self.git_ops = GitOps(self.context.repo_path, self.context)

        if not self.git_ops.validate_repo():
            raise ValueError(f"Not a valid git repository: {self.context.repo_path}")

        # Initialize workflow
        self.workflow = AgentWorkflow(self.context)

        self.context.log("INFO", "Agent executor setup complete")

    def _gather_repo_context(self) -> dict[str, Any]:
        """Gather repository context for agents."""
        context: dict[str, Any] = {
            "repo_path": str(self.context.repo_path),
            "files": [],
            "file_contents": {},
            "git_status": None,
        }

        if not self.git_ops:
            return context

        try:
            # Get file list
            files = self.git_ops.get_file_list()
            context["files"] = files

            # Get git status
            status = self.git_ops.get_status()
            context["git_status"] = status

            # Read important files (limit to avoid token overflow)
            important_patterns = [
                "README.md", "readme.md",
                "pyproject.toml", "package.json", "setup.py",
                "requirements.txt",
                "src/__init__.py", "src/main.py", "app.py", "main.py",
            ]

            for pattern in important_patterns:
                for f in files:
                    if f.endswith(pattern.split("/")[-1]) or f == pattern:
                        try:
                            content = self.git_ops.read_file(f)
                            if len(content) < 5000:  # Limit file size
                                context["file_contents"][f] = content
                        except Exception:
                            pass
                        break

        except Exception as e:
            self.context.log("WARNING", f"Error gathering repo context: {e}")

        return context

    def create_branch(self) -> str:
        """Create dedicated branch for this run."""
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        branch_name = self.git_ops.generate_branch_name(self.context.goal)
        self.context.log("INFO", f"Creating branch: {branch_name}")

        try:
            self.git_ops.create_branch(branch_name)
            self.context.branch_name = branch_name
            return branch_name
        except Exception as e:
            self.context.add_error(f"Failed to create branch: {e}")
            raise

    async def execute_workflow(self) -> AgentState:
        """Execute the multi-agent workflow."""
        if not self.workflow:
            raise RuntimeError("Workflow not initialized")

        self.context.set_status(RunStatus.EXECUTING)
        self.context.log("INFO", "Executing multi-agent workflow...")

        # Gather repo context
        repo_context = self._gather_repo_context()

        # Execute workflow
        self.final_state = await self.workflow.execute(
            goal=self.context.goal,
            repo_path=str(self.context.repo_path),
            repo_context=repo_context,
        )

        # Save state
        self._save_agent_outputs()

        return self.final_state

    def _save_agent_outputs(self) -> None:
        """Save agent outputs to run directory."""
        if not self.final_state:
            return

        outputs_dir = self.context.run_dir / "agent_outputs"
        outputs_dir.mkdir(exist_ok=True)

        agent_names = ["architect", "implementer", "tester", "documenter", "reviewer"]

        for name in agent_names:
            output: AgentOutput | None = self.final_state.get(f"{name}_output")
            if output:
                output_file = outputs_dir / f"{name}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(output.model_dump(), f, indent=2, default=str)

    def apply_file_changes(self) -> list[str]:
        """Apply file changes from agents to repository."""
        if not self.final_state:
            self.context.log("WARNING", "No final state to apply")
            return []

        self.context.log("INFO", "Applying file changes...")

        # Use reviewer's changes if available, otherwise aggregate
        all_changes: list[FileChange] = self.final_state.get("all_file_changes", [])

        if not all_changes and self.final_state.get("reviewer_output"):
            all_changes = self.final_state["reviewer_output"].file_changes

        # Deduplicate by path (prefer later changes)
        changes_by_path: dict[str, FileChange] = {}
        for change in all_changes:
            changes_by_path[change.path] = change

        for path, change in changes_by_path.items():
            try:
                self._apply_single_change(change)
                self.modified_files.append(path)
                self.context.log("INFO", f"Applied: {change.action} {path}")
            except Exception as e:
                self.context.add_error(f"Failed to apply {path}: {e}")

        return self.modified_files

    def _apply_single_change(self, change: FileChange) -> None:
        """Apply a single file change."""
        file_path = self.context.repo_path / change.path

        if change.action == "create":
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(change.content, encoding="utf-8")

        elif change.action == "modify":
            if file_path.exists():
                # For now, just overwrite. Could do smart merge later.
                file_path.write_text(change.content, encoding="utf-8")
            else:
                # Create if doesn't exist
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(change.content, encoding="utf-8")

        elif change.action == "delete":
            if file_path.exists():
                file_path.unlink()

    def commit_changes(self, message: str | None = None) -> bool:
        """Commit all changes."""
        if not self.git_ops or not self.modified_files:
            self.context.log("INFO", "No changes to commit")
            return False

        commit_message = message or f"[orchestrator] {self.context.goal[:50]}"

        try:
            self.git_ops.stage_files(self.modified_files)
            result = self.git_ops.commit(commit_message)
            self.context.log("INFO", f"Committed: {commit_message}")
            return result.success
        except Exception as e:
            self.context.add_error(f"Commit failed: {e}")
            return False

    def generate_report(self) -> str:
        """Generate final run report."""
        self.context.log("INFO", "Generating report...")

        report_parts = [
            "# Multi-Agent Orchestrator Run Report",
            "",
            "## Run Information",
            "",
            f"| Property | Value |",
            f"|----------|-------|",
            f"| Run ID | `{self.context.run_id}` |",
            f"| Goal | {self.context.goal} |",
            f"| Repository | `{self.context.repo_path}` |",
            f"| Branch | `{self.context.branch_name or 'N/A'}` |",
            f"| Status | {self.context.status.value} |",
            f"| Created | {self.context.created_at.isoformat()} |",
            "",
            "## Agent Outputs",
            "",
        ]

        if self.final_state:
            agent_names = ["architect", "implementer", "tester", "documenter", "reviewer"]

            for name in agent_names:
                output: AgentOutput | None = self.final_state.get(f"{name}_output")
                if output:
                    status = "✅" if output.success else "❌"
                    report_parts.append(f"### {status} {name.capitalize()}")
                    report_parts.append("")
                    report_parts.append(f"**Summary:** {output.summary}")
                    report_parts.append("")
                    report_parts.append("<details>")
                    report_parts.append("<summary>Reasoning</summary>")
                    report_parts.append("")
                    report_parts.append(output.reasoning)
                    report_parts.append("")
                    report_parts.append("</details>")
                    report_parts.append("")

                    if output.file_changes:
                        report_parts.append("**File Changes:**")
                        for fc in output.file_changes:
                            report_parts.append(f"- `{fc.path}` ({fc.action}): {fc.description}")
                        report_parts.append("")

        report_parts.extend([
            "## Applied Changes",
            "",
        ])

        if self.modified_files:
            for f in self.modified_files:
                report_parts.append(f"- `{f}`")
        else:
            report_parts.append("No files modified.")

        report_parts.extend([
            "",
            "## Errors",
            "",
        ])

        if self.context.errors:
            for err in self.context.errors:
                report_parts.append(f"- ❌ {err}")
        else:
            report_parts.append("No errors.")

        report_parts.extend([
            "",
            "---",
            "*Generated by dev-orchestrator v0.2.0 (Multi-Agent)*",
        ])

        report = "\n".join(report_parts)

        # Save report
        self.context.report_file.write_text(report, encoding="utf-8")
        self.context.artifacts["report"] = str(self.context.report_file)

        return report

    async def run(self) -> str:
        """Execute the full orchestration workflow.

        Returns:
            Path to generated report
        """
        try:
            self.setup()
            self.create_branch()
            await self.execute_workflow()
            self.apply_file_changes()
            self.commit_changes()

            self.context.set_status(RunStatus.COMPLETED)
            report = self.generate_report()
            self.context.save()

            return str(self.context.report_file)

        except Exception as e:
            self.context.set_status(RunStatus.FAILED)
            self.context.add_error(str(e))
            self.generate_report()
            self.context.save()
            raise


async def execute_agent_run(repo_path: str | Path, goal: str) -> str:
    """Convenience function to execute a multi-agent run.

    Args:
        repo_path: Path to target repository
        goal: Goal to accomplish

    Returns:
        Path to generated report
    """
    context = RunContext.create(repo_path, goal)
    executor = AgentExecutor(context)
    return await executor.run()
