from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models import User

router = APIRouter()

class MagicLinkRequest(BaseModel):
    email: EmailStr
    next_url: str | None = None

@router.post("/magic-link")
async def request_magic_link(
    request_data: MagicLinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a magic link and 'send' it (log to console).
    Auto-registers user if they don't explicitly exist (simplified flow).
    """
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
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    # In production, send email. Here, logging.
    base_url = "http://localhost:8000/auth/verify"
    next_param = f"&next={request_data.next_url}" if request_data.next_url else ""
    magic_link = f"{base_url}?token={access_token}{next_param}"
    
    print(f"MAGIC LINK FOR {email}: {magic_link}") # Print to console for manual testing
    
    return {"message": "Magic link sent (check console)"}

@router.get("/verify")
async def verify_magic_link(
    token: str = Query(...),
    next: str | None = Query(None)
):
    """
    Verify token and set session cookie.
    """
    payload = security.verify_token(token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    redirect_url = next if next else "/health"
    response = RedirectResponse(url=redirect_url)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response

@router.get("/me")
async def read_users_me(current_user: User = Depends(deps.get_current_user)):
    """
    Test endpoint to verify authentication.
    """
    return {
        "email": current_user.email,
        "role": current_user.role,
        "id": current_user.id
    }
