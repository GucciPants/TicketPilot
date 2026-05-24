from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import redis
import json
import os
import asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)

from app.models import Ticket, TicketStatus, User
from app.database import get_db, SessionLocal
from app.rag.document_processor import DocumentProcessor
from app.metrics import ticket_created_counter, metrics_endpoint
from app.auth.dependencies import get_optional_user, require_role
from app.auth.utils import decode_access_token

router = APIRouter()

# Pydantic models
class TicketCreate(BaseModel):
    description: str

class TicketResponse(BaseModel):
    id: int
    description: str
    status: str
    resolution: str | None = None
    escalation_info: dict | None = None
    resolved_by: str | None = None
    user_id: int | None = None
    user_email: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

# Redis connection
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))


# ── Helper: resolve user from SSE query param token ──────────────
def _get_user_from_token(token: str | None, db: Session) -> User | None:
    """Decode a JWT token from a query param (for SSE EventSource limitation)."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    except (ValueError, Exception):
        return None


def _filter_tickets_for_user(query, user: User | None):
    """If user is a customer, filter to only their tickets."""
    if user is None or user.role.value in ("agent", "admin"):
        return query  # agents and admins see all
    return query.filter(Ticket.user_id == user.id)


# ── Tickets ───────────────────────────────────────────────────────

@router.post("/tickets", response_model=TicketResponse)
async def create_ticket(
    ticket_data: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """Create a new support ticket. Links to user if authenticated."""
    ticket = Ticket(
        description=ticket_data.description,
        status=TicketStatus.OPEN,
        user_id=current_user.id if current_user else None,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    ticket_created_counter.inc()

    ticket_payload = {
        "ticket_id": ticket.id,
        "description": ticket.description,
    }
    redis_client.lpush("ticket_queue", json.dumps(ticket_payload))

    return ticket.to_dict()


@router.get("/tickets")
async def list_tickets(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    current_user: User | None = Depends(get_optional_user),
):
    """List tickets. Customers see only their own; agents/admins see all."""
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    query = _filter_tickets_for_user(query, current_user)
    tickets = query.order_by(Ticket.created_at.desc(), Ticket.id.desc()).all()
    return {"tickets": [ticket.to_dict() for ticket in tickets]}


@router.get("/tickets/stream")
async def ticket_stream(token: Optional[str] = Query(None)):
    """SSE endpoint for real-time ticket updates via Redis Pub/Sub.

    Accepts an optional `?token=` query param for authentication
    (EventSource does not support custom headers). Unauthenticated
    users see all tickets; authenticated customers see only their own.
    """
    async def event_generator(user: User | None):
        # Step 1: Send initial ticket list
        db = SessionLocal()
        try:
            query = db.query(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc())
            query = _filter_tickets_for_user(query, user)
            tickets_data = [t.to_dict() for t in query.all()]
            yield f"event: tickets_updated\ndata: {json.dumps({'tickets': tickets_data})}\n\n"
        finally:
            db.close()

        # Step 2: Subscribe to Redis Pub/Sub for real-time updates
        pubsub = redis_client.pubsub()
        pubsub.subscribe("ticket:events")

        try:
            while True:
                try:
                    message = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: pubsub.get_message(timeout=1.0)
                    )
                    if message and message["type"] == "message":
                        db2 = SessionLocal()
                        try:
                            query = db2.query(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc())
                            query = _filter_tickets_for_user(query, user)
                            tickets_data = [t.to_dict() for t in query.all()]
                            yield f"event: tickets_updated\ndata: {json.dumps({'tickets': tickets_data})}\n\n"
                        finally:
                            db2.close()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("SSE stream error", exc_info=True)
                    await asyncio.sleep(2)
        finally:
            pubsub.unsubscribe()
            pubsub.close()

    # Resolve user from token query param (EventSource can't set headers)
    db = SessionLocal()
    try:
        current_user = _get_user_from_token(token, db)
    finally:
        db.close()

    return StreamingResponse(event_generator(current_user), media_type="text/event-stream")


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """Get ticket by ID. Customers can only see their own tickets."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Customers can only view their own tickets
    if current_user and current_user.role.value not in ("agent", "admin"):
        if ticket.user_id is not None and ticket.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket.to_dict()


class TicketResolve(BaseModel):
    resolution: str


@router.patch("/tickets/{ticket_id}/resolve", response_model=TicketResponse)
async def resolve_ticket(
    ticket_id: int,
    body: TicketResolve,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin", "agent")),
):
    """Resolve an escalated ticket. Admin or agent only."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status != TicketStatus.ESCALATED:
        raise HTTPException(status_code=400, detail="Only escalated tickets can be manually resolved")

    ticket.resolution = body.resolution
    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_by = _admin.role
    db.commit()
    db.refresh(ticket)

    redis_client.publish("ticket:events", json.dumps({
        "type": "ticket_updated",
        "ticket_id": ticket.id,
        "status": "resolved"
    }))

    return ticket.to_dict()


# ── Health & Metrics (public) ────────────────────────────────────

@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/metrics")
async def metrics():
    return metrics_endpoint()


# ── Document management (agent/admin only) ────────────────────────

class DocumentIngest(BaseModel):
    text: str
    doc_id: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/documents")
async def ingest_document(
    doc: DocumentIngest,
    _user: User = Depends(require_role("agent", "admin")),
):
    """Ingest a document into the RAG knowledge base. Agent/admin only."""
    processor = DocumentProcessor()
    doc_id = doc.doc_id or f"manual_{datetime.now().timestamp()}"
    chunks = processor.process_text(doc.text, doc_id, doc.metadata)
    return {"status": "success", "doc_id": doc_id, "chunks": chunks}


@router.post("/knowledge-base/ingest")
async def ingest_knowledge_base(
    _user: User = Depends(require_role("agent", "admin")),
):
    """Ingest the sample knowledge base. Agent/admin only."""
    processor = DocumentProcessor()
    count = processor.ingest_sample_knowledge_base()
    return {"status": "success", "documents_ingested": count}


@router.get("/documents/search")
async def search_documents(
    query: str,
    limit: int = 3,
    _user: User | None = Depends(get_optional_user),
):
    """Search for relevant documents. Available to any authenticated user."""
    from app.rag.vector_store import VectorStore
    store = VectorStore()
    results = store.search(query, limit)
    return {"query": query, "results": results}
