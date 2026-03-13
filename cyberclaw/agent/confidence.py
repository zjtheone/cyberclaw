"""
Self-Improving Agent: Confidence Injection (P1)

Evaluates answer confidence before responding to avoid low-quality outputs.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from cyberclaw.providers.base import LLMProvider


@dataclass
class ConfidenceResult:
    """Confidence evaluation result."""
    score: float  # 0.0 - 1.0
    level: str  # "high" | "medium" | "low"
    factors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    should_verify: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "factors": self.factors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "should_verify": self.should_verify,
        }


class ConfidenceEvaluator:
    """
    Evaluates answer confidence before responding.
    
    Analyzes:
    - Answer characteristics (length, certainty language)
    - Historical similarity (similar questions answered well before)
    - Tool execution success rate
    - Knowledge domain confidence
    
    Outputs:
    - Confidence score (0.0 - 1.0)
    - Confidence level (high/medium/low)
    - Verification recommendations
    """
    
    # Certainty/uncertainty language patterns
    CERTAINTY_PATTERNS = {
        "high_confidence": [
            r"\b(definitely|certainly|absolutely|clearly|obviously)\b",
            r"\b(always|never|must|will|would)\b",
            r"\b(fact|truth|evidence|proven|confirmed)\b",
            r"\b(I'm sure|I'm certain|no doubt)\b",
        ],
        "low_confidence": [
            r"\b(maybe|perhaps|possibly|might|could|may)\b",
            r"\b(I think|I believe|I guess|I suppose)\b",
            r"\b(uncertain|unsure|unclear|ambiguous)\b",
            r"\b(probably|likely|seems|appears)\b",
            r"\b(not sure|don't know|can't say|hard to tell)\b",
            r"\b(approximately|roughly|around|about)\b",
        ],
    }
    
    # Knowledge domain confidence weights
    DOMAIN_CONFIDENCE = {
        "code": 0.85,  # High confidence for code tasks
        "file_operation": 0.90,  # Very high for file ops (verifiable)
        "math": 0.75,  # Medium-high for math
        "factual": 0.70,  # Medium for factual queries (may be outdated)
        "opinion": 0.60,  # Lower for opinions
        "creative": 0.80,  # High for creative tasks
        "debugging": 0.70,  # Medium for debugging (complex)
        "web_search": 0.65,  # Medium-low for web info (changes)
    }
    
    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider | None = None,
        model: str | None = None,
        threshold: float = 0.7,
        auto_verify: bool = True,
    ):
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.threshold = threshold
        self.auto_verify = auto_verify

        # 实例级别领域权重（可通过反馈自适应调整）
        self.domain_confidence = dict(self.DOMAIN_CONFIDENCE)

        # Confidence history for learning
        self.history_file = workspace / ".cyberclaw" / "confidence_history.jsonl"
        self._history: list[dict] = []
        self._load_history()
    
    def _load_history(self) -> None:
        """Load confidence history."""
        import json
        if not self.history_file.exists():
            return
        
        try:
            for line in self.history_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._history.append(json.loads(line))
            logger.info(f"Loaded {len(self._history)} confidence history records")
        except Exception as e:
            logger.error(f"Failed to load confidence history: {e}")
    
    def _save_record(self, record: dict) -> None:
        """Save confidence evaluation record."""
        import json
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to save confidence record: {e}")
    
    def evaluate(
        self,
        question: str,
        answer: str,
        context: Optional[dict] = None,
        tool_results: Optional[list[dict]] = None,
    ) -> ConfidenceResult:
        """
        Evaluate confidence in an answer.
        
        Args:
            question: The original question/task.
            answer: The generated answer.
            context: Optional context (task category, domain, etc.).
            tool_results: Optional tool execution results.
        
        Returns:
            ConfidenceResult with score and recommendations.
        """
        factors = []
        warnings = []
        suggestions = []
        
        # 1. Analyze answer characteristics
        answer_score, answer_factors = self._analyze_answer(answer)
        factors.extend(answer_factors)
        
        # 2. Check for uncertainty language
        uncertainty_score, uncertainty_factors = self._check_uncertainty(answer)
        factors.extend(uncertainty_factors)
        
        # 3. Analyze task domain
        domain = (context or {}).get("domain", "general")
        domain_score = self.domain_confidence.get(domain, 0.70)
        factors.append(f"Domain '{domain}' baseline: {domain_score:.2f}")
        
        # 4. Check tool execution success
        if tool_results:
            tool_score, tool_factors = self._analyze_tool_results(tool_results)
            factors.extend(tool_factors)
        else:
            tool_score = 0.80  # Default if no tools used
        
        # 5. Check historical similarity
        historical_score, history_factors = self._check_history(question, answer, domain)
        factors.extend(history_factors)
        
        # 6. Calculate weighted score
        weights = {
            "answer": 0.25,
            "uncertainty": 0.25,
            "domain": 0.15,
            "tool": 0.20,
            "history": 0.15,
        }
        
        raw_score = (
            weights["answer"] * answer_score +
            weights["uncertainty"] * uncertainty_score +
            weights["domain"] * domain_score +
            weights["tool"] * tool_score +
            weights["history"] * historical_score
        )
        
        # Apply adjustments
        final_score = self._apply_adjustments(raw_score, answer, warnings, suggestions)
        
        # Determine level
        if final_score >= 0.8:
            level = "high"
        elif final_score >= 0.5:
            level = "medium"
        else:
            level = "low"
        
        # Determine if verification needed
        should_verify = (
            (self.auto_verify and final_score < self.threshold) or
            level == "low" or
            len(warnings) > 0
        )
        
        result = ConfidenceResult(
            score=round(final_score, 3),
            level=level,
            factors=factors,
            warnings=warnings,
            suggestions=suggestions,
            should_verify=should_verify,
        )
        
        # Save to history
        self._save_record({
            "question": question[:200],
            "answer_preview": answer[:200],
            "domain": domain,
            "result": result.to_dict(),
        })
        
        return result

    def record_outcome(
        self,
        question: str,
        predicted_score: float,
        actual_success: bool,
        domain: str = "general",
    ) -> None:
        """记录置信度预测 vs 实际结果，用于校准领域权重。"""
        import json
        outcome_record = {
            "type": "outcome",
            "question": question[:200],
            "predicted_score": predicted_score,
            "actual_success": actual_success,
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
        }
        self._save_record(outcome_record)
        self._history.append(outcome_record)
        self._adjust_domain_weight(domain, predicted_score, actual_success)

    def _adjust_domain_weight(
        self,
        domain: str,
        predicted_score: float,
        actual_success: bool,
        learning_rate: float = 0.05,
    ) -> None:
        """根据预测准确度微调领域权重。"""
        if domain not in self.domain_confidence:
            return

        current_weight = self.domain_confidence[domain]
        actual_score = 1.0 if actual_success else 0.0
        error = actual_score - predicted_score

        # 简单在线学习：预测偏低且实际成功则提高权重，反之降低
        adjustment = learning_rate * error
        new_weight = max(0.1, min(0.99, current_weight + adjustment))
        self.domain_confidence[domain] = round(new_weight, 3)
        logger.debug(f"Domain '{domain}' weight adjusted: {current_weight:.3f} -> {new_weight:.3f}")

    def _analyze_answer(self, answer: str) -> tuple[float, list[str]]:
        """Analyze answer characteristics."""
        factors = []
        score = 0.70  # Base score
        
        # Length analysis
        word_count = len(answer.split())
        if word_count < 20:
            score -= 0.15
            factors.append(f"Very short answer ({word_count} words) may be incomplete")
        elif word_count > 1000:
            score -= 0.05
            factors.append(f"Very long answer ({word_count} words) may have focus issues")
        elif 50 <= word_count <= 500:
            score += 0.10
            factors.append(f"Good answer length ({word_count} words)")
        else:
            factors.append(f"Answer length: {word_count} words")
        
        # Structure analysis
        has_structure = any([
            "##" in answer or "###" in answer,  # Markdown headers
            "- " in answer or "* " in answer,  # Bullet points
            "1." in answer or "2." in answer,  # Numbered lists
            "```" in answer,  # Code blocks
        ])
        if has_structure:
            score += 0.10
            factors.append("Well-structured answer")
        
        # Code presence (for technical tasks)
        if "```" in answer:
            score += 0.05
            factors.append("Includes code examples")
        
        return min(1.0, max(0.0, score)), factors
    
    def _check_uncertainty(self, answer: str) -> tuple[float, list[str]]:
        """Check for uncertainty language."""
        factors = []
        score = 0.80  # Base score
        
        answer_lower = answer.lower()
        
        # Count certainty patterns
        certainty_count = 0
        for pattern in self.CERTAINTY_PATTERNS["high_confidence"]:
            matches = re.findall(pattern, answer_lower)
            certainty_count += len(matches)
        
        # Count uncertainty patterns
        uncertainty_count = 0
        uncertainty_matches = []
        for pattern in self.CERTAINTY_PATTERNS["low_confidence"]:
            matches = re.findall(pattern, answer_lower)
            uncertainty_count += len(matches)
            if matches:
                uncertainty_matches.extend(matches)
        
        if uncertainty_count > 3:
            score -= 0.25
            factors.append(f"High uncertainty language ({uncertainty_count} instances)")
            if uncertainty_matches:
                factors.append(f"Examples: {', '.join(uncertainty_matches[:3])}")
        elif uncertainty_count > 0:
            score -= 0.10
            factors.append(f"Some uncertainty language ({uncertainty_count} instances)")
        
        if certainty_count > 0 and uncertainty_count == 0:
            score += 0.10
            factors.append(f"Confident language used ({certainty_count} instances)")
        
        return min(1.0, max(0.0, score)), factors
    
    def _analyze_tool_results(self, tool_results: list[dict]) -> tuple[float, list[str]]:
        """Analyze tool execution results."""
        factors = []
        
        if not tool_results:
            return 0.80, ["No tool results to analyze"]
        
        total = len(tool_results)
        successful = sum(1 for r in tool_results if r.get("success", False))
        success_rate = successful / total if total > 0 else 0
        
        if success_rate == 1.0:
            score = 0.95
            factors.append(f"All {total} tool calls succeeded")
        elif success_rate >= 0.8:
            score = 0.80
            factors.append(f"Most tool calls succeeded ({successful}/{total})")
        elif success_rate >= 0.5:
            score = 0.60
            factors.append(f"Mixed tool results ({successful}/{total} succeeded)")
        else:
            score = 0.40
            factors.append(f"Low tool success rate ({successful}/{total})")
        
        return score, factors
    
    def _check_history(
        self,
        question: str,
        answer: str,
        domain: str,
    ) -> tuple[float, list[str]]:
        """Check historical performance on similar tasks."""
        factors = []
        
        if not self._history:
            return 0.70, ["No historical data available"]
        
        # Simple similarity check (last 20 records)
        recent = self._history[-20:]
        similar_count = 0
        successful_count = 0
        
        for record in recent:
            # Check domain match
            if record.get("domain") == domain:
                similar_count += 1
                result = record.get("result", {})
                if result.get("score", 0) >= 0.7:
                    successful_count += 1
        
        if similar_count == 0:
            return 0.70, ["No similar tasks in history"]
        
        similarity_ratio = similar_count / len(recent)
        success_ratio = successful_count / similar_count if similar_count > 0 else 0
        
        if success_ratio >= 0.8 and similarity_ratio >= 0.3:
            score = 0.90
            factors.append(f"Strong history in {domain} tasks ({success_ratio*100:.0f}% success)")
        elif success_ratio >= 0.6:
            score = 0.75
            factors.append(f"Moderate history in {domain} tasks")
        else:
            score = 0.60
            factors.append(f"Weak history in {domain} tasks ({success_ratio*100:.0f}% success)")
        
        return score, factors
    
    def _apply_adjustments(
        self,
        raw_score: float,
        answer: str,
        warnings: list[str],
        suggestions: list[str],
    ) -> float:
        """Apply adjustments based on specific conditions."""
        score = raw_score
        
        # Critical warnings
        if "I don't know" in answer.lower() or "I cannot" in answer.lower():
            score -= 0.30
            warnings.append("Answer indicates inability to complete task")
        
        if "error" in answer.lower() and "failed" in answer.lower():
            score -= 0.25
            warnings.append("Answer mentions errors or failures")
        
        if "not enough information" in answer.lower():
            score -= 0.20
            warnings.append("Insufficient information acknowledged")
        
        # Positive adjustments
        if "verified" in answer.lower() or "confirmed" in answer.lower():
            score += 0.05
            suggestions.append("Answer mentions verification")
        
        if any(x in answer.lower() for x in ["test", "verify", "check"]):
            score += 0.05
            suggestions.append("Answer includes verification steps")
        
        # Safety suggestions
        if score < 0.5:
            suggestions.append("Consider verifying this answer before acting on it")
        elif score < 0.7:
            suggestions.append("Review key assumptions in this answer")
        
        return min(1.0, max(0.0, score))
    
    def should_verify(self, result: ConfidenceResult) -> bool:
        """Determine if answer should be verified."""
        return result.should_verify
    
    def generate_verification_prompt(self, result: ConfidenceResult) -> str:
        """Generate a verification prompt for low-confidence answers."""
        if result.level == "high":
            return ""
        
        parts = [f"⚠️ **Confidence: {result.level.upper()}** (Score: {result.score:.2f})"]
        
        if result.warnings:
            parts.append("\n**Warnings:**")
            for warning in result.warnings:
                parts.append(f"- {warning}")
        
        if result.suggestions:
            parts.append("\n**Suggestions:**")
            for suggestion in result.suggestions:
                parts.append(f"- {suggestion}")
        
        if result.level == "low":
            parts.append("\n❓ **Would you like me to verify this answer or try a different approach?**")
        elif result.level == "medium":
            parts.append("\n💡 **You may want to verify key details.**")
        
        return "\n".join(parts)
    
    def get_confidence_factors(self) -> dict[str, Any]:
        """Get current confidence configuration."""
        return {
            "threshold": self.threshold,
            "auto_verify": self.auto_verify,
            "domain_weights": self.DOMAIN_CONFIDENCE,
            "history_records": len(self._history),
        }
