"""FastAPI dependency injection for authentication and authorization.

Provides:
    - get_optional_user: returns User or None (no auth required, used for anonymous tickets)
    - get_current_user: requires valid token, raises 401
    - require_role(*roles): factory that returns a dependency checking user.role
    - require_admin: convenience for require_role("admin")
"""
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth.utils import decode_access_token

logger = logging.getLogger(__name__)

# FastAPI security scheme for Bearer tokens
_bearer_scheme = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the authenticated user or None if no/invalid token.

    Used for endpoints that work both with and without authentication
    (e.g., ticket creation — anonymous users can still create tickets).
    """
    if credentials is None:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None

        user = db.query(User).filter(User.id == int(user_id_str)).first()
        if user is None or not user.is_active:
            return None

        return user
    except (ValueError, Exception) as e:
        logger.debug("Optional auth failed (non-fatal): %s", str(e))
        return None


async def get_current_user(
    user: User | None = Depends(get_optional_user),
) -> User:
    """Require a valid authenticated user. Raises 401 if missing.

    Use on endpoints that need a logged-in user.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*roles: str):
    """Factory: returns a dependency that checks the user has one of the given roles.

    Usage:
        @router.get("/admin/users")
        async def list_users(user: User = Depends(require_role("admin"))):
            ...

        @router.post("/documents")
        async def ingest_doc(user: User = Depends(require_role("agent", "admin"))):
            ...
    """
    async def _role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in roles:
            role_list = ", ".join(sorted(roles))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of these roles: {role_list}",
            )
        return user

    return _role_checker


# Convenience alias
require_admin = require_role("admin")
