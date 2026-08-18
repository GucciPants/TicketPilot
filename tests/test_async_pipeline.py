"""Tests for the async pipeline agents (F1: SSE event publishing)."""
import asyncio
import json
from unittest.mock import AsyncMock, patch

from app.agents.async_persistence import PersistenceAgent
from app.database import SessionLocal
from app.models import Ticket, TicketStatus


class TestPersistenceAgentSSE:
    def test_publishes_ticket_events_on_completion(self):
        db = SessionLocal()
        ticket = Ticket(description="I cannot log in", status=TicketStatus.OPEN)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        ticket_id = ticket.id
        db.close()

        async def scenario():
            agent = PersistenceAgent()
            redis_mock = AsyncMock()
            redis_mock.publish = AsyncMock(return_value=1)
            with patch.object(agent, "_get_redis", new=AsyncMock(return_value=redis_mock)):
                await agent.process_message({
                    "ticket_id": ticket_id,
                    "status": "resolved",
                    "resolution": "Reset your password.",
                    "escalation_info": {"confidence": 0.9, "citation_score": 0.8, "reason": "ok"},
                })
            return redis_mock

        redis_mock = asyncio.run(scenario())

        publish_calls = redis_mock.publish.await_args_list
        assert any(call.args[0] == "ticket:events" for call in publish_calls)

        payload = json.loads(publish_calls[0].args[1])
        assert payload["type"] == "ticket_updated"
        assert payload["ticket_id"] == ticket_id
        assert payload["status"] == "resolved"

        db = SessionLocal()
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        assert ticket.status == TicketStatus.RESOLVED
        assert ticket.resolution == "Reset your password."
        db.close()