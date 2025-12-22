"""Executor module - coordinates roles and produces reports.

The executor is the main orchestration engine that:
1. Creates the execution plan
2. Coordinates role execution
3. Applies changes to the target repo
4. Generates reports
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import get_config
from .git_ops import GitOps
from .planner import Plan, Planner, Task, TaskStatus
from .roles import ArchitectRole, DocumenterRole, ImplementerRole, TesterRole
from .roles.base import BaseRole, RoleProposal
from .run_context import RunContext, RunStatus


class Executor:
    """Main executor that coordinates the orchestration workflow."""

    def __init__(self, context: RunContext):
        """Initialize executor with run context.

        Args:
            context: The run context for this execution
        """
        self.context = context
        self.config = get_config()
        self.git_ops: GitOps | None = None
        self.roles: dict[str, BaseRole] = {}
        self.plan: Plan | None = None
        self.proposals: list[RoleProposal] = []
        self.modified_files: list[str] = []

    def setup(self) -> None:
        """Set up the executor for a run."""
        self.context.ensure_run_dir()
        self.context.log("INFO", "Setting up executor...")

        # Validate and setup git operations
        if not self.context.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.context.repo_path}")

        self.git_ops = GitOps(self.context.repo_path, self.context)

        if not self.git_ops.validate_repo():
            raise ValueError(f"Not a valid git repository: {self.context.repo_path}")

        # Initialize roles
        self.roles = {
            "architect": ArchitectRole(self.context, self.git_ops),
            "implementer": ImplementerRole(self.context, self.git_ops),
            "tester": TesterRole(self.context, self.git_ops),
            "documenter": DocumenterRole(self.context, self.git_ops),
        }

        self.context.log("INFO", "Executor setup complete")

    def create_plan(self) -> Plan:
        """Create execution plan from goal."""
        self.context.set_status(RunStatus.PLANNING)
        self.context.log("INFO", f"Creating plan for goal: {self.context.goal}")

        planner = Planner(self.context)
        self.plan = planner.create_plan(self.context.goal)

        # Save plan
        self.plan.save(self.context.plan_file)
        self.context.artifacts["plan"] = str(self.context.plan_file)

        self.context.log("INFO", f"Plan created with {len(self.plan.tasks)} tasks")
        return self.plan

    def create_branch(self) -> str:
        """Create a dedicated branch for this run."""
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

    def execute_task(self, task: Task) -> RoleProposal:
        """Execute a single task using the appropriate role."""
        role = self.roles.get(task.role)
        if not role:
            return RoleProposal(
                role=task.role,
                task_id=task.id,
                success=False,
                summary=f"Unknown role: {task.role}",
                details="",
                errors=[f"No role found: {task.role}"],
            )

        task.status = TaskStatus.IN_PROGRESS
        self.context.log("INFO", f"Executing task {task.id}: {task.title}")

        try:
            proposal = role.execute(task)
            task.status = TaskStatus.COMPLETED if proposal.success else TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.outputs = {"proposal": proposal.to_dict()}

            self.proposals.append(proposal)
            return proposal

        except Exception as e:
            task.status = TaskStatus.FAILED
            self.context.add_error(f"Task {task.id} failed: {e}")
            return RoleProposal(
                role=task.role,
                task_id=task.id,
                success=False,
                summary=f"Task failed: {e}",
                details=str(e),
                errors=[str(e)],
            )

    def execute_plan(self) -> list[RoleProposal]:
        """Execute all tasks in the plan."""
        if not self.plan:
            raise RuntimeError("No plan created")

        self.context.set_status(RunStatus.EXECUTING)
        self.context.log("INFO", "Starting plan execution...")

        for task in self.plan.tasks:
            proposal = self.execute_task(task)
            self.context.save()  # Persist state after each task

            if not proposal.success and task.status == TaskStatus.FAILED:
                self.context.log("WARNING", f"Task {task.id} failed, continuing...")

        return self.proposals

    def apply_changes(self) -> list[str]:
        """Apply proposed changes from implementer and documenter."""
        self.context.log("INFO", "Applying proposed changes...")

        for proposal in self.proposals:
            if not proposal.success or not proposal.file_changes:
                continue

            role = self.roles.get(proposal.role)

            if isinstance(role, ImplementerRole):
                files = role.apply_changes(proposal.file_changes, self.context.repo_path)
                self.modified_files.extend(files)

            elif isinstance(role, DocumenterRole):
                files = role.apply_documentation(proposal.file_changes, self.context.repo_path)
                self.modified_files.extend(files)

        return self.modified_files

    def commit_changes(self, message: str | None = None) -> bool:
        """Commit all changes to the branch."""
        if not self.git_ops or not self.modified_files:
            self.context.log("INFO", "No changes to commit")
            return False

        commit_message = message or f"[orchestrator] {self.context.goal[:50]}"

        try:
            self.git_ops.stage_files(self.modified_files)
            result = self.git_ops.commit(commit_message)
            self.context.log("INFO", f"Committed changes: {commit_message}")
            return result.success
        except Exception as e:
            self.context.add_error(f"Commit failed: {e}")
            return False

    def generate_report(self) -> str:
        """Generate the final run report."""
        self.context.log("INFO", "Generating report...")

        # Build report sections
        task_summary = self._format_task_summary()
        proposal_details = self._format_proposals()
        file_changes = self._format_file_changes()
        git_info = self._format_git_info()
        checklist = self._generate_checklist()

        report = f"""# Orchestrator Run Report

