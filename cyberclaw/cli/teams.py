"""CLI commands for managing agent teams."""

import typer
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

app = typer.Typer(name="teams", help="Manage agent teams")
console = Console()


@app.command("list")
def list_teams():
    """List all configured agent teams."""
    from cyberclaw.config.loader import load_config

    config = load_config()
    teams = config.agents.teams

    if not teams:
        console.print("[yellow]No teams configured[/yellow]")
        console.print("\nAdd teams to ~/.cyberclaw/config.json under agents.teams")
        return

    table = Table(title="Agent Teams")
    table.add_column("Name", style="cyan")
    table.add_column("Members", style="green")
    table.add_column("Leader", style="yellow")
    table.add_column("Strategy", style="magenta")

    for team in teams:
        members_str = ", ".join(team.members)
        leader_str = team.leader or "-"
        strategy_str = team.strategy

        table.add_row(team.name, members_str, leader_str, strategy_str)

    console.print(table)
    console.print(f"\nTotal: {len(teams)} team(s)")


@app.command("info")
def team_info(team_name: str = typer.Argument(..., help="Team name")):
    """Show detailed information about a team."""
    from cyberclaw.config.loader import load_config
    from cyberclaw.agent.team.manager import TeamManager

    config = load_config()
    manager = TeamManager(config.agents)

    summary = manager.get_team_summary(team_name)

    if "error" in summary:
        console.print(f"[red]{summary['error']}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[cyan]Team:[/cyan] {summary['name']}")
    console.print(f"[cyan]Members:[/cyan] {summary['member_count']}")
    console.print(f"[cyan]Leader:[/cyan] {summary['leader'] or 'None'}")
    console.print(f"[cyan]Strategy:[/cyan] {summary['strategy']}")
    console.print(f"[cyan]Valid:[/cyan] {'✅ Yes' if summary['valid'] else '❌ No'}")

    if summary["errors"]:
        console.print("\n[red]Validation Errors:[/red]")
        for error in summary["errors"]:
            console.print(f"  • {error}")

    if summary["member_configs"]:
        console.print("\n[cyan]Member Details:[/cyan]")
        for member in summary["member_configs"]:
            console.print(f"  • {member['id']} (model: {member['model'] or 'default'})")


@app.command("status")
def team_status(team_name: str = typer.Argument(..., help="Team name")):
    """Show team member status (requires running gateway)."""
    console.print("[yellow]Team status requires a running gateway with --multi[/yellow]")
    console.print("This feature will be available in a future release.")


@app.command("validate")
def validate_team(team_name: str = typer.Argument(..., help="Team name to validate")):
    """Validate a team configuration."""
    from cyberclaw.config.loader import load_config
    from cyberclaw.agent.team.manager import TeamManager

    config = load_config()
    manager = TeamManager(config.agents)

    errors = manager.validate_team(team_name)

    if not errors:
        console.print(f"[green]✅ Team '{team_name}' is valid[/green]")
    else:
        console.print(f"[red]❌ Team '{team_name}' has {len(errors)} error(s):[/red]")
        for error in errors:
            console.print(f"  • {error}")
        raise typer.Exit(1)


