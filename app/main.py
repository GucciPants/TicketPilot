from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.database import Base, engine
from app.models import Ticket
import os
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TicketPilot API",
    description="AI-powered support ticket resolution system",
    version="0.1.0"
)

# CORS middleware (allow frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend CSS, JS)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Serve frontend at root
@app.get("/")
async def read_index():
    return FileResponse("frontend/index.html")

# Serve admin page
@app.get("/admin")
async def read_admin():
    return FileResponse("frontend/admin.html")

# Include API routes
app.include_router(router, prefix="/api/v1")
