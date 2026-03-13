
from typing import Any
from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.metrics import MetricsTracker

class GetMetricsTool(Tool):
    """Tool to retrieve agent performance metrics."""
    
    def __init__(self, tracker: MetricsTracker):
        self.tracker = tracker
    
    @property
    def name(self) -> str:
        return "get_agent_metrics"
    
    @property
    def description(self) -> str:
        return "Get a summary of the agent's performance metrics (tool usage, success rates, token consumption)."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        try:
            return self.tracker.get_summary()
        except Exception as e:
            return f"Error retrieving metrics: {e}"
