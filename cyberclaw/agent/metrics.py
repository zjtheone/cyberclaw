
import json
import time
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger

# Pricing per 1M tokens (input, output) — approximate
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (0.25, 1.25),
    "gpt-4o": (2.5, 10.0),
    "gpt-4": (30.0, 60.0),
    "gpt-3.5": (0.5, 1.5),
    "deepseek": (0.27, 1.10),
    "gemini-pro": (1.25, 5.0),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-2.5-pro": (1.25, 5.0),
    "gemini-flash": (0.075, 0.30),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.5-flash": (0.075, 0.30),
    "qwen": (0.5, 2.0),
}

@dataclass
class ToolCallRecord:
    timestamp: str
    tool_name: str
    success: bool
    duration_seconds: float
    error_message: str | None = None

@dataclass
class TokenUsageRecord:
    timestamp: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class MetricsTracker:
    """
    Tracks agent performance metrics:
    - Tool usage (success/fail, duration)
    - Token usage
    - Failure patterns (Self-Improving Agent P0)
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        # Store metrics in workspace/.cyberclaw/metrics.json for now to keep it project-specific
        self.metrics_dir = workspace / ".cyberclaw"
        self.metrics_file = self.metrics_dir / "metrics.json"
        self.failure_patterns_file = self.metrics_dir / "failure_patterns.json"
        self._ensure_storage()
        self._load()

    def _ensure_storage(self):
        if not self.metrics_dir.exists():
            self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        self.tool_calls: List[ToolCallRecord] = []
        self.token_usage: List[TokenUsageRecord] = []
        self.failure_patterns: Dict[str, int] = {}  # pattern -> count
        
        if self.metrics_file.exists():
            try:
                data = json.loads(self.metrics_file.read_text(encoding="utf-8"))
                for tc in data.get("tool_calls", []):
                    self.tool_calls.append(ToolCallRecord(**tc))
                for tu in data.get("token_usage", []):
                    self.token_usage.append(TokenUsageRecord(**tu))
            except Exception as e:
                logger.error(f"Failed to load metrics: {e}")
        
        # Load failure patterns (Self-Improving Agent P0)
        if self.failure_patterns_file.exists():
            try:
                self.failure_patterns = json.loads(self.failure_patterns_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to load failure patterns: {e}")

    def _save(self):
        try:
            data = {
                "tool_calls": [asdict(tc) for tc in self.tool_calls],
                "token_usage": [asdict(tu) for tu in self.token_usage],
                "last_updated": datetime.now().isoformat()
            }
            self.metrics_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            
            # Save failure patterns separately (Self-Improving Agent P0)
            self.failure_patterns_file.write_text(
                json.dumps(self.failure_patterns, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def record_tool_call(self, tool_name: str, success: bool, duration: float, error: str | None = None):
        record = ToolCallRecord(
            timestamp=datetime.now().isoformat(),
            tool_name=tool_name,
            success=success,
            duration_seconds=duration,
            error_message=str(error) if error else None
        )
        self.tool_calls.append(record)
        
        # Self-Improving: Track failure patterns (P0)
        if not success and error:
            self._track_failure_pattern(tool_name, error)
        
        # Auto-save every record for now (low volume)
        self._save()
    
    def _track_failure_pattern(self, tool_name: str, error: str) -> None:
        """
        Track failure patterns for self-improvement (P0).
        
        Extracts key error patterns and tracks their frequency.
        """
        # Normalize error message (first 100 chars, lowercase)
        error_key = error[:100].lower().strip()
        
        # Create pattern key with tool name
        pattern_key = f"{tool_name}: {error_key}"
        
        # Increment count
        self.failure_patterns[pattern_key] = self.failure_patterns.get(pattern_key, 0) + 1
        
        logger.debug(f"Tracked failure pattern: {pattern_key} (count: {self.failure_patterns[pattern_key]})")
    
    def get_failure_patterns(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Get top failure patterns sorted by frequency.
        
        Returns:
            List of (pattern, count) tuples.
        """
        sorted_patterns = sorted(
            self.failure_patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_patterns[:limit]
    
    def clear_failure_patterns(self) -> None:
        """Clear all tracked failure patterns."""
        self.failure_patterns = {}
        self._save()

    def record_tokens(self, prompt: int, completion: int):
        record = TokenUsageRecord(
            timestamp=datetime.now().isoformat(),
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion
        )
        self.token_usage.append(record)
        self._save()

    def estimate_cost(self, model: str = "") -> float:
        """Estimate total session cost based on model pricing."""
        pricing = self._match_pricing(model)
        if not pricing:
            return 0.0
        input_rate, output_rate = pricing
        total_input = sum(t.prompt_tokens for t in self.token_usage)
        total_output = sum(t.completion_tokens for t in self.token_usage)
        return (total_input * input_rate + total_output * output_rate) / 1_000_000

    def get_session_usage(self) -> dict[str, int]:
        """Get aggregated token usage for the current session."""
        return {
            "prompt_tokens": sum(t.prompt_tokens for t in self.token_usage),
            "completion_tokens": sum(t.completion_tokens for t in self.token_usage),
            "total_tokens": sum(t.total_tokens for t in self.token_usage),
        }

    def _match_pricing(self, model: str) -> tuple[float, float] | None:
        """Match a model name to pricing."""
        model_lower = model.lower()
        for key, pricing in MODEL_PRICING.items():
            if key in model_lower:
                return pricing
        return None

    def get_summary(self) -> str:
        """Generate a human-readable summary of metrics."""
        total_calls = len(self.tool_calls)
        if total_calls == 0:
            return "No tool calls recorded yet."

        # Tool Stats
        tool_stats: Dict[str, Dict] = {}
        for tc in self.tool_calls:
            if tc.tool_name not in tool_stats:
                tool_stats[tc.tool_name] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "total_duration": 0.0,
                }
            
            tool_stats[tc.tool_name]["total"] += 1
            if tc.success:
                tool_stats[tc.tool_name]["success"] += 1
            else:
                tool_stats[tc.tool_name]["failed"] += 1
            tool_stats[tc.tool_name]["total_duration"] += tc.duration_seconds
        
        lines = [
            "## Session Metrics",
            "",
            f"**Total Tool Calls**: {total_calls}",
            "",
            "### Tool Usage",
        ]
        
        for name, stats in sorted(tool_stats.items(), key=lambda x: x[1]["total"], reverse=True):
            success_rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            avg_duration = stats["total_duration"] / stats["total"] if stats["total"] > 0 else 0
            lines.append(f"- **{name}**: {stats['total']} calls, {success_rate:.0f}% success, {avg_duration:.2f}s avg")
        
        # Token usage
        token_summary = self.get_session_usage()
        if token_summary["total_tokens"] > 0:
            lines.extend([
                "",
                "### Token Usage",
                f"- **Prompt**: {token_summary['prompt_tokens']:,}",
                f"- **Completion**: {token_summary['completion_tokens']:,}",
                f"- **Total**: {token_summary['total_tokens']:,}",
            ])
            estimated_cost = self.estimate_cost()
            if estimated_cost > 0:
                lines.append(f"- **Estimated Cost**: ${estimated_cost:.4f}")
        
        # Failure patterns
        failure_patterns = self.get_failure_patterns(5)
        if failure_patterns:
            lines.extend([
                "",
                "### Top Failure Patterns",
            ])
            for pattern, count in failure_patterns:
                lines.append(f"- ({count}x) {pattern[:80]}")
        
        return "\n".join(lines)
    
    def get_tool_statistics(self, tool_name: str) -> dict[str, Any]:
        """
        Get detailed statistics for a specific tool (P1 - Tool Optimization).
        
        Args:
            tool_name: Name of the tool.
        
        Returns:
            Dictionary with tool statistics.
        """
        tool_calls = [tc for tc in self.tool_calls if tc.tool_name == tool_name]
        
        if not tool_calls:
            return {}
        
        total = len(tool_calls)
        successful = sum(1 for tc in tool_calls if tc.success)
        failed = total - successful
        total_duration = sum(tc.duration_seconds for tc in tool_calls)
        
        # Calculate duration percentiles
        durations = sorted(tc.duration_seconds for tc in tool_calls)
        p50 = durations[len(durations) // 2] if durations else 0
        p95 = durations[int(len(durations) * 0.95)] if durations else 0
        
        # Failure reasons
        failure_reasons: dict[str, int] = {}
        for tc in tool_calls:
            if not tc.success and tc.error_message:
                key = tc.error_message[:50].lower().strip()
                failure_reasons[key] = failure_reasons.get(key, 0) + 1
        
        return {
            "tool_name": tool_name,
            "total_calls": total,
            "successful_calls": successful,
            "failed_calls": failed,
            "success_rate": successful / total if total > 0 else 0,
            "total_duration": total_duration,
            "avg_duration": total_duration / total if total > 0 else 0,
            "p50_duration": p50,
            "p95_duration": p95,
            "max_duration": max(durations) if durations else 0,
            "failure_reasons": failure_reasons,
        }
    
    def get_tool_success_rates(self) -> dict[str, float]:
        """
        Get success rates for all tools (P1 - Tool Optimization).
        
        Returns:
            Dictionary mapping tool names to success rates.
        """
        tool_stats: dict[str, dict] = {}
        
        for tc in self.tool_calls:
            if tc.tool_name not in tool_stats:
                tool_stats[tc.tool_name] = {"total": 0, "success": 0}
            tool_stats[tc.tool_name]["total"] += 1
            if tc.success:
                tool_stats[tc.tool_name]["success"] += 1
        
        return {
            name: stats["success"] / stats["total"] if stats["total"] > 0 else 0
            for name, stats in tool_stats.items()
        }
    
    def get_tool_performance_ranking(
        self,
        min_calls: int = 1,
        metric: str = "success_rate",
    ) -> list[tuple[str, float]]:
        """
        Get tool performance ranking (P1 - Tool Optimization).
        
        Args:
            min_calls: Minimum number of calls to include.
            metric: Metric to rank by (success_rate, avg_duration, total_calls).
        
        Returns:
            List of (tool_name, score) tuples sorted by score.
        """
        tool_stats: dict[str, dict] = {}
        
        for tc in self.tool_calls:
            if tc.tool_name not in tool_stats:
                tool_stats[tc.tool_name] = {
                    "total": 0,
                    "success": 0,
                    "total_duration": 0.0,
                }
            tool_stats[tc.tool_name]["total"] += 1
            if tc.success:
                tool_stats[tc.tool_name]["success"] += 1
            tool_stats[tc.tool_name]["total_duration"] += tc.duration_seconds
        
        rankings = []
        for name, stats in tool_stats.items():
            if stats["total"] < min_calls:
                continue
            
            if metric == "success_rate":
                score = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            elif metric == "avg_duration":
                score = stats["total_duration"] / stats["total"] if stats["total"] > 0 else 0
            else:  # total_calls
                score = float(stats["total"])
            
            rankings.append((name, score))
        
        # Sort: higher is better for success_rate/total_calls, lower for duration
        reverse = metric != "avg_duration"
        rankings.sort(key=lambda x: x[1], reverse=reverse)
        
        return rankings
