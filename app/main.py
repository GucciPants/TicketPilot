from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router
from app.database import Base, engine
from app.models import Ticket

# Create database tables
Base.metadata.create_all(bind=engine)

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

app = FastAPI(
    title="TicketPilot API",
    description="AI-powered support ticket resolution system",
    version="0.1.0"
)
    
@app.get("/")
async def read_index():
    """Serve the frontend index.html."""
    return FileResponse("frontend/index.html")

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
