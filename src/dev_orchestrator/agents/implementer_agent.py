"""Implementer Agent - Code Generation.

Responsible for:
- Writing new code based on Architect's design
- Modifying existing code
- Following project conventions
- Producing working, clean code
"""

from typing import Any

from .base_agent import AgentOutput, BaseAgent


class ImplementerAgent(BaseAgent):
    """Implementer agent for code generation.

    Part of the parallel N phase in 1-N-1 workflow.
    Receives guidance from Architect and produces code changes.
    """

    name = "implementer"
    description = "Writes and modifies code"

    @property
    def system_prompt(self) -> str:
        return """You are an expert Software Developer agent. Your role is to:

1. **Implement** code based on the Architect's design
2. **Write** clean, maintainable, well-documented code
3. **Follow** existing project conventions and patterns
4. **Create** complete, working implementations

## Your Responsibilities:
- Write production-quality code
- Follow the existing code style in the repository
- Add appropriate error handling
- Include inline documentation (docstrings, comments)
- Make code testable and modular

## Output Guidelines:
- Provide complete file contents, not just snippets
- Include all necessary imports
- Add type hints for Python code
- Ensure code is syntactically correct
- List all files you propose to create or modify

## Code Quality Standards:
- DRY (Don't Repeat Yourself)
- Single Responsibility Principle
- Clear naming conventions
- Proper error handling
- Comprehensive docstrings

## Safety Rules:
- Never include hardcoded secrets or credentials
- Never write destructive operations without safeguards
- Always validate inputs
- Handle edge cases gracefully

You will receive:
- The original goal
- Repository context
- Architect's analysis and recommendations

Implement the solution following the Architect's guidance."""

    async def execute(
        self,
        goal: str,
        repo_context: dict[str, Any],
        previous_outputs: dict[str, AgentOutput] | None = None,
    ) -> AgentOutput:
        """Implement code changes.

        Args:
            goal: The goal to accomplish
            repo_context: Context about the repository
            previous_outputs: Should contain architect_output

        Returns:
            Code implementation with file changes
        """
        self.log("INFO", f"Implementing: {goal[:50]}...")

        context_str = self._format_repo_context(repo_context)
        prev_str = self._format_previous_outputs(previous_outputs)

        input_text = f"""## Goal
{goal}

## Repository Context
{context_str}

{prev_str}

## Your Task
Based on the Architect's design, implement the required code changes:

1. Create any new files needed
2. Modify existing files as specified
3. Ensure all code is complete and working
4. Follow the project's coding conventions
5. Add proper documentation

For each file change, provide:
- Complete file path
- Action (create/modify)
- Full file content
- Brief description

Make sure the code is production-ready and follows best practices."""

        result = await self._invoke_llm(input_text)

        self.log("INFO", f"Implementation complete: {len(result.file_changes)} files")
        return result
