"""Multi-Agent Gateway Manager.

Manages multiple AgentLoop instances and routes messages to the appropriate agent.
"""

import asyncio
from typing import Dict, Optional

from loguru import logger

from cyberclaw.config.schema import Config, AgentConfig
from cyberclaw.bus.events import InboundMessage
from cyberclaw.bus.queue import MessageBus
from cyberclaw.agent.loop import AgentLoop
from cyberclaw.agent.a2a.router import A2ARouter
from cyberclaw.gateway.router import MessageRouter
from cyberclaw.gateway.http_server import GatewayHTTPServer


class MultiAgentGateway:
    """管理多个 AgentLoop 实例的生命周期和消息路由。

    功能：
    1. 根据配置启动多个 AgentLoop 实例
    2. 通过 MessageRouter 将消息路由到正确的 agent
    3. 提供健康检查接口
    4. 优雅关闭所有 agent 实例
    """

    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.agents: Dict[str, AgentLoop] = {}  # agent_id -> AgentLoop
        self._health_tasks: Dict[str, asyncio.Task] = {}
        self._running = False

        # 创建消息路由器
        self.router = MessageRouter(
            bindings=config.agents.bindings, default_agent=config.agents.default_agent
        )

        # 创建共享 A2A 路由器（所有 agent 共用）
        self.a2a_router = A2ARouter()

        logger.info(
            f"MultiAgentGateway initialized with {len(config.agents.agent_list)} agents, "
            f"default={config.agents.default_agent}"
        )
        
        # Record start time for uptime calculation
        self._start_time: float | None = None
        
        # HTTP Server
        self._http_server: GatewayHTTPServer | None = None

    async def start(self):
        """启动所有配置的 agent 实例。

        启动流程：
        1. 始终创建 default agent（即使没有在 agent_list 中配置）
        2. 为 agent_list 中每个 agent 创建实例
        3. 订阅 bus 消息并路由
        """
        if self._running:
            logger.warning("MultiAgentGateway already running")
            return

        self._running = True

        # 1. 始终创建 default agent
        default_agent_id = self.config.agents.default_agent
        default_config = self.config.agents.get_agent(default_agent_id)
        self._create_agent_loop(default_config)
        logger.info(f"Created default agent: {default_agent_id}")

        # 2. 为 agent_list 中每个 agent 创建实例
        for agent_config in self.config.agents.agent_list:
            if agent_config.id != default_agent_id:
                self._create_agent_loop(agent_config)
                logger.info(f"Created agent: {agent_config.id}")

        # 3. 启动所有 agent 的内部循环
        for agent_id, agent in self.agents.items():
            # AgentLoop 不需要显式 start，它通过 bus 订阅自动工作
            logger.info(f"Agent {agent_id} ready")

        # 4. 订阅 bus 消息
        self._message_task = asyncio.create_task(self._message_dispatcher())

        # 5. 启动 A2A mailbox 轮询（让每个 agent 能接收来自其他 agent 的请求）
        self._a2a_poll_tasks: dict[str, asyncio.Task] = {}
        for agent_id, agent in self.agents.items():
            task = asyncio.create_task(self._a2a_poll_loop(agent_id, agent))
            self._a2a_poll_tasks[agent_id] = task
        logger.info(f"Started A2A mailbox polling for {len(self._a2a_poll_tasks)} agents")
        
        # 记录启动时间
        self._start_time = asyncio.get_event_loop().time()
        
        # Start HTTP Server (default port 18791)
        self._http_server = GatewayHTTPServer(self, port=18791)
        await self._http_server.start()
        
        logger.info(
            f"MultiAgentGateway started with {len(self.agents)} agents: {list(self.agents.keys())}"
        )


    async def run_interactive_cli(self):
        """Run interactive CLI for testing message routing."""
        print("\n" + "="*70)
        print("Gateway started. Type messages to test routing.")
        print("Type 'quit' or 'exit' to exit.")
        print("="*70 + "\n")
        
        loop = asyncio.get_event_loop()
        
        while self._running:
            try:
                message = await loop.run_in_executor(None, input, ">> You: ")
                
                if message.lower() in ['quit', 'exit', 'q']:
                    print("Exiting interactive CLI.")
                    break
                
                if not message.strip():
                    continue
                
                # Create and publish message
                from cyberclaw.bus.events import InboundMessage
                from datetime import datetime
                
                msg = InboundMessage(
                    channel='cli',
                    chat_id='interactive',
                    content=message,
                    sender_id='user',
                    timestamp=datetime.now()
                )
                
                print("\n>> Sending to Gateway...\n")
                await self.bus.publish_inbound(msg)
                
            except (EOFError, KeyboardInterrupt):
                print("\nInterrupted.")
                break
            except Exception as e:
                logger.error(f"Interactive CLI error: {e}")

    async def stop(self):
        """优雅关闭所有 agent。"""
        if not self._running:
            return

        logger.info("Stopping MultiAgentGateway...")
        self._running = False

        # 停止消息分发任务
        # Stop HTTP Server
        if self._http_server:
            await self._http_server.stop()

        # Close A2A router
        await self.a2a_router.close()

        # Stop A2A poll tasks
        for task in getattr(self, '_a2a_poll_tasks', {}).values():
            task.cancel()
        for task in getattr(self, '_a2a_poll_tasks', {}).values():
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Stop message dispatcher
        if hasattr(self, "_message_task"):
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass

        # 健康检查任务取消
        for task in self._health_tasks.values():
            task.cancel()

        # AgentLoop 没有显式的 stop 方法，它们通过 bus 订阅工作
        # 当 bus 关闭时，agent 会自动停止

        self.agents.clear()
        self._health_tasks.clear()

        logger.info("MultiAgentGateway stopped")
    
    def get_status(self) -> dict:
        """获取 gateway 和所有 agent 的状态（含运行时详情）。"""
        uptime = 0
        if self._start_time and self._running:
            uptime = asyncio.get_event_loop().time() - self._start_time

        # 收集每个 agent 的运行时状态
        agent_details = {}
        for agent_id, agent in self.agents.items():
            if hasattr(agent, "get_runtime_status"):
                agent_details[agent_id] = agent.get_runtime_status()
            else:
                agent_details[agent_id] = {"agent_id": agent_id, "running": getattr(agent, "_running", False)}

        # A2A 路由器摘要
        a2a_registered = list(self.a2a_router._mailboxes.keys()) if self.a2a_router else []

        return {
            "status": "running" if self._running else "stopped",
            "uptime": uptime,
            "uptime_human": self._format_uptime(uptime) if uptime > 0 else "0s",
            "agent_count": len(self.agents),
            "agents": list(self.agents.keys()),
            "agent_details": agent_details,
            "default_agent": self.config.agents.default_agent,
            "routing_rules": len(self.router.bindings),
            "teams": len(self.config.agents.teams),
            "team_names": [t.name for t in self.config.agents.teams],
            "a2a_registered_agents": a2a_registered,
        }

    def _format_uptime(self, seconds: float) -> str:
        """格式化运行时间。"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    
    async def _message_dispatcher(self):
        """持续监听 bus 消息并路由到正确的 agent。"""
        from cyberclaw.bus.events import InboundMessage
        
        # 持续消费 inbound 消息
        while self._running:
            try:
                msg = await self.bus.consume_inbound()
                if not self._running:
                    break
                
                await self._handle_message(msg)
            except Exception as e:
                logger.error(f"Error routing message: {e}", exc_info=True)

    async def _handle_message(self, msg: InboundMessage):
        """路由消息到目标 agent。"""
        # 使用路由器确定目标 agent
        agent_id = self.router.route(msg)

        # 获取目标 agent 实例
        agent = self.agents.get(agent_id)
        if not agent:
            # 如果指定的 agent 不存在，fallback 到 default
            logger.warning(f"Agent {agent_id} not found, falling back to default")
            agent = self.agents.get(self.config.agents.default_agent)

        if not agent:
            logger.error("No agent available to handle message")
            return

        logger.info(f"\n📥 [{agent_id.upper()}] Routing message from {msg.channel}:{msg.chat_id}")
        logger.info(f"   Content: {msg.content[:80]}...\n")
        
        # 构建带 agent_id 前缀的 session_key
        session_key = f"{agent_id}:{msg.session_key}"
        
        try:
            # 使用 process_direct 处理消息
            response = await agent.process_direct(
                content=msg.content,
                session_key=session_key,
                channel=msg.channel,
                chat_id=msg.chat_id,
                media=msg.media if msg.media else None,
            )

            # process_direct 返回结果字符串但不发布到 bus outbound，
            # 需要手动发布以便 ChannelManager._dispatch_outbound 将回复送达 QQ 等渠道
            if response:
                from cyberclaw.bus.events import OutboundMessage
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=response,
                ))
        except Exception as e:
            logger.error(f"Error processing message in agent {agent_id}: {e}", exc_info=True)

    async def _a2a_poll_loop(self, agent_id: str, agent: AgentLoop) -> None:
        """Continuously poll A2A mailbox for an agent and process incoming requests.

        This is essential in gateway mode where agents don't run their own event loop.
        When another agent sends an A2A request, this loop picks it up, lets the target
        agent process it, and sends the response back via the router.
        """
        logger.debug(f"A2A poll loop started for agent {agent_id}")
        while self._running:
            try:
                await agent._poll_a2a_mailbox()
                await asyncio.sleep(0.1)  # Avoid busy loop
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"A2A poll error for {agent_id}: {e}")
                await asyncio.sleep(1)
        logger.debug(f"A2A poll loop stopped for agent {agent_id}")

    def _create_agent_loop(self, agent_config: AgentConfig) -> AgentLoop:
        """根据 AgentConfig 创建 AgentLoop 实例。
        
        从 agent_config 提取参数，覆盖 defaults。
        """
        from cyberclaw.providers.litellm_provider import LiteLLMProvider
        from cyberclaw.providers.registry import find_by_name
        
        # 确定使用的 model 和 provider
        model = agent_config.model or self.config.agents.defaults.model
        provider_name = self.config.get_provider_name(model)
        provider_config = self.config.get_provider(model)
        
        # 创建 provider
        spec = find_by_name(provider_name) if provider_name else None
        if spec and spec.is_direct:
            from cyberclaw.providers.custom_provider import CustomProvider
            provider = CustomProvider(
                api_key=provider_config.api_key if provider_config else None,
                api_base=self.config.get_api_base(model),
                default_model=model,
            )
        else:
            provider = LiteLLMProvider(
                api_key=provider_config.api_key if provider_config else None,
                api_base=self.config.get_api_base(model),
                default_model=model,
                extra_headers=provider_config.extra_headers if provider_config else None,
                provider_name=provider_name,
            )
        
        # 获取 workspace 路径
        workspace = agent_config.get_workspace_path()
        
        # 创建 AgentLoop
        agent = AgentLoop(
            bus=self.bus,
            provider=provider,
            workspace=workspace,
            agent_id=agent_config.id,
            model=model,
            max_iterations=agent_config.max_tool_iterations,
            max_tokens=agent_config.max_tokens,
            temperature=agent_config.temperature,
            frequency_penalty=agent_config.frequency_penalty,
            context_window=agent_config.context_window,
            exec_config=self.config.tools.exec,
            restrict_to_workspace=self.config.tools.restrict_to_workspace,
            session_manager=None,  # TODO: 可能需要为每个 agent 创建独立的 session manager
            sandbox=agent_config.sandbox,
            permission_mode=agent_config.permission_mode,
            thinking_budget=agent_config.thinking_budget,
            memory_search_config=self.config.memory_search.model_dump() if self.config.memory_search else None,
            agents_config=self.config.agents,  # Pass agents config for Broadcast tool
        )
        
        self.agents[agent_config.id] = agent

        # 注入共享 A2A 路由器并注册 agent 的 mailbox
        agent.a2a_router = self.a2a_router
        self.a2a_router.register_agent(agent_config.id, agent)

        return agent

    async def health_check(self) -> dict[str, str]:
        """返回各 agent 健康状态。

        Returns:
            dict: {agent_id: "healthy"|"unknown"}
        """
        status = {}
        for agent_id in self.agents.keys():
            # 目前 AgentLoop 没有健康检查接口，简单返回"healthy"
            # TODO: 实现更详细的健康检查
            status[agent_id] = "healthy"
        return status

    def get_agent_ids(self) -> list[str]:
        """返回所有已注册的 agent IDs."""
        return list(self.agents.keys())

    def get_agent(self, agent_id: str) -> Optional[AgentLoop]:
        """获取指定 agent 实例。"""
        return self.agents.get(agent_id)

    def get_router_info(self) -> dict:
        """返回路由器配置信息（用于调试）。"""
        return self.router.get_routing_info()
