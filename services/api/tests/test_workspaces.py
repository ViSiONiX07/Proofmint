"""Session workspace isolation tests against an isolated in-memory database."""

from uuid import UUID

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.audits import get_audit_session
from app.api.candidate_rules import get_review_db_session
from app.api.guidelines import get_guideline_db_session
from app.api.import_review import get_import_review_db_session
from app.api.imports import get_import_db_session
from app.api.workspaces import get_workspace_session
from app.main import app
from app.models import Base, ImportedFact, Workspace


def _pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Never use “guaranteed” claims in product advertising.")
    content = document.tobytes()
    document.close()
    return content


@pytest.mark.asyncio
async def test_workspaces_isolate_documents_imports_reviews_audits_and_legacy_data():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def override():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    dependencies = (
        get_guideline_db_session, get_import_db_session, get_import_review_db_session,
        get_review_db_session, get_audit_session,
        get_workspace_session,
    )
    for dependency in dependencies:
        app.dependency_overrides[dependency] = override

    legacy_id = UUID("00000000-0000-4000-8000-000000000001")
    with Session(engine) as session:
        legacy = Workspace(id=legacy_id, kind="legacy")
        session.add(legacy)
        session.flush()
        legacy_fact = ImportedFact(
            workspace_id=legacy_id, claim_type="legacy", approved_statement="Legacy-only evidence.",
            source_filename="legacy.csv", source_row_number=2, source_sha256="f" * 64,
        )
        session.add(legacy_fact)
        session.commit()
        legacy_fact_id = legacy_fact.id

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first_upload = await client.post("/api/v1/guidelines/ingest", files={"files": ("same.pdf", _pdf(), "application/pdf")})
            second_upload = await client.post("/api/v1/guidelines/ingest", files={"files": ("same.pdf", _pdf(), "application/pdf")})
            assert first_upload.status_code == second_upload.status_code == 200
            workspace_a, workspace_b = first_upload.json()["workspace_id"], second_upload.json()["workspace_id"]
            document_a = first_upload.json()["results"][0]["extraction"]["document_id"]
            document_b = second_upload.json()["results"][0]["extraction"]["document_id"]
            assert workspace_a != workspace_b
            assert document_a != document_b

            rules_a = await client.get(f"/api/v1/guidelines/{document_a}/rules", params={"workspace_id": workspace_a})
            rules_b = await client.get(f"/api/v1/guidelines/{document_b}/rules", params={"workspace_id": workspace_b})
            assert rules_a.json()["total"] == rules_b.json()["total"] == 1
            rule_a, rule_b = rules_a.json()["items"][0], rules_b.json()["items"][0]
            assert (await client.post(f"/api/v1/rules/{rule_a['id']}/approve", params={"workspace_id": workspace_a})).status_code == 200
            assert (await client.post(f"/api/v1/rules/{rule_b['id']}/approve", params={"workspace_id": workspace_b})).status_code == 200
            assert (await client.get(f"/api/v1/rules/{rule_a['id']}", params={"workspace_id": workspace_b})).status_code == 404

            facts_a = b"approved_statement,claim_type\nWorkspace A unique statement,capability\n"
            # The exact same bytes and filename are accepted as fresh rows in workspace B.
            facts_b = facts_a
            imported_a = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_a}, files={"file": ("same.csv", facts_a, "text/csv")})
            repeated_a = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_a}, files={"file": ("same.csv", facts_a, "text/csv")})
            imported_b = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_b}, files={"file": ("same.csv", facts_b, "text/csv")})
            assert imported_a.json()["summary"]["rows_imported"] == 1
            assert repeated_a.json()["summary"]["rows_skipped"] == 1
            assert imported_b.json()["summary"]["rows_imported"] == 1

            fact_a = (await client.get("/api/v1/facts", params={"workspace_id": workspace_a})).json()["items"][0]
            fact_b = (await client.get("/api/v1/facts", params={"workspace_id": workspace_b})).json()["items"][0]
            assert fact_a["id"] != fact_b["id"]
            assert fact_a["review_status"] == fact_b["review_status"] == "pending_review"
            assert (await client.post(f"/api/v1/facts/{fact_a['id']}/approve", params={"workspace_id": workspace_a})).status_code == 200
            assert (await client.get(f"/api/v1/facts/{fact_a['id']}", params={"workspace_id": workspace_b})).status_code == 404
            assert (await client.get("/api/v1/facts", params={"workspace_id": workspace_b})).json()["items"][0]["review_status"] == "pending_review"

            terms_a = b"term,preferred_form,category\nshared,sharable,preferred\n"
            terms_b = b"term,category\nshared,banned\n"
            imported_terms_a = await client.post("/api/v1/terms/import", data={"workspace_id": workspace_a}, files={"file": ("same-terms.csv", terms_a, "text/csv")})
            imported_terms_b = await client.post("/api/v1/terms/import", data={"workspace_id": workspace_b}, files={"file": ("same-terms.csv", terms_b, "text/csv")})
            assert imported_terms_a.json()["summary"]["rows_imported"] == 1
            assert imported_terms_b.json()["summary"]["rows_imported"] == 1
            term_a = (await client.get("/api/v1/terms", params={"workspace_id": workspace_a})).json()["items"][0]
            term_b = (await client.get("/api/v1/terms", params={"workspace_id": workspace_b})).json()["items"][0]
            assert (await client.post(f"/api/v1/terms/{term_a['id']}/approve", params={"workspace_id": workspace_a})).status_code == 200
            assert (await client.post(f"/api/v1/terms/{term_b['id']}/reject", params={"workspace_id": workspace_b})).status_code == 200
            assert (await client.get("/api/v1/terms", params={"workspace_id": workspace_a})).json()["items"][0]["review_status"] == "approved"

            # Audit A considers only its own approved rule and fact, even when the copy contains B's text.
            audit = await client.post("/api/v1/audits", json={
                "workspace_id": workspace_a,
                "document_id": document_a,
                "content": "Workspace A unique statement. shared guaranteed",
            })
            assert audit.status_code == 201, audit.text
            audit_body = audit.json()
            assert audit_body["approved_rules_considered"] == 1
            assert all(finding["fact_id"] != fact_b["id"] for finding in audit_body["findings"])
            audit_id = audit_body["id"]
            assert (await client.get(f"/api/v1/audits/{audit_id}", params={"workspace_id": workspace_b})).status_code == 404
            actionable = next((item for item in audit_body["findings"] if item["status"] == "pending_review"), None)
            assert actionable is not None, {"findings": audit_body["findings"], "term_a": term_a}
            assert (await client.post(
                f"/api/v1/audits/{audit_id}/findings/{actionable['id']}/decisions",
                params={"workspace_id": workspace_b}, json={"action": "dismiss"},
            )).status_code == 404
            assert (await client.post(
                f"/api/v1/audits/{audit_id}/findings/{actionable['id']}/decisions",
                params={"workspace_id": workspace_a}, json={"action": "dismiss"},
            )).status_code == 200
            assert (await client.post(
                f"/api/v1/audits/{audit_id}/clearance",
                params={"workspace_id": workspace_b}, json={"decision": "cleared"},
            )).status_code == 404

            restored = await client.get(f"/api/v1/workspaces/{workspace_a}")
            assert restored.status_code == 200
            assert restored.json()["documents"][0]["id"] == document_a
            assert restored.json()["latest_audit_id"] == audit_id
            assert (await client.get("/api/v1/facts", params={"workspace_id": workspace_a})).json()["total"] == 1
            assert (await client.get("/api/v1/facts", params={"workspace_id": workspace_b})).json()["total"] == 1
            assert (await client.get("/api/v1/facts", params={"workspace_id": str(legacy_id)})).status_code == 404

        with Session(engine) as session:
            assert session.get(ImportedFact, legacy_fact_id).approved_statement == "Legacy-only evidence."
    finally:
        for dependency in dependencies:
            app.dependency_overrides.pop(dependency, None)
        Base.metadata.drop_all(engine)
        engine.dispose()
