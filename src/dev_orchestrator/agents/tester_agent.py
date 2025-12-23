"""Tester Agent - Test Generation and Validation.

Responsible for:
- Creating unit tests
- Creating integration tests
- Validating code quality
- Identifying edge cases
"""

from typing import Any

from .base_agent import AgentOutput, BaseAgent


class TesterAgent(BaseAgent):
    """Tester agent for test generation.

    Part of the parallel N phase in 1-N-1 workflow.
    Creates tests based on Architect's design and Implementer's code.
    """

    name = "tester"
    description = "Creates tests and validates code"

    @property
    def system_prompt(self) -> str:
        return """You are an expert Software Testing agent. Your role is to:

1. **Create** comprehensive tests for new and modified code
2. **Validate** that implementations meet requirements
3. **Identify** edge cases and potential bugs
4. **Ensure** adequate test coverage

## Your Responsibilities:
- Write unit tests for all new functions/methods
- Write integration tests where appropriate
- Test edge cases and error conditions
- Ensure tests are maintainable and clear
- Follow the project's testing conventions

## Testing Best Practices:
- Use descriptive test names
- Follow Arrange-Act-Assert pattern
- Test one thing per test
- Mock external dependencies
- Include positive and negative test cases
- Test boundary conditions

## Output Guidelines:
- Provide complete test files
- Include all necessary imports and fixtures
- Add docstrings explaining what each test validates
- List expected test commands to run

## Test Types to Consider:
1. **Unit Tests**: Test individual functions/methods
2. **Integration Tests**: Test component interactions
3. **Edge Case Tests**: Boundary conditions, empty inputs, etc.
4. **Error Tests**: Verify proper error handling

You will receive:
- The original goal
- Repository context
- Architect's design
- Implementer's code (if available)

Create tests that fully validate the implementation."""

    async def execute(
        self,
        goal: str,
        repo_context: dict[str, Any],
        previous_outputs: dict[str, AgentOutput] | None = None,
    ) -> AgentOutput:
        """Create tests for the implementation.

        Args:
            goal: The goal to accomplish
            repo_context: Context about the repository
            previous_outputs: Should contain architect_output, maybe implementer_output

        Returns:
            Test files and validation results
        """
        self.log("INFO", f"Creating tests for: {goal[:50]}...")

        context_str = self._format_repo_context(repo_context)
        prev_str = self._format_previous_outputs(previous_outputs)

        input_text = f"""## Goal
{goal}

## Repository Context
{context_str}

{prev_str}

## Your Task
Create comprehensive tests for the implementation:

1. Analyze the Architect's design and any implementation code
2. Create unit tests for all new functions/methods
3. Create integration tests if appropriate
4. Test edge cases and error handling
5. Follow the project's testing patterns (pytest)

For each test file, provide:
- Complete file path (usually in tests/ directory)
- Full file content with all tests
- Description of what is being tested

Include test commands that should be run:
- pytest command with appropriate flags
- Any setup needed before testing

Ensure tests are comprehensive and would catch common bugs."""

        result = await self._invoke_llm(input_text)

        self.log("INFO", f"Tests created: {len(result.file_changes)} test files")
        return result
