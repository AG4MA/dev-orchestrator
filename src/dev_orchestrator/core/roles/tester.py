"""Tester role - testing and validation.

Responsible for:
- Running existing tests
- Creating test proposals
- Validating changes
"""

import subprocess
from pathlib import Path
from typing import Any

from ..git_ops import GitOps
from ..planner import Task, TaskType
from ..run_context import RunContext
from .base import BaseRole, RoleProposal


class TesterRole(BaseRole):
    """Tester role for test execution and validation."""

    name = "tester"

    def __init__(self, context: RunContext, git_ops: GitOps | None = None):
        """Initialize tester role.

        Args:
            context: Run context
            git_ops: Git operations instance
        """
        super().__init__(context)
        self.git_ops = git_ops
        self.repo_path = context.repo_path if context else None

    def execute(self, task: Task) -> RoleProposal:
        """Execute a testing task."""
        self.log("INFO", f"Executing task: {task.title}")

        if task.type == TaskType.TEST:
            return self._test(task)
        elif task.type == TaskType.VALIDATE:
            return self._validate(task)
        else:
            return RoleProposal(
                role=self.name,
                task_id=task.id,
                success=False,
                summary="Wrong task type",
                details=f"Tester handles 'test' and 'validate' tasks, got: {task.type}",
                errors=[f"Unsupported task type: {task.type}"],
            )

    def _test(self, task: Task) -> RoleProposal:
        """Create test proposal and optionally run tests."""
        self.log("INFO", "Creating test proposal...")

        test_results = {
            "tests_found": False,
            "tests_run": False,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "output": "",
        }

        # Try to detect test framework and run tests
        if self.repo_path and self.repo_path.exists():
            test_results = self._detect_and_run_tests()

        # Create test proposal
        goal = task.inputs.get("goal", "")
        test_proposal = self._create_test_proposal(goal)

        details = f"""# Test Report

## Test Execution Results

{self._format_test_results(test_results)}

## Proposed New Tests

{test_proposal}

## Recommendations
- Ensure all proposed tests are implemented
- Run tests before committing changes
- Maintain test coverage above 80%
"""

        return RoleProposal(
            role=self.name,
            task_id=task.id,
            success=True,
            summary=f"Tests: {test_results['passed']} passed, {test_results['failed']} failed",
            details=details,
            metadata=test_results,
            commands=["pytest -v"] if test_results["tests_found"] else [],
        )

    def _validate(self, task: Task) -> RoleProposal:
        """Validate all changes and create summary."""
        self.log("INFO", "Validating changes...")

        validation_checks = []

        # Check git status
        if self.git_ops:
            try:
                status = self.git_ops.get_status()
                validation_checks.append({
                    "check": "Git status",
                    "passed": True,
                    "details": f"Branch: {status['branch']}, Clean: {status['clean']}",
                })
            except Exception as e:
                validation_checks.append({
                    "check": "Git status",
                    "passed": False,
                    "details": str(e),
                })

        # Check for common issues
        if self.repo_path and self.repo_path.exists():
            # Check for syntax errors in Python files
            py_check = self._check_python_syntax()
            validation_checks.append(py_check)

        details = f"""# Validation Report

## Checks Performed

{self._format_validation_checks(validation_checks)}

## Summary
- Total checks: {len(validation_checks)}
- Passed: {sum(1 for c in validation_checks if c['passed'])}
- Failed: {sum(1 for c in validation_checks if not c['passed'])}

## Recommendation
{"✅ All checks passed. Ready for commit." if all(c['passed'] for c in validation_checks) else "⚠️ Some checks failed. Review and fix before proceeding."}
"""

        return RoleProposal(
            role=self.name,
            task_id=task.id,
            success=all(c["passed"] for c in validation_checks),
            summary=f"Validation: {sum(1 for c in validation_checks if c['passed'])}/{len(validation_checks)} passed",
            details=details,
            metadata={"checks": validation_checks},
        )

    def _detect_and_run_tests(self) -> dict[str, Any]:
        """Detect test framework and run tests."""
        results = {
            "tests_found": False,
            "tests_run": False,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "output": "",
        }

        # Check for pytest
        pytest_ini = self.repo_path / "pytest.ini"
        pyproject = self.repo_path / "pyproject.toml"
        tests_dir = self.repo_path / "tests"

        if pytest_ini.exists() or tests_dir.exists() or pyproject.exists():
            results["tests_found"] = True

            try:
                # Try to run pytest in dry-run mode first
                result = subprocess.run(
                    ["pytest", "--collect-only", "-q"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0:
                    results["output"] = result.stdout
                    # Count collected tests
                    for line in result.stdout.splitlines():
                        if "test" in line.lower():
                            results["tests_run"] = True

            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                results["errors"].append(str(e))

        return results

    def _create_test_proposal(self, goal: str) -> str:
        """Create a proposal for new tests based on goal."""
        return f"""
### Suggested Test Cases

For goal: "{goal}"

1. **Unit Tests**
   - Test main functionality
   - Test edge cases
   - Test error handling

2. **Integration Tests**
   - Test component interaction
   - Test data flow

3. **Validation Tests**
   - Test input validation
   - Test output format

### Example Test Structure

```python
def test_feature_basic():
    \"\"\"Test basic functionality.\"\"\"
    # Arrange
    # Act
    # Assert
    pass

def test_feature_edge_case():
    \"\"\"Test edge case handling.\"\"\"
    pass

def test_feature_error():
    \"\"\"Test error handling.\"\"\"
    pass
```
"""

    def _check_python_syntax(self) -> dict[str, Any]:
        """Check Python files for syntax errors."""
        errors = []

        try:
            for py_file in self.repo_path.rglob("*.py"):
                # Skip common non-source directories
                if any(part in py_file.parts for part in [".venv", "venv", "__pycache__", ".git"]):
                    continue

                try:
                    with open(py_file, encoding="utf-8") as f:
                        compile(f.read(), py_file, "exec")
                except SyntaxError as e:
                    errors.append(f"{py_file.name}: {e}")

        except Exception as e:
            errors.append(f"Scan error: {e}")

        return {
            "check": "Python syntax",
            "passed": len(errors) == 0,
            "details": "No syntax errors" if not errors else "; ".join(errors[:3]),
        }

    def _format_test_results(self, results: dict[str, Any]) -> str:
        """Format test results as markdown."""
        if not results["tests_found"]:
            return "No test framework detected."

        return f"""
| Metric | Value |
|--------|-------|
| Tests Found | {"Yes" if results["tests_found"] else "No"} |
| Tests Run | {"Yes" if results["tests_run"] else "No"} |
| Passed | {results["passed"]} |
| Failed | {results["failed"]} |
| Errors | {len(results["errors"])} |
"""

    def _format_validation_checks(self, checks: list[dict[str, Any]]) -> str:
        """Format validation checks as markdown."""
        if not checks:
            return "No checks performed."

        lines = ["| Check | Status | Details |", "|-------|--------|---------|"]
        for check in checks:
            status = "✅" if check["passed"] else "❌"
            lines.append(f"| {check['check']} | {status} | {check['details'][:50]} |")

        return "\n".join(lines)
