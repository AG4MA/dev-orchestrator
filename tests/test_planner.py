"""Tests for planner module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from dev_orchestrator.core.planner import (
    Plan,
    Planner,
    Task,
    TaskStatus,
    TaskType,
    create_plan_for_goal,
)


class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation(self):
        """Test creating a task."""
        task = Task(
            id="task_01",
            type=TaskType.IMPLEMENT,
            title="Test task",
            description="A test task",
            role="implementer",
        )

        assert task.id == "task_01"
        assert task.type == TaskType.IMPLEMENT
        assert task.status == TaskStatus.PENDING
        assert task.role == "implementer"

    def test_task_to_dict(self):
        """Test task serialization."""
        task = Task(
            id="task_01",
            type=TaskType.IMPLEMENT,
            title="Test task",
            description="A test task",
            role="implementer",
            dependencies=["task_00"],
        )

        data = task.to_dict()

        assert data["id"] == "task_01"
        assert data["type"] == "implement"
        assert data["status"] == "pending"
        assert data["dependencies"] == ["task_00"]

    def test_task_from_dict(self):
        """Test task deserialization."""
        data = {
            "id": "task_01",
            "type": "implement",
            "title": "Test task",
            "description": "A test task",
            "role": "implementer",
            "status": "completed",
            "dependencies": [],
            "inputs": {},
            "outputs": {},
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }

        task = Task.from_dict(data)

        assert task.id == "task_01"
        assert task.type == TaskType.IMPLEMENT
        assert task.status == TaskStatus.COMPLETED


class TestPlan:
    """Tests for Plan dataclass."""

    def test_plan_creation(self):
        """Test creating a plan."""
        plan = Plan(
            goal="Test goal",
            tasks=[
                Task(
                    id="t1",
                    type=TaskType.ANALYZE,
                    title="Analyze",
                    description="Analyze code",
                    role="architect",
                ),
            ],
        )

        assert plan.goal == "Test goal"
        assert len(plan.tasks) == 1

    def test_plan_to_dict(self):
        """Test plan serialization."""
        plan = Plan(goal="Test goal", tasks=[])
        data = plan.to_dict()

        assert data["goal"] == "Test goal"
        assert data["tasks"] == []
        assert "created_at" in data

    def test_plan_save_and_load(self, tmp_path):
        """Test saving and loading a plan."""
        plan = Plan(
            goal="Test goal",
            tasks=[
                Task(
                    id="t1",
                    type=TaskType.IMPLEMENT,
                    title="Implement",
                    description="Implement feature",
                    role="implementer",
                ),
            ],
            metadata={"test": True},
        )

        plan_file = tmp_path / "plan.json"
        plan.save(plan_file)

        loaded = Plan.load(plan_file)

        assert loaded.goal == plan.goal
        assert len(loaded.tasks) == 1
        assert loaded.tasks[0].id == "t1"
        assert loaded.metadata["test"] is True

    def test_plan_get_pending_tasks(self):
        """Test getting pending tasks respecting dependencies."""
        plan = Plan(
            goal="Test",
            tasks=[
                Task(
                    id="t1",
                    type=TaskType.ANALYZE,
                    title="Analyze",
                    description="",
                    role="architect",
                    status=TaskStatus.COMPLETED,
                ),
                Task(
                    id="t2",
                    type=TaskType.IMPLEMENT,
                    title="Implement",
                    description="",
                    role="implementer",
                    dependencies=["t1"],
                ),
                Task(
                    id="t3",
                    type=TaskType.TEST,
                    title="Test",
                    description="",
                    role="tester",
                    dependencies=["t2"],
                ),
            ],
        )

        pending = plan.get_pending_tasks()

        # Only t2 should be pending (t1 done, t3 depends on t2)
        assert len(pending) == 1
        assert pending[0].id == "t2"

    def test_plan_get_task(self):
        """Test getting task by ID."""
        task = Task(
            id="target",
            type=TaskType.ANALYZE,
            title="Target",
            description="",
            role="architect",
        )
        plan = Plan(goal="Test", tasks=[task])

        found = plan.get_task("target")
        assert found is task

        not_found = plan.get_task("nonexistent")
        assert not_found is None


class TestPlanner:
    """Tests for Planner class."""

    def test_planner_creates_plan(self):
        """Test planner creates a valid plan."""
        planner = Planner()
        plan = planner.create_plan("Add a new feature")

        assert plan.goal == "Add a new feature"
        assert len(plan.tasks) > 0

    def test_planner_detects_healthcheck_keywords(self):
        """Test planner detects healthcheck-related keywords."""
        planner = Planner()
        plan = planner.create_plan("Add healthcheck endpoint")

        task_types = [t.type for t in plan.tasks]

        assert TaskType.DESIGN in task_types
        assert TaskType.IMPLEMENT in task_types
        assert TaskType.TEST in task_types

    def test_planner_detects_test_keywords(self):
        """Test planner detects test-related keywords."""
        planner = Planner()
        plan = planner.create_plan("Add unit tests for module X")

        task_types = [t.type for t in plan.tasks]

        assert TaskType.TEST in task_types

    def test_planner_detects_refactor_keywords(self):
        """Test planner detects refactoring keywords."""
        planner = Planner()
        plan = planner.create_plan("Refactor the authentication module")

        task_types = [t.type for t in plan.tasks]

        assert TaskType.ANALYZE in task_types
        assert TaskType.IMPLEMENT in task_types

    def test_planner_tasks_have_dependencies(self):
        """Test that tasks have proper dependencies."""
        planner = Planner()
        plan = planner.create_plan("Add a new API endpoint")

        # First task should have no dependencies
        assert plan.tasks[0].dependencies == []

        # Subsequent tasks should depend on previous
        for i in range(1, len(plan.tasks)):
            assert plan.tasks[i - 1].id in plan.tasks[i].dependencies

    def test_planner_assigns_correct_roles(self):
        """Test that tasks are assigned to correct roles."""
        planner = Planner()
        plan = planner.create_plan("Create new feature")

        role_types = {t.type: t.role for t in plan.tasks}

        if TaskType.ANALYZE in role_types:
            assert role_types[TaskType.ANALYZE] == "architect"
        if TaskType.IMPLEMENT in role_types:
            assert role_types[TaskType.IMPLEMENT] == "implementer"
        if TaskType.TEST in role_types:
            assert role_types[TaskType.TEST] == "tester"
        if TaskType.DOCUMENT in role_types:
            assert role_types[TaskType.DOCUMENT] == "documenter"

    def test_planner_extracts_goal_summary(self):
        """Test goal summary extraction."""
        planner = Planner()

        summary = planner._extract_goal_summary("Add healthcheck endpoint")
        assert "healthcheck" in summary.lower()

        long_summary = planner._extract_goal_summary("A" * 100)
        assert len(long_summary) <= 53  # 50 + "..."

    def test_default_workflow_for_unknown_goal(self):
        """Test default workflow for unrecognized goals."""
        planner = Planner()
        plan = planner.create_plan("Some random task xyz123")

        # Should have default workflow tasks
        task_types = {t.type for t in plan.tasks}
        assert TaskType.ANALYZE in task_types
        assert TaskType.VALIDATE in task_types


class TestCreatePlanForGoal:
    """Tests for convenience function."""

    def test_create_plan_for_goal(self):
        """Test the convenience function."""
        plan = create_plan_for_goal("Test goal")

        assert plan is not None
        assert plan.goal == "Test goal"
        assert len(plan.tasks) > 0
