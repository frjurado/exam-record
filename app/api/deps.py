import logging

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import verify_token
from app.db.session import get_db
from app.models import Report, User, Vote

logger = logging.getLogger("uvicorn")


async def _get_user_from_request(
    request: Request,
    db: AsyncSession,
    *,
    required: bool,
) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        if required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        return None

    try:
        payload = verify_token(token)
        if not payload:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                )
            return None

        user_email = payload.get("sub")
        if not user_email:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                )
            return None

        result = await db.execute(select(User).filter(User.email == user_email))
        user = result.scalar_one_or_none()

        if not user:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                )
            return None

        return user

    except jwt.PyJWTError as e:
        logger.warning("Invalid JWT token: %s", e)
        if required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from e
        return None


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user = await _get_user_from_request(request, db, required=True)
    assert user is not None  # required=True guarantees raise-or-return
    return user


async def get_current_user_optional(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User | None:
    return await _get_user_from_request(request, db, required=False)


async def check_user_event_participation(
    db: AsyncSession,
    user_id: int,
    event_id: int,
) -> tuple[bool, int | None]:
    """Return (has_participated, report_id_or_none).

    Checks first for an existing Report by this user, then for a Vote on any
    Report in the event. Returns the relevant report.id so callers can render
    participation UI.
    """
    existing_report = await db.execute(
        select(Report).filter(Report.event_id == event_id, Report.user_id == user_id)
    )
    if existing_event_report := existing_report.scalars().first():
        return True, existing_event_report.id

    existing_vote_result = await db.execute(
        select(Vote).join(Report).filter(Report.event_id == event_id, Vote.user_id == user_id)
    )
    if existing_vote := existing_vote_result.scalars().first():
        return True, existing_vote.report_id

    return False, None
