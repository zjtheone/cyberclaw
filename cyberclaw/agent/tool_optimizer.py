"""
Self-Improving Agent: Tool Selection Optimization (P1)

Analyzes historical tool performance to recommend optimal tools for tasks.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from cyberclaw.agent.metrics import MetricsTracker


@dataclass
class ToolStatistics:
    """Statistics for a single tool."""
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    success_rate: float = 0.0
    last_used: str | None = None
    first_used: str | None = None
    
    # Performance metrics
    p50_duration: float = 0.0
    p95_duration: float = 0.0
    max_duration: float = 0.0
    
    # Failure analysis
    failure_reasons: dict[str, int] = field(default_factory=dict)
    
    # Context tracking
    common_tasks: list[str] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_duration": self.total_duration,
            "avg_duration": self.avg_duration,
            "success_rate": self.success_rate,
            "last_used": self.last_used,
            "first_used": self.first_used,
            "p50_duration": self.p50_duration,
            "p95_duration": self.p95_duration,
            "max_duration": self.max_duration,
            "failure_reasons": self.failure_reasons,
            "common_tasks": self.common_tasks,
            "categories": self.categories,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolStatistics":
        return cls(**data)


@dataclass
class ToolRecommendation:
    """Tool recommendation for a task."""
    tool_name: str
    score: float
    reasons: list[str] = field(default_factory=list)
    estimated_duration: float = 0.0
    success_probability: float = 0.0
    alternatives: list[str] = field(default_factory=list)


class ToolOptimizer:
    """
    Optimizes tool selection based on historical performance.
    
    Features:
    - Analyze tool performance metrics
    - Calculate success rates and execution times
    - Recommend optimal tools for tasks
    - Track tool usage patterns
    - Identify underperforming tools
    """
    
    # Task category to tool mapping (keywords -> preferred tools)
    TASK_TOOL_MAPPING = {
        "file": ["read_file", "write_file", "edit_file", "list_dir"],
        "search": ["web_search", "web_fetch", "grep", "find_files"],
        "code": ["read_file", "edit_file", "exec", "code"],
        "git": ["git_status", "git_diff", "git_commit", "git_log"],
        "shell": ["exec", "shell"],
        "memory": ["memory_search"],
        "test": ["exec", "run_diagnostics"],
        "web": ["web_search", "web_fetch"],
        "message": ["message"],
        "spawn": ["spawn"],
    }
    
    def __init__(
        self,
        workspace: Path,
        metrics_tracker: MetricsTracker,
        min_samples: int = 3,
        prefer_fast_tools: bool = True,
        decay_factor: float = 0.95,  # Recent performance weighted higher
    ):
        self.workspace = workspace
        self.metrics_tracker = metrics_tracker
        self.min_samples = min_samples
        self.prefer_fast_tools = prefer_fast_tools
        self.decay_factor = decay_factor
        
        self.stats_dir = workspace / ".cyberclaw"
        self.stats_file = self.stats_dir / "tool_stats.json"
        
        self._stats: dict[str, ToolStatistics] = {}
        self._duration_history: dict[str, list[float]] = {}

        # 自适应权重（通过反馈闭环调整）
        self._adaptive_weights = {
            "success_rate": 0.40,
            "speed": 0.30,
            "experience": 0.20,
            "recency": 0.10,
        }
        self._recommendation_outcomes: list[dict] = []

        self._load()
        self._sync_with_metrics()
    
    def _load(self) -> None:
        """Load tool statistics from disk."""
        if not self.stats_file.exists():
            return
        
        try:
            data = json.loads(self.stats_file.read_text(encoding="utf-8"))
            for name, stats_data in data.items():
                self._stats[name] = ToolStatistics.from_dict(stats_data)
            logger.info(f"Loaded statistics for {len(self._stats)} tools")
        except Exception as e:
            logger.error(f"Failed to load tool statistics: {e}")
    
    def _save(self) -> None:
        """Save tool statistics to disk."""
        try:
            self.stats_dir.mkdir(parents=True, exist_ok=True)
            data = {name: stats.to_dict() for name, stats in self._stats.items()}
            self.stats_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save tool statistics: {e}")
    
    def _sync_with_metrics(self) -> None:
        """Sync statistics with metrics tracker."""
        for record in self.metrics_tracker.tool_calls:
            self._update_stats(
                tool_name=record.tool_name,
                success=record.success,
                duration=record.duration_seconds,
                error=record.error_message,
                timestamp=record.timestamp,
            )
    
    def _update_stats(
        self,
        tool_name: str,
        success: bool,
        duration: float,
        error: str | None = None,
        timestamp: str | None = None,
        task_description: str | None = None,
        category: str | None = None,
    ) -> None:
        """Update statistics for a tool."""
        if tool_name not in self._stats:
            self._stats[tool_name] = ToolStatistics(name=tool_name)
        
        stats = self._stats[tool_name]
        stats.total_calls += 1
        
        if success:
            stats.successful_calls += 1
        else:
            stats.failed_calls += 1
            if error:
                # Categorize error
                error_key = error[:50].lower().strip()
                stats.failure_reasons[error_key] = stats.failure_reasons.get(error_key, 0) + 1
        
        stats.total_duration += duration
        stats.avg_duration = stats.total_duration / stats.total_calls
        
        # Track duration history for percentiles
        if tool_name not in self._duration_history:
            self._duration_history[tool_name] = []
        self._duration_history[tool_name].append(duration)
        
        # Update percentiles
        if len(self._duration_history[tool_name]) >= self.min_samples:
            durations = sorted(self._duration_history[tool_name])
            stats.p50_duration = durations[len(durations) // 2]
            stats.p95_duration = durations[int(len(durations) * 0.95)]
            stats.max_duration = max(durations)
        
        stats.success_rate = stats.successful_calls / stats.total_calls if stats.total_calls > 0 else 0
        
        ts = timestamp or datetime.now().isoformat()
        if not stats.first_used:
            stats.first_used = ts
        stats.last_used = ts
        
        # Track task categories
        if category:
            stats.categories[category] = stats.categories.get(category, 0) + 1
        
        # Track common tasks (last 10)
        if task_description:
            if len(stats.common_tasks) >= 10:
                stats.common_tasks.pop(0)
            stats.common_tasks.append(task_description[:100])
        
        self._save()
    
    def record_tool_execution(
        self,
        tool_name: str,
        success: bool,
        duration: float,
        error: str | None = None,
        task_description: str | None = None,
        category: str | None = None,
    ) -> None:
        """
        Record a tool execution for optimization.
        
        Args:
            tool_name: Name of the tool used.
            success: Whether execution succeeded.
            duration: Execution duration in seconds.
            error: Error message if failed.
            task_description: Description of the task.
            category: Task category.
        """
        self._update_stats(
            tool_name=tool_name,
            success=success,
            duration=duration,
            error=error,
            task_description=task_description,
            category=category,
        )
    
    def get_statistics(self, tool_name: str) -> ToolStatistics | None:
        """Get statistics for a specific tool."""
        return self._stats.get(tool_name)
    
    def get_all_statistics(self) -> dict[str, ToolStatistics]:
        """Get statistics for all tools."""
        return self._stats.copy()
    
    def get_success_rate(self, tool_name: str) -> float:
        """Get success rate for a tool."""
        stats = self._stats.get(tool_name)
        return stats.success_rate if stats else 0.0
    
    def get_avg_execution_time(self, tool_name: str) -> float:
        """Get average execution time for a tool."""
        stats = self._stats.get(tool_name)
        return stats.avg_duration if stats else 0.0
    
    def get_tool_rankings(
        self,
        metric: str = "success_rate",
        min_calls: int = 1,
    ) -> list[tuple[str, float]]:
        """
        Get tool rankings by specified metric.
        
        Args:
            metric: Metric to rank by (success_rate, avg_duration, total_calls).
            min_calls: Minimum number of calls to include.
        
        Returns:
            List of (tool_name, score) tuples sorted by score.
        """
        rankings = []
        
        for name, stats in self._stats.items():
            if stats.total_calls < min_calls:
                continue
            
            if metric == "success_rate":
                score = stats.success_rate
            elif metric == "avg_duration":
                score = stats.avg_duration
            elif metric == "total_calls":
                score = float(stats.total_calls)
            else:
                score = stats.success_rate
            
            rankings.append((name, score))
        
        # Sort: higher is better for success_rate, lower is better for duration
        reverse = metric != "avg_duration"
        rankings.sort(key=lambda x: x[1], reverse=reverse)
        
        return rankings
    
    def recommend_tool(
        self,
        task_description: str,
        max_recommendations: int = 3,
    ) -> list[ToolRecommendation]:
        """
        Recommend optimal tools for a task.
        
        Args:
            task_description: Description of the task.
            max_recommendations: Maximum number of recommendations.
        
        Returns:
            List of ToolRecommendation objects.
        """
        task_lower = task_description.lower()
        
        # Identify candidate tools based on task keywords
        candidate_tools = set()
        for keyword, tools in self.TASK_TOOL_MAPPING.items():
            if keyword in task_lower:
                candidate_tools.update(tools)
        
        # If no keyword matches, consider all tools with sufficient history
        if not candidate_tools:
            candidate_tools = {
                name for name, stats in self._stats.items()
                if stats.total_calls >= self.min_samples
            }
        
        # Score each candidate
        recommendations = []
        for tool_name in candidate_tools:
            stats = self._stats.get(tool_name)
            if not stats or stats.total_calls < self.min_samples:
                continue
            
            # Calculate composite score
            score = self._calculate_tool_score(stats, task_description)
            
            reasons = []
            if stats.success_rate >= 0.9:
                reasons.append(f"High success rate ({stats.success_rate*100:.0f}%)")
            if stats.avg_duration < 5.0:
                reasons.append(f"Fast execution ({stats.avg_duration:.1f}s)")
            if stats.total_calls >= 10:
                reasons.append(f"Well-tested ({stats.total_calls} calls)")
            
            rec = ToolRecommendation(
                tool_name=tool_name,
                score=score,
                reasons=reasons,
                estimated_duration=stats.avg_duration,
                success_probability=stats.success_rate,
            )
            recommendations.append(rec)
        
        # Sort by score and return top recommendations
        recommendations.sort(key=lambda x: x.score, reverse=True)
        
        # Add alternatives to top recommendation
        if recommendations:
            for i, rec in enumerate(recommendations[:max_recommendations]):
                if i < len(recommendations) - 1:
                    rec.alternatives = [r.tool_name for r in recommendations[i+1:max_recommendations+1]]
        
        return recommendations[:max_recommendations]
    
    def _calculate_tool_score(
        self,
        stats: ToolStatistics,
        task_description: str,
    ) -> float:
        """Calculate composite score for a tool (weights are adaptive)."""
        w = self._adaptive_weights
        score = 0.0

        # Success rate
        score += w["success_rate"] * stats.success_rate

        # Speed score - normalized
        if self.prefer_fast_tools and stats.avg_duration > 0:
            speed_score = 1.0 / (1.0 + stats.avg_duration / 10.0)
            score += w["speed"] * speed_score

        # Experience - more calls = more reliable
        experience_score = min(1.0, stats.total_calls / 20.0)
        score += w["experience"] * experience_score

        # Recency - recently used tools preferred
        if stats.last_used:
            try:
                last_used = datetime.fromisoformat(stats.last_used)
                days_since = (datetime.now() - last_used).days
                recency_score = max(0.0, 1.0 - (days_since / 30.0))
                score += w["recency"] * recency_score
            except Exception:
                pass

        return score

    def record_recommendation_outcome(
        self,
        recommended_tool: str,
        actual_tool_used: str,
        task_description: str,
        success: bool,
    ) -> None:
        """记录推荐结果，用于评估推荐效果并自适应调整权重。"""
        was_followed = (recommended_tool == actual_tool_used)
        self._recommendation_outcomes.append({
            "recommended": recommended_tool,
            "actual": actual_tool_used,
            "followed": was_followed,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })
        self._adapt_weights()

    def _adapt_weights(self) -> None:
        """根据推荐结果自适应调整权重。"""
        recent = self._recommendation_outcomes[-50:]
        if len(recent) < 10:
            return

        followed = [r for r in recent if r["followed"]]
        not_followed = [r for r in recent if not r["followed"]]

        if not followed or not not_followed:
            return

        followed_success = sum(1 for r in followed if r["success"]) / len(followed)
        not_followed_success = sum(1 for r in not_followed if r["success"]) / len(not_followed)

        # 如果被采纳的推荐效果不如未采纳的，降低成功率权重，提高速度权重
        if followed_success < not_followed_success:
            self._adaptive_weights["success_rate"] = max(0.20, self._adaptive_weights["success_rate"] - 0.02)
            self._adaptive_weights["speed"] = min(0.50, self._adaptive_weights["speed"] + 0.02)
        else:
            self._adaptive_weights["success_rate"] = min(0.60, self._adaptive_weights["success_rate"] + 0.01)

        logger.debug(f"Adaptive weights adjusted: {self._adaptive_weights}")

    def get_performance_report(self) -> str:
        """Generate a comprehensive performance report."""
        lines = ["## Tool Performance Report", ""]
        
        if not self._stats:
            lines.append("No tool usage data available yet.")
            return "\n".join(lines)
        
        # Summary statistics
        total_calls = sum(s.total_calls for s in self._stats.values())
        total_success = sum(s.successful_calls for s in self._stats.values())
        overall_rate = total_success / total_calls if total_calls > 0 else 0
        
        lines.append(f"- **Total Tool Calls**: {total_calls}")
        lines.append(f"- **Overall Success Rate**: {overall_rate*100:.1f}%")
        lines.append(f"- **Tools Used**: {len(self._stats)}")
        lines.append("")
        
        # Top performers
        lines.append("### Top Performers (by success rate)")
        rankings = self.get_tool_rankings("success_rate", min_calls=3)
        for tool_name, score in rankings[:5]:
            stats = self._stats[tool_name]
            lines.append(f"- **{tool_name}**: {score*100:.0f}% success ({stats.total_calls} calls, {stats.avg_duration:.1f}s avg)")
        lines.append("")
        
        # Fastest tools
        lines.append("### Fastest Tools (by avg duration)")
        rankings = self.get_tool_rankings("avg_duration", min_calls=3)
        for tool_name, duration in rankings[:5]:
            stats = self._stats[tool_name]
            lines.append(f"- **{tool_name}**: {duration:.2f}s ({stats.success_rate*100:.0f}% success)")
        lines.append("")
        
        # Tools needing improvement
        lines.append("### Tools Needing Improvement")
        for name, stats in self._stats.items():
            if stats.total_calls >= 3 and stats.success_rate < 0.7:
                lines.append(f"- ⚠️ **{name}**: {stats.success_rate*100:.0f}% success")
                if stats.failure_reasons:
                    top_reason = max(stats.failure_reasons.items(), key=lambda x: x[1])
                    lines.append(f"  - Common issue: {top_reason[0][:80]} ({top_reason[1]}x)")
        
        return "\n".join(lines)
    
    def identify_underperforming_tools(
        self,
        min_calls: int = 5,
        max_failure_rate: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Identify tools with poor performance."""
        underperforming = []
        
        for name, stats in self._stats.items():
            if stats.total_calls < min_calls:
                continue
            
            failure_rate = 1.0 - stats.success_rate
            if failure_rate > max_failure_rate:
                underperforming.append({
                    "tool_name": name,
                    "failure_rate": failure_rate,
                    "total_calls": stats.total_calls,
                    "common_failures": list(stats.failure_reasons.items())[:3],
                })
        
        return underperforming
