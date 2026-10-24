"""Opt-in local PostgreSQL API integration test; all writes are rolled back."""

import os
from uuid import UUID, uuid4

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.candidate_rules import get_review_db_session
from app.api.guidelines import get_guideline_db_session
from app.core.database import DatabaseNotConfiguredError, get_engine
from app.main import app


pytestmark = pytest.mark.skipif(
    os.getenv("PROOFMINT_RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set PROOFMINT_RUN_POSTGRES_INTEGRATION=1 to run the rollback-only PostgreSQL API test.",
)


def _make_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "Claims must cite current sources in all marketing assets. "
        "Never promise guaranteed business outcomes to customers.",
    )
    data = document.tobytes()
    document.close()
    return data


@pytest.mark.asyncio
async def test_pdf_candidates_review_lifecycle_against_postgres_with_rollback():
    engine = get_engine()
    try:
        connection = engine.connect()
    except (DatabaseNotConfiguredError, SQLAlchemyError):
        engine.dispose()
        pytest.skip("Configured PostgreSQL server is not reachable.")

    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    token = uuid4().hex
    filename = f"candidate-review-{token}.pdf"

    def override_session():
        try:
            yield session
        finally:
            if session.in_transaction():
                session.rollback()

    app.dependency_overrides[get_guideline_db_session] = override_session
    app.dependency_overrides[get_review_db_session] = override_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            upload = await client.post(
                "/api/v1/guidelines/ingest",
                files=[
                    ("files", (filename, _make_pdf(), "application/pdf")),
                    ("files", (f"invalid-{token}.pdf", b"not a PDF", "application/pdf")),
                ],
            )
            assert upload.status_code == 200, upload.text
            upload_body = upload.json()
            assert [entry["status"] for entry in upload_body["results"]] == ["success", "error"]
            extracted = upload_body["results"][0]["extraction"]
            workspace_id = upload_body["workspace_id"]
            document_id = extracted["document_id"]
            assert extracted["candidate_rule_count"] == 2

            by_document = await client.get(f"/api/v1/guidelines/{document_id}/rules", params={"workspace_id": workspace_id})
            assert by_document.status_code == 200, by_document.text
            candidates = by_document.json()["items"]
            assert len(candidates) == 2
            assert all(candidate["review_status"] == "pending_review" for candidate in candidates)
            assert all(candidate["source_filename"] == filename for candidate in candidates)
            for candidate in candidates:
                page_text = extracted["pages"][candidate["source_page"] - 1]["text"]
                assert page_text[candidate["source_start_offset"]:candidate["source_end_offset"]] == candidate["source_excerpt"]

            pending = await client.get("/api/v1/rules/pending", params={"document_id": document_id, "workspace_id": workspace_id})
            assert pending.status_code == 200
            assert pending.json()["total"] == 2

            first_id, second_id = [candidate["id"] for candidate in candidates]
            detail = await client.get(f"/api/v1/rules/{first_id}", params={"workspace_id": workspace_id})
            assert detail.status_code == 200
            assert detail.json()["document_id"] == document_id
            approved = await client.post(f"/api/v1/rules/{first_id}/approve", params={"workspace_id": workspace_id})
            assert approved.status_code == 200
            assert approved.json()["review_status"] == "approved"
            repeat_approval = await client.post(f"/api/v1/rules/{first_id}/approve", params={"workspace_id": workspace_id})
            assert repeat_approval.status_code == 409
            pending_after = await client.get("/api/v1/rules/pending", params={"document_id": document_id, "workspace_id": workspace_id})
            assert pending_after.json()["total"] == 1

            rejected = await client.post(f"/api/v1/rules/{second_id}/reject", params={"workspace_id": workspace_id})
            assert rejected.status_code == 200
            assert rejected.json()["review_status"] == "rejected"
            invalid_transition = await client.post(f"/api/v1/rules/{second_id}/approve", params={"workspace_id": workspace_id})
            assert invalid_transition.status_code == 409

            missing = str(uuid4())
            assert (await client.get(f"/api/v1/rules/{missing}", params={"workspace_id": workspace_id})).status_code == 404
            assert (await client.post(f"/api/v1/rules/{missing}/approve", params={"workspace_id": workspace_id})).status_code == 404
            assert (await client.get("/api/v1/rules/not-a-uuid")).status_code == 422

        stored = connection.execute(
            text("select count(*) from candidate_rules where document_id = :document_id"),
            {"document_id": UUID(document_id)},
        ).scalar_one()
        assert stored == 2
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()
        session.close()
        connection.close()
        app.dependency_overrides.pop(get_guideline_db_session, None)
        app.dependency_overrides.pop(get_review_db_session, None)
        with engine.connect() as check:
            leftovers = check.execute(
                text("select count(*) from guideline_documents where source_filename = :filename"),
                {"filename": filename},
            ).scalar_one()
        assert leftovers == 0
        engine.dispose()
