"""Rate limiting middleware using Redis."""
import os
import time
import redis
import json
from starlette.responses import JSONResponse
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

# Rate limits per endpoint (requests per window)
RATE_LIMITS = {
    "/api/v1/tickets": {"POST": {"limit": 10, "window": 60}},        # 10 POST/minute
    "/api/v1/knowledge-base/ingest": {"POST": {"limit": 5, "window": 60}},  # 5 POST/minute
    "/api/v1/documents/search": {"GET": {"limit": 30, "window": 60}}, # 30 GET/minute
    "/api/v1/tickets/stream": {"GET": {"limit": 10, "window": 60}},  # 10 connections/minute
    "/api/v1/tickets/": {"PATCH": {"limit": 20, "window": 60}},  # 20 PATCH/min (matches /api/v1/tickets/{id}/resolve)
}

DEFAULT_LIMIT = 60  # requests per window for unmached endpoints
DEFAULT_WINDOW = 60  # seconds


def _get_rate_limit_key(request: Request) -> str:
    """Generate a unique key for rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    # Match against configured endpoints (strip dynamic path segments)
    path = request.url.path
    method = request.method

    # Try exact match first, then prefix match
    for route, methods in RATE_LIMITS.items():
        if method in methods and path.startswith(route):
            return f"ratelimit:{client_ip}:{method}:{route}"

    return f"ratelimit:{client_ip}:{method}:{path}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limits via Redis."""

    def __init__(self, app):
        super().__init__(app)
        try:
            self.redis = redis.from_url(
                os.getenv("REDIS_URL", "redis://redis:6379/0")
            )
            self.redis.ping()
            self.available = True
        except Exception:
            self.available = False  # Redis unavailable -> skip rate limiting

    async def dispatch(self, request: Request, call_next):
        if not self.available:
            return await call_next(request)

        key = _get_rate_limit_key(request)
        now = time.time()

        try:
            # Determine limit for this endpoint
            limit = DEFAULT_LIMIT
            window = DEFAULT_WINDOW
            for route, methods in RATE_LIMITS.items():
                if request.method in methods and request.url.path.startswith(route):
                    limit = methods[request.method]["limit"]
                    window = methods[request.method]["window"]
                    break

            # Redis: remove old entries, add current, count
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window)
            pipe.zcard(key)
            results = pipe.execute()
            count = results[3]  # zcard result

            # Check if over limit BEFORE processing
            if count > limit:
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": f"Rate limit exceeded ({limit} requests per {window}s). Try again later."},
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(now + window)),
                        "Retry-After": str(window)
                    }
                )

            # Process request
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
            response.headers["X-RateLimit-Reset"] = str(int(now + window))

            return response

        except Exception:
            # Any error -> pass through without rate limiting
            return await call_next(request)

    @staticmethod
    def get_rate_limit(request: Request) -> dict:
        """Get rate limit info for a request (for debugging)."""
        for route, methods in RATE_LIMITS.items():
            if request.method in methods and request.url.path.startswith(route):
                return methods[request.method]
        return {"limit": DEFAULT_LIMIT, "window": DEFAULT_WINDOW}
