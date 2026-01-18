from fastapi import FastAPI
from app.core.config import settings
from app.api.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
