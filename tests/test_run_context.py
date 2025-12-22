"""Tests for run context module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from dev_orchestrator.core.config import OrchestratorConfig, reset_config
from dev_orchestrator.core.run_context import RunContext, RunStatus


@pytest.fixture(autouse=True)
def reset_global_config():
    """Reset global config before each test."""
    reset_config()
    yield
    reset_config()


class TestRunContext:
    """Tests for RunContext class."""

    def test_create_run_context(self, tmp_path):
        """Test creating a run context."""
        context = RunContext.create(tmp_path, "Test goal")

        assert context.run_id.startswith("run_")
        assert context.repo_path == tmp_path.resolve()
        assert context.goal == "Test goal"
        assert context.status == RunStatus.PENDING

    def test_run_id_is_unique(self, tmp_path):
        """Test that run IDs are unique."""
        context1 = RunContext.create(tmp_path, "Goal 1")
        context2 = RunContext.create(tmp_path, "Goal 2")

        assert context1.run_id != context2.run_id

    def test_run_id_contains_timestamp(self, tmp_path):
        """Test that run ID contains timestamp."""
        context = RunContext.create(tmp_path, "Test")
        today = datetime.now().strftime("%Y%m%d")

        assert today in context.run_id

    def test_log_entries(self, tmp_path):
        """Test logging entries."""
        context = RunContext.create(tmp_path, "Test")
        context.log("INFO", "Test message", {"key": "value"})

        assert len(context.logs) == 1
        assert context.logs[0]["level"] == "INFO"
        assert context.logs[0]["message"] == "Test message"
        assert context.logs[0]["data"]["key"] == "value"

    def test_add_error(self, tmp_path):
        """Test adding errors."""
        context = RunContext.create(tmp_path, "Test")
        context.add_error("Something went wrong")

        assert len(context.errors) == 1
        assert context.errors[0] == "Something went wrong"
        assert any("Something went wrong" in log["message"] for log in context.logs)

    def test_set_status(self, tmp_path):
        """Test status changes."""
        context = RunContext.create(tmp_path, "Test")
        initial_updated = context.updated_at

        context.set_status(RunStatus.EXECUTING)

        assert context.status == RunStatus.EXECUTING
        assert context.updated_at >= initial_updated

    def test_to_dict(self, tmp_path):
        """Test serialization to dict."""
        context = RunContext.create(tmp_path, "Test goal")
        context.branch_name = "test-branch"

        data = context.to_dict()

        assert data["run_id"] == context.run_id
        assert data["goal"] == "Test goal"
        assert data["branch_name"] == "test-branch"
        assert data["status"] == "pending"

    def test_save_and_load(self, tmp_path):
        """Test saving and loading run context."""
        # Create custom config to use tmp_path for runs
        from dev_orchestrator.core.config import _config, get_config

        config = get_config()
        config.runs_dir = tmp_path / "runs"
        config.ensure_dirs()

        context = RunContext.create(tmp_path / "repo", "Test goal")
        context.branch_name = "feature/test"
        context.add_error("Test error")
        context.save()

        # Load it back
        loaded = RunContext.load(context.run_id)

        assert loaded.run_id == context.run_id
        assert loaded.goal == "Test goal"
        assert loaded.branch_name == "feature/test"
        assert len(loaded.errors) == 1

    def test_load_nonexistent(self, tmp_path):
        """Test loading non-existent run."""
        from dev_orchestrator.core.config import get_config

        config = get_config()
        config.runs_dir = tmp_path / "runs"

        with pytest.raises(FileNotFoundError):
            RunContext.load("nonexistent_run_id")

    def test_list_runs(self, tmp_path):
        """Test listing runs."""
        from dev_orchestrator.core.config import get_config

        config = get_config()
        config.runs_dir = tmp_path / "runs"
        config.ensure_dirs()

        # Create some runs
        ctx1 = RunContext.create(tmp_path / "repo1", "Goal 1")
        ctx1.save()

        ctx2 = RunContext.create(tmp_path / "repo2", "Goal 2")
        ctx2.save()

        runs = RunContext.list_runs()

        assert len(runs) == 2
        assert ctx1.run_id in runs
        assert ctx2.run_id in runs

    def test_run_paths(self, tmp_path):
        """Test run directory paths."""
        from dev_orchestrator.core.config import get_config

        config = get_config()
        config.runs_dir = tmp_path / "runs"

        context = RunContext.create(tmp_path / "repo", "Test")

        assert context.run_dir == config.runs_dir / context.run_id
        assert context.state_file == context.run_dir / "state.json"
        assert context.report_file == context.run_dir / "report.md"
        assert context.plan_file == context.run_dir / "plan.json"


class TestRunStatus:
    """Tests for RunStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.EXECUTING.value == "executing"
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.FAILED.value == "failed"

    def test_status_from_string(self):
        """Test creating status from string."""
        assert RunStatus("pending") == RunStatus.PENDING
        assert RunStatus("completed") == RunStatus.COMPLETED
