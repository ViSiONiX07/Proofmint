import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.guidelines import get_guideline_db_session
from app.api.candidate_rules import get_review_db_session
from app.core.database import get_db_session
from app.main import app
from app.models import Base, CandidateRule, Workspace


def pdf_bytes():
    doc = pymupdf.open(); page = doc.new_page()
    page.insert_text((72, 72), "Never use revolutionary claims without evidence.")
    data = doc.tobytes(); doc.close(); return data


@pytest.mark.asyncio
async def test_judge_guideline_ingestion_preserves_judge_workspace_and_authorization(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db_session] = override
    app.dependency_overrides[get_guideline_db_session] = override
    app.dependency_overrides[get_review_db_session] = override
    monkeypatch.setattr("app.main.get_session_factory", lambda: factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            started = await client.post("/api/v1/auth/judge")
            assert started.status_code == 200
            workspace_id = started.json()["workspace_id"]
            uploaded = await client.post("/api/v1/guidelines/ingest", data={"workspace_id": workspace_id}, files={"files": ("guide.pdf", pdf_bytes(), "application/pdf")}, headers={"X-CSRF-Token": client.cookies.get("proofmint_csrf")})
            assert uploaded.status_code == 200, uploaded.text
            rules = await client.get(f"/api/v1/guidelines/{uploaded.json()['results'][0]['extraction']['document_id']}/rules", params={"workspace_id": workspace_id})
            assert rules.status_code == 200, rules.text
            assert rules.json()["total"] == 1
            with Session(engine) as db:
                workspace = db.get(Workspace, UUID(workspace_id))
                assert workspace.kind == "judge_demo"
                assert workspace.owner_judge_session_id is not None
                assert db.query(CandidateRule).count() == 1
        with Session(engine) as db:
            assert db.query(Workspace).filter(Workspace.id == UUID(workspace_id), Workspace.kind == "judge_demo").count() == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine); engine.dispose()
