"""Documenter Agent - Documentation Generation.

Responsible for:
- Updating README and docs
- Creating/updating CHANGELOG
- Writing API documentation
- Adding inline documentation
"""

from typing import Any

from .base_agent import AgentOutput, BaseAgent


class DocumenterAgent(BaseAgent):
    """Documenter agent for documentation tasks.

    Part of the parallel N phase in 1-N-1 workflow.
    Creates documentation based on the implementation.
    """

    name = "documenter"
    description = "Creates and updates documentation"

    @property
    def system_prompt(self) -> str:
        return """You are an expert Technical Documentation agent. Your role is to:

1. **Document** new features and changes clearly
2. **Update** existing documentation to reflect changes
3. **Write** clear, user-friendly documentation
4. **Maintain** consistency with project documentation style

## Your Responsibilities:
- Update README.md with new features/usage
- Add or update CHANGELOG.md entries
- Write API documentation if applicable
- Ensure documentation is complete and accurate

## Documentation Best Practices:
- Write for the intended audience (developers, users, etc.)
- Use clear, concise language
- Include code examples where helpful
- Keep formatting consistent
- Add table of contents for long documents

## Output Guidelines:
- Provide complete file contents or clear diffs
- Include all markdown formatting
- Add code blocks with appropriate language tags
- List files to be created or modified

## Documentation Types:
1. **README**: Overview, installation, usage, examples
2. **CHANGELOG**: Version history, what changed
3. **API Docs**: Endpoints, parameters, responses
4. **Inline Docs**: Docstrings, comments

You will receive:
- The original goal
- Repository context
- Architect's design
- Implementer's code (if available)

Create documentation that helps users understand and use the new features."""

    async def execute(
        self,
        goal: str,
        repo_context: dict[str, Any],
        previous_outputs: dict[str, AgentOutput] | None = None,
    ) -> AgentOutput:
        """Create documentation for the implementation.

        Args:
            goal: The goal to accomplish
            repo_context: Context about the repository
            previous_outputs: Outputs from architect and possibly implementer

        Returns:
            Documentation changes
        """
        self.log("INFO", f"Documenting: {goal[:50]}...")

        context_str = self._format_repo_context(repo_context)
        prev_str = self._format_previous_outputs(previous_outputs)

        input_text = f"""## Goal
{goal}

## Repository Context
{context_str}

{prev_str}

## Your Task
Create or update documentation for the implementation:

1. Review the design and implementation
2. Update README.md if needed (new features, usage examples)
3. Add CHANGELOG.md entry for this change
4. Add any necessary API documentation
5. Ensure inline documentation is complete

For each documentation file, provide:
- Complete file path
- Action (create/modify)
- Full content or the sections to add/update
- Description of the documentation change

Make documentation clear, helpful, and consistent with the project style."""

        result = await self._invoke_llm(input_text)

        self.log("INFO", f"Documentation created: {len(result.file_changes)} files")
        return result
