from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.auth.routes import auth_router
from app.database import Base, engine, SessionLocal
from app.models import Ticket, User, UserRole
from app.auth.utils import hash_password
from app.middleware.rate_limit import RateLimitMiddleware
def _seed_default_admin():
    """Create a default admin user on first startup if no users exist."""
    try:
        db = SessionLocal()
        if not db.query(User).first():
            admin = User(
                email="admin@ticketpilot.app",
                hashed_password=hash_password("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin created: admin@ticketpilot.app / admin123")
        db.close()
    except Exception as e:
        logger.warning("Failed to seed default admin (non-fatal): %s", str(e))

import os
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TicketPilot API",
    description="AI-powered support ticket resolution system",
    version="0.2.0"
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

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
app.include_router(auth_router, prefix="/api/v1/auth")

# Seed default admin user if no users exist
_seed_default_admin()
