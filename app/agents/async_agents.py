"""Async pipeline agents wrapping the synchronous agent logic in event-driven handlers.

Pipeline:
  ticket:new → AsyncRouterAgent → ticket:classified
  ticket:classified → AsyncContextAgent → ticket:context_ready
  ticket:context_ready → AsyncResolverAgent → ticket:resolved
  ticket:resolved → AsyncQualityAgent → ticket:completed
  ticket:completed → PersistenceAgent → ticket:persisted
"""
import asyncio
import logging
from app.agents.async_base import AsyncBaseAgent
from app.agents.router_agent import RouterAgent
from app.agents.context_agent import ContextAgent
from app.agents.resolver_agent import ResolverAgent
from app.agents.quality_agent import QualityAgent

logger = logging.getLogger(__name__)


class AsyncRouterAgent(AsyncBaseAgent):
    """Async wrapper around RouterAgent.

    Input:  ticket:new     {"ticket_id": N, "description": "..."}
    Output: ticket:classified  state dict with category, priority
    """

    def __init__(self):
        super().__init__(
            input_stream="ticket:new",
            output_stream="ticket:classified",
        )
        self._agent = RouterAgent()

    async def process_message(self, message: dict) -> dict:
        state = dict(message)
        loop = asyncio.get_running_loop()
        state = await loop.run_in_executor(None, self._agent.run, state)
        return state


class AsyncContextAgent(AsyncBaseAgent):
    """Async wrapper around ContextAgent."""

    def __init__(self):
        super().__init__(
            input_stream="ticket:classified",
            output_stream="ticket:context_ready",
        )
        self._agent = ContextAgent()

    async def process_message(self, message: dict) -> dict:
        state = dict(message)
        if state.get("requires_rag", True):
            loop = asyncio.get_running_loop()
            state = await loop.run_in_executor(None, self._agent.run, state)
        else:
            state["context_docs"] = []
        return state


class AsyncResolverAgent(AsyncBaseAgent):
    """Async wrapper around ResolverAgent."""

    def __init__(self):
        super().__init__(
            input_stream="ticket:context_ready",
            output_stream="ticket:resolved",
        )
        self._agent = ResolverAgent()

    async def process_message(self, message: dict) -> dict:
        state = dict(message)
        loop = asyncio.get_running_loop()
        state = await loop.run_in_executor(None, self._agent.run, state)
        return state


class AsyncQualityAgent(AsyncBaseAgent):
    """Async wrapper around QualityAgent."""

    def __init__(self):
        super().__init__(
            input_stream="ticket:resolved",
            output_stream="ticket:completed",
        )
        self._agent = QualityAgent()

    async def process_message(self, message: dict) -> dict:
        state = dict(message)
        loop = asyncio.get_running_loop()
        state = await loop.run_in_executor(None, self._agent.run, state)

        # Determine final status
        qc = state.get("quality_check", {})
        state["status"] = "resolved" if qc.get("passed") else "escalated"
        state["escalation_info"] = {
            "reason": qc.get("reason", "Quality check completed"),
            "confidence": qc.get("confidence", 0.0),
            "citation_score": qc.get("citation_score", 0.0),
            "hallucination_warnings": qc.get("hallucination_warnings", []),
            "critical_issues": qc.get("critical_issues", False),
            "category": state.get("category"),
            "priority": state.get("priority"),
            "agent_notes": f"Auto-resolved by QualityAgent" if qc.get("passed") else f"Escalated by QualityAgent: {qc.get('reason', '')}",
        }
        return state
