from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.audits import get_audit_session
from app.main import app
from app.models import Base, CandidateRule, GuidelineDocument, ImportedFact, ImportedTerm, Workspace


@pytest.fixture
def audit_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        workspace = Workspace(kind="session")
        session.add(workspace); session.flush()
        document = GuidelineDocument(workspace_id=workspace.id, source_filename="brand.pdf", source_sha256="a" * 64, file_size_bytes=12, page_count=1)
        session.add(document); session.flush()
        rule = CandidateRule(document_id=document.id, rule_text='Never use “guaranteed”.', category="restriction",
            source_page=1, source_start_offset=0, source_end_offset=30, source_excerpt='Never use “guaranteed”.', review_status="approved")
        pending = CandidateRule(document_id=document.id, rule_text='Never use “pending-only”.', category="restriction",
            source_page=1, source_start_offset=31, source_end_offset=60, source_excerpt='Never use “pending-only”.', review_status="pending_review")
        fact = ImportedFact(workspace_id=workspace.id, claim_type="capability", approved_statement="The platform supports CSV exports.", source_filename="facts.csv", source_row_number=2, source_sha256="b" * 64, review_status="approved")
        term = ImportedTerm(workspace_id=workspace.id, term="ProofMint", preferred_form="Proofmint", source_filename="terms.csv", source_row_number=2, source_sha256="c" * 64, review_status="approved")
        rejected = ImportedFact(workspace_id=workspace.id, claim_type="capability", approved_statement="Rejected statement.", source_filename="facts.csv", source_row_number=3, source_sha256="b" * 64, review_status="rejected")
        session.add_all([rule, pending, fact, term, rejected]); session.commit()
        doc_id = document.id
        workspace_id = workspace.id
    def override():
        with Session(engine, expire_on_commit=False) as session:
            yield session
    app.dependency_overrides[get_audit_session] = override
    yield doc_id, workspace_id
    app.dependency_overrides.pop(get_audit_session, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.mark.asyncio
async def test_audit_api_persists_run_findings_decision_and_clearance_with_hash(audit_db):
    document_id, workspace_id = audit_db
    content = "Our guaranteed platform is ProofMint. The platform supports CSV exports."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={"document_id": str(document_id), "workspace_id": str(workspace_id), "content": content})
        assert created.status_code == 201, created.text
        audit = created.json()
        assert audit["character_count"] == len(content)
        assert audit["approved_rules_considered"] == 1
        assert len(audit["findings"]) == 3
        assert {f["finding_type"] for f in audit["findings"]} == {"restricted_phrase", "preferred_terminology", "approved_fact_match"}
        assert any(f["source_filename"] == "brand.pdf" and f["source_page"] == 1 for f in audit["findings"])
        run_id = audit["id"]
        actionable = [f for f in audit["findings"] if f["status"] == "pending_review"]
        params = {"workspace_id": str(workspace_id)}
        blocked = await client.post(f"/api/v1/audits/{run_id}/clearance", params=params, json={"decision": "cleared"})
        assert blocked.status_code == 409
        for finding in actionable:
            decision = await client.post(f"/api/v1/audits/{run_id}/findings/{finding['id']}/decisions", params=params, json={"action": "dismiss"})
            assert decision.status_code == 200 and "dismissed" in [f["status"] for f in decision.json()["findings"]]
        refreshed = await client.get(f"/api/v1/audits/{run_id}", params=params)
        assert refreshed.status_code == 200
        assert {finding["status"] for finding in refreshed.json()["findings"] if finding["status"] != "informational"} == {"dismissed"}
        assert {decision["action"] for decision in refreshed.json()["decisions"]} == {"dismiss"}
        clearance = await client.post(f"/api/v1/audits/{run_id}/clearance", params=params, json={"decision": "cleared"})
        assert clearance.status_code == 200 and clearance.json()["review_status"] == "cleared"
        assert clearance.json()["clearance"]["content_sha256"] == audit["content_sha256"]
        retrieved = await client.get(f"/api/v1/audits/{run_id}", params=params)
        assert retrieved.status_code == 200 and retrieved.json()["clearance"]["decision"] == "cleared"


@pytest.mark.asyncio
async def test_audit_api_rejects_blank_copy_and_missing_document(audit_db):
    _, workspace_id = audit_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        blank = await client.post("/api/v1/audits", json={"content": "   ", "workspace_id": str(workspace_id)})
        assert blank.status_code == 422
        missing = await client.post("/api/v1/audits", json={"content": "copy", "document_id": str(uuid4()), "workspace_id": str(workspace_id)})
        assert missing.status_code == 404
