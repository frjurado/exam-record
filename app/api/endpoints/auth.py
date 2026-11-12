import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.constants import RateLimit, Roles
from app.core.limiter import allow, limiter
from app.core.urls import public_base_url, safe_next_path
from app.db.session import get_db
from app.models import User
from app.services.email import email_service

logger = logging.getLogger("uvicorn")

router = APIRouter()

INVALID_LINK_PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WikiAnálisis | Enlace caducado</title></head>
<body style="font-family: Georgia, serif; max-width: 32rem; margin: 4rem auto; padding: 0 1rem;">
<h1 style="font-weight: 500;">El enlace ha caducado</h1>
<p>Este enlace ya no es válido. Vuelve a la página donde estabas y pide uno nuevo.</p>
<p><a href="/">Ir al inicio</a></p>
</body></html>"""


class MagicLinkRequest(BaseModel):
    email: EmailStr
    next_url: str | None = None


@router.post(
    "/magic-link",
    summary="Request a magic-link login email",
    description=(
        "Email a short-lived sign-in link to the given address. No account is created "
        "until the link is opened. In development the link is printed to the console "
        "instead of being emailed."
    ),
    responses={
        200: {"description": "Magic link sent successfully"},
        429: {"description": "Too many requests from this address or for this email"},
        500: {"description": "Failed to deliver the magic-link email"},
    },
)
@limiter.limit(RateLimit.MAGIC_LINK_REQUEST)
async def request_magic_link(request: Request, request_data: MagicLinkRequest) -> dict[str, str]:
    """Send a sign-in link. Nothing is stored: the address is only proven when the link is opened."""
    email = request_data.email

    if not allow(RateLimit.MAGIC_LINK_PER_EMAIL, "magic-link-email", email.lower()):
        raise HTTPException(status_code=429, detail="Demasiados enlaces pedidos para ese email")

    params = {"token": security.create_token(email, security.LINK)}
    if request_data.next_url:
        params["next"] = safe_next_path(request_data.next_url, request)
    magic_link = f"{public_base_url(request)}/api/auth/verify?{urlencode(params)}"

    try:
        await email_service.send_magic_link(email, magic_link)
    except Exception:
        raise HTTPException(status_code=500, detail="Error sending email") from None

    return {"message": "Magic link sent"}


async def _get_or_create_user(db: AsyncSession, email: str) -> User:
    query = select(User).filter(User.email == email)
    user: User | None = (await db.execute(query)).scalar_one_or_none()
    if user is None:
        user = User(email=email, role=Roles.VISITOR)
        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            # The same link opened twice at once: the other request created the row.
            await db.rollback()
            user = (await db.execute(query)).scalar_one()
    return user


@router.get(
    "/verify",
    summary="Verify magic-link token and open a session",
    description=(
        "Validate the link token. On success, create the account if it is new, set an "
        "HTTP-only session cookie and redirect to `next` (a path on this site; the home "
        "page otherwise). An invalid or expired link gets a short explanation page."
    ),
    responses={
        307: {"description": "Token valid — redirecting with session cookie set"},
        400: {"description": "Token is invalid or expired"},
    },
)
async def verify_magic_link(
    request: Request,
    token: str = Query(...),
    next: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Exchange the emailed link token for a session cookie, and redirect."""
    payload = security.verify_token(token, security.LINK)
    if not payload:
        return HTMLResponse(INVALID_LINK_PAGE, status_code=400)

    user = await _get_or_create_user(db, payload["sub"])

    max_age = int(security.SESSION_LIFETIME.total_seconds())
    response = RedirectResponse(url=safe_next_path(next, request))
    response.set_cookie(
        key="access_token",
        value=security.create_token(str(user.email), security.SESSION),
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        max_age=max_age,
        samesite="lax",
        path="/",
    )
    return response


@router.get(
    "/me",
    summary="Return the currently authenticated user",
    description="Decode the session cookie and return basic profile info. Requires a valid session.",
    responses={
        200: {"description": "Authenticated user profile"},
        401: {"description": "Missing or invalid session cookie"},
    },
)
async def read_users_me(current_user: User = Depends(deps.get_current_user)) -> dict[str, Any]:
    """Return the email, role, and ID of the currently authenticated user."""
    return {"email": current_user.email, "role": current_user.role, "id": current_user.id}
