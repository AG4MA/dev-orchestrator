"""CLI entrypoint for dev-orchestrator.

Uses Typer for CLI and Rich for beautiful output.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

from . import __version__
from .core.config import get_config
from .core.executor import Executor
from .core.run_context import RunContext, RunStatus

app = typer.Typer(
    name="orchestrator",
    help="Dev Orchestrator - Agentic development workflow orchestrator",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"[bold blue]dev-orchestrator[/] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Dev Orchestrator - Agentic development workflow orchestrator."""
    pass


@app.command("run")
def run_command(
    repo: str = typer.Option(
        ...,
        "--repo",
        "-r",
        help="Path or URL to the target repository",
    ),
    goal: str = typer.Option(
        ...,
        "--goal",
        "-g",
        help="The goal/objective to accomplish",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Plan only, don't apply changes",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output",
    ),
) -> None:
    """Execute an orchestrator run on a target repository.

    Example:
        orchestrator run --repo /path/to/repo --goal "Add healthcheck endpoint"
    """
    config = get_config()
    config.dry_run = dry_run
    config.verbose = verbose
    config.ensure_dirs()

    repo_path = Path(repo).resolve()

    # Header
    console.print()
    console.print(Panel.fit(
        f"[bold blue]Dev Orchestrator[/] v{__version__}",
        subtitle="Agentic Development Workflow",
    ))
    console.print()

    # Show run info
    table = Table(title="Run Configuration", show_header=False, box=None)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Repository", str(repo_path))
    table.add_row("Goal", goal[:60] + "..." if len(goal) > 60 else goal)
    table.add_row("Dry Run", "Yes" if dry_run else "No")
    console.print(table)
    console.print()

    # Create run context
    context = RunContext.create(repo_path, goal)

    console.print(f"[dim]Run ID: {context.run_id}[/]")
    console.print()

    try:
        executor = Executor(context)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Setup
            task = progress.add_task("Setting up...", total=None)
            executor.setup()
            progress.update(task, description="[green]✓[/] Setup complete")

            # Create plan
            progress.update(task, description="Creating plan...")
            plan = executor.create_plan()
            progress.update(task, description=f"[green]✓[/] Plan created ({len(plan.tasks)} tasks)")

            if dry_run:
                progress.update(task, description="[yellow]⏹[/] Dry run - stopping before changes")
                console.print()
                _show_plan(plan)
                context.set_status(RunStatus.COMPLETED)
                context.save()
                return

            # Create branch
            progress.update(task, description="Creating branch...")
            branch = executor.create_branch()
            progress.update(task, description=f"[green]✓[/] Branch created: {branch}")

            # Execute tasks
            for i, plan_task in enumerate(plan.tasks, 1):
                progress.update(
                    task,
                    description=f"Executing task {i}/{len(plan.tasks)}: {plan_task.title[:30]}...",
                )
                executor.execute_task(plan_task)

            progress.update(task, description="[green]✓[/] Tasks executed")

            # Apply changes
            progress.update(task, description="Applying changes...")
            modified = executor.apply_changes()
            progress.update(task, description=f"[green]✓[/] Applied {len(modified)} file(s)")

            # Commit
            progress.update(task, description="Committing changes...")
            executor.commit_changes()
            progress.update(task, description="[green]✓[/] Changes committed")

            # Generate report
            progress.update(task, description="Generating report...")
            report_path = executor.generate_report()
            progress.update(task, description="[green]✓[/] Report generated")

            context.set_status(RunStatus.COMPLETED)
            context.save()

        # Show summary
        console.print()
        _show_summary(context, executor)

        console.print()
        console.print(f"[bold green]✓ Run completed successfully![/]")
        console.print(f"[dim]Report: {report_path}[/]")

    except Exception as e:
        context.set_status(RunStatus.FAILED)
        context.add_error(str(e))
        context.save()

        console.print()
        console.print(f"[bold red]✗ Run failed: {e}[/]")
        raise typer.Exit(code=1)


