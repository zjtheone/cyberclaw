#!/usr/bin/env python3
"""Test script for A2A (Agent-to-Agent) communication."""

import asyncio
import sys
from pathlib import Path

# Add cyberclaw to path
sys.path.insert(0, str(Path(__file__).parent))

from cyberclaw.agent.a2a import (
    A2ARouter,
    AgentMessage,
    MessageType,
    MessagePriority,
)


class MockAgent:
    """Mock agent for testing."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.received_messages: list[AgentMessage] = []
    
    def __str__(self):
        return f"MockAgent({self.agent_id})"


async def test_basic_messaging():
    """Test basic A2A messaging."""
    print("\n" + "="*70)
    print("TEST 1: Basic A2A Messaging")
    print("="*70 + "\n")
    
    # Create router
    router = A2ARouter()
    
    # Create mock agents
    agent_a = MockAgent("agent-a")
    agent_b = MockAgent("agent-b")
    
    # Register agents
    router.register_agent(agent_a.agent_id, agent_a)
    router.register_agent(agent_b.agent_id, agent_b)
    
    print(f"✓ Registered agents: {agent_a.agent_id}, {agent_b.agent_id}")
    
    # Send notification
    await router.send_notification(
        from_agent=agent_a.agent_id,
        to_agent=agent_b.agent_id,
        content="Hello from Agent A!",
        priority=MessagePriority.NORMAL,
    )
    print("✓ Sent notification from agent-a to agent-b")
    
    # Receive message
    try:
        msg = await router.get_message(agent_b.agent_id, timeout=1.0)
        print(f"✓ Agent B received message: '{msg.content}'")
        assert msg.from_agent == "agent-a"
        assert msg.type == MessageType.NOTIFICATION
    except asyncio.TimeoutError:
        print("✗ Failed to receive message (timeout)")
        return False
    
    # Clean up
    await router.close()
    print("\n✅ TEST 1 PASSED: Basic messaging works!\n")
    return True


async def test_request_response():
    """Test request-response pattern."""
    print("\n" + "="*70)
    print("TEST 2: Request-Response Pattern")
    print("="*70 + "\n")
    
    # Create router
    router = A2ARouter()
    
    # Create mock agents
    requester = MockAgent("requester")
    responder = MockAgent("responder")
    
    # Register agents
    router.register_agent(requester.agent_id, requester)
    router.register_agent(responder.agent_id, responder)
    
    print(f"✓ Registered agents: {requester.agent_id}, {responder.agent_id}")
    
    # Send request in background
    async def send_request():
        try:
            response = await router.send_request(
                from_agent=requester.agent_id,
                to_agent=responder.agent_id,
                content="Please process this data",
                timeout=5.0,
            )
            return response
        except asyncio.TimeoutError:
            print("✗ Request timed out")
            return None
    
    request_task = asyncio.create_task(send_request())
    
    # Wait a bit for request to arrive
    await asyncio.sleep(0.5)
    
    # Responder receives request
    try:
        request = await router.get_message(responder.agent_id, timeout=1.0)
        print(f"✓ Responder received request: '{request.content}'")
        
        # Send response
        await router.send_response(
            from_agent=responder.agent_id,
            to_agent=requester.agent_id,
            request_id=request.message_id,
            content="Data processed successfully!",
        )
        print("✓ Responder sent response")
    except asyncio.TimeoutError:
        print("✗ Failed to receive request")
        return False
    
    # Wait for response
    response = await request_task
    if response:
        print(f"✓ Requester received response: '{response.content}'")
    else:
        print("✗ Failed to receive response")
        return False
    
    # Clean up
    await router.close()
    print("\n✅ TEST 2 PASSED: Request-response works!\n")
    return True


async def test_priority_queue():
    """Test priority-based message queuing."""
    print("\n" + "="*70)
    print("TEST 3: Priority Queue")
    print("="*70 + "\n")
    
    # Create router
    router = A2ARouter()
    
    # Create mock agents
    sender = MockAgent("sender")
    receiver = MockAgent("receiver")
    
    # Register agents
    router.register_agent(sender.agent_id, sender)
    router.register_agent(receiver.agent_id, receiver)
    
    print("✓ Registered agents")
    
    # Send messages with different priorities (in reverse order)
    await router.send_notification(
        from_agent=sender.agent_id,
        to_agent=receiver.agent_id,
        content="LOW priority message",
        priority=MessagePriority.LOW,
    )
    await router.send_notification(
        from_agent=sender.agent_id,
        to_agent=receiver.agent_id,
        content="URGENT priority message",
        priority=MessagePriority.URGENT,
    )
    await router.send_notification(
        from_agent=sender.agent_id,
        to_agent=receiver.agent_id,
        content="NORMAL priority message",
        priority=MessagePriority.NORMAL,
    )
    await router.send_notification(
        from_agent=sender.agent_id,
        to_agent=receiver.agent_id,
        content="HIGH priority message",
        priority=MessagePriority.HIGH,
    )
    
    print("✓ Sent 4 messages with different priorities")
    
    # Receive messages (should come in priority order)
    expected_order = ["URGENT", "HIGH", "NORMAL", "LOW"]
    received_order = []
    
    for _ in range(4):
        try:
            msg = await router.get_message(receiver.agent_id, timeout=1.0)
            received_order.append(msg.priority.name)
            print(f"  Received: {msg.priority.name} - '{msg.content}'")
        except asyncio.TimeoutError:
            break
    
    # Verify order
    if received_order == expected_order:
        print(f"\n✓ Messages received in correct priority order: {received_order}")
        result = True
    else:
        print(f"\n✗ Messages received in wrong order: {received_order}")
        print(f"  Expected: {expected_order}")
        result = False
    
    # Clean up
    await router.close()
    
    if result:
        print("\n✅ TEST 3 PASSED: Priority queue works!\n")
    else:
        print("\n❌ TEST 3 FAILED: Priority order incorrect\n")
    
    return result


async def test_broadcast():
    """Test broadcast messaging."""
    print("\n" + "="*70)
    print("TEST 4: Broadcast")
    print("="*70 + "\n")
    
    # Create router
    router = A2ARouter()
    
    # Create mock agents
    broadcaster = MockAgent("broadcaster")
    receiver1 = MockAgent("receiver-1")
    receiver2 = MockAgent("receiver-2")
    receiver3 = MockAgent("receiver-3")
    
    # Register agents
    router.register_agent(broadcaster.agent_id, broadcaster)
    router.register_agent(receiver1.agent_id, receiver1)
    router.register_agent(receiver2.agent_id, receiver2)
    router.register_agent(receiver3.agent_id, receiver3)
    
    print("✓ Registered 4 agents")
    
    # Broadcast message
    count = await router.broadcast(
        from_agent=broadcaster.agent_id,
        content="System maintenance in 5 minutes",
        priority=MessagePriority.URGENT,
    )
    
    print(f"✓ Broadcast sent to {count} agents")
    
    # Verify all receivers got the message
    for receiver in [receiver1, receiver2, receiver3]:
        try:
            msg = await router.get_message(receiver.agent_id, timeout=1.0)
            print(f"  ✓ {receiver.agent_id} received: '{msg.content}'")
        except asyncio.TimeoutError:
            print(f"  ✗ {receiver.agent_id} did not receive message")
            await router.close()
            print("\n❌ TEST 4 FAILED: Not all agents received broadcast\n")
            return False
    
    # Clean up
    await router.close()
    print("\n✅ TEST 4 PASSED: Broadcast works!\n")
    return True


async def main():
    """Run all A2A tests."""
    print("\n" + "="*70)
    print("A2A (Agent-to-Agent) Communication Tests")
    print("="*70)
    
    tests = [
        ("Basic Messaging", test_basic_messaging),
        ("Request-Response", test_request_response),
        ("Priority Queue", test_priority_queue),
        ("Broadcast", test_broadcast),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ TEST FAILED: {name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
