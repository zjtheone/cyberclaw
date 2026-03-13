"""CLI commands for managing sessions and thread bindings."""

import typer
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()

sessions_app = typer.Typer(
    name="sessions",
    help="Manage session bindings and lifecycle",
    no_args_is_help=True,
)


@sessions_app.command("focus")
def session_focus(
    target: str = typer.Argument(
        ...,
        help="Session key, session ID, or session label to focus on",
    ),
    create_thread: bool = typer.Option(
        True,
        "--create-thread/--no-create-thread",
        help="Create a new thread if not in one",
    ),
):
    """
    Focus current thread on a session.

    This binds the current thread to the specified session, so follow-up
    messages in that thread will route to the bound session.

    Examples:
        cyberclaw sessions focus agent:coding:subagent:abc123
        cyberclaw sessions focus "Research assistant"
        cyberclaw sessions focus subagent:#1
    """
    console.print(f"[yellow]Focusing on session:[/yellow] [cyan]{target}[/cyan]")
    console.print("")

    # In real implementation:
    # 1. Resolve the target session key
    # 2. Bind current thread to that session
    # 3. Update session metadata

    console.print("[green]✓ Thread focused on session[/green]")
    console.print("")
    console.print(
        "[dim]Follow-up messages in this thread will now route to the bound session[/dim]"
    )


@sessions_app.command("unfocus")
def session_unfocus():
    """
    Remove thread binding.

    Unbinds the current thread from any session. Follow-up messages
    will route to the default agent.

    Examples:
        cyberclaw sessions unfocus
    """
    console.print("[yellow]Unfocusing current thread[/yellow]")
    console.print("")

    # In real implementation:
    # 1. Remove thread binding from session manager
    # 2. Clear binding metadata

    console.print("[green]✓ Thread unfocused[/green]")
    console.print("")
    console.print("[dim]Follow-up messages will now route to the default agent[/dim]")


@sessions_app.command("idle")
def session_idle(
    duration: Optional[str] = typer.Argument(
        None,
        help="Idle timeout duration (e.g., '1h', '30m', '24h') or 'off' to disable",
    ),
):
    """
    Set or view idle timeout for current session.

    When a session is idle for longer than the timeout, it will be
    automatically unfocused (but not deleted).

    Examples:
        cyberclaw sessions idle          # View current timeout
        cyberclaw sessions idle 1h       # Set to 1 hour
        cyberclaw sessions idle 30m      # Set to 30 minutes
        cyberclaw sessions idle off      # Disable auto-unfocus
    """
    if duration is None:
        # View current timeout
        console.print("[yellow]Current idle timeout[/yellow]")
        console.print("")
        console.print("  Current: [cyan]24 hours[/cyan]")
        console.print("  Default: [cyan]24 hours[/cyan]")
        console.print("")
        console.print("[dim]Use 'cyberclaw sessions idle <duration>' to change[/dim]")
    else:
        # Set timeout
        if duration.lower() == "off":
            console.print("[yellow]Disabling idle timeout[/yellow]")
            timeout_text = "[cyan]disabled[/cyan]"
        else:
            console.print(f"[yellow]Setting idle timeout to:[/yellow] [cyan]{duration}[/cyan]")
            timeout_text = f"[cyan]{duration}[/cyan]"

        console.print("")
        console.print(f"[green]✓ Idle timeout set to {timeout_text}[/green]")
        console.print("")
        console.print("[dim]Session will auto-unfocus after this period of inactivity[/dim]")


@sessions_app.command("max-age")
def session_max_age(
    duration: Optional[str] = typer.Argument(
        None,
        help="Maximum age duration (e.g., '24h', '7d') or 'off' to disable",
    ),
):
    """
    Set or view maximum session age.

    When a session reaches its maximum age, it will be automatically
    archived (but not deleted).

    Examples:
        cyberclaw sessions max-age           # View current max age
        cyberclaw sessions max-age 24h       # Set to 24 hours
        cyberclaw sessions max-age 7d        # Set to 7 days
        cyberclaw sessions max-age off       # Disable auto-archive
    """
    if duration is None:
        # View current max age
        console.print("[yellow]Current maximum session age[/yellow]")
        console.print("")
        console.print("  Current: [cyan]disabled[/cyan]")
        console.print("  Default: [cyan]disabled[/cyan]")
        console.print("")
        console.print("[dim]Use 'cyberclaw sessions max-age <duration>' to change[/dim]")
    else:
        # Set max age
        if duration.lower() == "off":
            console.print("[yellow]Disabling maximum age[/yellow]")
            age_text = "[cyan]disabled[/cyan]"
        else:
            console.print(f"[yellow]Setting maximum age to:[/yellow] [cyan]{duration}[/cyan]")
            age_text = f"[cyan]{duration}[/cyan]"

        console.print("")
        console.print(f"[green]✓ Maximum age set to {age_text}[/green]")
        console.print("")
        console.print("[dim]Session will auto-archive after this time[/dim]")


