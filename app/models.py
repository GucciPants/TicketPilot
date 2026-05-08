from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum
import json

class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"

class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False)
    resolution = Column(Text, nullable=True)
    escalation_info = Column(Text, nullable=True)  # JSON: reason, sla_deadline, agent_notes
    resolved_by = Column(String(50), nullable=True)  # 'agent' or 'admin'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def to_dict(self):
        result = {
            "id": self.id,
            "description": self.description,
            "status": self.status.value if self.status else None,
            "resolution": self.resolution,
            "resolved_by": self.resolved_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        if self.escalation_info:
            try:
                result["escalation_info"] = json.loads(self.escalation_info)
            except (json.JSONDecodeError, TypeError):
                result["escalation_info"] = self.escalation_info
        return result
