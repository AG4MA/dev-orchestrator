"""LangGraph workflow for multi-agent orchestration.

Implements the 1-N-1 pattern:
1. Architect (analyze and design)
N. Implementer, Tester, Documenter (parallel execution)
1. Reviewer (aggregate and finalize)
"""

import asyncio
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from .base_agent import AgentOutput, AgentState
from .architect_agent import ArchitectAgent
from .implementer_agent import ImplementerAgent
from .tester_agent import TesterAgent
from .documenter_agent import DocumenterAgent
from .reviewer_agent import ReviewerAgent
from ..core.run_context import RunContext


def create_initial_state(
    goal: str,
    repo_path: str,
    repo_context: dict[str, Any],
) -> AgentState:
    """Create initial state for the workflow.

    Args:
        goal: The goal to accomplish
        repo_path: Path to target repository
        repo_context: Repository context (files, contents, etc.)

    Returns:
        Initial AgentState
    """
    return AgentState(
        goal=goal,
        repo_path=repo_path,
        repo_context=repo_context,
        architect_output=None,
        implementer_output=None,
        tester_output=None,
        documenter_output=None,
        reviewer_output=None,
        all_file_changes=[],
        all_issues=[],
        all_recommendations=[],
        messages=[],
        current_phase="init",
        errors=[],
    )


async def architect_node(state: AgentState, context: RunContext | None = None) -> AgentState:
    """Execute architect agent.

    Phase 1: Analyze and design.
    """
    agent = ArchitectAgent(context=context)

    output = await agent.execute(
        goal=state["goal"],
        repo_context=state.get("repo_context", {}),
    )

    return {
        **state,
        "architect_output": output,
        "current_phase": "architect_done",
    }


async def parallel_agents_node(state: AgentState, context: RunContext | None = None) -> AgentState:
    """Execute implementer, tester, and documenter in parallel.

    Phase N: Parallel execution.
    """
    # Get architect's output for context
    previous_outputs = {}
    if state.get("architect_output"):
        previous_outputs["architect"] = state["architect_output"]

    # Create agents
    implementer = ImplementerAgent(context=context)
    tester = TesterAgent(context=context)
    documenter = DocumenterAgent(context=context)

    # Execute in parallel
    results = await asyncio.gather(
        implementer.execute(
            goal=state["goal"],
            repo_context=state.get("repo_context", {}),
            previous_outputs=previous_outputs,
        ),
        tester.execute(
            goal=state["goal"],
            repo_context=state.get("repo_context", {}),
            previous_outputs=previous_outputs,
        ),
        documenter.execute(
            goal=state["goal"],
            repo_context=state.get("repo_context", {}),
            previous_outputs=previous_outputs,
        ),
        return_exceptions=True,
    )

    # Process results
    implementer_output = results[0] if not isinstance(results[0], Exception) else _error_output("implementer", results[0])
    tester_output = results[1] if not isinstance(results[1], Exception) else _error_output("tester", results[1])
    documenter_output = results[2] if not isinstance(results[2], Exception) else _error_output("documenter", results[2])

    return {
        **state,
        "implementer_output": implementer_output,
        "tester_output": tester_output,
        "documenter_output": documenter_output,
        "current_phase": "parallel_done",
    }


async def reviewer_node(state: AgentState, context: RunContext | None = None) -> AgentState:
    """Execute reviewer agent.

    Phase 1 (final): Review and aggregate.
    """
    agent = ReviewerAgent(context=context)

    # Collect all previous outputs
    previous_outputs = {}
    if state.get("architect_output"):
        previous_outputs["architect"] = state["architect_output"]
    if state.get("implementer_output"):
        previous_outputs["implementer"] = state["implementer_output"]
    if state.get("tester_output"):
        previous_outputs["tester"] = state["tester_output"]
    if state.get("documenter_output"):
        previous_outputs["documenter"] = state["documenter_output"]

    output = await agent.execute(
        goal=state["goal"],
        repo_context=state.get("repo_context", {}),
        previous_outputs=previous_outputs,
    )

    # Aggregate all file changes
    all_changes = []
    all_issues = []
    all_recommendations = []

    for agent_output in previous_outputs.values():
        all_changes.extend(agent_output.file_changes)
        all_issues.extend(agent_output.issues)
        all_recommendations.extend(agent_output.recommendations)

    # Add reviewer's changes/issues
    all_changes.extend(output.file_changes)
    all_issues.extend(output.issues)
    all_recommendations.extend(output.recommendations)

    return {
        **state,
        "reviewer_output": output,
        "all_file_changes": all_changes,
        "all_issues": all_issues,
        "all_recommendations": all_recommendations,
        "current_phase": "complete",
    }


