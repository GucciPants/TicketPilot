"""Async persistence agent - saves completed tickets to the database."""
import json
import logging
from app.agents.async_base import AsyncBaseAgent
from app.models import Ticket, TicketStatus
from app.database import SessionLocal
from app.metrics import ticket_resolved_counter, ticket_escalated_counter

logger = logging.getLogger(__name__)


class PersistenceAgent(AsyncBaseAgent):
    """Consumes completed ticket events and persists to database."""

    def __init__(self):
        super().__init__(
            input_stream="ticket:completed",
            output_stream="ticket:persisted",
            concurrency=1
        )

    async def process_message(self, message: dict) -> dict:
        """Save ticket result to database."""
        ticket_id = message.get("ticket_id")
        status = message.get("status", "escalated")
        resolution = message.get("resolution", "")
        escalation_info = message.get("escalation_info")

        db = SessionLocal()
        try:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                logger.warning("Ticket %s not found for persistence", ticket_id)
                return message

            ticket.resolution = resolution
            ticket.status = TicketStatus(status) if status in [s.value for s in TicketStatus] else TicketStatus.ESCALATED

            if escalation_info:
                ticket.escalation_info = json.dumps(escalation_info)

            ticket.resolved_by = "agent" if status == "resolved" else None
            db.commit()

            if status == "resolved":
                ticket_resolved_counter.inc()
            else:
                ticket_escalated_counter.inc()

            logger.info("Ticket %d persisted with status %s", ticket_id, status)

            # Notify the SSE endpoint (GET /api/v1/tickets/stream) via Pub/Sub
            await self.publish_event("ticket:events", {
                "type": "ticket_updated",
                "ticket_id": ticket_id,
                "status": status,
            })

        except Exception as e:
            logger.error("Failed to persist ticket %d: %s", ticket_id, e)
            db.rollback()
        finally:
            db.close()

        return message
