from fastapi import FastAPI
from app.api.routes import router
from app.database import Base, engine
from app.models import Ticket

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TicketPilot API",
    description="AI-powered support ticket resolution system",
    version="0.1.0"
)

app.include_router(router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {
        "message": "TicketPilot API",
        "version": "0.1.0",
        "endpoints": {
            "create_ticket": "POST /api/v1/tickets",
            "get_ticket": "GET /api/v1/tickets/{ticket_id}",
            "health": "GET /api/v1/health"
        }
    }
