"""Opt-in PostgreSQL audit persistence test; all fixture writes roll back."""

import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.audits import get_audit_session
from app.api.workspaces import get_workspace_session
from app.core.database import DatabaseNotConfiguredError, get_engine
from app.main import app
from app.models.audit import AuditRun
from app.models.guideline import CandidateRule, GuidelineDocument
from app.models.workspace import Workspace

pytestmark = pytest.mark.skipif(os.getenv("PROOFMINT_RUN_POSTGRES_INTEGRATION") != "1", reason="Set PROOFMINT_RUN_POSTGRES_INTEGRATION=1 to run rollback-only audit persistence integration.")


@pytest.mark.asyncio
async def test_audit_persistence_and_clearance_on_postgres_with_rollback():
    engine = get_engine()
    try:
        connection = engine.connect()
    except (DatabaseNotConfiguredError, SQLAlchemyError):
        engine.dispose()
        pytest.skip("Configured PostgreSQL server is not reachable.")
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    token = uuid4().hex
    workspace = Workspace(kind="session")
    session.add(workspace); session.flush()
    document = GuidelineDocument(workspace_id=workspace.id, source_filename=f"audit-{token}.pdf", source_sha256="d" * 64, file_size_bytes=10, page_count=1)
    session.add(document); session.flush()
    rule_text = 'Never use “guaranteed”.'
    rule = CandidateRule(document_id=document.id, rule_text=rule_text, category="restriction",
        source_page=1, source_start_offset=0, source_end_offset=len(rule_text), source_excerpt=rule_text, review_status="approved")
    session.add(rule); session.commit()
    doc_id = str(document.id)
    workspace_id = str(workspace.id)
    source_filename = document.source_filename
    session.close()

    def override():
        with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as request_session:
            yield request_session

    app.dependency_overrides[get_audit_session] = override
    app.dependency_overrides[get_workspace_session] = override
    audit_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post("/api/v1/audits", json={"content": "A guaranteed result", "document_id": doc_id, "workspace_id": workspace_id})
            assert created.status_code == 201, created.text
            body = created.json(); audit_id = UUID(body["id"])
            assert body["findings"][0]["matched_phrase"] == "guaranteed"
            assert body["findings"][0]["source_filename"] == source_filename
            # The rule source excerpt is persisted, but the original PDF is not
            # retained for independent re-reading, so the safe status is uncertain.
            assert body["findings"][0]["verification_status"] == "uncertain"
            assert body["findings"][0]["verification_reason"] == "source_document_not_retained"
            with Session(bind=connection, join_transaction_mode="create_savepoint") as check_session:
                assert check_session.get(AuditRun, audit_id) is not None
                assert check_session.execute(
                    text("select count(*) from audit_runs where workspace_id = :workspace_id and content_sha256 = :content_sha256"),
                    {"workspace_id": workspace_id, "content_sha256": body["content_sha256"]},
                ).scalar_one() == 1
            retried = await client.post("/api/v1/audits", json={"content": "A guaranteed result", "document_id": doc_id, "workspace_id": workspace_id})
            assert retried.status_code == 200, retried.text
            assert retried.json()["id"] == body["id"]
            assert retried.json()["findings"] == body["findings"]
            with Session(bind=connection, join_transaction_mode="create_savepoint") as check_session:
                assert check_session.execute(
                    text("select count(*) from audit_runs where workspace_id = :workspace_id and content_sha256 = :content_sha256"),
                    {"workspace_id": workspace_id, "content_sha256": body["content_sha256"]},
                ).scalar_one() == 1
            workspace = await client.get(f"/api/v1/workspaces/{workspace_id}")
            assert workspace.status_code == 200
            assert workspace.json()["latest_audit_id"] == body["id"]
            finding_id = body["findings"][0]["id"]
            decision = await client.post(f"/api/v1/audits/{audit_id}/findings/{finding_id}/decisions?workspace_id={workspace_id}", json={"action": "dismiss"})
            assert decision.status_code == 200, decision.text
            cleared = await client.post(f"/api/v1/audits/{audit_id}/clearance?workspace_id={workspace_id}", json={"decision": "cleared"})
            assert cleared.status_code == 200 and cleared.json()["review_status"] == "cleared"
            persisted = await client.get(f"/api/v1/audits/{audit_id}?workspace_id={workspace_id}")
            assert persisted.status_code == 200
            assert persisted.json()["clearance"]["content_sha256"] == body["content_sha256"]
            findings = await client.get(f"/api/v1/audits/{audit_id}?workspace_id={workspace_id}")
            assert [item["id"] for item in findings.json()["findings"]] == [item["id"] for item in body["findings"]]
            assert findings.json()["findings"][0]["verification_status"] == "uncertain"
    finally:
        app.dependency_overrides.pop(get_audit_session, None)
        app.dependency_overrides.pop(get_workspace_session, None)
        if outer.is_active:
            outer.rollback()
        connection.close()
        with engine.connect() as check:
            if audit_id:
                assert check.execute(text("select count(*) from audit_runs where id = :id"), {"id": audit_id}).scalar_one() == 0
            assert check.execute(text("select count(*) from guideline_documents where source_filename = :filename"), {"filename": source_filename}).scalar_one() == 0
        engine.dispose()
