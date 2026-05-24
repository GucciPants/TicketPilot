"""Authentication routes: register, login, me, and admin user management."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, UserRole
from app.auth.utils import hash_password, verify_password, create_access_token
from app.auth.schemas import UserCreate, UserLogin, TokenResponse, UserResponse, UserRoleUpdate
from app.auth.dependencies import get_current_user, require_admin

logger = logging.getLogger(__name__)

auth_router = APIRouter(tags=["auth"])


@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account. Returns a JWT token on success."""
    # Check if email already exists
    existing = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Create user
    user = User(
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("New user registered: %s (id=%d, role=%s)", user.email, user.id, user.role.value)

    # Generate token
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate with email and password. Returns a JWT token on success."""
    user = db.query(User).filter(func.lower(User.email) == payload.email.lower().strip()).first()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    logger.info("User logged in: %s (id=%d, role=%s)", user.email, user.id, user.role.value)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@auth_router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ─── Admin user management ───────────────────────────────────────


@auth_router.get("/admin/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all registered users. Admin only."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]


@auth_router.patch("/admin/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Change a user's role. Admin only. Cannot change own role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    old_role = user.role.value
    user.role = UserRole(payload.role)
    db.commit()
    db.refresh(user)

    logger.info("Role changed: %s: %s → %s (by admin %d)", user.email, old_role, payload.role, admin.id)

    return UserResponse.model_validate(user)
