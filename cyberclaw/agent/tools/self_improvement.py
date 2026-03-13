"""
Self-Improving Agent: Tools for accessing reflection and experience data.
"""

from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.reflection import ReflectionEngine
from cyberclaw.agent.experience import ExperienceRepository
from cyberclaw.agent.metrics import MetricsTracker
from cyberclaw.agent.confidence import ConfidenceEvaluator
from cyberclaw.agent.tool_optimizer import ToolOptimizer
from cyberclaw.agent.skill_evolution import SkillEvolutionAnalyzer


class GetReflectionsTool(Tool):
    """Tool to retrieve reflection reports and summaries."""
    
    name = "get_reflections"
    description = """Get reflection reports and self-improvement insights.
    
    Commands:
    - summary: Get overall reflection summary
    - recent [N]: Get N most recent reflections (default: 5)
    - failures: Get reflections for failed tasks
    - patterns: Get common failure patterns
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["summary", "recent", "failures", "patterns"],
                "description": "Command to execute",
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "Number of items to return (for recent command)",
            },
        },
        "required": ["command"],
    }
    
    def __init__(self, reflection_engine: ReflectionEngine, experience_repo: ExperienceRepository):
        self.reflection_engine = reflection_engine
        self.experience_repo = experience_repo
    
    async def execute(self, command: str, limit: int = 5) -> str:
        if command == "summary":
            return self.reflection_engine.generate_summary_report()
        
        elif command == "recent":
            reports = self.reflection_engine.get_recent_reflections(limit)
            if not reports:
                return "No reflection reports yet."
            
            lines = ["## Recent Reflection Reports", ""]
            for report in reversed(reports):
                icon = "✓" if report.status == "success" else "✗"
                lines.append(f"### {icon} Task: {report.task_description[:80]}")
                lines.append(f"- Status: {report.status}")
                lines.append(f"- Confidence: {report.confidence_score:.2f}")
                lines.append(f"- Duration: {report.duration_seconds:.1f}s")
                if report.lessons_learned:
                    lines.append(f"- Key Lesson: {report.lessons_learned[0][:100]}")
                lines.append("")
            
            return "\n".join(lines)
        
        elif command == "failures":
            reports = self.reflection_engine.get_reflections_by_status("failure")
            if not reports:
                return "No failed tasks recorded yet."
            
            lines = ["## Failed Task Reflections", ""]
            for report in reversed(reports[-limit:]):
                lines.append(f"### Task: {report.task_description[:80]}")
                lines.append(f"- Duration: {report.duration_seconds:.1f}s")
                lines.append(f"- Tool Calls: {report.tool_calls_count}")
                if report.root_causes:
                    lines.append("- Root Causes:")
                    for cause in report.root_causes[:3]:
                        lines.append(f"  - {cause[:100]}")
                lines.append("")
            
            return "\n".join(lines)
        
        elif command == "patterns":
            patterns = self.reflection_engine.get_failure_patterns()
            if not patterns:
                return "No failure patterns detected yet."
            
            lines = ["## Common Failure Patterns", ""]
            for pattern, count in list(patterns.items())[:10]:
                lines.append(f"- ({count}x) {pattern[:100]}")
            
            return "\n".join(lines)
        
        return f"Unknown command: {command}. Use: summary, recent, failures, patterns"


class GetExperienceTool(Tool):
    """Tool to retrieve experience records and insights."""
    
    name = "get_experience"
    description = """Query the experience repository for past solutions and patterns.
    
    Commands:
    - search <query>: Search for similar experiences
    - successes [category]: Get successful patterns
    - warnings [tool]: Get warnings for specific tool
    - stats: Get repository statistics
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["search", "successes", "warnings", "stats"],
                "description": "Command to execute",
            },
            "query": {
                "type": "string",
                "description": "Search query or category/tool name",
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "Number of items to return",
            },
        },
        "required": ["command"],
    }
    
    def __init__(self, experience_repo: ExperienceRepository):
        self.experience_repo = experience_repo
    
    async def execute(self, command: str, query: str = "", limit: int = 5) -> str:
        if command == "search":
            if not query:
                return "Please provide a search query."
            
            experiences = self.experience_repo.get_similar_experiences(query, limit=limit)
            if not experiences:
                return f"No similar experiences found for: {query}"
            
            lines = [f"## Similar Experiences for '{query}'", ""]
            for exp in experiences:
                icon = "✓" if exp.success else "✗"
                lines.append(f"### {icon} {exp.task_description[:80]}")
                lines.append(f"- Category: {exp.task_category}")
                lines.append(f"- Approach: {exp.solution_approach[:100]}")
                lines.append(f"- Reused: {exp.reuse_count} times")
                if exp.key_insights:
                    lines.append(f"- Insight: {exp.key_insights[0][:100]}")
                lines.append("")
            
            return "\n".join(lines)
        
        elif command == "successes":
            experiences = self.experience_repo.get_success_patterns(query if query else None)
            if not experiences:
                return "No successful patterns recorded yet."
            
            lines = ["## Successful Patterns", ""]
            for exp in experiences[:limit]:
                lines.append(f"### ✓ [{exp.task_category}] {exp.task_description[:60]}")
                lines.append(f"- Approach: {exp.solution_approach[:100]}")
                lines.append(f"- Reused: {exp.reuse_count} times")
                lines.append("")
            
            return "\n".join(lines)
        
        elif command == "warnings":
            if not query:
                return "Please provide a tool name."
            
            warnings = self.experience_repo.get_warnings_for_tools([query])
            if not warnings:
                return f"No warnings found for tool: {query}"
            
            lines = [f"## Warnings for '{query}'", ""]
            for exp, warning in warnings[:limit]:
                lines.append(f"- ⚠️ {warning[:100]}")
                lines.append(f"  (from: {exp.task_description[:50]})")
                lines.append("")
            
            return "\n".join(lines)
        
        elif command == "stats":
            stats = self.experience_repo.get_statistics()
            
            lines = [
                "## Experience Repository Statistics",
                "",
                f"- Total Records: {stats['total_records']}",
                f"- Success Rate: {stats['success_rate']*100:.1f}%",
                f"- Average Confidence: {stats['average_confidence']:.2f}",
                f"- Total Reuses: {stats['total_reuses']}",
                "",
                "### By Category",
            ]
            
            for category, count in sorted(stats["categories"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {category}: {count}")
            
            return "\n".join(lines)
        
        return f"Unknown command: {command}. Use: search, successes, warnings, stats"


class GetConfidenceTool(Tool):
    """Tool to evaluate answer confidence (P1 - Confidence Injection)."""
    
    name = "get_confidence"
    description = """Evaluate confidence in an answer before acting on it.
    
    Commands:
    - evaluate <question> <answer>: Evaluate confidence score
    - factors: Get confidence evaluation factors
    - history: Get recent confidence evaluations
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["evaluate", "factors", "history"],
                "description": "Command to execute",
            },
            "question": {
                "type": "string",
                "description": "Original question (for evaluate command)",
            },
            "answer": {
                "type": "string",
                "description": "Generated answer (for evaluate command)",
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "Number of history items to return",
            },
        },
        "required": ["command"],
    }
    
    def __init__(self, evaluator: ConfidenceEvaluator):
        self.evaluator = evaluator
    
    async def execute(
        self,
        command: str,
        question: str = "",
        answer: str = "",
        limit: int = 5,
    ) -> str:
        if command == "evaluate":
            if not question or not answer:
                return "Please provide both question and answer for evaluation."
            
            result = self.evaluator.evaluate(question, answer)
            
            lines = [
                "## Confidence Evaluation",
                "",
                f"**Score**: {result.score:.2f} / 1.00",
                f"**Level**: {result.level.upper()}",
                f"**Should Verify**: {'Yes' if result.should_verify else 'No'}",
                "",
            ]
            
            if result.factors:
                lines.append("### Factors")
                for factor in result.factors[:5]:
                    lines.append(f"- {factor}")
                lines.append("")
            
            if result.warnings:
                lines.append("### ⚠️ Warnings")
                for warning in result.warnings:
                    lines.append(f"- {warning}")
                lines.append("")
            
            if result.suggestions:
                lines.append("### 💡 Suggestions")
                for suggestion in result.suggestions:
                    lines.append(f"- {suggestion}")
            
            return "\n".join(lines)
        
        elif command == "factors":
            factors = self.evaluator.get_confidence_factors()
            lines = [
                "## Confidence Evaluation Factors",
                "",
                f"- **Threshold**: {factors['threshold']}",
                f"- **Auto Verify**: {factors['auto_verify']}",
                f"- **History Records**: {factors['history_records']}",
                "",
                "### Domain Weights",
            ]
            for domain, weight in list(factors['domain_weights'].items())[:5]:
                lines.append(f"- {domain}: {weight:.2f}")
            
            return "\n".join(lines)
        
        elif command == "history":
            if not self.evaluator._history:
                return "No confidence evaluation history yet."
            
            recent = self.evaluator._history[-limit:]
            lines = ["## Recent Confidence Evaluations", ""]
            
            for record in reversed(recent):
                result = record.get("result", {})
                score = result.get("score", 0)
                level = result.get("level", "unknown")
                question = record.get("question", "Unknown")[:60]
                
                icon = "✓" if score >= 0.7 else "⚠️"
                lines.append(f"- {icon} [{level.upper()}] {question}... (score: {score:.2f})")
            
            return "\n".join(lines)
        
        return f"Unknown command: {command}. Use: evaluate, factors, history"


class GetToolRecommendationsTool(Tool):
    """Tool to get tool recommendations based on historical performance (P1 - Tool Optimization)."""
    
    name = "get_tool_recommendations"
    description = """Get tool recommendations for a task based on historical performance.
    
    Commands:
    - recommend <task>: Get tool recommendations
    - performance: Get tool performance report
    - rankings: Get tool rankings by success rate
    - stats <tool>: Get statistics for specific tool
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["recommend", "performance", "rankings", "stats"],
                "description": "Command to execute",
            },
            "task": {
                "type": "string",
                "description": "Task description (for recommend command)",
            },
            "tool": {
                "type": "string",
                "description": "Tool name (for stats command)",
            },
            "limit": {
                "type": "integer",
                "default": 3,
                "description": "Number of recommendations to return",
            },
        },
        "required": ["command"],
    }
    
    def __init__(self, optimizer: ToolOptimizer):
        self.optimizer = optimizer
    
    async def execute(
        self,
        command: str,
        task: str = "",
        tool: str = "",
        limit: int = 3,
    ) -> str:
        if command == "recommend":
            if not task:
                return "Please provide a task description."
            
            recommendations = self.optimizer.recommend_tool(task, max_recommendations=limit)
            
            if not recommendations:
                return f"No tool recommendations available for: {task}"
            
            lines = [f"## Tool Recommendations for '{task[:50]}...'", ""]
            
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"### {i}. **{rec.tool_name}** (Score: {rec.score:.2f})")
                lines.append(f"- Success Probability: {rec.success_probability*100:.0f}%")
                lines.append(f"- Estimated Duration: {rec.estimated_duration:.1f}s")
                if rec.reasons:
                    lines.append("- Why:")
                    for reason in rec.reasons:
                        lines.append(f"  - {reason}")
                if rec.alternatives:
                    lines.append(f"- Alternatives: {', '.join(rec.alternatives)}")
                lines.append("")
            
            return "\n".join(lines)
        
        elif command == "performance":
            return self.optimizer.get_performance_report()
        
        elif command == "rankings":
            rankings = self.optimizer.get_tool_rankings("success_rate", min_calls=1)
            
            if not rankings:
                return "No tool usage data available yet."
            
            lines = ["## Tool Rankings (by Success Rate)", ""]
            for tool_name, score in rankings[:10]:
                stats = self.optimizer.get_statistics(tool_name)
                if stats:
                    lines.append(
                        f"- **{tool_name}**: {score*100:.0f}% success "
                        f"({stats.total_calls} calls, {stats.avg_duration:.1f}s avg)"
                    )
            
            return "\n".join(lines)
        
        elif command == "stats":
            if not tool:
                return "Please provide a tool name."
            
            stats = self.optimizer.get_statistics(tool)
            if not stats:
                return f"No statistics available for tool: {tool}"
            
            lines = [
                f"## Statistics for '{tool}'",
                "",
                f"- **Total Calls**: {stats.total_calls}",
                f"- **Success Rate**: {stats.success_rate*100:.0f}%",
                f"- **Avg Duration**: {stats.avg_duration:.2f}s",
                f"- **P50 Duration**: {stats.p50_duration:.2f}s",
                f"- **P95 Duration**: {stats.p95_duration:.2f}s",
                f"- **Max Duration**: {stats.max_duration:.2f}s",
            ]
            
            if stats.failure_reasons:
                lines.append("")
                lines.append("### Common Failure Reasons")
                for reason, count in list(stats.failure_reasons.items())[:3]:
                    lines.append(f"- ({count}x) {reason[:60]}")
            
            if stats.categories:
                lines.append("")
                lines.append("### Task Categories")
                for cat, count in sorted(stats.categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                    lines.append(f"- {cat}: {count}")
            
            return "\n".join(lines)
        
        return f"Unknown command: {command}. Use: recommend, performance, rankings, stats"


class GetSkillEvolutionTool(Tool):
    """Tool to get skill evolution analysis and suggestions (P2 - Skill Evolution)."""
    
    name = "get_skill_evolution"
    description = """Analyze skill usage and get improvement suggestions.
    
    Commands:
    - report: Generate full evolution report
    - suggestions: Get improvement suggestions
    - gaps: Identify skill gaps
    - health <skill>: Get health score for specific skill
    - stats: Get skill usage statistics
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["report", "suggestions", "gaps", "health", "stats"],
                "description": "Command to execute",
            },
            "skill": {
                "type": "string",
                "description": "Skill name (for health command)",
            },
            "period": {
                "type": "integer",
                "default": 30,
                "description": "Analysis period in days",
            },
        },
        "required": ["command"],
    }
    
    def __init__(self, analyzer: SkillEvolutionAnalyzer):
        self.analyzer = analyzer
    
    async def execute(
        self,
        command: str,
        skill: str = "",
        period: int = 30,
    ) -> str:
        if command == "report":
            report = self.analyzer.generate_evolution_report(period_days=period)
            return self.analyzer.get_report_text(report)
        
        elif command == "suggestions":
            suggestions = self.analyzer.generate_improvement_suggestions()
            
            if not suggestions:
                return "No improvement suggestions at this time."
            
            lines = ["## Skill Improvement Suggestions", ""]
            for i, suggestion in enumerate(suggestions[:10], 1):
                lines.append(f"{i}. {suggestion}")
            
            return "\n".join(lines)
        
        elif command == "gaps":
            gaps = self.analyzer.identify_gaps()
            
            if not gaps:
                return "No significant skill gaps identified."
            
            lines = ["## Identified Skill Gaps", ""]
            for gap in gaps[:10]:
                impact_icon = "🔴" if gap.impact == "high" else "🟡"
                lines.append(f"- {impact_icon} **{gap.gap_type}**: {gap.description}")
                lines.append(f"  - {gap.recommendation}")
            
            return "\n".join(lines)
        
        elif command == "health":
            if not skill:
                return "Please provide a skill name."
            
            health = self.analyzer.get_skill_health_score(skill)
            
            if health == 0.0:
                return f"No data available for skill: {skill}"
            
            icon = "✓" if health >= 0.7 else "⚠️" if health >= 0.4 else "✗"
            level = "Good" if health >= 0.7 else "Fair" if health >= 0.4 else "Poor"
            
            return f"## Health Score for '{skill}'\n\n{icon} **{level}**: {health:.2f} / 1.00"
        
        elif command == "stats":
            stats = self.analyzer.analyze_skill_usage(period_days=period)
            
            if not stats:
                return f"No skill usage data in the last {period} days."
            
            lines = [f"## Skill Usage Statistics (Last {period} Days)", ""]
            
            sorted_stats = sorted(stats.items(), key=lambda x: x[1].total_uses, reverse=True)
            for name, s in sorted_stats[:10]:
                icon = "✓" if s.success_rate >= 0.8 else "⚠️" if s.success_rate >= 0.5 else "✗"
                lines.append(
                    f"- {icon} **{name}**: {s.total_uses} uses, "
                    f"{s.success_rate*100:.0f}% success, "
                    f"health: {s.health_score:.2f}"
                )
            
            return "\n".join(lines)
        
        return f"Unknown command: {command}. Use: report, suggestions, gaps, health, stats"


class GetSelfImprovementMetricsTool(Tool):
    """Tool to get combined self-improvement metrics (P0/P1/P2)."""
    
    name = "get_improvement_metrics"
    description = """Get comprehensive self-improvement metrics and insights.
    
    Includes:
    - Reflection summary (P0)
    - Experience repository stats (P0)
    - Failure patterns (P0)
    - Tool performance (P1)
    - Skill evolution (P2)
    """
    
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    
    def __init__(
        self,
        reflection_engine: ReflectionEngine,
        experience_repo: ExperienceRepository,
        metrics: MetricsTracker,
        tool_optimizer: ToolOptimizer | None = None,
        skill_analyzer: SkillEvolutionAnalyzer | None = None,
    ):
        self.reflection_engine = reflection_engine
        self.experience_repo = experience_repo
        self.metrics = metrics
        self.tool_optimizer = tool_optimizer
        self.skill_analyzer = skill_analyzer
    
    async def execute(self) -> str:
        lines = [
            "# 🧠 Self-Improvement Metrics Report",
            "",
        ]
        
        # Reflection summary (P0)
        lines.append("## Reflection Summary")
        lines.append(self.reflection_engine.generate_summary_report())
        lines.append("")
        
        # Experience repository (P0)
        lines.append("## Experience Repository")
        lines.append(self.experience_repo.generate_summary_report())
        lines.append("")
        
        # Failure patterns from metrics (P0)
        failure_patterns = self.metrics.get_failure_patterns(limit=5)
        if failure_patterns:
            lines.append("## Top Failure Patterns (from Metrics)")
            for pattern, count in failure_patterns:
                lines.append(f"- ({count}x) {pattern[:80]}...")
            lines.append("")
        
        # Tool performance (P1)
        if self.tool_optimizer:
            lines.append("## Tool Performance (P1)")
            lines.append(self.tool_optimizer.get_performance_report())
            lines.append("")
        
        # Skill evolution (P2)
        if self.skill_analyzer:
            lines.append("## Skill Evolution (P2)")
            report = self.skill_analyzer.generate_evolution_report(period_days=30)
            lines.append(f"- **Total Skills**: {report.total_skills}")
            lines.append(f"- **Active Skills**: {report.active_skills}")
            lines.append(f"- **Overall Health**: {report.overall_health:.2f}")
            
            if report.top_performers:
                lines.append(f"- **Top Performers**: {', '.join(report.top_performers[:3])}")
            if report.underperforming:
                lines.append(f"- **Needs Improvement**: {', '.join(report.underperforming[:3])}")
            lines.append("")
        
        # Suggestions
        lines.append("## Improvement Suggestions")
        lines.append("1. Review recent failures to identify recurring issues")
        lines.append("2. Search experience repository before tackling similar tasks")
        lines.append("3. Pay attention to low-confidence reflections for learning opportunities")
        
        if self.tool_optimizer:
            lines.append("4. Use get_tool_recommendations for optimal tool selection")
        
        if self.skill_analyzer:
            lines.append("5. Run get_skill_evolution report for skill improvement suggestions")
        
        return "\n".join(lines)