@app.command("exec")
def exec_team(
    team_name: str = typer.Argument(..., help="Team name to execute task"),
    task: str = typer.Argument(..., help="Task description"),
    timeout: int = typer.Option(600, "--timeout", "-t", help="Timeout in seconds per worker"),
    parallel: bool = typer.Option(True, "--parallel", "-p", help="Run workers in parallel"),
):
    """Execute a task using a team of agents.

    This command DIRECTLY spawns team members to work on the task.

    Unlike the gateway mode (which relies on orchestrator's decision),
    this command GUARANTEES multi-agent execution.

    Example:
        cyberclaw teams exec dev-team "Build a web scraper"
        cyberclaw teams exec research-team "Research AI trends"
    """
    from cyberclaw.config.loader import load_config
    from cyberclaw.bus.queue import MessageBus
    from cyberclaw.gateway.manager import MultiAgentGateway

    console.print(f"\n[bold cyan]🚀 Team Execution[/bold cyan]")
    console.print(f"[dim]Team:[/dim] {team_name}")
    console.print(f"[dim]Task:[/dim] {task}\n")

    # Load config
    config = load_config()

    # Get team
    team = None
    for t in config.agents.teams:
        if t.name == team_name:
            team = t
            break

    if not team:
        console.print(f"[red]❌ Team '{team_name}' not found[/red]")
        console.print("\nAvailable teams:")
        for t in config.agents.teams:
            console.print(f"  - {t.name}")
        raise typer.Exit(1)

    # Show team info
    console.print(f"[green]✓[/green] Members: {', '.join(team.members)}")
    console.print(f"[green]✓[/green] Strategy: {team.strategy}")
    console.print(f"[green]✓[/green] Timeout: {timeout}s per worker\n")

    # Start gateway
    console.print("[cyan]⚙️  Starting Gateway...[/cyan]")
    bus = MessageBus()
    gw = MultiAgentGateway(config, bus)

    async def run_team_execution():
        await gw.start()

        console.print(f"[green]✓[/green] Gateway started with {len(gw.agents)} agents\n")

        # Spawn workers directly
        console.print(f"[cyan]🔨 Spawning {len(team.members)} workers...[/cyan]\n")

        workers = []
        for i, member_id in enumerate(team.members, 1):
            agent = gw.get_agent(member_id)
            if not agent:
                console.print(f"[red]❌ Agent '{member_id}' not found[/red]")
                continue

            # Create member-specific prompt
            member_prompt = create_member_prompt(member_id, task, team)

            console.print(f"  [{i}/{len(team.members)}] Spawning [bold]{member_id}[/bold]...")

            worker_task = asyncio.create_task(
                agent.process_direct(
                    content=member_prompt,
                    session_key=f"{member_id}:team-exec",
                    channel="cli",
                    chat_id=f"team-exec-{member_id}",
                )
            )
            workers.append((member_id, worker_task))

        console.print(f"\n[green]✓[/green] All {len(workers)} workers spawned!\n")
        console.print(
            f"[cyan]⏳ Waiting for workers to complete (timeout: {timeout}s each)...[/cyan]\n"
        )

        # Wait for all workers with progress display
        results = {}
        errors = {}

        import time

        start_time = time.time()

        for i, (member_id, worker) in enumerate(workers, 1):
            try:
                elapsed = time.time() - start_time
                console.print(
                    f"  [{i}/{len(workers)}] Waiting for [bold]{member_id}[/bold]... ({elapsed:.1f}s)"
                )

                result = await asyncio.wait_for(worker, timeout=timeout)
                results[member_id] = result

                elapsed = time.time() - start_time
                console.print(f"  ✅ {member_id} completed in {elapsed:.1f}s")

            except asyncio.TimeoutError:
                errors[member_id] = f"Timeout after {timeout}s"
                console.print(f"  ❌ {member_id} timed out")
            except Exception as e:
                errors[member_id] = str(e)
                console.print(f"  ❌ {member_id} failed: {e}")

        # Aggregate results
        total_time = time.time() - start_time

        console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
        console.print(f"[bold cyan]📊 Team Execution Results[/bold cyan]")
        console.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")

        console.print(f"[dim]Team:[/dim] {team_name}")
        console.print(f"[dim]Task:[/dim] {task[:100]}...")
        console.print(f"[dim]Total Time:[/dim] {total_time:.1f}s")
        console.print(f"[dim]Success:[/dim] {len(results)}/{len(workers)}\n")

        if results:
            console.print(f"[bold green]📝 Results:[/bold green]\n")
            for member_id, result in results.items():
                # Truncate long results for display
                display_result = (
                    result[:1000] + "\n\n...(truncated)" if len(result) > 1000 else result
                )
                console.print(
                    Panel(
                        Markdown(
                            display_result[:500] + "..."
                            if len(display_result) > 500
                            else display_result
                        ),
                        title=f"[bold]{member_id}[/bold]",
                        border_style="green",
                    )
                )
                console.print()  # Empty line

        if errors:
            console.print(f"[bold red]❌ Errors:[/bold red]\n")
            for member_id, error in errors.items():
                console.print(f"  [red]{member_id}:[/red] {error}")

        console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]\n")

        await gw.stop()

    try:
        asyncio.run(run_team_execution())
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        raise typer.Exit(1)


def create_member_prompt(member_id: str, task: str, team) -> str:
    """Create a task prompt for a specific team member."""

    # Role-specific instructions
    role_instructions = {
        "coding": """
You are the CODING expert on the team.

Your responsibilities:
1. Implement the actual code
2. Follow best practices and design patterns
3. Write clean, maintainable, well-documented code
4. Include error handling and validation

Focus on: Implementation, coding, architecture, patterns
""",
        "research": """
You are the RESEARCH expert on the team.

Your responsibilities:
1. Research best practices and existing solutions
2. Analyze requirements and constraints
3. Provide recommendations and guidelines
4. Document findings clearly

Focus on: Research, analysis, recommendations, documentation
""",
        "reviewer": """
You are the CODE REVIEW expert on the team.

Your responsibilities:
1. Review code quality and best practices
2. Check for potential bugs and issues
3. Suggest improvements and optimizations
4. Ensure code follows standards

Focus on: Code review, quality assurance, best practices
""",
        "debugger": """
You are the DEBUGGING expert on the team.

Your responsibilities:
1. Test the implementation
2. Find and fix bugs
3. Write test cases
4. Ensure reliability

Focus on: Testing, debugging, validation, reliability
""",
    }

    # Get role-specific instruction or default
    instruction = role_instructions.get(
        member_id,
        f"""
You are {member_id} on the team.

Your role is to contribute to the team task with your expertise.
""",
    )

    # Team context
    team_context = f"""
You are working as part of team '{team.name}' with strategy '{team.strategy}'.

Team members: {", ".join(team.members)}

{instruction}

=====================================
TASK: {task}
=====================================

Please provide your contribution to this team task.
Be specific, detailed, and practical.

Your output will be combined with other team members' work.
"""

    return team_context


# Alias for backward compatibility
validate = validate_team
