"""JWT creation/verification and password hashing for the API. Role in
the token is read from the DB at login time and never from client input
-- see backend/main.py's get_current_user, which is the only source of
user_id/role for every /chat request."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 30


class InvalidTokenError(Exception):
    pass


def _get_secret():
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET is not set. Set it in the environment before starting the API."
        )
    return secret


def verify_password(password, password_hash):
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id, role):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token):
    """Returns (user_id, role). Raises InvalidTokenError on anything
    wrong (bad signature, expired, malformed) -- callers convert that to
    an HTTP 401 rather than leaking which specific thing was wrong."""
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    try:
        return int(payload["sub"]), payload["role"]
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("token missing required claims") from exc
