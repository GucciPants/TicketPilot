from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# Mount static files (frontend CSS, JS)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Serve frontend at root
@app.get("/")
async def read_index():
    return FileResponse("frontend/index.html")

# Include API routes
app.include_router(router, prefix="/api/v1")
