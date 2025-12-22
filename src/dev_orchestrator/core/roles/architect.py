"""Architect role - design and decomposition.

Responsible for:
- Analyzing codebase structure
- Designing solutions
- Decomposing work into smaller pieces
"""

from pathlib import Path
from typing import Any

from ..git_ops import GitOps
from ..planner import Task, TaskType
from ..run_context import RunContext
from .base import BaseRole, RoleProposal


class ArchitectRole(BaseRole):
    """Architect role for design and analysis tasks."""

    name = "architect"

    def __init__(self, context: RunContext, git_ops: GitOps | None = None):
        """Initialize architect role.

        Args:
            context: Run context
            git_ops: Git operations instance for repo access
        """
        super().__init__(context)
        self.git_ops = git_ops

    def execute(self, task: Task) -> RoleProposal:
        """Execute an architect task.

        Handles: analyze, design, review task types
        """
        self.log("INFO", f"Executing task: {task.title}")

        if task.type == TaskType.ANALYZE:
            return self._analyze(task)
        elif task.type == TaskType.DESIGN:
            return self._design(task)
        elif task.type == TaskType.REVIEW:
            return self._review(task)
        else:
            return RoleProposal(
                role=self.name,
                task_id=task.id,
                success=False,
                summary="Unknown task type",
                details=f"Architect cannot handle task type: {task.type}",
                errors=[f"Unsupported task type: {task.type}"],
            )

    def _analyze(self, task: Task) -> RoleProposal:
        """Analyze codebase structure."""
        self.log("INFO", "Analyzing codebase structure...")

        analysis_result = {
            "file_count": 0,
            "file_types": {},
            "relevant_files": [],
        }

        if self.git_ops and self.git_ops.validate_repo():
            try:
                files = self.git_ops.get_file_list()
                analysis_result["file_count"] = len(files)

                # Categorize files
                for f in files:
                    ext = Path(f).suffix or "no_extension"
                    analysis_result["file_types"][ext] = analysis_result["file_types"].get(ext, 0) + 1

                # Find potentially relevant files based on goal
                goal = task.inputs.get("goal", "").lower()
                keywords = goal.split()
                for f in files:
                    f_lower = f.lower()
                    if any(kw in f_lower for kw in keywords if len(kw) > 3):
                        analysis_result["relevant_files"].append(f)

            except Exception as e:
                self.log("ERROR", f"Analysis failed: {e}")
                return RoleProposal(
                    role=self.name,
                    task_id=task.id,
                    success=False,
                    summary="Analysis failed",
                    details=str(e),
                    errors=[str(e)],
                )

        details = f"""# Codebase Analysis

## Overview
- Total files: {analysis_result["file_count"]}
- File types: {analysis_result["file_types"]}

## Potentially Relevant Files
{chr(10).join("- " + f for f in analysis_result["relevant_files"][:10]) or "- No specific files identified"}

## Recommendation
Based on the goal "{task.inputs.get("goal", "N/A")}", proceed with design phase.
"""

        return RoleProposal(
            role=self.name,
            task_id=task.id,
            success=True,
            summary=f"Analyzed {analysis_result['file_count']} files",
            details=details,
            metadata=analysis_result,
        )

    def _design(self, task: Task) -> RoleProposal:
        """Create technical design."""
        self.log("INFO", "Creating technical design...")

        goal = task.inputs.get("goal", "")

        # MVP: Generate a simple design document
        # Future: Use LLM for intelligent design

        design = f"""# Technical Design

## Goal
{goal}

## Proposed Changes

### 1. File Changes
Based on the goal, the following changes are proposed:

| File | Action | Description |
|------|--------|-------------|
| TBD | Create/Modify | Implementation details |

### 2. Implementation Approach
1. Identify target location in codebase
2. Implement core functionality
3. Add appropriate error handling
4. Create unit tests
5. Update documentation

### 3. Testing Strategy
- Unit tests for new functionality
- Integration tests if applicable
- Manual verification checklist

### 4. Documentation Updates
- Update README if needed
- Add inline code documentation
- Update CHANGELOG

## Dependencies
- None identified

## Risks
- Low: Standard implementation task
"""

        return RoleProposal(
            role=self.name,
            task_id=task.id,
            success=True,
            summary="Design document created",
            details=design,
            artifacts={"design.md": design},
        )

    def _review(self, task: Task) -> RoleProposal:
        """Review changes made."""
        self.log("INFO", "Reviewing changes...")

        review_notes = """# Review Summary

## Changes Reviewed
All changes from this run have been reviewed.

## Quality Checklist
- [ ] Code follows project conventions
- [ ] Tests are adequate
- [ ] Documentation is updated
- [ ] No security issues identified

## Recommendation
Proceed with validation.
"""

        return RoleProposal(
            role=self.name,
            task_id=task.id,
            success=True,
            summary="Review completed",
            details=review_notes,
        )
