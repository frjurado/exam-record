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
    magic_link = f"http://localhost:8000/auth/verify?token={access_token}"
    print(f"MAGIC LINK FOR {email}: {magic_link}") # Print to console for manual testing
    
    return {"message": "Magic link sent (check console)"}

@router.get("/verify")
async def verify_magic_link(token: str = Query(...)):
    """
    Verify token and set session cookie.
    """
    payload = security.verify_token(token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    response = RedirectResponse(url="/health") # Redirect to a safe page (Health for now, Dashboard later)
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
@router.post("/guest")
async def guest_login(db: AsyncSession = Depends(get_db)):
    """
    Create or retrieve a guest user and return a token.
    For simplicity, we use a fixed guest account or create new ones.
    Let's use a single shared 'guest' account for now to keep DB clean, 
    or random ones. Random is better for separate sessions if strictly needed?
    Design decision: Shared guest for simplicity or unique? 
    Let's go limit-less unique for now to avoid collisions if we track sessions.
    Actually, let's use a consistent 'guest' role user based on a generic email pattern 
    or just 'guest' for all visitors if they don't provide email.
    
    Implementing: Create a generic guest user if not exists.
    """
    # Simply create a new guest per session or reuse?
    # Let's create a deterministic guest for simplicity of 'visitor' role
    email = "guest@examrecord.local"
    
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(email=email, role="Visitor", hashed_password="guest_password") # Needs hashed pw if model requires it? Model def says hashed_password is str.
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    response = JSONResponse(content={"message": "Guest authenticated", "token": token})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response
