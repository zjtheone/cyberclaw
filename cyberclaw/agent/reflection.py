"""
Self-Improving Agent: Task Reflection Module (P0)

Automatically generates reflection reports after task completion to enable
continuous learning and improvement.
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from cyberclaw.providers.base import LLMProvider


@dataclass
class ReflectionReport:
    """Reflection report for a completed task."""
    task_id: str
    task_description: str
    timestamp: str
    status: str  # success | partial_success | failure
    duration_seconds: float
    tool_calls_count: int
    tokens_consumed: int
    
    # Reflection analysis
    what_went_well: list[str] = field(default_factory=list)
    what_went_poorly: list[str] = field(default_factory=list)
    root_causes: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    suggested_improvements: list[str] = field(default_factory=list)
    
    # Metadata
    confidence_score: float = 0.0  # 0-1, agent's confidence in the solution
    complexity_score: float = 0.0  # 0-1, estimated task complexity
    patterns_detected: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReflectionEngine:
    """
    Generates reflection reports after task completion.
    
    Analyzes:
    - Task outcome (success/failure)
    - Tool usage patterns
    - Error patterns
    - Time efficiency
    - Token efficiency
    
    Outputs:
    - Structured reflection report
    - Actionable improvement suggestions
    - Pattern detection for recurring issues
    """
    
    REFLECTION_PROMPT = """You are a Self-Reflection Agent. Analyze the completed task and generate a structured reflection report.

## Task Information
- Description: {task_description}
- Status: {status}
- Duration: {duration:.2f} seconds
- Tool Calls: {tool_calls}
- Tokens Used: {tokens}

## Tool Execution History
{tool_history}

## Errors Encountered (if any)
{errors}

## Analysis Instructions

Analyze this task execution and provide:

1. **What Went Well** (2-4 items)
   - Successful strategies
   - Efficient tool usage
   - Good decisions

2. **What Went Poorly** (2-4 items)
   - Mistakes or inefficiencies
   - Unnecessary steps
   - Poor tool choices

3. **Root Causes** (for failures/issues)
   - Underlying reasons for problems
   - Knowledge gaps
   - Tool limitations

4. **Lessons Learned** (2-4 items)
   - Key takeaways
   - Patterns to remember
   - Insights for future tasks

5. **Suggested Improvements** (2-4 items)
   - Concrete actions for next time
   - Alternative approaches
   - Tool optimizations

6. **Confidence Score** (0.0-1.0)
   - How confident are you in the solution?

7. **Patterns Detected**
   - Any recurring patterns from similar tasks?

