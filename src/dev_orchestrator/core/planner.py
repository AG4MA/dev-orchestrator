"""Planner module - transforms goals into actionable task lists.

The planner uses heuristics to decompose a goal into smaller tasks.
In MVP, this is a simple rule-based decomposition.
Future: integrate with LLM for smarter planning.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .run_context import RunContext


class TaskType(str, Enum):
    """Types of tasks the orchestrator can handle."""

    ANALYZE = "analyze"  # Analyze existing code/structure
    DESIGN = "design"  # Design solution/architecture
    IMPLEMENT = "implement"  # Write/modify code
    TEST = "test"  # Write/run tests
    DOCUMENT = "document"  # Update documentation
    REVIEW = "review"  # Review changes
    VALIDATE = "validate"  # Validate/verify work


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """A single task in the execution plan."""

    id: str
    type: TaskType
    title: str
    description: str
    role: str  # Which role should handle this
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "role": self.role,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Deserialize task from dictionary."""
        return cls(
            id=data["id"],
            type=TaskType(data["type"]),
            title=data["title"],
            description=data["description"],
            role=data["role"],
            status=TaskStatus(data.get("status", "pending")),
            dependencies=data.get("dependencies", []),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )


@dataclass
class Plan:
    """Execution plan containing ordered tasks."""

    goal: str
    tasks: list[Task] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize plan to dictionary."""
        return {
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    def save(self, path: Path) -> None:
        """Save plan to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> "Plan":
        """Load plan from JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            goal=data["goal"],
            tasks=[Task.from_dict(t) for t in data["tasks"]],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )

    def get_pending_tasks(self) -> list[Task]:
        """Get tasks that are ready to execute."""
        pending = []
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}

        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            # Check if all dependencies are completed
            if all(dep in completed_ids for dep in task.dependencies):
                pending.append(task)

        return pending

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


class Planner:
    """Transforms goals into actionable task plans.

    Uses keyword detection and heuristics to create appropriate tasks.
    This is deliberately simple for the MVP.
    """

    # Keywords that suggest specific task types
    KEYWORDS = {
        "endpoint": ["implement", "test", "document"],
        "api": ["design", "implement", "test", "document"],
        "test": ["analyze", "implement", "test"],
        "refactor": ["analyze", "design", "implement", "test"],
        "fix": ["analyze", "implement", "test"],
        "bug": ["analyze", "implement", "test"],
        "feature": ["design", "implement", "test", "document"],
        "add": ["design", "implement", "test", "document"],
        "create": ["design", "implement", "test", "document"],
        "update": ["analyze", "implement", "test"],
        "documentation": ["analyze", "document"],
        "healthcheck": ["design", "implement", "test", "document"],
        "health": ["design", "implement", "test"],
    }

    # Standard task templates
    TASK_TEMPLATES = {
        "analyze": {
            "role": "architect",
            "title_template": "Analyze codebase for {goal_summary}",
            "description_template": "Review existing code structure and identify relevant files and patterns for: {goal}",
        },
        "design": {
            "role": "architect",
            "title_template": "Design solution for {goal_summary}",
            "description_template": "Create technical design and identify changes needed for: {goal}",
        },
        "implement": {
            "role": "implementer",
            "title_template": "Implement {goal_summary}",
            "description_template": "Write or modify code to implement: {goal}",
        },
        "test": {
            "role": "tester",
            "title_template": "Create tests for {goal_summary}",
            "description_template": "Write and run tests to verify: {goal}",
        },
        "document": {
            "role": "documenter",
            "title_template": "Document {goal_summary}",
            "description_template": "Update documentation and changelog for: {goal}",
        },
        "review": {
            "role": "architect",
            "title_template": "Review changes for {goal_summary}",
            "description_template": "Review all changes made and ensure quality for: {goal}",
        },
        "validate": {
            "role": "tester",
            "title_template": "Validate {goal_summary}",
            "description_template": "Run final validation and create summary for: {goal}",
        },
    }

    def __init__(self, context: RunContext | None = None):
        """Initialize planner.

        Args:
            context: Optional run context for logging
        """
        self.context = context

    def _extract_goal_summary(self, goal: str, max_length: int = 50) -> str:
        """Extract a short summary from the goal."""
        # Remove common prefixes
        prefixes = ["aggiungi", "add", "create", "implement", "fix", "update"]
        summary = goal.lower()
        for prefix in prefixes:
            if summary.startswith(prefix):
                summary = summary[len(prefix):].strip()
                break

        # Truncate if needed
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(" ", 1)[0] + "..."

        return summary

    def _detect_task_types(self, goal: str) -> list[str]:
        """Detect which task types are needed based on goal keywords."""
        goal_lower = goal.lower()
        detected_types: set[str] = set()

        for keyword, types in self.KEYWORDS.items():
            if keyword in goal_lower:
                detected_types.update(types)

        # If nothing detected, use default workflow
        if not detected_types:
            detected_types = {"analyze", "design", "implement", "test", "validate"}

        # Ensure proper ordering
        ordered_types = ["analyze", "design", "implement", "test", "document", "review", "validate"]
        return [t for t in ordered_types if t in detected_types]

    def create_plan(self, goal: str, repo_context: dict[str, Any] | None = None) -> Plan:
        """Create an execution plan from a goal.

        Args:
            goal: The goal/objective to accomplish
            repo_context: Optional context about the target repository

        Returns:
            Plan with ordered tasks
        """
        goal_summary = self._extract_goal_summary(goal)
        task_types = self._detect_task_types(goal)

        tasks: list[Task] = []
        prev_task_id: str | None = None

        for i, task_type in enumerate(task_types):
            template = self.TASK_TEMPLATES[task_type]
            task_id = f"task_{i+1:02d}_{task_type}"

            task = Task(
                id=task_id,
                type=TaskType(task_type),
                title=template["title_template"].format(goal_summary=goal_summary),
                description=template["description_template"].format(goal=goal),
                role=template["role"],
                dependencies=[prev_task_id] if prev_task_id else [],
                inputs={"goal": goal, "repo_context": repo_context or {}},
            )

            tasks.append(task)
            prev_task_id = task_id

        plan = Plan(
            goal=goal,
            tasks=tasks,
            metadata={
                "detected_types": task_types,
                "goal_summary": goal_summary,
            },
        )

        if self.context:
            self.context.log("INFO", f"Created plan with {len(tasks)} tasks")
            self.context.tasks = [t.to_dict() for t in tasks]

        return plan


def create_plan_for_goal(goal: str, context: RunContext | None = None) -> Plan:
    """Convenience function to create a plan for a goal."""
    planner = Planner(context)
    return planner.create_plan(goal)
