from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.health import router as health_router
from app.api.guidelines import router as guidelines_router
from app.api.imports import router as imports_router
from app.api.candidate_rules import router as candidate_rules_router
from app.api.import_review import router as import_review_router
from app.api.audits import router as audits_router
from app.api.workspaces import router as workspaces_router
from app.core.upload_limits import GuidelineUploadBodyLimitMiddleware

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
app.add_middleware(GuidelineUploadBodyLimitMiddleware)

app.include_router(health_router, prefix=settings.API_V1_STR, tags=["Health"])
app.include_router(guidelines_router, prefix=settings.API_V1_STR, tags=["Guidelines"])
app.include_router(imports_router, prefix=settings.API_V1_STR, tags=["Imports"])
app.include_router(candidate_rules_router, prefix=settings.API_V1_STR, tags=["Candidate Rules"])
app.include_router(import_review_router, prefix=settings.API_V1_STR, tags=["Imported Row Review"])
app.include_router(audits_router, prefix=settings.API_V1_STR, tags=["Audits"])
app.include_router(workspaces_router, prefix=settings.API_V1_STR, tags=["Workspaces"])

@app.get("/")
async def root():
    return {
        "product": "Proofmint",
        "tagline": "Nothing ships unproven.",
        "status": "online",
        "docs": "/docs"
    }
