"""Architect Agent - Analysis and Design.

Responsible for:
- Analyzing codebase structure
- Understanding the goal and context
- Designing solutions
- Decomposing work for other agents
"""

from typing import Any

from .base_agent import AgentOutput, BaseAgent


class ArchitectAgent(BaseAgent):
    """Architect agent for analysis and design tasks.

    First in the 1-N-1 workflow. Analyzes the goal and repository,
    then provides guidance for Implementer, Tester, and Documenter.
    """

    name = "architect"
    description = "Analyzes codebase and designs solutions"

    @property
    def system_prompt(self) -> str:
        return """You are an expert Software Architect agent. Your role is to:

1. **Analyze** the codebase structure and understand existing patterns
2. **Design** solutions that fit the codebase architecture
3. **Decompose** the goal into specific, actionable tasks
4. **Guide** other agents (Implementer, Tester, Documenter) with clear instructions

## Your Responsibilities:
- Identify which files need to be created or modified
- Determine the best location for new code
- Ensure consistency with existing code style and patterns
- Consider edge cases and error handling
- Think about testing strategy
- Consider documentation needs

## Output Guidelines:
- Be specific about file paths and changes needed
- Provide clear reasoning for your design decisions
- List potential issues or risks
- Give concrete recommendations for each subsequent agent

## Safety Rules:
- Never suggest modifying protected branches directly
- Always recommend creating changes on a feature branch
- Consider backward compatibility
- Flag any security concerns

You will receive:
- The goal/objective to accomplish
- Repository context (file structure, relevant file contents)

Analyze thoroughly and provide a detailed technical design."""

    async def execute(
        self,
        goal: str,
        repo_context: dict[str, Any],
        previous_outputs: dict[str, AgentOutput] | None = None,
    ) -> AgentOutput:
        """Analyze repository and design solution.

        Args:
            goal: The goal to accomplish
            repo_context: Context about the repository
            previous_outputs: Not used (architect is first)

        Returns:
            Design document with recommendations for other agents
        """
        self.log("INFO", f"Analyzing goal: {goal[:50]}...")

        context_str = self._format_repo_context(repo_context)

        input_text = f"""## Goal
{goal}

## Repository Context
{context_str}

## Your Task
1. Analyze the repository structure and understand the context
2. Design a solution for the goal
3. Identify specific files to create or modify
4. Provide clear guidance for:
   - Implementer: What code to write and where
   - Tester: What tests to create
   - Documenter: What documentation to update

Be specific and actionable. Include file paths, function signatures, and implementation details."""

        result = await self._invoke_llm(input_text)

        self.log("INFO", f"Analysis complete: {len(result.file_changes)} changes proposed")
        return result
