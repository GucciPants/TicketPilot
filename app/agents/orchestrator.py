"""Orchestrator agent for the TicketPilot multi-agent pipeline."""
from app.agents.base import BaseAgent
from app.agents.router_agent import RouterAgent
from app.agents.context_agent import ContextAgent
from app.agents.resolver_agent import ResolverAgent
from app.agents.quality_agent import QualityAgent
from app.metrics import ticket_processing_seconds, worker_processed_counter, ticket_resolved_counter, ticket_escalated_counter
from app.models import Ticket, TicketStatus
from app.database import SessionLocal
import time
import json
import logging
import redis
import os
import threading
import atexit
import warnings

# Redis event publisher — thread-safe singleton
_redis_pub = None
_redis_lock = threading.Lock()

def _get_redis_pub():
    """Get or create the Redis publisher client (thread-safe)."""
    global _redis_pub
    if _redis_pub is None:
        with _redis_lock:
            if _redis_pub is None:
                try:
                    _redis_pub = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
                    atexit.register(_cleanup_redis)
                except Exception:
                    return None
    return _redis_pub

def _cleanup_redis():
    """Close the Redis connection on shutdown."""
    global _redis_pub
    if _redis_pub is not None:
        try:
            _redis_pub.close()
        except Exception:
            pass
        _redis_pub = None

def _publish_ticket_event(ticket_id: int, status: str):
    """Publish ticket update event to Redis Pub/Sub."""
    pub = _get_redis_pub()
    if pub is None:
        return
    try:
        pub.publish("ticket:events", json.dumps({
            "type": "ticket_updated",
            "ticket_id": ticket_id,
            "status": status
        }))
    except Exception as e:
        logger.warning("Failed to publish ticket event: %s", e)


def publish_ticket_to_stream(ticket_id: int, description: str):
    """Publish a new ticket event to the async Redis Stream pipeline.

    This is the thin facade that replaces the synchronous Orchestrator.process_ticket().
    The async pipeline agents will consume this event and process it concurrently.
    """
    import json as _json
    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        r.xadd("ticket:new", {"data": _json.dumps({
            "ticket_id": ticket_id,
            "description": description
        })}, maxlen=10000)
        logger.info("Published ticket %d to async stream", ticket_id)
    except Exception as e:
        logger.warning("Failed to publish to async stream: %s", e)


logger = logging.getLogger(__name__)

class Orchestrator:
    """Coordinates the multi-agent pipeline for ticket resolution."""

    def __init__(self):
        self.router = RouterAgent()
        self.context = ContextAgent()
        self.resolver = ResolverAgent()
        self.quality = QualityAgent()

    def process_ticket(self, ticket_id: int, description: str) -> str:
        """Run the full agent pipeline for a ticket.

        Deprecated: Use publish_ticket_to_stream() for the async event-driven pipeline.

        Args:
            ticket_id: The ticket ID
            description: The ticket description

        Returns:
            Resolution text
        """
        warnings.warn(
            "Orchestrator.process_ticket() is deprecated. Use publish_ticket_to_stream() for async pipeline.",
            DeprecationWarning, stacklevel=2
        )
        start_time = time.time()
        
        # Initialize shared pipeline state
        state = {
            "ticket_id": ticket_id,
            "description": description,
            "category": None,
            "priority": "medium",
            "context_docs": [],
            "resolution": None,
            "quality_check": None,
            "status": "open",
            "errors": []
        }

        try:
            # Step 1: Route the ticket (classify)
            logger.info(f"[{ticket_id}] Router Agent: classifying...")
            state = self.router.run(state)
            
            # Step 2: Retrieve context from knowledge base
            logger.info(f"[{ticket_id}] Context Agent: retrieving documents...")
            if state.get("requires_rag", True):
                state = self.context.run(state)
            else:
                state["context_docs"] = []
                logger.info(f"[{ticket_id}] Skipping RAG (Router marked not required)")
            
            # Step 3: Generate resolution
            logger.info(f"[{ticket_id}] Resolver Agent: generating response...")
            state = self.resolver.run(state)
            
            # Step 4: Quality check
            logger.info(f"[{ticket_id}] Quality Agent: validating...")
            state = self.quality.run(state)
            
            # Final decision
            qc = state.get("quality_check", {})
            if qc.get("passed"):
                state["status"] = "resolved"
                ticket_resolved_counter.inc()
                # Store quality check result for resolved tickets too
                state["escalation_info"] = {
                    "confidence": qc.get("confidence", 0.0),
                    "citation_score": qc.get("citation_score", 0.0),
                    "hallucination_warnings": qc.get("hallucination_warnings", []),
                    "category": state.get("category"),
                    "priority": state.get("priority"),
                    "agent_notes": "Auto-resolved by QualityAgent"
                }
                logger.info(f"[{ticket_id}] Resolution passed quality check (confidence: {qc.get('confidence', 0)})")
            else:
                state["status"] = "escalated"
                ticket_escalated_counter.inc()
                reason = state.get("quality_check", {}).get("reason", "Quality check failed")
                # Store escalation details
                qc = state.get("quality_check", {})
                state["escalation_info"] = {
                    "reason": qc.get("reason", reason),
                    "confidence": qc.get("confidence", 0.0),
                    "citation_score": qc.get("citation_score", 0.0),
                    "hallucination_warnings": qc.get("hallucination_warnings", []),
                    "critical_issues": qc.get("critical_issues", False),
                    "category": state.get("category"),
                    "priority": state.get("priority"),
                    "agent_notes": f"Escalated by QualityAgent: {reason}"
                }
                logger.info(f"[{ticket_id}] Escalated: {reason}")
            
            # Track metrics
            worker_processed_counter.inc()
            
        except Exception as e:
            logger.error(f"[{ticket_id}] Pipeline error: {e}")
            state["status"] = "escalated"
            state["resolution"] = f"Error: Pipeline failed - {str(e)}"
            state["errors"].append(str(e))
        
        finally:
            # Record processing time
            elapsed = time.time() - start_time
            ticket_processing_seconds.observe(elapsed)
            logger.info(f"[{ticket_id}] Pipeline completed in {elapsed:.2f}s, status={state['status']}")
        
        # Update ticket in database
        self._update_ticket(ticket_id, state)
        
        return state.get("resolution", "No resolution generated")

    def _update_ticket(self, ticket_id: int, state: dict):
        """Update the ticket in the database."""
        db = SessionLocal()
        try:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.resolution = state.get("resolution")
                ticket.status = TicketStatus(state["status"]) if state["status"] in [s.value for s in TicketStatus] else TicketStatus.ESCALATED
                
                if "escalation_info" in state:
                    ticket.escalation_info = json.dumps(state["escalation_info"])
                
                ticket.resolved_by = "agent" if state.get("status") == "resolved" else None
                
                db.commit()
                
                # Publish event for SSE
                _publish_ticket_event(ticket.id, state["status"])
        except Exception as e:
            logger.error(f"Failed to update ticket {ticket_id}: {e}")
            db.rollback()
        finally:
            db.close()
