
from pathlib import Path
from typing import Any

from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.planner import Planner

class PlanTool(Tool):
    """
    Tool to generate an implementation plan.
    """
    def __init__(self, planner: Planner):
        self.planner = planner

    @property
    def name(self) -> str:
        return "create_implementation_plan"

    @property
    def description(self) -> str:
        return (
            "Analyze requirements and create a detailed IMPLEMENTATION_PLAN.md. "
            "Use this BEFORE writing code for complex tasks."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "requirements": {
                    "type": "string",
                    "description": "Detailed description of what needs to be implemented."
                }
            },
            "required": ["requirements"]
        }

    async def execute(self, requirements: str, **kwargs: Any) -> str:
        try:
            plan = await self.planner.create_plan(requirements)
            self.planner.parse_steps(plan)
            n = len(self.planner.steps)
            return (
                f"Plan created at {self.planner.plan_path} ({n} steps).\n"
                "Use update_plan_step to track progress as you implement."
            )
        except Exception as e:
            return f"Error creating plan: {str(e)}"


class UpdatePlanStepTool(Tool):
    """Tool to update plan step status."""

    def __init__(self, planner: Planner):
        self.planner = planner

    @property
    def name(self) -> str:
        return "update_plan_step"

    @property
    def description(self) -> str:
        return "Mark a plan step as in_progress or completed to track implementation progress."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "step_id": {
                    "type": "integer",
                    "description": "The step number to update.",
                },
                "status": {
                    "type": "string",
                    "enum": ["in_progress", "completed"],
                    "description": "New status for the step.",
                },
            },
            "required": ["step_id", "status"],
        }

    async def execute(self, step_id: int, status: str, **kwargs: Any) -> str:
        step = self.planner.update_step(step_id, status)
        if not step:
            return f"Error: Step {step_id} not found."
        return self.planner.get_progress_context()
