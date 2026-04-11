"""JWT auth utilities for the sample project."""

from datetime import timedelta

import jwt

from .models import User  # noqa: F401 — used by indexer tests


def create_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token for a user."""
    payload = {"sub": user_id}
    return jwt.encode(payload, "secret", algorithm="HS256")


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    return jwt.decode(token, "secret", algorithms=["HS256"])


class AuthMiddleware:
    """Middleware that validates JWT tokens on protected routes."""

    def __init__(self, app: object) -> None:
        self.app = app