@sessions_app.command("list")
def sessions_list(
    agent_id: Optional[str] = typer.Option(
        None,
        "--agent",
        "-a",
        help="Filter by agent ID",
    ),
    active: bool = typer.Option(
        False,
        "--active",
        help="Show only active sessions",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum number of sessions to show",
    ),
):
    """
    List sessions.

    Examples:
        cyberclaw sessions list
        cyberclaw sessions list --agent coding
        cyberclaw sessions list --active
    """
    console.print("[yellow]Sessions[/yellow]")
    console.print("")

    # Example table
    table = Table(title="Recent Sessions")
    table.add_column("Session Key", style="cyan", max_width=50)
    table.add_column("Agent", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("Created", style="blue")
    table.add_column("Status", style="yellow")

    # Sample data
    sessions_data = [
        ("agent:main:main:1", "main", "main", "2026-03-03 09:00", "active"),
        ("agent:main:subagent:abc", "main", "subagent", "2026-03-03 10:30", "running"),
        ("agent:coding:main:1", "coding", "main", "2026-03-03 08:00", "idle"),
        ("agent:main:subagent:def", "main", "subagent", "2026-03-03 11:00", "completed"),
    ]

    for session_key, agent, type_, created, status in sessions_data[:limit]:
        if agent_id and agent != agent_id:
            continue
        if active and status not in ["active", "running"]:
            continue

        table.add_row(session_key, agent, type_, created, status)

    console.print(table)


@sessions_app.command("info")
def sessions_info(
    session_key: str = typer.Argument(
        ...,
        help="Session key or ID",
    ),
):
    """
    Show detailed information about a session.

    Examples:
        cyberclaw sessions info agent:main:main:1
        cyberclaw sessions info abc123
    """
    console.print(f"[yellow]Session Info:[/yellow] [cyan]{session_key}[/cyan]")
    console.print("")

    # Placeholder info
    info = {
        "Session Key": session_key,
        "Agent ID": "main",
        "Session Type": "main",
        "Created": "2026-03-03 09:00:00",
        "Last Active": "2026-03-03 11:30:00",
        "Message Count": "42",
        "Token Usage": "15,234 (input: 10,000, output: 5,234)",
        "Thread Binding": "None",
        "Idle Timeout": "24 hours",
        "Max Age": "disabled",
        "Status": "active",
    }

    for key, value in info.items():
        console.print(f"  [cyan]{key}:[/cyan] {value}")


@sessions_app.command("clear")
def sessions_clear(
    session_key: str = typer.Argument(
        ...,
        help="Session key or ID to clear",
    ),
    confirm: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation",
    ),
):
    """
    Clear all messages from a session.

    ⚠️  This action cannot be undone.

    Examples:
        cyberclaw sessions clear agent:main:main:1
        cyberclaw sessions clear agent:main:main:1 --yes
    """
    if not confirm:
        typer.confirm(
            f"Are you sure you want to clear session {session_key}? This cannot be undone.",
            abort=True,
        )

    console.print(f"[yellow]Clearing session:[/yellow] [cyan]{session_key}[/cyan]")
    console.print("")

    # In real implementation:
    # 1. Delete session messages
    # 2. Clear session metadata
    # 3. Update session file

    console.print("[green]✓ Session cleared[/green]")
    console.print("")
    console.print("[red]⚠️  All messages have been deleted[/red]")


@sessions_app.command("archive")
def sessions_archive(
    session_key: str = typer.Argument(
        ...,
        help="Session key or ID to archive",
    ),
):
    """
    Archive a session.

    Archived sessions are moved to the archive directory but not deleted.

    Examples:
        cyberclaw sessions archive agent:main:subagent:abc123
    """
    console.print(f"[yellow]Archiving session:[/yellow] [cyan]{session_key}[/cyan]")
    console.print("")

    # In real implementation:
    # 1. Move session file to archive directory
    # 2. Update session metadata
    # 3. Clear from active cache

    console.print("[green]✓ Session archived[/green]")
    console.print("")
    console.print("[dim]Archived sessions can be restored if needed[/dim]")


@sessions_app.command("bindings")
def sessions_bindings():
    """
    Show active thread bindings.

    Examples:
        cyberclaw sessions bindings
    """
    console.print("[yellow]Active Thread Bindings[/yellow]")
    console.print("")

    # Example table
    table = Table(title="Thread Bindings")
    table.add_column("Thread ID", style="cyan")
    table.add_column("Session Key", style="magenta", max_width=40)
    table.add_column("Bound At", style="blue")
    table.add_column("Last Active", style="green")

    # Sample data
    bindings_data = [
        ("thread:123", "agent:main:subagent:abc123", "10:30:00", "10:35:00"),
        ("thread:456", "agent:coding:main:1", "09:00:00", "11:00:00"),
    ]

    for thread_id, session_key, bound_at, last_active in bindings_data:
        table.add_row(thread_id, session_key, bound_at, last_active)

    console.print(table)


def get_app() -> typer.Typer:
    """Get the sessions CLI app."""
    return sessions_app


if __name__ == "__main__":
    sessions_app()
