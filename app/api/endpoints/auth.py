from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models import User

router = APIRouter()


class MagicLinkRequest(BaseModel):
    email: EmailStr
    next_url: str | None = None


@router.post(
    "/magic-link",
    summary="Request a magic-link login email",
    description=(
        "Generate a time-limited JWT magic link and deliver it to the given email address. "
        "If the email is not yet registered, a new Visitor account is created automatically. "
        "In development the link is printed to the console instead of being emailed."
    ),
    responses={
        200: {"description": "Magic link sent successfully"},
        500: {"description": "Failed to deliver the magic-link email"},
    },
)
async def request_magic_link(
    request: Request, request_data: MagicLinkRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Generate a magic link and send it to the user's email. Auto-registers unknown addresses."""
    email = request_data.email

    # Check if user exists, if not create
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=email, role="Visitor")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role}, expires_delta=access_token_expires
    )

    # In production, send email. Here, logging.
    # Dynamic base URL to match the user's current host (localhost vs 127.0.0.1)
    base_url = str(request.base_url).rstrip("/") + "/api/auth/verify"

    next_param = ""
    if request_data.next_url:
        from urllib.parse import quote_plus

        encoded_next = quote_plus(request_data.next_url)
        next_param = f"&next={encoded_next}"

    magic_link = f"{base_url}?token={access_token}{next_param}"

    from app.services.email import email_service

    try:
        await email_service.send_magic_link(email, magic_link)
    except Exception:
        # If email fails, don't break the client flow immediately but log it
        # Actually for auth, if we can't send email, we should probably error out.
        raise HTTPException(status_code=500, detail="Error sending email") from None

    return {"message": "Magic link sent"}


@router.get(
    "/verify",
    summary="Verify magic-link token and open a session",
    description=(
        "Validate the JWT supplied in the magic link. On success, set an HTTP-only session cookie "
        "and redirect to `next` (or `/health` if omitted). Returns 400 if the token is invalid or expired."
    ),
    responses={
        307: {"description": "Token valid — redirecting with session cookie set"},
        400: {"description": "Token is invalid or expired"},
    },
)
async def verify_magic_link(token: str = Query(...), next: str | None = Query(None)) -> RedirectResponse:
    """Verify the magic-link JWT, set the session cookie, and redirect."""
    payload = security.verify_token(token)
    if not payload:
        raise HTTPException(status_code=400, detail="Token inválido")

    redirect_url = next if next else "/health"
    response = RedirectResponse(url=redirect_url)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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
