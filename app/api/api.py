from fastapi import APIRouter
from app.api.endpoints import auth, composers, works

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(composers.router, prefix="/api/composers", tags=["composers"])
api_router.include_router(works.router, prefix="/api/works", tags=["works"])
