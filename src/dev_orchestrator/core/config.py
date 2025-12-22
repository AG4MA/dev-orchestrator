"""Configuration management for dev-orchestrator.

Assumptions:
- Config is loaded from environment variables or local files (never committed)
- Default values are safe and work for local development
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OrchestratorConfig:
    """Main configuration for the orchestrator."""

    # Base paths
    orchestrator_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)
    runs_dir: Path = field(default=None)  # type: ignore
    templates_dir: Path = field(default=None)  # type: ignore

    # Git settings
    git_executable: str = "git"
    default_branch: str = "main"
    branch_prefix: str = "orchestrator"

    # Safety settings
    allow_push: bool = False  # MVP: no remote push by default
    dry_run: bool = False

    # Logging
    log_level: str = "INFO"
    verbose: bool = False

    def __post_init__(self) -> None:
        """Initialize derived paths and load environment overrides."""
        if self.runs_dir is None:
            self.runs_dir = self.orchestrator_root / "runs"
        if self.templates_dir is None:
            self.templates_dir = self.orchestrator_root / "templates"

        # Load environment overrides
        self._load_env_overrides()

    def _load_env_overrides(self) -> None:
        """Load configuration overrides from environment variables."""
        env_mappings: dict[str, tuple[str, type]] = {
            "ORCHESTRATOR_GIT_EXECUTABLE": ("git_executable", str),
            "ORCHESTRATOR_DEFAULT_BRANCH": ("default_branch", str),
            "ORCHESTRATOR_BRANCH_PREFIX": ("branch_prefix", str),
            "ORCHESTRATOR_ALLOW_PUSH": ("allow_push", bool),
            "ORCHESTRATOR_DRY_RUN": ("dry_run", bool),
            "ORCHESTRATOR_LOG_LEVEL": ("log_level", str),
            "ORCHESTRATOR_VERBOSE": ("verbose", bool),
        }

        for env_var, (attr, attr_type) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                if attr_type == bool:
                    setattr(self, attr, value.lower() in ("true", "1", "yes"))
                else:
                    setattr(self, attr, attr_type(value))

    def ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "orchestrator_root": str(self.orchestrator_root),
            "runs_dir": str(self.runs_dir),
            "templates_dir": str(self.templates_dir),
            "git_executable": self.git_executable,
            "default_branch": self.default_branch,
            "branch_prefix": self.branch_prefix,
            "allow_push": self.allow_push,
            "dry_run": self.dry_run,
            "log_level": self.log_level,
            "verbose": self.verbose,
        }


# Global config instance (lazy loaded)
_config: OrchestratorConfig | None = None


def get_config() -> OrchestratorConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = OrchestratorConfig()
    return _config


def reset_config() -> None:
    """Reset config (useful for testing)."""
    global _config
    _config = None
