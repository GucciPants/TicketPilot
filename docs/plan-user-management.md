# Implementation Plan: User Management (Phase 2)

## Overview

Add user authentication, role-based access control (RBAC), and ticket ownership to TicketPilot.
Customers can register/login, agents/admins manage escalated tickets, and all API endpoints require proper authorization.

**Roles:** `customer` (default), `agent`, `admin`

---

## Dependencies

### New pip packages
```
python-jose[cryptography]==3.3.0   # JWT creation/verification
passlib[bcrypt]==1.7.4             # password hashing
```

### New files to create
```
app/auth/__init__.py
app/auth/utils.py        — password hashing, JWT helpers
app/auth/schemas.py      — Pydantic request/response models
app/auth/dependencies.py — FastAPI dependency injection (get_current_user, require_role)
app/auth/routes.py       — /api/v1/auth/* endpoints
docs/plan-user-management.md
```

### Files to modify
```
app/models.py            — add User model, user_id FK on Ticket
app/main.py              — mount auth router
app/api/routes.py        — protect endpoints with auth deps
frontend/index.html      — login/register modal, auth headers, role-based UI
frontend/admin.html      — login check, user management section
requirements.txt         — add python-jose + passlib
tests/conftest.py        — add auth fixtures (test user, auth headers)
tests/test_api.py        — add auth + RBAC tests
tests/test_auth.py       — new file for auth-specific tests
```

---

## Step-by-step

### Step 1: Auth Package Scaffold

#### `app/auth/utils.py`
- `hash_password(password: str) -> str` — passlib bcrypt hash
- `verify_password(password: str, hashed: str) -> bool`
- `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str`
- `decode_access_token(token: str) -> dict` — raises 401 on expiry/invalid

**Config:** read `SECRET_KEY` from env (default: auto-generated for dev), `ALGORITHM=HS256`, `ACCESS_TOKEN_EXPIRE_MINUTES=1440` (24h)

#### `app/auth/schemas.py`
```python
class UserCreate(BaseModel):
    email: str  (with EmailStr after adding pydantic[email-validator])
    password: str  (min_length=6)

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
```

#### `app/auth/dependencies.py`
- `get_optional_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User | None` — returns None if no/invalid token (anonymous ticket creation)
- `get_current_user(user: User | None = Depends(get_optional_user)) -> User` — raises 401 if None
- `require_role(*roles: str)` — factory: `require_role("admin")` returns a dependency that checks `user.role in roles`
- `require_admin = require_role("admin")` — convenience

