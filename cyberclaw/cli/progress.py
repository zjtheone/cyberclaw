"""Tool execution progress display for CLI."""

import sys
import time

from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text


console = Console(stderr=True)

# ANSI escape codes for dim italic text
_DIM_ITALIC = "\033[2;3m"
_RESET = "\033[0m"


class ToolProgressDisplay:
    """
    Displays tool execution progress in the CLI with spinners and status.

    Usage:
        display = ToolProgressDisplay()
        display.on_tool_start("read_file", {"path": "loop.py"})
        display.on_tool_complete("read_file", "796 lines", 0.02)
    """

    def __init__(self, show_diff: bool = True):
        self._show_diff = show_diff
        self._start_times: dict[str, float] = {}
        self._thinking_shown = False
        self._thinking_has_content = False

    def _end_thinking(self) -> None:
        """Finish the current thinking line if any content was written."""
        if self._thinking_has_content:
            console.print()  # Add final newline
            self._thinking_has_content = False

    def on_thinking(self, content: str) -> None:
        """Display LLM reasoning/thinking content inline (streaming-friendly)."""
        if not self._thinking_shown:
            console.print("  [dim italic]💭 Thinking...[/dim italic]", highlight=False)
            self._thinking_shown = True
        if not content:
            return
            
        if not self._thinking_has_content:
            content = "  " + content
            self._thinking_has_content = True
        else:
            # If the previous chunk ended in a newline, the next chunk needs indentation
            pass  # Handled by replacing newlines with newline + spaces
            
        if "\n" in content:
            content = content.replace("\n", "\n  ")
            
        # Print using rich to safely handle styles without exposing ANSI escapes
        console.print(Text(content, style="dim italic"), end="", highlight=False)
    def on_iteration(self, iteration: int, max_iterations: int) -> None:
        """Display iteration progress. Skip step 1 to reduce noise."""
        self._end_thinking()
        self._thinking_shown = False  # Reset for new iteration
        if iteration > 1:
            console.print(f"\n  [dim]── Step {iteration}/{max_iterations} ──[/dim]", highlight=False)

    def on_status(self, status: str) -> None:
        """Display agent status changes."""
        self._end_thinking()
        labels = {
            "thinking": "🤖 Analyzing...",
            "executing_tools": "🔧 Executing tools...",
            "compacting_context": "📦 Compacting context...",
        }
        label = labels.get(status, status)
        console.print(f"  [dim]{label}[/dim]", highlight=False)

    def on_tool_start(self, name: str, args: dict) -> None:
        """Display tool start with a brief description."""
        self._end_thinking()
        self._start_times[name] = time.time()
        summary = self._summarize_args(name, args)
        console.print(f"  [dim]⚙ {name}({summary})[/dim]", highlight=False)

    def on_tool_complete(self, name: str, result_preview: str, duration: float) -> None:
        """Display tool completion with result preview and timing."""
        # Truncate preview
        preview = result_preview.replace("\n", " ")[:80]
        dur = f"{duration:.2f}s" if duration >= 0.01 else "<0.01s"
        console.print(f"  [green]✓[/green] [dim]{name}[/dim] → {preview} [dim]({dur})[/dim]", highlight=False)

    def on_tool_error(self, name: str, error: str) -> None:
        """Display tool error."""
        err_preview = error.replace("\n", " ")[:100]
        console.print(f"  [red]✗[/red] [dim]{name}[/dim] → {err_preview}", highlight=False)

    def on_plan_progress(self, steps: list) -> None:
        """Display a live checklist of plan steps."""
        self._end_thinking()
        console.print()
        console.print("  [bold]📋 Plan Progress:[/bold]", highlight=False)
        for s in steps:
            st = s.status if hasattr(s, "status") else s.get("status", "pending")
            title = s.title if hasattr(s, "title") else s.get("title", "?")
            sid = s.id if hasattr(s, "id") else s.get("id", "?")
            if st == "completed":
                console.print(f"  [green]✓[/green] [dim]{sid}. {title}[/dim]", highlight=False)
            elif st == "in_progress":
                console.print(f"  [yellow]▸[/yellow] [bold]{sid}. {title}[/bold]", highlight=False)
            else:
                console.print(f"  [dim]○ {sid}. {title}[/dim]", highlight=False)
        console.print()

    def show_diff(self, diff_text: str) -> None:
        """Display a colored unified diff."""
        if not self._show_diff or not diff_text:
            return
        try:
            syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
            console.print(syntax)
        except Exception:
            # Fallback to plain text
            console.print(diff_text)

    def show_cost(self, usage: dict, cost: float | None = None) -> None:
        """Display token usage and estimated cost."""
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)
        parts = [f"tokens: {prompt:,} in + {completion:,} out = {total:,} total"]
        if cost is not None:
            parts.append(f"~${cost:.4f}")
        console.print(f"\n[dim][{' | '.join(parts)}][/dim]", highlight=False)

    def _summarize_args(self, name: str, args: dict) -> str:
        """Create a brief summary of tool arguments."""
        if name in ("read_file", "write_file", "edit_file"):
            return args.get("path", "?")
        if name == "exec":
            cmd = args.get("command", "?")
            return cmd[:50] + "..." if len(cmd) > 50 else cmd
        if name == "grep":
            return f"{args.get('pattern', '?')} in {args.get('path', '.')}"
        if name in ("git_commit",):
            return args.get("message", "?")[:40]
        if name == "git_checkout":
            return args.get("target", "?")
        # Generic: show first arg value
        for v in args.values():
            s = str(v)
            return s[:40] + "..." if len(s) > 40 else s
        return ""
