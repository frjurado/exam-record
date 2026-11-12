from datetime import datetime, timedelta, timezone
from typing import Any, cast

import jwt

from app.core.config import settings

# What a token may be used for. The emailed link carries a short-lived LINK token; opening
# it is exchanged for a long-lived SESSION token kept in the cookie. Neither is accepted in
# the other's place, so a leaked link stops being useful after a few minutes.
LINK = "link"
SESSION = "session"

LINK_LIFETIME = timedelta(minutes=settings.LINK_TOKEN_EXPIRE_MINUTES)
SESSION_LIFETIME = timedelta(days=settings.SESSION_EXPIRE_DAYS)


def create_token(email: str, purpose: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = LINK_LIFETIME if purpose == LINK else SESSION_LIFETIME
    payload = {
        "sub": email,
        "purpose": purpose,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str, purpose: str) -> dict[str, Any] | None:
    """The token's payload, or None if it is invalid, expired or meant for something else."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != purpose or not payload.get("sub"):
        return None
    return cast(dict[str, Any], payload)