Respond with a JSON object in this exact format:
{{
    "what_went_well": ["item1", "item2"],
    "what_went_poorly": ["item1", "item2"],
    "root_causes": ["cause1", "cause2"],
    "lessons_learned": ["lesson1", "lesson2"],
    "suggested_improvements": ["improvement1", "improvement2"],
    "confidence_score": 0.85,
    "patterns_detected": ["pattern1"]
}}
"""
    
    def __init__(self, workspace: Path, provider: LLMProvider, model: str):
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.reports_dir = ensure_dir(workspace / ".cyberclaw" / "reflections")
        self.reports_file = self.reports_dir / "reflection_reports.jsonl"
        self._reports_cache: list[ReflectionReport] = []
        self._load_reports()
    
    def _load_reports(self) -> None:
        """Load existing reflection reports."""
        if not self.reports_file.exists():
            return
        
        try:
            for line in self.reports_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    data = json.loads(line)
                    self._reports_cache.append(ReflectionReport(**data))
            logger.info(f"Loaded {len(self._reports_cache)} reflection reports")
        except Exception as e:
            logger.error(f"Failed to load reflection reports: {e}")
    
    def _save_report(self, report: ReflectionReport) -> None:
        """Append a reflection report to storage."""
        try:
            with open(self.reports_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(report.to_dict()) + "\n")
            self._reports_cache.append(report)
        except Exception as e:
            logger.error(f"Failed to save reflection report: {e}")
    
    async def generate_reflection(
        self,
        task_id: str,
        task_description: str,
        status: str,
        duration: float,
        tool_calls: list[dict[str, Any]],
        tokens_used: int,
        errors: list[str],
    ) -> ReflectionReport:
        """
        Generate a reflection report for a completed task.
        
        Args:
            task_id: Unique task identifier
            task_description: What the task was trying to accomplish
            status: Task outcome (success/partial_success/failure)
            duration: Task duration in seconds
            tool_calls: List of tool call records
            tokens_used: Total tokens consumed
            errors: List of error messages encountered
            
        Returns:
            ReflectionReport with analysis and suggestions
        """
        logger.info(f"Generating reflection report for task {task_id}")
        
        # Build tool history summary
        tool_history = self._format_tool_history(tool_calls)
        errors_text = "\n".join(errors) if errors else "None"
        
        # Prepare reflection prompt
        prompt = self.REFLECTION_PROMPT.format(
            task_description=task_description,
            status=status,
            duration=duration,
            tool_calls=len(tool_calls),
            tokens=tokens_used,
            tool_history=tool_history,
            errors=errors_text,
        )
        
        try:
            # Call LLM for reflection analysis with timeout
            logger.debug(f"Calling LLM for reflection analysis (model={self.model})")
            
            import asyncio
            response = await asyncio.wait_for(
                self.provider.chat(
                    messages=[
                        {"role": "system", "content": "You are a Self-Reflection Agent. Analyze task execution and provide structured JSON output."},
                        {"role": "user", "content": prompt},
                    ],
                    model=self.model,
                    temperature=0.3,  # Lower temperature for consistent analysis
                    max_tokens=1024,  # Limit response size
                ),
                timeout=30.0  # 30 second timeout for reflection
            )
            
            logger.debug(f"LLM reflection response received: {len(response.content)} chars")
            
            # Parse reflection data
            reflection_data = self._parse_reflection_response(response.content)
            
            # Create reflection report
            report = ReflectionReport(
                task_id=task_id,
                task_description=task_description,
                timestamp=datetime.now().isoformat(),
                status=status,
                duration_seconds=duration,
                tool_calls_count=len(tool_calls),
                tokens_consumed=tokens_used,
                what_went_well=reflection_data.get("what_went_well", []),
                what_went_poorly=reflection_data.get("what_went_poorly", []),
                root_causes=reflection_data.get("root_causes", []),
                lessons_learned=reflection_data.get("lessons_learned", []),
                suggested_improvements=reflection_data.get("suggested_improvements", []),
                confidence_score=reflection_data.get("confidence_score", 0.5),
                complexity_score=self._estimate_complexity(tool_calls, duration),
                patterns_detected=reflection_data.get("patterns_detected", []),
            )
            
            # Save report
            self._save_report(report)
            
            logger.info(f"Reflection report generated: status={status}, confidence={report.confidence_score:.2f}")
            return report
            
        except asyncio.TimeoutError:
            logger.warning(f"Reflection generation timed out after 30s (task={task_id})")
            # Return minimal report on timeout
            return ReflectionReport(
                task_id=task_id,
                task_description=task_description,
                timestamp=datetime.now().isoformat(),
                status=status,
                duration_seconds=duration,
                tool_calls_count=len(tool_calls),
                tokens_consumed=tokens_used,
                what_went_poorly=["Reflection analysis timed out (LLM response too slow)"],
                suggested_improvements=["Consider simplifying task or reducing tool calls"],
                confidence_score=0.0,
            )
        except Exception as e:
            logger.error(f"Reflection generation failed: {type(e).__name__}: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # Return minimal report on failure
            return ReflectionReport(
                task_id=task_id,
                task_description=task_description,
                timestamp=datetime.now().isoformat(),
                status=status,
                duration_seconds=duration,
                tool_calls_count=len(tool_calls),
                tokens_consumed=tokens_used,
                what_went_poorly=[f"Reflection analysis failed: {type(e).__name__}: {str(e)}"],
                confidence_score=0.0,
            )
    
    def _format_tool_history(self, tool_calls: list[dict[str, Any]]) -> str:
        """Format tool call history for reflection prompt."""
        if not tool_calls:
            return "No tool calls made"
        
        lines = []
        for i, call in enumerate(tool_calls, 1):
            tool_name = call.get("tool_name", "unknown")
            success = call.get("success", False)
            duration = call.get("duration", 0)
            error = call.get("error", "")
            
            status_icon = "✓" if success else "✗"
            line = f"{i}. [{status_icon}] {tool_name} ({duration:.2f}s)"
            if error:
                line += f" - Error: {error[:100]}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _parse_reflection_response(self, content: str) -> dict[str, Any]:
        """Parse LLM response to extract reflection data."""
        import json_repair
        
        try:
            # Try to extract JSON from response
            content = content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```", 1)[1]
                if "```" in content:
                    content = content.rsplit("```", 1)[0]
            
            data = json_repair.loads(content)
            
            if not isinstance(data, dict):
                logger.warning("Reflection response is not a dict, using defaults")
                return {}
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse reflection response: {e}")
            return {}
    
    def _estimate_complexity(
        self,
        tool_calls: list[dict[str, Any]],
        duration: float,
    ) -> float:
        """
        Estimate task complexity based on tool usage and duration.
        
        Returns a score from 0.0 (simple) to 1.0 (complex).
        """
        # Base complexity on number of tool calls
        tool_complexity = min(len(tool_calls) / 20.0, 1.0)
        
        # Add time complexity (normalized, assuming 5 min max for typical tasks)
        time_complexity = min(duration / 300.0, 1.0)
        
        # Check for error retries (increases complexity)
        error_count = sum(1 for call in tool_calls if not call.get("success", True))
        error_complexity = min(error_count / 5.0, 1.0)
        
        # Weighted average
        complexity = (tool_complexity * 0.4 + time_complexity * 0.3 + error_complexity * 0.3)
        
        return round(complexity, 2)
    
    def get_recent_reflections(self, limit: int = 10) -> list[ReflectionReport]:
        """Get most recent reflection reports."""
        return self._reports_cache[-limit:]
    
    def get_reflections_by_status(self, status: str) -> list[ReflectionReport]:
        """Get reflection reports filtered by status."""
        return [r for r in self._reports_cache if r.status == status]
    
    def get_failure_patterns(self) -> dict[str, int]:
        """Analyze failure patterns from reflection reports."""
        patterns: dict[str, int] = {}
        
        for report in self.get_reflections_by_status("failure"):
            for pattern in report.patterns_detected:
                patterns[pattern] = patterns.get(pattern, 0) + 1
            for cause in report.root_causes:
                # Extract key phrase (first 50 chars)
                key = cause[:50] + "..." if len(cause) > 50 else cause
                patterns[key] = patterns.get(key, 0) + 1
        
        return dict(sorted(patterns.items(), key=lambda x: x[1], reverse=True))
    
    def generate_summary_report(self) -> str:
        """Generate a summary report of all reflections."""
        if not self._reports_cache:
            return "No reflection reports available yet."
        
        total = len(self._reports_cache)
        successes = len(self.get_reflections_by_status("success"))
        failures = len(self.get_reflections_by_status("failure"))
        partial = total - successes - failures
        
        avg_confidence = sum(r.confidence_score for r in self._reports_cache) / total
        avg_duration = sum(r.duration_seconds for r in self._reports_cache) / total
        
        lines = [
            "# Self-Reflection Summary Report",
            "",
            "## Overview",
            f"- Total Tasks Analyzed: {total}",
            f"- Success Rate: {successes/total*100:.1f}%",
            f"- Average Confidence: {avg_confidence:.2f}",
            f"- Average Duration: {avg_duration:.1f}s",
            "",
            "## Status Breakdown",
            f"- ✓ Success: {successes}",
            f"- ⚠ Partial: {partial}",
            f"- ✗ Failure: {failures}",
            "",
        ]
        
        # Add common lessons learned
        all_lessons: dict[str, int] = {}
        for report in self._reports_cache:
            for lesson in report.lessons_learned:
                # Normalize lesson (first 60 chars)
                key = lesson[:60] + "..." if len(lesson) > 60 else lesson
                all_lessons[key] = all_lessons.get(key, 0) + 1
        
        if all_lessons:
            lines.append("## Top Lessons Learned")
            for lesson, count in list(all_lessons.items())[:5]:
                lines.append(f"- ({count}x) {lesson}")
            lines.append("")
        
        # Add failure patterns
        failure_patterns = self.get_failure_patterns()
        if failure_patterns:
            lines.append("## Common Failure Patterns")
            for pattern, count in list(failure_patterns.items())[:5]:
                lines.append(f"- ({count}x) {pattern}")
            lines.append("")
        
        return "\n".join(lines)


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path
