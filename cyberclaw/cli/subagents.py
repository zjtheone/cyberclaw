"""CLI commands for managing subagents."""

import typer
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()

subagents_app = typer.Typer(
    name="subagents",
    help="Manage subagent runs for the current session",
    no_args_is_help=True,
)


@subagents_app.command("list")
def subagents_list(
    all: bool = typer.Option(False, "--all", "-a", help="Show completed subagents"),
):
    """
    List active subagents for the current session.

    Examples:
        cyberclaw subagents list
        cyberclaw subagents list --all
    """
    from cyberclaw.agent.subagent import SubagentManager
    from cyberclaw.config.loader import load_config

    config = load_config()
    # In a real implementation, get the manager from context
    # For now, this is a placeholder

    console.print("[yellow]Subagents list command - Implementation placeholder[/yellow]")
    console.print("")
    console.print("This command will show:")
    console.print("  - Active subagent runs")
    console.print("  - Task labels and IDs")
    console.print("  - Status (running, completed, failed)")
    console.print("  - Runtime and token usage")
    console.print("")
    console.print("Example output:")
    console.print("")

    # Example table
    table = Table(title="Active Subagents")
    table.add_column("ID", style="cyan")
    table.add_column("Label", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Runtime", style="blue")
    table.add_column("Depth", justify="right")

    table.add_row("abc123", "Research task", "running", "45s", "1")
    table.add_row("def456", "Code review", "running", "30s", "1")
    table.add_row("ghi789", "API implementation", "completed", "2m15s", "2")

    console.print(table)


@subagents_app.command("kill")
def subagents_kill(
    target: str = typer.Argument(
        ...,
        help="Subagent ID, '#N' (Nth subagent), or 'all'",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force kill without confirmation"),
):
    """
    Kill a subagent by ID or 'all'.

    Examples:
        cyberclaw subagents kill abc123
        cyberclaw subagents kill #1
        cyberclaw subagents kill all
    """
    from cyberclaw.agent.subagent import SubagentManager
    from cyberclaw.config.loader import load_config

    console.print(f"[yellow]Kill subagent: {target}[/yellow]")

    if target == "all":
        if not force:
            confirm = typer.confirm("Are you sure you want to kill ALL subagents?")
            if not confirm:
                console.print("[red]Cancelled[/red]")
                raise typer.Exit(0)

        # In real implementation: cancel all subagents
        console.print("[green]✓ All subagents killed[/green]")
    else:
        # In real implementation: cancel specific subagent
        console.print(f"[green]✓ Subagent {target} killed[/green]")


@subagents_app.command("log")
def subagents_log(
    target: str = typer.Argument(
        ...,
        help="Subagent ID or '#N' (Nth subagent)",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Number of lines to show",
    ),
    tools: bool = typer.Option(
        False,
        "--tools",
        "-t",
        help="Include tool executions in log",
    ),
):
    """
    Show log for a subagent.

    Examples:
        cyberclaw subagents log abc123
        cyberclaw subagents log #1 --limit 50
        cyberclaw subagents log abc123 --tools
    """
    console.print(f"[yellow]Log for subagent: {target}[/yellow]")
    console.print("")

    # Placeholder log output
    log_lines = [
        "[10:30:00] Subagent started",
        "[10:30:01] Task: Research Python async patterns",
        "[10:30:05] Tool: web_search(query='Python asyncio best practices')",
        "[10:30:10] Tool: web_fetch(url='https://docs.python.org/3/library/asyncio.html')",
        "[10:30:30] Analyzing results...",
        "[10:30:45] Tool: write_file(path='research.md', ...)",
        "[10:31:00] Task completed",
    ]

    for line in log_lines[-limit:]:
        console.print(f"  {line}")

    if tools:
        console.print("")
        console.print("[dim]Tool executions included[/dim]")


@subagents_app.command("info")
def subagents_info(
    target: str = typer.Argument(
        ...,
        help="Subagent ID or '#N' (Nth subagent)",
    ),
):
    """
    Show detailed information about a subagent.

    Examples:
        cyberclaw subagents info abc123
        cyberclaw subagents info #1
    """
    console.print(f"[yellow]Info for subagent: {target}[/yellow]")
    console.print("")

    # Placeholder info
    info = {
        "Task ID": "abc123",
        "Label": "Research task",
        "Status": "running",
        "Depth": "1",
        "Parent Session": "agent:main:main:1",
        "Session Key": "agent:main:subagent:abc123",
        "Started": "2026-03-03 10:30:00",
        "Runtime": "45s",
        "Model": "deepseek-reasoner",
        "Tokens": "1,234 (input: 800, output: 434)",
    }

    for key, value in info.items():
        console.print(f"  [cyan]{key}:[/cyan] {value}")


@subagents_app.command("send")
def subagents_send(
    target: str = typer.Argument(
        ...,
        help="Subagent ID or '#N' (Nth subagent)",
    ),
    message: str = typer.Argument(
        ...,
        help="Message to send",
    ),
):
    """
    Send a message to a subagent.

    Examples:
        cyberclaw subagents send abc123 "Please focus on error handling"
        cyberclaw subagents send #1 "Change the approach"
    """
    console.print(f"[yellow]Sending message to {target}:[/yellow]")
    console.print(f"  [green]{message}[/green]")
    console.print("")
    console.print(
        "[dim]In real implementation, this will send the message to the subagent session[/dim]"
    )
    console.print("[green]✓ Message sent[/green]")


@subagents_app.command("steer")
def subagents_steering(
    target: str = typer.Argument(
        ...,
        help="Subagent ID or '#N' (Nth subagent)",
    ),
    message: str = typer.Argument(
        ...,
        help="Steering instruction",
    ),
    priority: str = typer.Option(
        "normal",
        "--priority",
        "-p",
        help="Priority: low, normal, high",
        case_sensitive=False,
    ),
):
    """
    Send a steering instruction to a running subagent.

    Steering messages guide the subagent's behavior without interrupting it.

    Examples:
        cyberclaw subagents steer abc123 "Focus on performance over features"
        cyberclaw subagents steer #1 "Use async/await pattern" --priority high
    """
    console.print(f"[yellow]Steering subagent {target}:[/yellow]")
    console.print(f"  [green]{message}[/green]")
    console.print(f"  Priority: [cyan]{priority}[/cyan]")
    console.print("")
    console.print(
        "[dim]In real implementation, this will inject the instruction into the subagent's context[/dim]"
    )
    console.print("[green]✓ Steering instruction sent[/green]")


@subagents_app.command("spawn")
def subagents_spawn(
    agent_id: str = typer.Argument(
        ...,
        help="Target agent ID",
    ),
    task: str = typer.Argument(
        ...,
        help="Task description",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Override model for this subagent",
    ),
    thinking: Optional[str] = typer.Option(
        None,
        "--thinking",
        "-t",
        help="Thinking level: quick, balanced, thorough",
    ),
    label: Optional[str] = typer.Option(
        None,
        "--label",
        "-l",
        help="Display label for the subagent",
    ),
):
    """
    Spawn a new subagent run.

    Examples:
        cyberclaw subagents spawn coding "Implement REST API endpoints"
        cyberclaw subagents spawn main "Research async patterns" --model claude-opus
        cyberclaw subagents spawn research "Analyze market trends" --thinking thorough
    """
    console.print(f"[yellow]Spawning subagent:[/yellow]")
    console.print(f"  Agent: [cyan]{agent_id}[/cyan]")
    console.print(f"  Task: [green]{task[:100]}{'...' if len(task) > 100 else ''}[/green]")
    if model:
        console.print(f"  Model: [magenta]{model}[/magenta]")
    if thinking:
        console.print(f"  Thinking: [magenta]{thinking}[/magenta]")
    if label:
        console.print(f"  Label: [magenta]{label}[/magenta]")
    console.print("")
    console.print("[dim]In real implementation, this will create a new subagent session[/dim]")
    console.print("[green]✓ Subagent spawned (id: abc123)[/green]")


@subagents_app.command("tree")
def subagents_tree(
    root: Optional[str] = typer.Option(
        None,
        "--root",
        "-r",
        help="Root session key (default: current session)",
    ),
):
    """
    Show the spawn tree structure.

    Examples:
        cyberclaw subagents tree
        cyberclaw subagents tree --root agent:main:main:1
    """
    console.print("[yellow]Spawn Tree[/yellow]")
    console.print("")

    # ASCII tree visualization
    tree_ascii = """
agent:main:main:1 (Main Agent)
├── agent:main:subagent:abc123 (Orchestrator)
│   ├── agent:main:subagent:def456 (Worker)
│   ├── agent:main:subagent:ghi789 (Worker)
│   └── agent:main:subagent:jkl012 (Worker)
└── agent:main:subagent:mno345 (Research)
    """

    console.print(f"[cyan]{tree_ascii}[/cyan]")


def get_app() -> typer.Typer:
    """Get the subagents CLI app."""
    return subagents_app


if __name__ == "__main__":
    subagents_app()
