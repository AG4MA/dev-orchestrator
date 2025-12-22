"""Implementer role - code modifications.

Responsible for:
- Writing new code
- Modifying existing code
- Creating file changes
"""

from pathlib import Path
from typing import Any

from ..git_ops import GitOps
from ..planner import Task, TaskType
from ..run_context import RunContext
from .base import BaseRole, RoleProposal


class ImplementerRole(BaseRole):
    """Implementer role for code changes."""

    name = "implementer"

    def __init__(self, context: RunContext, git_ops: GitOps | None = None):
        """Initialize implementer role.

        Args:
            context: Run context
            git_ops: Git operations instance
        """
        super().__init__(context)
        self.git_ops = git_ops

    def execute(self, task: Task) -> RoleProposal:
        """Execute an implementation task."""
        self.log("INFO", f"Executing task: {task.title}")

        if task.type != TaskType.IMPLEMENT:
            return RoleProposal(
                role=self.name,
                task_id=task.id,
                success=False,
                summary="Wrong task type",
                details=f"Implementer only handles 'implement' tasks, got: {task.type}",
                errors=[f"Unsupported task type: {task.type}"],
            )

        return self._implement(task)

    def _implement(self, task: Task) -> RoleProposal:
        """Create implementation proposal."""
        self.log("INFO", "Creating implementation proposal...")

        goal = task.inputs.get("goal", "").lower()

        # MVP: Generate placeholder implementation based on goal keywords
        # Future: Use LLM for actual code generation

        file_changes = []
        implementation_details = ""

        # Detect what kind of implementation is needed
        if "healthcheck" in goal or "health" in goal:
            file_changes = self._propose_healthcheck_changes()
            implementation_details = self._healthcheck_implementation()
        elif "endpoint" in goal or "api" in goal:
            file_changes = self._propose_api_changes()
            implementation_details = self._api_implementation()
        else:
            # Generic implementation proposal
            file_changes = self._propose_generic_changes(goal)
            implementation_details = self._generic_implementation(goal)

        details = f"""# Implementation Proposal

## Goal
{task.inputs.get("goal", "N/A")}

## Proposed File Changes

{self._format_file_changes(file_changes)}

## Implementation Details

{implementation_details}

## Notes
- This is a proposed change set
- Actual implementation may vary based on codebase structure
- Review before applying
"""

        return RoleProposal(
            role=self.name,
            task_id=task.id,
            success=True,
            summary=f"Proposed {len(file_changes)} file change(s)",
            details=details,
            file_changes=file_changes,
        )

    def _propose_healthcheck_changes(self) -> list[dict[str, Any]]:
        """Propose changes for healthcheck endpoint."""
        return [
            {
                "file": "src/health.py",
                "action": "create",
                "description": "Healthcheck endpoint module",
                "content": '''"""Healthcheck endpoint for service monitoring."""

from datetime import datetime
from typing import Any


def get_health_status() -> dict[str, Any]:
    """Return current health status.
    
    Returns:
        Dictionary with health information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "checks": {
            "database": "ok",
            "cache": "ok",
        }
    }


def health_endpoint() -> dict[str, Any]:
    """HTTP endpoint handler for health checks."""
    return get_health_status()
''',
            },
            {
                "file": "tests/test_health.py",
                "action": "create",
                "description": "Tests for healthcheck",
                "content": '''"""Tests for healthcheck module."""

import pytest
from src.health import get_health_status, health_endpoint


def test_get_health_status():
    """Test health status returns expected structure."""
    result = get_health_status()
    
    assert "status" in result
    assert result["status"] == "healthy"
    assert "timestamp" in result
    assert "version" in result


def test_health_endpoint():
    """Test health endpoint returns valid response."""
    result = health_endpoint()
    
    assert isinstance(result, dict)
    assert result["status"] == "healthy"
''',
            },
        ]

    def _propose_api_changes(self) -> list[dict[str, Any]]:
        """Propose changes for API endpoint."""
        return [
            {
                "file": "src/api/endpoints.py",
                "action": "modify",
                "description": "Add new API endpoint",
                "content": "# API endpoint implementation placeholder",
            },
        ]

    def _propose_generic_changes(self, goal: str) -> list[dict[str, Any]]:
        """Propose generic changes based on goal."""
        return [
            {
                "file": "src/feature.py",
                "action": "create",
                "description": f"Implementation for: {goal[:50]}",
                "content": f'"""Implementation for: {goal}"""\n\n# TODO: Implement\npass\n',
            },
        ]

    def _healthcheck_implementation(self) -> str:
        """Return healthcheck implementation details."""
        return """
### Healthcheck Module

Creates a simple healthcheck endpoint that returns:
- Current status (healthy/unhealthy)
- Timestamp of check
- Version information
- Individual service checks

### Integration

Add to your main application:
```python
from src.health import health_endpoint

# For Flask
@app.route('/health')
def health():
    return health_endpoint()

# For FastAPI
@app.get('/health')
def health():
    return health_endpoint()
```
"""

    def _api_implementation(self) -> str:
        """Return API implementation details."""
        return """
### API Endpoint

Standard REST endpoint implementation with:
- Input validation
- Error handling
- Response formatting
"""

    def _generic_implementation(self, goal: str) -> str:
        """Return generic implementation details."""
        return f"""
### Feature Implementation

Placeholder implementation for: {goal}

Requires further specification for actual code generation.
"""

    def _format_file_changes(self, changes: list[dict[str, Any]]) -> str:
        """Format file changes as markdown."""
        if not changes:
            return "No file changes proposed."

        lines = ["| File | Action | Description |", "|------|--------|-------------|"]
        for change in changes:
            lines.append(
                f"| `{change['file']}` | {change['action']} | {change['description']} |"
            )
        return "\n".join(lines)

    def apply_changes(self, file_changes: list[dict[str, Any]], repo_path: Path) -> list[str]:
        """Apply file changes to the repository.

        Args:
            file_changes: List of file change dictionaries
            repo_path: Path to the repository

        Returns:
            List of files that were modified
        """
        modified_files = []

        for change in file_changes:
            file_path = repo_path / change["file"]
            action = change["action"]
            content = change.get("content", "")

            if action == "create":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                modified_files.append(str(change["file"]))
                self.log("INFO", f"Created file: {change['file']}")

            elif action == "modify" and file_path.exists():
                # For MVP, append content as a simple modification
                existing = file_path.read_text(encoding="utf-8")
                file_path.write_text(existing + "\n" + content, encoding="utf-8")
                modified_files.append(str(change["file"]))
                self.log("INFO", f"Modified file: {change['file']}")

        return modified_files
