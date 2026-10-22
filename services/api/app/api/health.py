from fastapi import APIRouter
from datetime import datetime, timezone
from app.schemas.finding import HealthCheck
from app.core.config import settings

router = APIRouter()

@router.get("/health", response_model=HealthCheck)
async def health_check():
    return HealthCheck(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc)
    )
