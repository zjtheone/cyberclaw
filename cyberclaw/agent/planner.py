
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable

from loguru import logger
from cyberclaw.providers.base import LLMProvider
from cyberclaw.agent.context import ContextBuilder


@dataclass
class PlanStep:
    id: int
    title: str
    status: str = "pending"  # pending | in_progress | completed


class Planner:
    """
    The Planner Agent.
    Responsible for analyzing requirements and generating a detailed implementation plan
    BEFORE any code execution starts.
    """

    def __init__(self, provider: LLMProvider, context_builder: ContextBuilder, workspace: Path):
        self.provider = provider
        self.context = context_builder
        self.workspace = workspace
        self.plan_path = workspace / "implementation_plan.md"
        self._current_plan: str | None = None
        self.steps: list[PlanStep] = []
        self._steps_path = workspace / "implementation_plan_progress.json"
        self._on_plan_progress: Callable[[list[PlanStep]], None] | None = None
        self._load_steps()

    async def create_plan(self, user_request: str) -> str:
        """
        Generates an implementation plan for the given request.
        """
        logger.info("Planner: Analyzing request and generating plan...")

        system_prompt = self.context.build_system_prompt()

        planning_instructions = """
# PLANNING MODE

You are the Lead Architect. Your goal is NOT to write code, but to PLAN the implementation.
Analyze the user's request and the current codebase structure (RepoMap).

Output a detailed `implementation_plan.md` in markdown.
The plan MUST follow this structure:

# Implementation Plan - [Feature Name]

## Problem Analysis
Briefly explain the problem and why changes are needed.

## Proposed Changes
List the files to be modified/created. Group by component.

### [Component Name]
#### [MODIFY] path/to/file
- Description of changes...
#### [NEW] path/to/new_file
- Purpose of file...

## Verification Plan
How will we verify this works?
- Automated Tests: ...
- Manual Steps: ...

## Risks / Assumptions
Any potential issues?

---
Respond ONLY with the markdown content of the plan.
"""

        messages = [
            {"role": "system", "content": system_prompt + "\n\n" + planning_instructions},
            {"role": "user", "content": f"User Request: {user_request}"}
        ]

        response = await self.provider.chat(
            messages=messages,
            tools=[],
            model=None,
            temperature=0.7
        )

        plan_content = response.content
        self._current_plan = plan_content
        self._save_plan(plan_content)

        return plan_content

    def get_current_plan(self) -> str | None:
        """Get the current plan content (for injection into agent context)."""
        if self._current_plan:
            return self._current_plan
        # Try loading from disk
        if self.plan_path.exists():
            try:
                self._current_plan = self.plan_path.read_text(encoding="utf-8")
                return self._current_plan
            except Exception:
                pass
        return None

    def get_plan_context(self) -> str:
        """Get plan as a context string for injection into the agent's system prompt."""
        plan = self.get_current_plan()
        if not plan:
            return ""
        return f"# Active Implementation Plan\n\n{plan}\n\nFollow this plan step by step. Mark completed steps as you go."

    def _save_plan(self, content: str):
        """Save the plan to the workspace."""
        try:
            self.plan_path.write_text(content, encoding="utf-8")
            logger.info(f"Plan saved to {self.plan_path}")
        except Exception as e:
            logger.error(f"Failed to save plan: {e}")

    def parse_steps(self, plan_content: str) -> list[PlanStep]:
        """Parse #### lines from plan into trackable steps."""
        self.steps = []
        step_id = 0
        for line in plan_content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#### "):
                step_id += 1
                self.steps.append(PlanStep(id=step_id, title=stripped[5:].strip()))
        self._save_steps()
        if self._on_plan_progress:
            self._on_plan_progress(self.steps)
        return self.steps

    def update_step(self, step_id: int, status: str) -> PlanStep | None:
        """Update a step's status and notify callback."""
        for step in self.steps:
            if step.id == step_id:
                step.status = status
                self._save_steps()
                if self._on_plan_progress:
                    self._on_plan_progress(self.steps)
                return step
        return None

    def get_progress_context(self) -> str:
        """Format steps as context for LLM injection."""
        if not self.steps:
            return ""
        icons = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}
        lines = ["# Plan Progress"]
        for s in self.steps:
            lines.append(f"{icons[s.status]} {s.id}. {s.title}")
        lines.append("\nUse update_plan_step to mark steps in_progress/completed as you work.")
        return "\n".join(lines)

    def _save_steps(self) -> None:
        try:
            self._steps_path.write_text(
                json.dumps([asdict(s) for s in self.steps], indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save plan steps: {e}")

    def _load_steps(self) -> None:
        if self._steps_path.exists():
            try:
                data = json.loads(self._steps_path.read_text(encoding="utf-8"))
                self.steps = [PlanStep(**s) for s in data]
            except Exception:
                pass