#### `app/auth/routes.py`
| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/v1/auth/register` | POST | None | Create user, return token |
| `/api/v1/auth/login` | POST | None | Verify credentials, return token |
| `/api/v1/auth/me` | GET | `get_current_user` | Return current user profile |

Rate limiting: register 5/min, login 20/min (add to `rate_limit.py`)

---

### Step 2: User Model

Add to `app/models.py`:

```python
class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    tickets = relationship("Ticket", back_populates="user")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role.value if self.role else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
```

Add `user_id` FK to `Ticket` model:
```python
class Ticket(Base):
    # ... existing columns ...
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user = relationship("User", back_populates="tickets")
```

Update `Ticket.to_dict()` to include `user_id` and optional `user_email`.

**Notes:**
- `user_id` is nullable → anonymous tickets remain supported
- `Base.metadata.create_all` handles table creation (no Alembic needed yet)
- The `onupdate=func.now()` on `updated_at` may need `Column(..., onupdate=func.now(), server_default=func.now())` for SQLite compatibility

---

### Step 3: Wire Auth Routes

In `app/main.py`:
```python
from app.auth.routes import auth_router
app.include_router(auth_router, prefix="/api/v1/auth")
```

Add `SECRET_KEY` to `.env.example` and `.env` (auto-generate default for dev).

Update `rate_limit.py`:
```python
"/api/v1/auth/register": {"POST": {"limit": 5, "window": 60}},
"/api/v1/auth/login": {"POST": {"limit": 20, "window": 60}},
```

---

### Step 4: Protect Existing API Routes

| Endpoint | Auth | Ownership filter |
|---|---|---|
| `POST /api/v1/tickets` | `get_optional_user` → link `user_id` if logged in | N/A |
| `GET /api/v1/tickets` | `get_optional_user` → if customer, filter by `user_id` | ✅ |
| `GET /api/v1/tickets/{id}` | `get_optional_user` → if customer, check ownership | ✅ |
| `PATCH /api/v1/tickets/{id}/resolve` | `require_role("admin")` | N/A (admin) |
| `GET /api/v1/tickets/stream` | `get_optional_user` (via query param `?token=`) | Same as list |
| `POST /api/v1/documents` | `require_role("agent", "admin")` | N/A |
| `POST /api/v1/knowledge-base/ingest` | `require_role("agent", "admin")` | N/A |
| `/health`, `/metrics` | None | Public |
| `/api/v1/auth/*` | Mixed (see auth routes) | N/A |

SSE stream authentication:
- EventSource doesn't support custom headers → pass `?token=` query param
- Decode token in the stream handler, subscribe to user-specific channel if customer

Create an `admin` user on first startup (seed in `main.py`):
```python
# main.py — after create_all
from app.auth.utils import hash_password
# Create default admin if no users exist
db = SessionLocal()
if not db.query(User).first():
    db.add(User(email="admin@ticketpilot.app", 
                hashed_password=hash_password("admin123"),
                role=UserRole.ADMIN))
    db.commit()
db.close()
```

---

### Step 5: Admin User Management

Add to `app/auth/routes.py`:

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/v1/admin/users` | GET | `require_admin` | List all users |
| `/api/v1/admin/users/{id}/role` | PATCH | `require_admin` | Change user role |

Add role management UI to `admin.html` — a "Users" tab with user table and role dropdown.

---

### Step 6: Frontend Auth UI

**Login/Register Modal** — add to `index.html`:
- Auto-show if no token in localStorage
- Toggle between login and register forms
- On success: store token, close modal, reload data
- Logout button in sidebar → clear localStorage, refresh

**Auth headers on fetch() calls:**
```javascript
function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { 'Authorization': 'Bearer ' + token } : {};
}
```

Add to every fetch call:
```javascript
fetch('/api/v1/tickets', { headers: { ...authHeaders(), 'Content-Type': 'application/json' }, ... })
```

**Role-based UI:**
- Customers: don't show "Admin" nav link, don't show "Review" button on escalated tickets
- Agents/admins: show admin link, show review buttons
- If token expired (401 response on any fetch): clear token, redirect to login

**Admin.html** — add login check at init:
- If no token, redirect to `/`
- Show current admin email + logout button

---

### Step 7: Tests

#### New file: `tests/test_auth.py`
- `test_register_creates_user` — POST /auth/register, expect 201 + token
- `test_register_duplicate_email` — expect 409
- `test_login_valid` — POST /auth/login, expect token
- `test_login_invalid_password` — expect 401
- `test_login_nonexistent_email` — expect 401
- `test_me_authenticated` — GET /auth/me with token, expect user data
- `test_me_no_token` — expect 401
- `test_token_expiry` — mock time to verify expiry
- `test_rate_limit_register` — 6 rapid requests, 6th gets 429

#### Update `tests/conftest.py`
```python
@pytest.fixture
def test_user(db_session):
    """Create a test user and return (user, password)."""
    from app.auth.utils import hash_password
    user = User(email="test@example.com", 
                hashed_password=hash_password("testpass123"),
                role=UserRole.ADMIN)
    db_session.add(user)
    db_session.commit()
    return user, "testpass123"

@pytest.fixture
def auth_headers(test_user):
    """Return Authorization headers for test_user."""
    from app.auth.utils import create_access_token
    user, _ = test_user
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}
```

#### Updated: `tests/test_api.py`
- Update `test_create_ticket` → verify ticket gets `user_id` when authenticated
- Add test: customer sees only own tickets
- Add test: admin sees all tickets
- Add test: unauthenticated create still works (backwards compat)
- Add test: non-admin cannot resolve tickets (403)
- Add test: non-agent cannot ingest KB (403)
- Update mock fixtures to handle auth deps if needed

---

## File Change Summary

| File | Action | Summary |
|---|---|---|
| `app/auth/__init__.py` | **New** | Empty init |
| `app/auth/utils.py` | **New** | `hash_password`, `verify_password`, `create_access_token`, `decode_access_token` |
| `app/auth/schemas.py` | **New** | `UserCreate`, `UserLogin`, `UserResponse`, `TokenResponse` |
| `app/auth/dependencies.py` | **New** | `get_optional_user`, `get_current_user`, `require_role` |
| `app/auth/routes.py` | **New** | register, login, me, admin user management |
| `app/models.py` | **Modified** | Add `User` model, `UserRole` enum, `user_id` FK on `Ticket` |
| `app/main.py` | **Modified** | Mount auth router, seed default admin |
| `app/api/routes.py` | **Modified** | Add auth deps to all endpoints |
| `app/middleware/rate_limit.py` | **Modified** | Add auth endpoint rate limits |
| `requirements.txt` | **Modified** | Add `python-jose[cryptography]`, `passlib[bcrypt]` |
| `frontend/index.html` | **Modified** | Login/register modal, auth headers, role-based UI |
| `frontend/admin.html` | **Modified** | Login check, user management, logout |
| `tests/conftest.py` | **Modified** | Add `test_user`, `auth_headers` fixtures |
| `tests/test_auth.py` | **New** | Auth-specific test suite |
| `tests/test_api.py` | **Modified** | Auth-aware test updates |
| `docs/plan-user-management.md` | **New** | This plan |

---

## Risks & Open Questions

| Risk | Mitigation |
|---|---|
| **Anonymous ticket creation breaks** | `user_id` is nullable, `get_optional_user` returns None → no forced login |
| **SSE can't send custom headers** | Fallback to `?token=` query param for EventSource |
| **Token stored in localStorage** → XSS risk | Acceptable for demo/portfolio; production would use HttpOnly cookies |
| **No refresh tokens** → 24h expiry | Acceptable for v1; user re-logs in. Add later if needed |
| **Rate limiter silent degradation** | Pre-existing issue; auth endpoints add rate limits but can be bypassed if Redis is down |
| **Test DB (SQLite) vs PostgreSQL** | SQLAlchemy handles both; `onupdate=func.now()` may need adjustment |
