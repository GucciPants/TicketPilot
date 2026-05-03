from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import redis
import json
import os

from app.models import Ticket, TicketStatus
from app.database import get_db

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
    
    # Publish to Redis for worker processing
    ticket_payload = {
        "ticket_id": ticket.id,
        "description": ticket.description
    }
    redis_client.lpush("ticket_queue", json.dumps(ticket_payload))
    
    return ticket.to_dict()

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
