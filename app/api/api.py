from fastapi import APIRouter

from app.api.endpoints import admin, auth, composers, reports, works

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/api/auth", tags=["auth"])
api_router.include_router(composers.router, prefix="/api/composers", tags=["composers"])
api_router.include_router(works.router, prefix="/api/works", tags=["works"])
api_router.include_router(reports.router, prefix="/api/reports", tags=["reports"])
# Server-rendered maintenance page, not part of the public API.
api_router.include_router(admin.router, prefix="/admin")
