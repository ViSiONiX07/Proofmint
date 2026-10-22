from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.health import router as health_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Proofmint AI Brand Verification Workspace API — Foundation layer."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.API_V1_STR, tags=["Health"])

@app.get("/")
async def root():
    return {
        "product": "Proofmint",
        "tagline": "Nothing ships unproven.",
        "status": "online",
        "docs": "/docs"
    }