## Run Information

| Property | Value |
|----------|-------|
| Run ID | `{self.context.run_id}` |
| Goal | {self.context.goal} |
| Repository | `{self.context.repo_path}` |
| Branch | `{self.context.branch_name or "N/A"}` |
| Status | {self.context.status.value} |
| Created | {self.context.created_at.isoformat()} |
| Completed | {self.context.updated_at.isoformat()} |

## Goal

> {self.context.goal}

## Task Summary

{task_summary}

## Proposals

{proposal_details}

## File Changes

{file_changes}

## Git Information

{git_info}

## Checklist

{checklist}

## Errors

{self._format_errors()}

---
*Generated by dev-orchestrator v0.1.0*
"""

        # Save report
        self.context.report_file.write_text(report, encoding="utf-8")
        self.context.artifacts["report"] = str(self.context.report_file)

        return report

    def _format_task_summary(self) -> str:
        """Format task summary table."""
        if not self.plan:
            return "No plan executed."

        lines = ["| # | Task | Role | Status |", "|---|------|------|--------|"]
        for i, task in enumerate(self.plan.tasks, 1):
            status_icon = {
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.SKIPPED: "⏭️",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.PENDING: "⏳",
            }.get(task.status, "❓")

            lines.append(f"| {i} | {task.title[:40]} | {task.role} | {status_icon} {task.status.value} |")

        return "\n".join(lines)

    def _format_proposals(self) -> str:
        """Format proposal summaries."""
        if not self.proposals:
            return "No proposals generated."

        sections = []
        for proposal in self.proposals:
            status = "✅" if proposal.success else "❌"
            sections.append(f"""### {status} {proposal.role.capitalize()} - Task {proposal.task_id}

**Summary:** {proposal.summary}

<details>
<summary>Details</summary>

{proposal.details}

</details>
""")

        return "\n".join(sections)

    def _format_file_changes(self) -> str:
        """Format list of modified files."""
        if not self.modified_files:
            return "No files were modified."

        return "\n".join(f"- `{f}`" for f in self.modified_files)

    def _format_git_info(self) -> str:
        """Format git information."""
        if not self.git_ops:
            return "Git not initialized."

        try:
            status = self.git_ops.get_status()
            commits = self.git_ops.get_log(3)

            commit_info = "\n".join(
                f"- `{c['hash'][:7]}` {c['message'][:50]}"
                for c in commits
            ) if commits else "No commits"

            return f"""
**Current Branch:** `{status['branch']}`
**Working Tree Clean:** {status['clean']}

**Recent Commits:**
{commit_info}
"""
        except Exception as e:
            return f"Error getting git info: {e}"

    def _generate_checklist(self) -> str:
        """Generate verification checklist."""
        items = [
            ("Plan created", self.plan is not None),
            ("Branch created", self.context.branch_name is not None),
            ("Tasks executed", len(self.proposals) > 0),
            ("All tasks successful", all(p.success for p in self.proposals)),
            ("Changes applied", len(self.modified_files) > 0),
            ("Changes committed", self.git_ops.get_status()["clean"] if self.git_ops else False),
            ("Report generated", True),
        ]

        return "\n".join(
            f"- [{'x' if done else ' '}] {item}"
            for item, done in items
        )

    def _format_errors(self) -> str:
        """Format error list."""
        if not self.context.errors:
            return "No errors recorded."

        return "\n".join(f"- ❌ {err}" for err in self.context.errors)

    def run(self) -> str:
        """Execute the full orchestration workflow.

        Returns:
            Path to the generated report
        """
        try:
            self.setup()
            self.create_plan()
            self.create_branch()
            self.execute_plan()
            self.apply_changes()
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


def execute_run(repo_path: str | Path, goal: str) -> str:
    """Convenience function to execute a complete run.

    Args:
        repo_path: Path to target repository
        goal: The goal to accomplish

    Returns:
        Path to the generated report
    """
    context = RunContext.create(repo_path, goal)
    executor = Executor(context)
    return executor.run()
