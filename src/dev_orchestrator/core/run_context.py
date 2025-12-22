"""Run context management for orchestrator executions.

Each run has:
- Unique ID (timestamp-based for determinism)
- Dedicated directory for artifacts
- State tracking (JSON)
- Timestamps for auditability
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .config import get_config


class RunStatus(str, Enum):
    """Status of a run."""

    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class RunContext:
    """Context for a single orchestrator run.

    Tracks all state and provides paths for artifacts.
    """

    run_id: str
    repo_path: Path
    goal: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: RunStatus = RunStatus.PENDING
    branch_name: str | None = None
    tasks: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, repo_path: str | Path, goal: str) -> "RunContext":
        """Create a new run context with generated ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:8]
        run_id = f"run_{timestamp}_{short_id}"

        return cls(
            run_id=run_id,
            repo_path=Path(repo_path).resolve(),
            goal=goal,
        )

    @property
    def run_dir(self) -> Path:
        """Get the directory for this run's artifacts."""
        config = get_config()
        return config.runs_dir / self.run_id

    @property
    def state_file(self) -> Path:
        """Path to the run state JSON file."""
        return self.run_dir / "state.json"

    @property
    def report_file(self) -> Path:
        """Path to the run report Markdown file."""
        return self.run_dir / "report.md"

    @property
    def plan_file(self) -> Path:
        """Path to the task plan JSON file."""
        return self.run_dir / "plan.json"

    @property
    def log_file(self) -> Path:
        """Path to the execution log file."""
        return self.run_dir / "execution.log"

    def ensure_run_dir(self) -> None:
        """Create run directory if it doesn't exist."""
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def log(self, level: str, message: str, data: dict[str, Any] | None = None) -> None:
        """Add a log entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
        }
        if data:
            entry["data"] = data
        self.logs.append(entry)
        self.updated_at = datetime.now()

    def add_error(self, error: str) -> None:
        """Record an error."""
        self.errors.append(error)
        self.log("ERROR", error)

    def set_status(self, status: RunStatus) -> None:
        """Update run status."""
        self.status = status
        self.updated_at = datetime.now()
        self.log("INFO", f"Status changed to {status.value}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "run_id": self.run_id,
            "repo_path": str(self.repo_path),
            "goal": self.goal,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "branch_name": self.branch_name,
            "tasks": self.tasks,
            "logs": self.logs,
            "errors": self.errors,
            "artifacts": self.artifacts,
        }

    def save(self) -> None:
        """Persist state to filesystem."""
        self.ensure_run_dir()
        self.updated_at = datetime.now()

        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, run_id: str) -> "RunContext":
        """Load a run context from filesystem."""
        config = get_config()
        state_file = config.runs_dir / run_id / "state.json"

        if not state_file.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")

        with open(state_file, encoding="utf-8") as f:
            data = json.load(f)

        ctx = cls(
            run_id=data["run_id"],
            repo_path=Path(data["repo_path"]),
            goal=data["goal"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            status=RunStatus(data["status"]),
            branch_name=data.get("branch_name"),
            tasks=data.get("tasks", []),
            logs=data.get("logs", []),
            errors=data.get("errors", []),
            artifacts=data.get("artifacts", {}),
        )
        return ctx

    @classmethod
    def list_runs(cls) -> list[str]:
        """List all run IDs."""
        config = get_config()
        if not config.runs_dir.exists():
            return []
        return [
            d.name
            for d in config.runs_dir.iterdir()
            if d.is_dir() and (d / "state.json").exists()
        ]
