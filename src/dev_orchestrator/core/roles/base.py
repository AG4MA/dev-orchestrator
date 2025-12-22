"""Base role interface for agentic modules."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..planner import Task
from ..run_context import RunContext


@dataclass
class RoleProposal:
    """Output from a role's execution.

    Represents a proposed action or change that can be reviewed/applied.
    """

    role: str
    task_id: str
    success: bool
    summary: str
    details: str
    file_changes: list[dict[str, Any]] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "role": self.role,
            "task_id": self.task_id,
            "success": self.success,
            "summary": self.summary,
            "details": self.details,
            "file_changes": self.file_changes,
            "commands": self.commands,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "errors": self.errors,
        }


class BaseRole(ABC):
    """Base class for all orchestrator roles.

    Each role is responsible for a specific type of work:
    - Architect: design and decomposition
    - Implementer: code changes
    - Tester: testing and validation
    - Documenter: documentation updates
    """

    name: str = "base"

    def __init__(self, context: RunContext):
        """Initialize role with run context.

        Args:
            context: The run context for logging and state
        """
        self.context = context

    @abstractmethod
    def execute(self, task: Task) -> RoleProposal:
        """Execute a task and return a proposal.

        Args:
            task: The task to execute

        Returns:
            RoleProposal with the results
        """
        pass

    def log(self, level: str, message: str, data: dict[str, Any] | None = None) -> None:
        """Log a message through the context."""
        self.context.log(level, f"[{self.name}] {message}", data)

    def can_handle(self, task: Task) -> bool:
        """Check if this role can handle the given task."""
        return task.role == self.name
