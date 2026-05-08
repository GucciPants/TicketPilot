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
async def list_tickets(db: Session = Depends(get_db)):
    """List all tickets."""
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc()).all()
    return {"tickets": [ticket.to_dict() for ticket in tickets]}


@router.get("/tickets/stream")
async def ticket_stream(db: Session = Depends(get_db)):
    """SSE endpoint for real-time ticket updates."""
    async def event_generator():
        last_ticket_count = 0
        while True:
            try:
                tickets = db.query(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc()).all()
                current_count = len(tickets)
                
                if current_count != last_ticket_count:
                    last_ticket_count = current_count
                    tickets_data = [t.to_dict() for t in tickets]
                    yield f"event: tickets_updated\ndata: {json.dumps({'tickets': tickets_data})}\n\n"
                
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"SSE error: {e}")
                await asyncio.sleep(2)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Get ticket status by ID."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
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
