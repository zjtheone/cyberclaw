"""
Self-Improving Agent: Skill Evolution Suggestions (P2)

Analyzes skill usage patterns and generates improvement suggestions.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from cyberclaw.agent.experience import ExperienceRepository
from cyberclaw.agent.metrics import MetricsTracker
from cyberclaw.agent.tool_optimizer import ToolOptimizer


@dataclass
class SkillUsageStats:
    """Statistics for a single skill."""
    name: str
    total_uses: int = 0
    successful_uses: int = 0
    failed_uses: int = 0
    success_rate: float = 0.0
    source: str = "unknown"  # "workspace" / "builtin" / "unknown"

    # Timing
    first_used: str | None = None
    last_used: str | None = None
    avg_duration: float = 0.0

    # Task analysis
    common_tasks: list[str] = field(default_factory=list)
    task_categories: dict[str, int] = field(default_factory=dict)

    # Performance
    failure_patterns: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)

    # Health score (0-1)
    health_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_uses": self.total_uses,
            "successful_uses": self.successful_uses,
            "failed_uses": self.failed_uses,
            "success_rate": self.success_rate,
            "source": self.source,
            "first_used": self.first_used,
            "last_used": self.last_used,
            "avg_duration": self.avg_duration,
            "common_tasks": self.common_tasks,
            "task_categories": self.task_categories,
            "failure_patterns": self.failure_patterns,
            "improvement_suggestions": self.improvement_suggestions,
            "health_score": self.health_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillUsageStats":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SkillGap:
    """Identified skill gap."""
    gap_type: str  # "missing", "underperforming", "outdated"
    description: str
    impact: str  # "high", "medium", "low"
    recommendation: str
    related_tasks: list[str] = field(default_factory=list)


@dataclass
class EvolutionReport:
    """Skill evolution analysis report."""
    timestamp: str
    analysis_period_days: int
    
    # Overview
    total_skills: int
    active_skills: int
    overall_health: float
    
    # Skill stats
    skill_stats: dict[str, SkillUsageStats]
    
    # Analysis
    top_performers: list[str]
    underperforming: list[str]
    skill_gaps: list[SkillGap]
    
    # Recommendations
    improvement_suggestions: list[str]
    new_skill_recommendations: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "analysis_period_days": self.analysis_period_days,
            "total_skills": self.total_skills,
            "active_skills": self.active_skills,
            "overall_health": self.overall_health,
            "skill_stats": {k: v.to_dict() for k, v in self.skill_stats.items()},
            "top_performers": self.top_performers,
            "underperforming": self.underperforming,
            "skill_gaps": [
                {
                    "gap_type": g.gap_type,
                    "description": g.description,
                    "impact": g.impact,
                    "recommendation": g.recommendation,
                }
                for g in self.skill_gaps
            ],
            "improvement_suggestions": self.improvement_suggestions,
            "new_skill_recommendations": self.new_skill_recommendations,
        }


class SkillEvolutionAnalyzer:
    """
    Analyzes skill usage and generates evolution suggestions.
    
    Features:
    - Track skill usage frequency and success rates
    - Detect usage patterns and trends
    - Identify skill gaps
    - Generate improvement suggestions
    - Calculate skill health scores
    """
    
    # Known skill categories and expected capabilities
    SKILL_CATEGORIES = {
        "data": ["csv", "excel", "json", "database", "analytics"],
        "web": ["search", "fetch", "scrape", "browser", "http"],
        "file": ["organize", "convert", "pdf", "markdown", "document"],
        "communication": ["email", "message", "notify", "slack", "telegram"],
        "development": ["code", "git", "test", "debug", "deploy"],
        "automation": ["cron", "schedule", "workflow", "trigger"],
        "ai": ["llm", "embedding", "vector", "summarize", "translate"],
        "cloud": ["aws", "gcp", "azure", "jdcloud", "deploy"],
    }
    
    # Common task patterns that suggest missing skills
    TASK_SKILL_HINTS = {
        "transcribe": ["audio", "speech-to-text"],
        "convert.*image": ["image-processing", "ocr"],
        "schedule.*meeting": ["calendar", "scheduling"],
        "send.*email": ["email", "communication"],
        "deploy.*server": ["deployment", "cloud"],
        "analyze.*data": ["data-analysis", "visualization"],
        "translate": ["translation", "language"],
        "summarize": ["summarization", "text-processing"],
    }
    
    def __init__(
        self,
        workspace: Path,
        experience_repo: ExperienceRepository,
        metrics_tracker: MetricsTracker,
        tool_optimizer: ToolOptimizer,
        skills_dir: Path | None = None,
        skills_loader: "SkillsLoader | None" = None,
    ):
        self.workspace = workspace
        self.experience_repo = experience_repo
        self.metrics_tracker = metrics_tracker
        self.tool_optimizer = tool_optimizer
        self.skills_dir = skills_dir or workspace / "skills"
        self.skills_loader = skills_loader
        
        self.stats_dir = workspace / ".cyberclaw"
        self.skill_stats_file = self.stats_dir / "skill_usage.json"
        self.reports_dir = self.stats_dir / "skill_evolution"
        
        self._stats: dict[str, SkillUsageStats] = {}
        self._reports: list[EvolutionReport] = []
        
        self._load()
        self._analyze_from_experience()
    
    def _load(self) -> None:
        """Load skill usage statistics."""
        if not self.skill_stats_file.exists():
            return
        
        try:
            data = json.loads(self.skill_stats_file.read_text(encoding="utf-8"))
            for name, stats_data in data.items():
                self._stats[name] = SkillUsageStats.from_dict(stats_data)
            logger.info(f"Loaded statistics for {len(self._stats)} skills")
        except Exception as e:
            logger.error(f"Failed to load skill statistics: {e}")
    
    def _save(self) -> None:
        """Save skill usage statistics."""
        try:
            self.stats_dir.mkdir(parents=True, exist_ok=True)
            data = {name: stats.to_dict() for name, stats in self._stats.items()}
            self.skill_stats_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save skill statistics: {e}")
    
    def _analyze_from_experience(self) -> None:
        """从 SkillsLoader 发现已知技能，并为未跟踪的技能创建初始统计。"""
        if not self.skills_loader:
            return
        try:
            known_skills = self.skills_loader.list_skills(filter_unavailable=False)
            for skill_info in known_skills:
                name = skill_info["name"]
                if name not in self._stats:
                    self._stats[name] = SkillUsageStats(
                        name=name,
                        source=skill_info.get("source", "unknown"),
                    )
            if known_skills:
                logger.info(f"Discovered {len(known_skills)} skills from loader")
        except Exception as e:
            logger.error(f"Failed to analyze skills from loader: {e}")

    def get_known_skill_names(self) -> set[str]:
        """返回所有已知技能名称（来自 SkillsLoader 和已跟踪数据）。"""
        names = set(self._stats.keys())
        if self.skills_loader:
            try:
                for s in self.skills_loader.list_skills(filter_unavailable=False):
                    names.add(s["name"])
            except Exception:
                pass
        return names

    def get_frequently_used_skills(self, min_uses: int = 3, min_success_rate: float = 0.5) -> list[str]:
        """返回高频且成功率达标的技能名，用于自动加载到系统提示词。"""
        result = []
        for name, stats in self._stats.items():
            if stats.total_uses >= min_uses and stats.success_rate >= min_success_rate:
                result.append(name)
        return result
    
    def track_skill_usage(
        self,
        skill_name: str,
        success: bool,
        duration: float = 0.0,
        task_description: str = "",
        error_message: str = "",
        skill_source: str = "unknown",
    ) -> None:
        """
        Track skill usage in real-time.
        
        Args:
            skill_name: Name of the skill used
            success: Whether the skill execution was successful
            duration: Execution time in seconds
            task_description: What task was being performed
            error_message: Error message if failed
        """
        if skill_name not in self._stats:
            self._stats[skill_name] = SkillUsageStats(name=skill_name, source=skill_source)
        elif self._stats[skill_name].source == "unknown" and skill_source != "unknown":
            self._stats[skill_name].source = skill_source
        
        stats = self._stats[skill_name]
        stats.total_uses += 1
        
        if success:
            stats.successful_uses += 1
        else:
            stats.failed_uses += 1
            if error_message:
                stats.failure_patterns.append(error_message[:200])
        
        # Update task info
        if task_description and len(stats.common_tasks) < 20:
            # Avoid duplicates
            if task_description[:100] not in stats.common_tasks:
                stats.common_tasks.append(task_description[:100])
        
        # Update timing
        now = datetime.now().isoformat()
        if not stats.first_used or now < stats.first_used:
            stats.first_used = now
        if not stats.last_used or now > stats.last_used:
            stats.last_used = now
        
        # Update average duration
        if duration > 0:
            total_duration = stats.avg_duration * (stats.total_uses - 1) + duration
            stats.avg_duration = total_duration / stats.total_uses
        
        # Update success rate
        stats.success_rate = stats.successful_uses / stats.total_uses if stats.total_uses > 0 else 0.0

        # Recalculate health score
        stats.health_score = self._calculate_health_score(stats)

        # 持久化
        self._save()

        logger.debug(f"Tracked skill usage: {skill_name} (success={success}, duration={duration:.2f}s)")
    
    def generate_report(self, period_days: int = 30) -> EvolutionReport:
        """
        Generate skill evolution report (wrapper for generate_evolution_report).
        
        Args:
            period_days: Analysis period in days.
        
        Returns:
            EvolutionReport with full analysis.
        """
        return self.generate_evolution_report(period_days)
    
    def analyze_skill_usage(self, period_days: int = 30) -> dict[str, SkillUsageStats]:
        """
        Analyze skill usage over a period.
        
        Args:
            period_days: Number of days to analyze.
        
        Returns:
            Dictionary of skill statistics.
        """
        cutoff = datetime.now() - timedelta(days=period_days)
        
        # Start with already tracked skills from memory
        skill_usage = self._stats.copy()
        
        # Also analyze from experience records
        experiences = self.experience_repo._records
        
        for exp in experiences:
            try:
                exp_time = datetime.fromisoformat(exp.timestamp)
                if exp_time < cutoff:
                    continue
            except Exception:
                continue
            
            # Extract skill from tools used
            for tool_name in exp.tools_used:
                if tool_name not in skill_usage:
                    skill_usage[tool_name] = SkillUsageStats(name=tool_name)
                
                stats = skill_usage[tool_name]
                stats.total_uses += 1
                
                if exp.success:
                    stats.successful_uses += 1
                else:
                    stats.failed_uses += 1
                    if exp.warnings:
                        stats.failure_patterns.append(exp.warnings[0][:100])
                
                # Update task info
                if len(stats.common_tasks) < 10:
                    stats.common_tasks.append(exp.task_description[:100])
                
                category = exp.task_category
                stats.task_categories[category] = stats.task_categories.get(category, 0) + 1
                
                # Update timing
                if not stats.first_used or exp.timestamp < stats.first_used:
                    stats.first_used = exp.timestamp
                if not stats.last_used or exp.timestamp > stats.last_used:
                    stats.last_used = exp.timestamp
        
        # Calculate derived metrics
        for stats in skill_usage.values():
            if stats.total_uses > 0:
                stats.success_rate = stats.successful_uses / stats.total_uses
            stats.health_score = self._calculate_health_score(stats)
        
        self._stats = skill_usage
        self._save()
        
        return skill_usage
    
    def _calculate_health_score(self, stats: SkillUsageStats) -> float:
        """Calculate health score for a skill (0-1)."""
        score = 0.0
        
        # Success rate (50% weight)
        score += 0.50 * stats.success_rate
        
        # Usage frequency (20% weight) - more usage = more tested
        usage_score = min(1.0, stats.total_uses / 20.0)
        score += 0.20 * usage_score
        
        # Recency (20% weight)
        if stats.last_used:
            try:
                last_used = datetime.fromisoformat(stats.last_used)
                days_since = (datetime.now() - last_used).days
                recency_score = max(0.0, 1.0 - (days_since / 30.0))
                score += 0.20 * recency_score
            except Exception:
                pass
        
        # Failure pattern diversity (10% weight) - fewer unique failures = better
        if stats.failed_uses > 0 and stats.total_uses > 0:
            failure_diversity = len(set(stats.failure_patterns)) / min(stats.failed_uses, 10)
            diversity_score = 1.0 - failure_diversity
            score += 0.10 * diversity_score
        elif stats.total_uses > 0:
            # No failures = perfect diversity score
            score += 0.10 * 1.0
        
        return round(min(1.0, max(0.0, score)), 3)
    
    def detect_usage_patterns(self) -> dict[str, list[str]]:
        """
        Detect common usage patterns for skills.
        
        Returns:
            Dictionary mapping skills to their usage patterns.
        """
        patterns: dict[str, list[str]] = {}
        
        for name, stats in self._stats.items():
            skill_patterns = []
            
            # Analyze task categories
            if stats.task_categories:
                top_category = max(stats.task_categories.items(), key=lambda x: x[1])
                skill_patterns.append(f"Primarily used for: {top_category[0]}")
            
            # Analyze timing
            if stats.total_uses >= 5:
                skill_patterns.append(f"Regular usage ({stats.total_uses} times)")
            
            # Analyze success trends
            if stats.success_rate >= 0.9:
                skill_patterns.append("Highly reliable")
            elif stats.success_rate <= 0.5:
                skill_patterns.append("Needs improvement")
            
            # Analyze failure patterns
            if stats.failure_patterns:
                common_failures = {}
                for pattern in stats.failure_patterns:
                    key = pattern[:50]
                    common_failures[key] = common_failures.get(key, 0) + 1
                
                if common_failures:
                    top_failure = max(common_failures.items(), key=lambda x: x[1])
                    skill_patterns.append(f"Common issue: {top_failure[0]}")
            
            patterns[name] = skill_patterns
        
        return patterns
    
    def identify_gaps(self) -> list[SkillGap]:
        """
        Identify skill gaps based on task patterns.
        
        Returns:
            List of identified skill gaps.
        """
        gaps = []
        
        # Analyze experiences for unhandled task types
        experiences = self.experience_repo._records
        
        # Group failed experiences by task description patterns
        failed_tasks: dict[str, list] = {}
        for exp in experiences:
            if not exp.success:
                # Extract keywords from task description
                keywords = exp.task_description.lower().split()[:5]
                key = " ".join(keywords)
                failed_tasks.setdefault(key, []).append(exp)
        
        # Identify patterns in failures
        import re
        for task_pattern, task_list in failed_tasks.items():
            if len(task_list) >= 2:  # Multiple failures on similar tasks
                # Check if we have relevant skills
                relevant_skills = self._find_relevant_skills(task_pattern)
                
                if not relevant_skills:
                    gaps.append(SkillGap(
                        gap_type="missing",
                        description=f"Tasks matching '{task_pattern}' have high failure rate",
                        impact="high" if len(task_list) >= 5 else "medium",
                        recommendation=f"Consider adding or improving skills for: {task_pattern}",
                        related_tasks=[t.task_description[:100] for t in task_list[:5]],
                    ))
        
        # Check for underperforming skills
        for name, stats in self._stats.items():
            if stats.total_uses >= 3 and stats.success_rate < 0.6:
                gaps.append(SkillGap(
                    gap_type="underperforming",
                    description=f"Skill '{name}' has low success rate ({stats.success_rate*100:.0f}%)",
                    impact="high" if stats.total_uses >= 10 else "medium",
                    recommendation=f"Review and improve '{name}' skill implementation",
                ))
        
        return gaps
    
    def _find_relevant_skills(self, task_description: str) -> list[str]:
        """Find skills relevant to a task description."""
        task_lower = task_description.lower()
        relevant = []
        
        for category, keywords in self.SKILL_CATEGORIES.items():
            for keyword in keywords:
                if keyword in task_lower:
                    relevant.append(category)
                    break
        
        return relevant
    
    def generate_improvement_suggestions(self) -> list[str]:
        """Generate skill improvement suggestions."""
        suggestions = []
        
        # Analyze failure patterns
        for name, stats in self._stats.items():
            if stats.failure_patterns:
                # Group similar failures
                failure_counts: dict[str, int] = {}
                for pattern in stats.failure_patterns:
                    key = pattern[:50]
                    failure_counts[key] = failure_counts.get(key, 0) + 1
                
                # Add suggestion for common failures
                for pattern, count in failure_counts.items():
                    if count >= 2:
                        suggestions.append(
                            f"Fix recurring issue in '{name}': {pattern} ({count} occurrences)"
                        )
        
        # Analyze skill health
        unhealthy_skills = [
            (name, stats) for name, stats in self._stats.items()
            if stats.health_score < 0.5 and stats.total_uses >= 3
        ]
        
        for name, stats in unhealthy_skills:
            suggestions.append(
                f"Improve '{name}' (health: {stats.health_score:.2f}, "
                f"success: {stats.success_rate*100:.0f}%)"
            )
        
        return suggestions
    
    def get_skill_health_score(self, skill_name: str) -> float:
        """Get health score for a specific skill."""
        stats = self._stats.get(skill_name)
        return stats.health_score if stats else 0.0
    
    def generate_evolution_report(self, period_days: int = 30) -> EvolutionReport:
        """
        Generate comprehensive skill evolution report.
        
        Args:
            period_days: Analysis period in days.
        
        Returns:
            EvolutionReport with full analysis.
        """
        # Analyze usage
        self.analyze_skill_usage(period_days)
        
        # Get patterns and gaps
        patterns = self.detect_usage_patterns()
        gaps = self.identify_gaps()
        
        # Calculate overview
        total_skills = len(self._stats)
        active_skills = sum(1 for s in self._stats.values() if s.total_uses > 0)
        overall_health = (
            sum(s.health_score for s in self._stats.values()) / total_skills
            if total_skills > 0 else 0.0
        )
        
        # Identify top performers
        sorted_skills = sorted(
            self._stats.items(),
            key=lambda x: (x[1].health_score, x[1].total_uses),
            reverse=True,
        )
        top_performers = [name for name, stats in sorted_skills[:5] if stats.total_uses >= 3]
        
        # Identify underperforming
        underperforming = [
            name for name, stats in self._stats.items()
            if stats.total_uses >= 3 and stats.success_rate < 0.7
        ]
        
        # Generate suggestions
        improvement_suggestions = self.generate_improvement_suggestions()
        
        # Recommend new skills based on gaps
        new_skill_recommendations = []
        for gap in gaps:
            if gap.gap_type == "missing":
                new_skill_recommendations.append(gap.recommendation)
        
        report = EvolutionReport(
            timestamp=datetime.now().isoformat(),
            analysis_period_days=period_days,
            total_skills=total_skills,
            active_skills=active_skills,
            overall_health=round(overall_health, 3),
            skill_stats=self._stats.copy(),
            top_performers=top_performers,
            underperforming=underperforming,
            skill_gaps=gaps,
            improvement_suggestions=improvement_suggestions[:10],
            new_skill_recommendations=list(set(new_skill_recommendations))[:5],
        )
        
        # Save report
        self._save_report(report)
        
        return report
    
    def _save_report(self, report: EvolutionReport) -> None:
        """Save evolution report."""
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.reports_dir / f"report_{timestamp}.json"
            
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2)
            
            logger.info(f"Saved skill evolution report: {report_file}")
        except Exception as e:
            logger.error(f"Failed to save skill evolution report: {e}")
    
    def get_report_text(self, report: EvolutionReport) -> str:
        """Convert evolution report to text format."""
        lines = [
            "## Skill Evolution Report",
            "",
            f"**Generated**: {report.timestamp}",
            f"**Analysis Period**: {report.analysis_period_days} days",
            "",
            "### Overview",
            f"- **Total Skills**: {report.total_skills}",
            f"- **Active Skills**: {report.active_skills}",
            f"- **Overall Health**: {report.overall_health:.2f}",
            "",
        ]
        
        # Top performers
        if report.top_performers:
            lines.append("### Top Performers")
            for name in report.top_performers:
                stats = report.skill_stats.get(name)
                if stats:
                    lines.append(
                        f"- ✓ **{name}**: {stats.success_rate*100:.0f}% success, "
                        f"health: {stats.health_score:.2f}"
                    )
            lines.append("")
        
        # Underperforming
        if report.underperforming:
            lines.append("### Needs Improvement")
            for name in report.underperforming:
                stats = report.skill_stats.get(name)
                if stats:
                    lines.append(
                        f"- ⚠️ **{name}**: {stats.success_rate*100:.0f}% success, "
                        f"health: {stats.health_score:.2f}"
                    )
            lines.append("")
        
        # Skill gaps
        if report.skill_gaps:
            lines.append("### Skill Gaps")
            for gap in report.skill_gaps[:5]:
                impact_icon = "🔴" if gap.impact == "high" else "🟡"
                lines.append(f"- {impact_icon} **{gap.gap_type}**: {gap.description}")
                lines.append(f"  - Recommendation: {gap.recommendation}")
            lines.append("")
        
        # Suggestions
        if report.improvement_suggestions:
            lines.append("### Improvement Suggestions")
            for suggestion in report.improvement_suggestions[:10]:
                lines.append(f"- {suggestion}")
            lines.append("")
        
        # New skill recommendations
        if report.new_skill_recommendations:
            lines.append("### Recommended New Skills")
            for rec in report.new_skill_recommendations:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)
