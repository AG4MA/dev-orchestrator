"""Reviewer Agent - Final Review and Aggregation.

Responsible for:
- Reviewing all proposed changes
- Resolving conflicts
- Creating final change set
- Quality assurance
"""

from typing import Any

from .base_agent import AgentOutput, BaseAgent, FileChange


class ReviewerAgent(BaseAgent):
    """Reviewer agent for final review and aggregation.

    Final "1" in the 1-N-1 workflow.
    Reviews outputs from all agents and creates final recommendations.
    """

    name = "reviewer"
    description = "Reviews and aggregates all changes"

    @property
    def system_prompt(self) -> str:
        return """You are an expert Code Reviewer agent. Your role is to:

1. **Review** all proposed changes from other agents
2. **Identify** conflicts or inconsistencies
3. **Aggregate** the best changes into a coherent set
4. **Ensure** overall quality and consistency

## Your Responsibilities:
- Review code changes for quality and correctness
- Verify tests adequately cover the implementation
- Ensure documentation is complete
- Identify any missing pieces
- Resolve conflicts between agent proposals
- Create the final, approved change set

## Review Checklist:
- [ ] Code follows project conventions
- [ ] Error handling is appropriate
- [ ] Tests cover main functionality and edge cases
- [ ] Documentation is clear and complete
- [ ] No security issues
- [ ] No hardcoded secrets
- [ ] Changes are consistent with each other

## Output Guidelines:
- Provide the final, consolidated list of file changes
- Include any modifications needed to resolve conflicts
- List any remaining issues or concerns
- Give clear go/no-go recommendation
- Include the final commit message

## Quality Gates:
1. **Code Quality**: Clean, maintainable, follows patterns
2. **Test Coverage**: Adequate tests for new code
3. **Documentation**: README/CHANGELOG updated
4. **Security**: No vulnerabilities introduced
5. **Consistency**: All changes work together

You will receive outputs from:
- Architect: Design and recommendations
- Implementer: Code changes
- Tester: Test files
- Documenter: Documentation updates

Synthesize these into a final, approved change set."""

    async def execute(
        self,
        goal: str,
        repo_context: dict[str, Any],
        previous_outputs: dict[str, AgentOutput] | None = None,
    ) -> AgentOutput:
        """Review and aggregate all agent outputs.

        Args:
            goal: The goal to accomplish
            repo_context: Context about the repository
            previous_outputs: All previous agent outputs

        Returns:
            Final reviewed and aggregated changes
        """
        self.log("INFO", "Reviewing all changes...")

        prev_str = self._format_previous_outputs(previous_outputs)

        # Collect all file changes from previous agents
        all_changes: list[FileChange] = []
        all_issues: list[str] = []

        if previous_outputs:
            for output in previous_outputs.values():
                all_changes.extend(output.file_changes)
                all_issues.extend(output.issues)

        changes_summary = "\n".join(
            f"- `{fc.path}` ({fc.action}): {fc.description}"
            for fc in all_changes
        ) if all_changes else "No file changes proposed."

        input_text = f"""## Goal
{goal}

{prev_str}

## All Proposed File Changes
{changes_summary}

## Known Issues from Agents
{chr(10).join(f"- {issue}" for issue in all_issues) if all_issues else "No issues reported."}

## Your Task
1. Review all proposed changes for quality and consistency
2. Identify any conflicts or issues
3. Resolve conflicts by choosing or merging the best approaches
4. Create the final, approved list of file changes
5. Verify the changes together fulfill the goal

Provide:
1. Your review assessment
2. The final consolidated file changes (may be same, modified, or merged)
3. Any remaining concerns
4. Recommended commit message
5. Go/No-Go recommendation

Be thorough but decisive. The goal is to produce a working, high-quality result."""

        result = await self._invoke_llm(input_text)

        # If no file changes in result, use aggregated changes
        if not result.file_changes and all_changes:
            result.file_changes = all_changes

        self.log("INFO", f"Review complete: {len(result.file_changes)} files approved")
        return result
