"""HTTP Server for Multi-Agent Gateway.

Provides REST API for sending messages to the gateway.
"""

import asyncio
import uuid
from typing import Dict, Optional
from loguru import logger

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not installed, HTTP server disabled")


class GatewayHTTPServer:
    """HTTP server for Multi-Agent Gateway.

    Endpoints:
    - POST /chat - Send a message to the gateway
    - GET /status - Get gateway status
    """

    def __init__(self, gateway, host: str = "127.0.0.1", port: int = 18791):
        self.gateway = gateway
        self.host = host
        self.port = port
        self.pending_responses: Dict[str, asyncio.Future] = {}
        self.app = web.Application() if AIOHTTP_AVAILABLE else None

        if self.app:
            self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_post("/chat", self.handle_chat)
        self.app.router.add_get("/status", self.handle_status)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/agents", self.handle_agents)
        self.app.router.add_get("/agents/{agent_id}", self.handle_agent_detail)
        self.app.router.add_get("/media/{filename}", self.handle_media)

    async def handle_chat(self, request: web.Request) -> web.Response:
        """Handle chat message requests.

        Request body:
        {
            "content": "message content",
            "chat_id": "optional chat id",
            "channel": "optional channel",
            "sender_id": "optional sender id"
        }

        Response:
        {
            "content": "agent response",
            "session_key": "session identifier"
        }
        """
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"error": f"Invalid JSON: {str(e)}"}, status=400)

        content = data.get("content", "").strip()
        if not content:
            return web.json_response({"error": "content is required"}, status=400)

        # Create inbound message
        from cyberclaw.bus.events import InboundMessage
        from datetime import datetime

        chat_id = data.get("chat_id", "default")
        channel = data.get("channel", "http")
        sender_id = data.get("sender_id", "user")

        msg = InboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            sender_id=sender_id,
            timestamp=datetime.now(),
        )

        # Create response future
        response_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.Future()
        self.pending_responses[response_id] = future

        logger.debug(f"HTTP chat request: {content[:50]}... (id: {response_id})")

        # Publish message to bus
        await self.gateway.bus.publish_inbound(msg)

        # Wait for response with timeout
        timeout = data.get("timeout", 300)  # 5 minutes default
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return web.json_response(
                {"content": response, "session_key": msg.session_key, "response_id": response_id}
            )
        except asyncio.TimeoutError:
            # Clean up
            self.pending_responses.pop(response_id, None)
            return web.json_response({"error": f"Timeout after {timeout}s"}, status=504)

    async def handle_status(self, request: web.Request) -> web.Response:
        """Handle status requests."""
        status = self.gateway.get_status()
        return web.json_response(status)

    async def handle_health(self, request: web.Request) -> web.Response:
        """Handle health check requests."""
        return web.json_response({"status": "healthy", "gateway_running": self.gateway._running})

    async def handle_agents(self, request: web.Request) -> web.Response:
        """Handle agents list with runtime status."""
        status = self.gateway.get_status()
        return web.json_response({
            "agent_count": status["agent_count"],
            "agents": status.get("agent_details", {}),
            "a2a_registered": status.get("a2a_registered_agents", []),
        })

    async def handle_agent_detail(self, request: web.Request) -> web.Response:
        """Handle single agent detail."""
        agent_id = request.match_info["agent_id"]
        agent = self.gateway.get_agent(agent_id)
        if not agent:
            return web.json_response({"error": f"Agent '{agent_id}' not found"}, status=404)
        if hasattr(agent, "get_runtime_status"):
            return web.json_response(agent.get_runtime_status())
        return web.json_response({"agent_id": agent_id, "running": getattr(agent, "_running", False)})

    async def handle_media(self, request: web.Request) -> web.Response:
        """Serve temporary media files (e.g. voice silk files for QQ upload)."""
        from cyberclaw.config.paths import get_media_dir

        filename = request.match_info["filename"]
        # Prevent path traversal
        if "/" in filename or "\\" in filename or ".." in filename:
            return web.json_response({"error": "invalid filename"}, status=400)

        media_dir = get_media_dir("qq")
        file_path = media_dir / filename

        if not file_path.exists():
            return web.json_response({"error": "not found"}, status=404)

        # Determine content type
        suffix = file_path.suffix.lower()
        content_types = {
            ".silk": "audio/silk",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".amr": "audio/amr",
        }
        content_type = content_types.get(suffix, "application/octet-stream")

        return web.FileResponse(file_path, headers={"Content-Type": content_type})

    async def start(self):
        """Start HTTP server."""
        if not AIOHTTP_AVAILABLE:
            logger.error("Cannot start HTTP server: aiohttp not installed")
            logger.error("Install with: pip install aiohttp")
            return

        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        logger.info(f"HTTP Server started at http://{self.host}:{self.port}")
        logger.info(f"Endpoints:")
        logger.info(f"  POST /chat             - Send message to gateway")
        logger.info(f"  GET  /status           - Get gateway status")
        logger.info(f"  GET  /health           - Health check")
        logger.info(f"  GET  /agents           - All agents runtime status")
        logger.info(f"  GET  /agents/{{agent_id}} - Single agent detail")
        logger.info(f"  GET  /media/{{filename}}  - Serve media files (voice etc.)")

    async def stop(self):
        """Stop HTTP server."""
        if not AIOHTTP_AVAILABLE:
            return

        # Cancel pending responses
        for future in self.pending_responses.values():
            if not future.done():
                future.cancel()

        self.pending_responses.clear()
        logger.info("HTTP Server stopped")

    async def set_response(self, session_key: str, response: str):
        """Set response for a pending request.

        This is called when the agent completes processing.
        """
        # Find matching pending response by session_key
        # For now, we'll use a simple approach - match by chat_id
        for response_id, future in list(self.pending_responses.items()):
            if not future.done():
                future.set_result(response)
                self.pending_responses.pop(response_id)
                logger.debug(f"Response sent for {response_id}")
                return

        logger.debug(f"No pending response found for session {session_key}")
