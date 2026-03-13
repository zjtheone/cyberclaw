"""Bridge between Web Console and cyberclaw AgentLoop."""

import sys
import asyncio
import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class AgentResponse:
    """Response from cyberclaw agent."""

    content: str
    role: str = "assistant"
    thinking: Optional[str] = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentBridge:
    """Bridge to communicate with cyberclaw agent."""

    def __init__(self, workspace: Optional[Path] = None):
        """Initialize the agent bridge."""
        self.workspace = workspace or Path.home() / ".cyberclaw" / "workspace"
        self.agent_loop = None
        self._initialized = False
        self._error = None

        # Add cyberclaw to path
        cyberclaw_path = Path(__file__).parent.parent
        if str(cyberclaw_path) not in sys.path:
            sys.path.insert(0, str(cyberclaw_path))

    def initialize(self) -> bool:
        """Initialize the cyberclaw agent loop."""
        try:
            from cyberclaw.agent.loop import AgentLoop
            from cyberclaw.bus.queue import MessageBus
            from cyberclaw.providers.litellm_provider import LiteLLMProvider
            
            # Load cyberclaw config
            config_path = Path.home() / ".cyberclaw" / "config.json"
            with open(config_path) as f:
                config_data = json.load(f)
            
            # Create required components
            bus = MessageBus()
            
            # Get provider info
            provider_name = None
            for pname in ['dashscope', 'deepseek', 'openai', 'gemini']:
                if pname in config_data.get('providers', {}):
                    pconfig = config_data['providers'][pname]
                    if pconfig.get('api_key'):
                        provider_name = pname
                        break
            
            if not provider_name:
                print("✗ No provider configured with API key")
                return False
            
            # Create provider
            provider_config = config_data['providers'][provider_name]
            provider = LiteLLMProvider(
                provider_name=provider_name,
                api_key=provider_config.get('api_key', ''),
                api_base=provider_config.get('api_base'),
            )
            
            # Get agent config
            agent_config = config_data.get('agents', {}).get('defaults', {})
            
            # Create agent loop with minimal required parameters
            self.agent_loop = AgentLoop(
                bus=bus,
                provider=provider,
                workspace=self.workspace,
                model=agent_config.get('model', 'qwen3.5-plus'),
                max_iterations=agent_config.get('max_tool_iterations', 20),
                max_tokens=agent_config.get('max_tokens', 8192),
                temperature=agent_config.get('temperature', 0.7),
                frequency_penalty=agent_config.get('frequency_penalty', 0.0),
                thinking_budget=agent_config.get('thinking_budget', 1024),
            )
            
            self._initialized = True
            print(f"✓ AgentBridge initialized successfully")
            print(f"  • Provider: {provider_name}")
            print(f"  • Model: {agent_config.get('model')}")
            print(f"  • Workspace: {self.workspace}")
            
            return True

        except Exception as e:
            print(f"✗ Failed to initialize agent bridge: {e}")
            import traceback
            traceback.print_exc()
            self._error = str(e)
            return False

    async def send_message(self, message: str, session_id: Optional[str] = None) -> AgentResponse:
        """Send a message to the agent and get response."""
        if not self._initialized:
            if not self.initialize():
                return AgentResponse(
                    content=f"⚠️ Agent not initialized. Please check configuration.\n\nError: {self._error}",
                    role="assistant",
                )

        try:
            response_text = ""
            thinking_text = ""
            
            # Use process_direct_stream
            if hasattr(self.agent_loop, 'process_direct_stream'):
                async for chunk in self.agent_loop.process_direct_stream(message):
                    # process_direct_stream returns string chunks directly
                    if isinstance(chunk, str):
                        # Check if it's thinking content (usually in brackets or special format)
                        if chunk.strip().startswith('[') and 'thinking' in chunk.lower():
                            thinking_text += chunk
                        else:
                            response_text += chunk
                    elif isinstance(chunk, dict):
                        # Handle dict format if returned
                        if chunk.get('type') == 'content':
                            response_text += chunk.get('content', '')
                        elif chunk.get('type') == 'thinking':
                            thinking_text += chunk.get('content', '')
            
            return AgentResponse(
                content=response_text.strip() or "No response from agent",
                role="assistant",
                thinking=thinking_text.strip() if thinking_text else None,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return AgentResponse(
                content=f"Error processing message: {e}",
                role="assistant",
            )

    def get_status(self) -> dict:
        """Get agent status."""
        return {
            "initialized": self._initialized,
            "workspace": str(self.workspace),
            "error": self._error,
        }