@app.command("status")
def status_command(
    run_id: Optional[str] = typer.Argument(
        None,
        help="Run ID to check. If not provided, lists recent runs.",
    ),
) -> None:
    """Check status of a run or list recent runs."""
    config = get_config()

    if run_id:
        # Show specific run
        try:
            context = RunContext.load(run_id)
            _show_run_details(context)
        except FileNotFoundError:
            console.print(f"[red]Run not found: {run_id}[/]")
            raise typer.Exit(code=1)
    else:
        # List recent runs
        runs = RunContext.list_runs()

        if not runs:
            console.print("[dim]No runs found.[/]")
            return

        table = Table(title="Recent Runs")
        table.add_column("Run ID", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Goal")

        for rid in sorted(runs, reverse=True)[:10]:
            try:
                ctx = RunContext.load(rid)
                status_color = {
                    RunStatus.COMPLETED: "green",
                    RunStatus.FAILED: "red",
                    RunStatus.EXECUTING: "yellow",
                }.get(ctx.status, "dim")

                table.add_row(
                    rid,
                    f"[{status_color}]{ctx.status.value}[/]",
                    ctx.goal[:50] + "..." if len(ctx.goal) > 50 else ctx.goal,
                )
            except Exception:
                table.add_row(rid, "[dim]unknown[/]", "[dim]Error loading[/]")

        console.print(table)


@app.command("list")
def list_command() -> None:
    """List all runs."""
    status_command(run_id=None)


@app.command("report")
def report_command(
    run_id: str = typer.Argument(..., help="Run ID to show report for"),
) -> None:
    """Display the report for a run."""
    try:
        context = RunContext.load(run_id)

        if context.report_file.exists():
            report = context.report_file.read_text(encoding="utf-8")
            from rich.markdown import Markdown
            console.print(Markdown(report))
        else:
            console.print("[yellow]Report not found for this run.[/]")

    except FileNotFoundError:
        console.print(f"[red]Run not found: {run_id}[/]")
        raise typer.Exit(code=1)


@app.command("config")
def config_command() -> None:
    """Show current configuration."""
    config = get_config()

    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    for key, value in config.to_dict().items():
        table.add_row(key, str(value))

    console.print(table)


def _show_plan(plan) -> None:
    """Display the execution plan."""
    tree = Tree(f"[bold]Plan: {plan.goal[:50]}...[/]")

    for task in plan.tasks:
        task_node = tree.add(f"[cyan]{task.id}[/] {task.title}")
        task_node.add(f"[dim]Role: {task.role}[/]")
        task_node.add(f"[dim]Type: {task.type.value}[/]")
        if task.dependencies:
            task_node.add(f"[dim]Depends on: {', '.join(task.dependencies)}[/]")

    console.print(tree)


def _show_summary(context: RunContext, executor: Executor) -> None:
    """Display run summary."""
    table = Table(title="Run Summary", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Run ID", context.run_id)
    table.add_row("Status", context.status.value)
    table.add_row("Branch", context.branch_name or "N/A")
    table.add_row("Tasks", str(len(executor.proposals)))
    table.add_row("Files Modified", str(len(executor.modified_files)))
    table.add_row("Errors", str(len(context.errors)))

    console.print(table)


def _show_run_details(context: RunContext) -> None:
    """Display detailed run information."""
    console.print(Panel.fit(f"[bold]{context.run_id}[/]"))

    table = Table(show_header=False, box=None)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    status_color = {
        RunStatus.COMPLETED: "green",
        RunStatus.FAILED: "red",
        RunStatus.EXECUTING: "yellow",
    }.get(context.status, "dim")

    table.add_row("Status", f"[{status_color}]{context.status.value}[/]")
    table.add_row("Goal", context.goal)
    table.add_row("Repository", str(context.repo_path))
    table.add_row("Branch", context.branch_name or "N/A")
    table.add_row("Created", context.created_at.isoformat())
    table.add_row("Updated", context.updated_at.isoformat())

    console.print(table)

    if context.errors:
        console.print()
        console.print("[bold red]Errors:[/]")
        for error in context.errors:
            console.print(f"  [red]• {error}[/]")


if __name__ == "__main__":
    app()
