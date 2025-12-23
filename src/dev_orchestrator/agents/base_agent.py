"""Base agent class for LangChain-powered agents.

Provides common functionality for all agentic roles.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ..core.llm_config import create_chat_model, get_llm_config
from ..core.run_context import RunContext


class FileChange(BaseModel):
    """Represents a proposed file change."""

    path: str = Field(description="File path relative to repository root")
    action: str = Field(description="Action: create, modify, delete")
    content: str = Field(description="New file content or diff")
    description: str = Field(description="What this change does")


class AgentOutput(BaseModel):
    """Structured output from an agent."""

    success: bool = Field(description="Whether the agent completed successfully")
    summary: str = Field(description="Brief summary of what was done")
    reasoning: str = Field(description="Agent's reasoning process")
    file_changes: list[FileChange] = Field(default_factory=list, description="Proposed file changes")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations for next steps")
    issues: list[str] = Field(default_factory=list, description="Issues or concerns found")


class AgentState(TypedDict, total=False):
    """Shared state between agents in the workflow.

    This is the state that flows through the LangGraph graph.
    """

    # Input
    goal: str
    repo_path: str
    repo_context: dict[str, Any]

    # Agent outputs (collected during execution)
    architect_output: AgentOutput | None
    implementer_output: AgentOutput | None
    tester_output: AgentOutput | None
    documenter_output: AgentOutput | None
    reviewer_output: AgentOutput | None

    # Aggregated results
    all_file_changes: list[FileChange]
    all_issues: list[str]
    all_recommendations: list[str]

    # Execution metadata
    messages: list[Any]
    current_phase: str
    errors: list[str]


class BaseAgent(ABC):
    """Base class for LangChain-powered agents.

    Each agent:
    - Has a specific role and system prompt
    - Uses structured output for consistency
    - Can access repository context
    - Produces verifiable outputs
    """

    name: str = "base"
    description: str = "Base agent"

    def __init__(
        self,
        context: RunContext | None = None,
        llm: ChatOpenAI | None = None,
        temperature: float | None = None,
    ):
        """Initialize agent.

        Args:
            context: Run context for logging
            llm: Pre-configured LLM (creates one if None)
            temperature: Override temperature for this agent
        """
        self.context = context
        self._llm = llm
        self._temperature = temperature
        self._chain = None

    @property
    def llm(self) -> ChatOpenAI:
        """Get or create LLM instance."""
        if self._llm is None:
            self._llm = create_chat_model(temperature=self._temperature)
        return self._llm

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        pass

    def _build_prompt(self) -> ChatPromptTemplate:
        """Build the prompt template for this agent."""
        return ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="messages", optional=True),
            ("human", "{input}"),
        ])

    def _get_structured_llm(self) -> Any:
        """Get LLM configured for structured output."""
        return self.llm.with_structured_output(AgentOutput, method="function_calling")

    def log(self, level: str, message: str) -> None:
        """Log through context if available."""
        if self.context:
            self.context.log(level, f"[{self.name}] {message}")

    def _format_repo_context(self, repo_context: dict[str, Any]) -> str:
        """Format repository context for the prompt."""
        if not repo_context:
            return "No repository context available."

        parts = []

        if "files" in repo_context:
            files = repo_context["files"][:50]  # Limit to 50 files
            parts.append(f"**Files ({len(repo_context['files'])} total):**\n" +
                        "\n".join(f"- {f}" for f in files))

        if "file_contents" in repo_context:
            parts.append("**File Contents:**")
            for path, content in repo_context["file_contents"].items():
                # Truncate long files
                truncated = content[:2000] + "..." if len(content) > 2000 else content
                parts.append(f"\n`{path}`:\n```\n{truncated}\n```")

        if "git_status" in repo_context:
            parts.append(f"**Git Status:** {repo_context['git_status']}")

        return "\n\n".join(parts)

    @abstractmethod
    async def execute(
        self,
        goal: str,
        repo_context: dict[str, Any],
        previous_outputs: dict[str, AgentOutput] | None = None,
    ) -> AgentOutput:
        """Execute the agent's task.

        Args:
            goal: The goal to accomplish
            repo_context: Context about the repository
            previous_outputs: Outputs from previous agents in the workflow

        Returns:
            Structured agent output
        """
        pass

    async def _invoke_llm(
        self,
        input_text: str,
        messages: list[Any] | None = None,
    ) -> AgentOutput:
        """Invoke the LLM and get structured output.

        Args:
            input_text: The input/question for the agent
            messages: Optional conversation history

        Returns:
            Structured AgentOutput
        """
        self.log("INFO", f"Invoking LLM...")

        prompt = self._build_prompt()
        structured_llm = self._get_structured_llm()

        chain = prompt | structured_llm

        try:
            result = await chain.ainvoke({
                "input": input_text,
                "messages": messages or [],
            })

            self.log("INFO", f"LLM response received: {result.summary}")
            return result

        except Exception as e:
            self.log("ERROR", f"LLM invocation failed: {e}")
            return AgentOutput(
                success=False,
                summary=f"Agent failed: {e}",
                reasoning="LLM invocation error",
                issues=[str(e)],
            )

    def _format_previous_outputs(
        self,
        previous_outputs: dict[str, AgentOutput] | None,
    ) -> str:
        """Format previous agent outputs for context."""
        if not previous_outputs:
            return ""

        parts = ["## Previous Agent Outputs\n"]

        for agent_name, output in previous_outputs.items():
            parts.append(f"### {agent_name.capitalize()}")
            parts.append(f"**Summary:** {output.summary}")
            parts.append(f"**Reasoning:** {output.reasoning[:500]}...")

            if output.file_changes:
                parts.append("**Proposed Changes:**")
                for fc in output.file_changes:
                    parts.append(f"- `{fc.path}` ({fc.action}): {fc.description}")

            if output.recommendations:
                parts.append("**Recommendations:**")
                for rec in output.recommendations[:3]:
                    parts.append(f"- {rec}")

            parts.append("")

        return "\n".join(parts)
