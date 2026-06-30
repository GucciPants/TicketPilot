"""Async pipeline agents wrapping the synchronous agent logic in event-driven handlers.

Pipeline:
  ticket:new → AsyncRouterAgent → ticket:classified
  ticket:classified → AsyncContextAgent → ticket:context_ready
  ticket:context_ready → AsyncResolverAgent → ticket:resolved
  ticket:resolved → AsyncQualityAgent → ticket:completed
  ticket:completed → PersistenceAgent → ticket:persisted
"""
import json
import logging
from app.agents.async_base import AsyncBaseAgent
from app.agents.router_agent import RouterAgent
from app.agents.context_agent import ContextAgent
from app.agents.resolver_agent import ResolverAgent
from app.agents.quality_agent import QualityAgent

logger = logging.getLogger(__name__)

# Shared sync agent instances (thread-safe: each async task creates its own)
# We instantiate per-process, not per-message, because agents are stateless.


class AsyncRouterAgent(AsyncBaseAgent):
    """Async wrapper around RouterAgent.

    Input:  ticket:new     {"ticket_id": N, "description": "..."}
    Output: ticket:classified  {"ticket_id": N, "description": "...", "category": "...", ...}
    """

    def __init__(self):
        super().__init__(
            input_stream="ticket:new",
            output_stream="ticket:classified",
        )
        self._agent = RouterAgent()

    async def process_message(self, message: dict) -> dict:
        state = dict(message)  # Copy input as pipeline state
        state = self._agent.run(state)
        return state


class AsyncContextAgent(AsyncBaseAgent):
    """Async wrapper around ContextAgent.

    Input:  ticket:classified  state dict with description
    Output: ticket:context_ready  state dict enriched with context_docs
    """

    def __init__(self):
        super().__init__(
            input_stream="ticket:classified",
            output_stream="ticket:context_ready",
        )
        self._agent = ContextAgent()

    async def process_message(self, message: dict) -> dict:
        state = dict(message)
        if state.get("requires_rag", True):
            state = self._agent.run(state)
        else:
            state["context_docs"] = []
        return state


class AsyncResolverAgent(AsyncBaseAgent):
    """Async wrapper around ResolverAgent.

    Input:  ticket:context_ready  state dict with context_docs
    Output: ticket:resolved  state dict enriched with resolution
    """

    def __init__(self):
        super().__init__(
            input_stream="ticket:context_ready",
            output_stream="ticket:resolved",
        )
        self._agent = ResolverAgent()

    async def process_message(self, message: dict) -> dict:
        state = dict(message)
        state = self._agent.run(state)
        return state


class AsyncQualityAgent(AsyncBaseAgent):
    """Async wrapper around QualityAgent.

    Input:  ticket:resolved  state dict with resolution
    Output: ticket:completed  state dict enriched with quality_check + final status
    """

    def __init__(self):
        super().__init__(
            input_stream="ticket:resolved",
            output_stream="ticket:completed",
        )
        self._agent = QualityAgent()

    async def process_message(self, message: dict) -> dict:
        state = dict(message)

        # Run quality check
        state = self._agent.run(state)

        # Determine final status
        qc = state.get("quality_check", {})
        if qc.get("passed"):
            state["status"] = "resolved"
        else:
            state["status"] = "escalated"

        # Build escalation info
        state["escalation_info"] = {
            "reason": qc.get("reason", "Quality check completed"),
            "confidence": qc.get("confidence", 0.0),
            "citation_score": qc.get("citation_score", 0.0),
            "hallucination_warnings": qc.get("hallucination_warnings", []),
            "critical_issues": qc.get("critical_issues", False),
            "suggest_escalation": qc.get("suggest_escalation", False),
        }

        return state
