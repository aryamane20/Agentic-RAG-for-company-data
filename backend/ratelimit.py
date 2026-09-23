"""Per-user rate limiting for /chat: ~20 requests/minute, keyed by the
user_id embedded in the caller's JWT -- not IP, since IP-based limiting
doesn't actually mean "per user" once multiple users share a NAT/proxy."""

from fastapi import Request
from slowapi import Limiter

from backend import auth

RATE_LIMIT = "20/minute"
LOGIN_RATE_LIMIT = "10/minute"  # by IP -- no JWT exists yet at login time


def rate_limit_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        try:
            user_id, _role = auth.decode_access_token(token)
            return f"user:{user_id}"
        except auth.InvalidTokenError:
            pass
    # No valid token -- falls back to IP. This path is reached in two
    # cases: /login (which never has a token) and /chat requests with a
    # missing/invalid token -- for the latter to actually be reached, the
    # auth check has to run AFTER the rate limiter, not via a FastAPI
    # Depends() that FastAPI resolves before the route body (and thus
    # before @limiter.limit's own check) ever executes. See chat()'s
    # manual get_current_user() call in main.py for why.
    return f"ip:{request.client.host if request.client else 'unknown'}"


limiter = Limiter(key_func=rate_limit_key, headers_enabled=True)