def _error_output(agent_name: str, error: Exception) -> AgentOutput:
    """Create error output for a failed agent."""
    return AgentOutput(
        success=False,
        summary=f"{agent_name} failed: {error}",
        reasoning="Agent execution failed with exception",
        issues=[str(error)],
    )


def create_workflow(context: RunContext | None = None) -> StateGraph:
    """Create the LangGraph workflow for multi-agent orchestration.

    Workflow:
        [START] -> architect -> parallel_agents -> reviewer -> [END]

    The parallel_agents node internally runs:
        - Implementer
        - Tester
        - Documenter
    in parallel using asyncio.gather.

    Args:
        context: Run context for logging

    Returns:
        Compiled LangGraph StateGraph
    """
    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes with context binding
    workflow.add_node(
        "architect",
        lambda state: asyncio.get_event_loop().run_until_complete(
            architect_node(state, context)
        ) if not asyncio.get_event_loop().is_running() else architect_node(state, context)
    )

    workflow.add_node(
        "parallel_agents",
        lambda state: asyncio.get_event_loop().run_until_complete(
            parallel_agents_node(state, context)
        ) if not asyncio.get_event_loop().is_running() else parallel_agents_node(state, context)
    )

    workflow.add_node(
        "reviewer",
        lambda state: asyncio.get_event_loop().run_until_complete(
            reviewer_node(state, context)
        ) if not asyncio.get_event_loop().is_running() else reviewer_node(state, context)
    )

    # Define edges: 1 -> N -> 1
    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "parallel_agents")
    workflow.add_edge("parallel_agents", "reviewer")
    workflow.add_edge("reviewer", END)

    return workflow


async def run_workflow(
    goal: str,
    repo_path: str,
    repo_context: dict[str, Any],
    context: RunContext | None = None,
) -> AgentState:
    """Execute the full multi-agent workflow.

    Args:
        goal: The goal to accomplish
        repo_path: Path to target repository
        repo_context: Repository context
        context: Run context for logging

    Returns:
        Final state with all agent outputs
    """
    # Create initial state
    initial_state = create_initial_state(goal, repo_path, repo_context)

    # Run phases sequentially (but parallel_agents is internally parallel)
    state = await architect_node(initial_state, context)
    state = await parallel_agents_node(state, context)
    state = await reviewer_node(state, context)

    return state


class AgentWorkflow:
    """High-level interface for the multi-agent workflow."""

    def __init__(self, context: RunContext | None = None):
        """Initialize workflow.

        Args:
            context: Run context for logging
        """
        self.context = context

    async def execute(
        self,
        goal: str,
        repo_path: str,
        repo_context: dict[str, Any],
    ) -> AgentState:
        """Execute the workflow.

        Args:
            goal: The goal to accomplish
            repo_path: Path to target repository
            repo_context: Repository context

        Returns:
            Final workflow state
        """
        if self.context:
            self.context.log("INFO", "Starting multi-agent workflow")
            self.context.log("INFO", f"Goal: {goal[:100]}...")

        state = await run_workflow(
            goal=goal,
            repo_path=repo_path,
            repo_context=repo_context,
            context=self.context,
        )

        if self.context:
            self.context.log("INFO", f"Workflow complete. Phase: {state['current_phase']}")
            self.context.log("INFO", f"Total file changes: {len(state['all_file_changes'])}")
            self.context.log("INFO", f"Total issues: {len(state['all_issues'])}")

        return state
