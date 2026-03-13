
import json
from pathlib import Path
from typing import Any, Dict

from loguru import logger

class ContextManager:
    """
    Manages the 'World Model' of the project.
    Persists high-level architectural decisions and state to .cyberclaw/state.json
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.state_dir = workspace / ".cyberclaw"
        self.state_file = self.state_dir / "state.json"
        self._state: Dict[str, Any] = {
            "project_type": "unknown",
            "architecture": "unknown",
            "conventions": [],
            "features": {},  # status of major features
            "tech_stack": []
        }
        self._load()

    def _load(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                content = self.state_file.read_text(encoding="utf-8")
                loaded = json.loads(content)
                self._state.update(loaded)
            except Exception as e:
                logger.warning(f"Failed to load context state: {e}")

    def save(self):
        """Save state to file."""
        try:
            if not self.state_dir.exists():
                self.state_dir.mkdir(parents=True, exist_ok=True)
            
            self.state_file.write_text(
                json.dumps(self._state, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save context state: {e}")

    def update(self, key: str, value: Any):
        """Update a specific state key."""
        self._state[key] = value
        self.save()

    def get_context_prompt(self) -> str:
        """
        Returns a formatted markdown string for the system prompt.
        """
        lines = ["# Project Context (World Model)"]
        
        if self._state["project_type"] != "unknown":
            lines.append(f"- **Type**: {self._state['project_type']}")
            
        if self._state["architecture"] != "unknown":
            lines.append(f"- **Architecture**: {self._state['architecture']}")
            
        if self._state["tech_stack"]:
            lines.append(f"- **Tech Stack**: {', '.join(self._state['tech_stack'])}")
            
        if self._state["conventions"]:
            lines.append("- **Conventions**:")
            for c in self._state["conventions"]:
                lines.append(f"  - {c}")
                
        # If very little info, return empty to save tokens?
        # Or return a prompt to encourage filling it?
        if len(lines) == 1:
             return ""
             
        return "\n".join(lines)
