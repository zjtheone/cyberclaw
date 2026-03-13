"""
Self-Improving Agent: Experience Repository (P0)

Stores and retrieves successful solutions and failure patterns to enable
learning from past experiences.
"""

import json
import hashlib
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from enum import Enum
from loguru import logger


class ExperienceType(str, Enum):
    """Type of experience record."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    PATTERN = "pattern"


@dataclass
class ExperienceRecord:
    """A single experience record."""
    id: str
    type: ExperienceType
    task_description: str
    task_category: str  # e.g., "file_operation", "code_analysis", "web_search"
    timestamp: str
    success: bool
    
    # Context
    input_context: str  # What was the situation
    solution_approach: str  # What approach was taken
    tools_used: list[str]  # Which tools were involved
    
    # Outcome
    outcome_description: str
    key_insights: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    # Reusability
    is_generalizable: bool = True
    applicability_conditions: list[str] = field(default_factory=list)
    
    # Metadata
    confidence_score: float = 0.0
    reuse_count: int = 0
    last_reused: str | None = None
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperienceRecord":
        data["type"] = ExperienceType(data["type"])
        return cls(**data)


class ExperienceRepository:
    """
    Repository for storing and retrieving experience records.
    
    Features:
    - Store successful solutions with context
    - Mark and track failure patterns
    - Retrieve similar experiences for current tasks
    - Track reuse statistics
    - Automatic deduplication
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.repo_dir = ensure_dir(workspace / ".cyberclaw" / "experience")
        self.records_file = self.repo_dir / "experiences.jsonl"
        self.index_file = self.repo_dir / "experience_index.json"
        
        self._records: list[ExperienceRecord] = []
        self._index: dict[str, list[str]] = {}  # category -> record_ids
        
        self._load()
    
    def _load(self) -> None:
        """Load experience records from disk."""
        if not self.records_file.exists():
            return
        
        try:
            for line in self.records_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    data = json.loads(line)
                    self._records.append(ExperienceRecord.from_dict(data))
            
            # Load or rebuild index
            if self.index_file.exists():
                self._index = json.loads(self.index_file.read_text(encoding="utf-8"))
            else:
                self._rebuild_index()
            
            logger.info(f"Loaded {len(self._records)} experience records")
        except Exception as e:
            logger.error(f"Failed to load experience repository: {e}")
    
    def _save(self) -> None:
        """Save all records to disk."""
        try:
            # Save records
            with open(self.records_file, "w", encoding="utf-8") as f:
                for record in self._records:
                    f.write(json.dumps(record.to_dict()) + "\n")
            
            # Save index
            self.index_file.write_text(json.dumps(self._index, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save experience repository: {e}")
    
    def _rebuild_index(self) -> None:
        """Rebuild the category index."""
        self._index = {}
        for record in self._records:
            if record.task_category not in self._index:
                self._index[record.task_category] = []
            self._index[record.task_category].append(record.id)
        self._save()
    
    def _generate_id(self, content: str) -> str:
        """Generate a unique ID based on content hash."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _deduplicate_key(self, record: ExperienceRecord) -> str:
        """Generate a key for deduplication."""
        # Use task description + category + approach as dedup key
        key_content = f"{record.task_description}|{record.task_category}|{record.solution_approach}"
        return self._generate_id(key_content)
    
    def add_experience(
        self,
        task_description: str,
        task_category: str,
        success: bool,
        input_context: str,
        solution_approach: str,
        tools_used: list[str],
        outcome_description: str,
        key_insights: list[str] | None = None,
        warnings: list[str] | None = None,
        is_generalizable: bool = True,
        applicability_conditions: list[str] | None = None,
        confidence_score: float = 0.0,
        tags: list[str] | None = None,
    ) -> ExperienceRecord:
        """
        Add a new experience record.
        
        Returns existing record if duplicate is found.
        """
        # Create record
        record = ExperienceRecord(
            id="",  # Will be set after dedup check
            type=self._determine_type(success),
            task_description=task_description,
            task_category=task_category,
            timestamp=datetime.now().isoformat(),
            success=success,
            input_context=input_context,
            solution_approach=solution_approach,
            tools_used=tools_used,
            outcome_description=outcome_description,
            key_insights=key_insights or [],
            warnings=warnings or [],
            is_generalizable=is_generalizable,
            applicability_conditions=applicability_conditions or [],
            confidence_score=confidence_score,
            tags=tags or [],
        )
        
        # Check for duplicates
        dedup_key = self._deduplicate_key(record)
        existing = self._find_by_dedup_key(dedup_key)
        
        if existing:
            logger.info(f"Duplicate experience found, updating existing record: {existing.id}")
            # Update reuse count and timestamp
            existing.reuse_count += 1
            existing.last_reused = datetime.now().isoformat()
            self._save()
            return existing
        
        # Add new record
        record.id = self._generate_id(f"{dedup_key}|{record.timestamp}")
        self._records.append(record)
        
        # Update index
        if task_category not in self._index:
            self._index[task_category] = []
        self._index[task_category].append(record.id)
        
        self._save()
        logger.info(f"Added new experience record: {record.id}")
        return record
    
    def _determine_type(self, success: bool) -> ExperienceType:
        """Determine experience type from success flag."""
        if success:
            return ExperienceType.SUCCESS
        return ExperienceType.FAILURE
    
    def _find_by_dedup_key(self, dedup_key: str) -> ExperienceRecord | None:
        """Find existing record by dedup key."""
        for record in self._records:
            if self._deduplicate_key(record) == dedup_key:
                return record
        return None
    
    def get_by_category(self, category: str) -> list[ExperienceRecord]:
        """Get all experiences in a category."""
        record_ids = self._index.get(category, [])
        return [r for r in self._records if r.id in record_ids]
    
    def get_similar_experiences(
        self,
        task_description: str,
        category: str | None = None,
        limit: int = 5,
    ) -> list[ExperienceRecord]:
        """
        Find similar experiences for current task.
        
        Uses simple keyword matching. For better similarity search,
        integrate with vector database.
        """
        candidates: list[tuple[ExperienceRecord, int]] = []
        
        # Extract keywords from task description
        keywords = set(task_description.lower().split())
        keywords = {k for k in keywords if len(k) > 3}  # Filter short words
        
        for record in self._records:
            # Category filter
            if category and record.task_category != category:
                continue
            
            # Keyword matching
            record_text = f"{record.task_description} {record.solution_approach}".lower()
            match_count = sum(1 for kw in keywords if kw in record_text)
            
            if match_count > 0:
                candidates.append((record, match_count))
        
        # Sort by match count and reuse count (prefer proven solutions)
        candidates.sort(key=lambda x: (x[1], x[0].reuse_count), reverse=True)
        
        return [r for r, _ in candidates[:limit]]
    
    def get_success_patterns(self, category: str | None = None) -> list[ExperienceRecord]:
        """Get successful patterns, optionally filtered by category."""
        records = [r for r in self._records if r.success]
        if category:
            records = [r for r in records if r.task_category == category]
        return sorted(records, key=lambda r: r.reuse_count, reverse=True)
    
    def get_failure_patterns(self, category: str | None = None) -> list[ExperienceRecord]:
        """Get failure patterns to avoid, optionally filtered by category."""
        records = [r for r in self._records if not r.success]
        if category:
            records = [r for r in records if r.task_category == category]
        return records
    
    def get_warnings_for_tools(self, tools: list[str]) -> list[tuple[ExperienceRecord, str]]:
        """Get warnings related to specific tools."""
        warnings = []
        for record in self._records:
            if not record.success:
                for tool in tools:
                    if tool in record.tools_used:
                        for warning in record.warnings:
                            warnings.append((record, warning))
        return warnings
    
    def mark_experience_reused(self, record_id: str) -> None:
        """Mark an experience as reused."""
        for record in self._records:
            if record.id == record_id:
                record.reuse_count += 1
                record.last_reused = datetime.now().isoformat()
                self._save()
                return
        logger.warning(f"Experience record not found: {record_id}")
    
    def search_by_tags(self, tags: list[str]) -> list[ExperienceRecord]:
        """Search experiences by tags."""
        results = []
        for record in self._records:
            if any(tag in record.tags for tag in tags):
                results.append(record)
        return results
    
    def get_statistics(self) -> dict[str, Any]:
        """Get repository statistics."""
        total = len(self._records)
        successes = sum(1 for r in self._records if r.success)
        failures = total - successes
        
        by_category: dict[str, int] = {}
        for record in self._records:
            by_category[record.task_category] = by_category.get(record.task_category, 0) + 1
        
        avg_confidence = sum(r.confidence_score for r in self._records) / total if total > 0 else 0
        
        return {
            "total_records": total,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / total if total > 0 else 0,
            "categories": by_category,
            "average_confidence": avg_confidence,
            "total_reuses": sum(r.reuse_count for r in self._records),
        }
    
    def generate_summary_report(self) -> str:
        """Generate a human-readable summary report."""
        stats = self.get_statistics()
        
        lines = [
            "# Experience Repository Summary",
            "",
            "## Overview",
            f"- Total Records: {stats['total_records']}",
            f"- Success Rate: {stats['success_rate']*100:.1f}%",
            f"- Average Confidence: {stats['average_confidence']:.2f}",
            f"- Total Reuses: {stats['total_reuses']}",
            "",
            "## Records by Category",
        ]
        
        for category, count in sorted(stats["categories"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {category}: {count}")
        
        # Add top reused experiences
        top_reused = sorted(self._records, key=lambda r: r.reuse_count, reverse=True)[:5]
        if top_reused:
            lines.append("")
            lines.append("## Most Reused Experiences")
            for record in top_reused:
                lines.append(f"- ({record.reuse_count}x) [{record.task_category}] {record.task_description[:50]}...")
        
        # Add recent failures
        recent_failures = [r for r in self._records if not r.success][-3:]
        if recent_failures:
            lines.append("")
            lines.append("## Recent Failures to Learn From")
            for record in recent_failures:
                lines.append(f"- [{record.task_category}] {record.task_description[:50]}...")
                for warning in record.warnings[:2]:
                    lines.append(f"  - ⚠️ {warning[:80]}")
        
        return "\n".join(lines)


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path
