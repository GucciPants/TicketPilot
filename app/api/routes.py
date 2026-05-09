from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import redis
import json
import os
import asyncio
from typing import Optional

from app.models import Ticket, TicketStatus
from app.database import get_db
from app.rag.document_processor import DocumentProcessor
from app.metrics import ticket_created_counter, metrics_endpoint

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
    created_at: datetime | None = None
    updated_at: datetime | None = None

# Redis connection
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))

@router.post("/tickets", response_model=TicketResponse)
async def create_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
    """Create a new support ticket and publish to Redis queue."""
    # Create ticket in database
    ticket = Ticket(
        description=ticket_data.description,
        status=TicketStatus.OPEN
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    # Increment metrics
    ticket_created_counter.inc()
    
    # Publish to Redis for worker processing
    ticket_payload = {
        "ticket_id": ticket.id,
        "description": ticket.description
    }
    redis_client.lpush("ticket_queue", json.dumps(ticket_payload))
    
    return ticket.to_dict()

@router.get("/tickets")
async def list_tickets(db: Session = Depends(get_db), status: Optional[str] = None):
    """List all tickets, optionally filtered by status."""
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    tickets = query.order_by(Ticket.created_at.desc(), Ticket.id.desc()).all()
    return {"tickets": [ticket.to_dict() for ticket in tickets]}


@router.get("/tickets/stream")
async def ticket_stream():
    """SSE endpoint for real-time ticket updates via Redis Pub/Sub."""
    async def event_generator():
        # Step 1: Send initial full ticket list
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            tickets = db.query(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc()).all()
            tickets_data = [t.to_dict() for t in tickets]
            yield f"event: tickets_updated\ndata: {json.dumps({'tickets': tickets_data})}\n\n"
        finally:
            db.close()
        
        # Step 2: Subscribe to Redis Pub/Sub for real-time updates
        pubsub = redis_client.pubsub()
        pubsub.subscribe("ticket:events")
        
        try:
            while True:
                try:
                    # Use asyncio.to_thread to avoid blocking the event loop
                    message = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: pubsub.get_message(timeout=1.0)
                    )
                    if message and message["type"] == "message":
                        # Fetch full updated ticket list
                        db2 = SessionLocal()
                        try:
                            tickets = db2.query(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc()).all()
                            tickets_data = [t.to_dict() for t in tickets]
                            yield f"event: tickets_updated\ndata: {json.dumps({'tickets': tickets_data})}\n\n"
                        finally:
                            db2.close()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"SSE error: {e}")
                    await asyncio.sleep(2)
        finally:
            pubsub.unsubscribe()
            pubsub.close()
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Get ticket status by ID."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket.to_dict()


class TicketResolve(BaseModel):
    resolution: str

@router.patch("/tickets/{ticket_id}/resolve", response_model=TicketResponse)
async def resolve_ticket(ticket_id: int, body: TicketResolve, db: Session = Depends(get_db)):
    """Manually resolve an escalated ticket (admin action)."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status != TicketStatus.ESCALATED:
        raise HTTPException(status_code=400, detail="Only escalated tickets can be manually resolved")
    
    ticket.resolution = body.resolution
    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_by = "admin"
    db.commit()
    db.refresh(ticket)
    
    # Publish event for SSE
    redis_client.publish("ticket:events", json.dumps({
        "type": "ticket_updated",
        "ticket_id": ticket.id,
        "status": "resolved"
    }))
    
    return ticket.to_dict()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return metrics_endpoint()

# Document ingestion endpoints
class DocumentIngest(BaseModel):
    text: str
    doc_id: Optional[str] = None
    metadata: Optional[dict] = None

@router.post("/documents")
async def ingest_document(doc: DocumentIngest):
    """Ingest a document into the RAG knowledge base."""
    processor = DocumentProcessor()
    doc_id = doc.doc_id or f"manual_{datetime.now().timestamp()}"
    chunks = processor.process_text(doc.text, doc_id, doc.metadata)
    return {"status": "success", "doc_id": doc_id, "chunks": chunks}

@router.post("/knowledge-base/ingest")
async def ingest_knowledge_base():
    """Ingest the sample knowledge base."""
    processor = DocumentProcessor()
    count = processor.ingest_sample_knowledge_base()
    return {"status": "success", "documents_ingested": count}

@router.get("/documents/search")
async def search_documents(query: str, limit: int = 3):
    """Search for relevant documents."""
    from app.rag.vector_store import VectorStore
    store = VectorStore()
    results = store.search(query, limit)
    return {"query": query, "results": results}
