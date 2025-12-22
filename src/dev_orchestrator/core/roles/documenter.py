"""Documenter role - documentation updates.

Responsible for:
- Updating README and docs
- Creating/updating CHANGELOG
- Adding inline documentation
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from ..git_ops import GitOps
from ..planner import Task, TaskType
from ..run_context import RunContext
from .base import BaseRole, RoleProposal


class DocumenterRole(BaseRole):
    """Documenter role for documentation tasks."""

    name = "documenter"

    def __init__(self, context: RunContext, git_ops: GitOps | None = None):
        """Initialize documenter role.

        Args:
            context: Run context
            git_ops: Git operations instance
        """
        super().__init__(context)
        self.git_ops = git_ops
        self.repo_path = context.repo_path if context else None

    def execute(self, task: Task) -> RoleProposal:
        """Execute a documentation task."""
        self.log("INFO", f"Executing task: {task.title}")

        if task.type != TaskType.DOCUMENT:
            return RoleProposal(
                role=self.name,
                task_id=task.id,
                success=False,
                summary="Wrong task type",
                details=f"Documenter only handles 'document' tasks, got: {task.type}",
                errors=[f"Unsupported task type: {task.type}"],
            )

        return self._document(task)

    def _document(self, task: Task) -> RoleProposal:
        """Create documentation proposal."""
        self.log("INFO", "Creating documentation proposal...")

        goal = task.inputs.get("goal", "")
        doc_changes = []

        # Propose CHANGELOG entry
        changelog_entry = self._create_changelog_entry(goal)
        doc_changes.append({
            "file": "CHANGELOG.md",
            "action": "prepend",
            "description": "Add changelog entry for this change",
            "content": changelog_entry,
        })

        # Propose README update if significant
        readme_update = self._create_readme_update(goal)
        if readme_update:
            doc_changes.append({
                "file": "README.md",
                "action": "update",
                "description": "Update README with new feature documentation",
                "content": readme_update,
            })

        details = f"""# Documentation Proposal

## Goal
{goal}

## Proposed Documentation Changes

### CHANGELOG Entry
```markdown
{changelog_entry}
```

### README Update
{readme_update if readme_update else "No README update needed for this change."}

## Documentation Checklist
- [ ] CHANGELOG updated
- [ ] README updated (if applicable)
- [ ] Inline code documentation added
- [ ] API documentation updated (if applicable)
"""

        return RoleProposal(
            role=self.name,
            task_id=task.id,
            success=True,
            summary=f"Proposed {len(doc_changes)} documentation update(s)",
            details=details,
            file_changes=doc_changes,
            artifacts={"changelog_entry.md": changelog_entry},
        )

    def _create_changelog_entry(self, goal: str) -> str:
        """Create a CHANGELOG entry for the change."""
        date = datetime.now().strftime("%Y-%m-%d")
        return f"""## [Unreleased] - {date}

### Added
- {goal}

### Changed
- (none)

### Fixed
- (none)

---
"""

    def _create_readme_update(self, goal: str) -> str | None:
        """Create README update if appropriate."""
        goal_lower = goal.lower()

        # Only suggest README update for significant features
        significant_keywords = ["feature", "endpoint", "api", "module", "integration"]
        if not any(kw in goal_lower for kw in significant_keywords):
            return None

        return f"""
## New Feature

### {goal.capitalize()}

Description of the new feature.

#### Usage

```python
# Example usage
```

#### Configuration

Any configuration needed.
"""

    def apply_documentation(self, doc_changes: list[dict[str, Any]], repo_path: Path) -> list[str]:
        """Apply documentation changes to the repository.

        Args:
            doc_changes: List of documentation changes
            repo_path: Path to repository

        Returns:
            List of modified files
        """
        modified = []

        for change in doc_changes:
            file_path = repo_path / change["file"]
            action = change["action"]
            content = change.get("content", "")

            if action == "prepend":
                if file_path.exists():
                    existing = file_path.read_text(encoding="utf-8")
                    file_path.write_text(content + "\n" + existing, encoding="utf-8")
                else:
                    file_path.write_text(content, encoding="utf-8")
                modified.append(change["file"])
                self.log("INFO", f"Updated: {change['file']}")

            elif action == "update" and file_path.exists():
                existing = file_path.read_text(encoding="utf-8")
                file_path.write_text(existing + "\n" + content, encoding="utf-8")
                modified.append(change["file"])
                self.log("INFO", f"Updated: {change['file']}")

            elif action == "create":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                modified.append(change["file"])
                self.log("INFO", f"Created: {change['file']}")

        return modified
