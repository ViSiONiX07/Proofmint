"""Opt-in PostgreSQL review integration test. All test writes are rolled back."""

import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.import_review import get_import_review_db_session
from app.core.database import DatabaseNotConfiguredError, get_engine
from app.main import app
from app.models.imports import ImportedFact, ImportedTerm
from app.models.workspace import Workspace


pytestmark = pytest.mark.skipif(
    os.getenv("PROOFMINT_RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set PROOFMINT_RUN_POSTGRES_INTEGRATION=1 to run the rollback-only PostgreSQL review test.",
)


@pytest.mark.asyncio
async def test_imported_fact_and_term_review_lifecycle_against_postgres_with_rollback():
    engine = get_engine()
    try:
        connection = engine.connect()
    except (DatabaseNotConfiguredError, SQLAlchemyError):
        engine.dispose()
        pytest.skip("Configured PostgreSQL server is not reachable.")

    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    token = uuid4().hex
    filename = f"review-{token}.csv"
    digest = "a" * 64
    workspace = Workspace(kind="session")
    session.add(workspace); session.flush()
    facts = [
        ImportedFact(workspace_id=workspace.id, claim_type="performance", approved_statement=f"Fact {token}", source_filename=filename,
                     source_row_number=row, source_sha256=digest)
        for row in (2, 3)
    ]
    terms = [
        ImportedTerm(workspace_id=workspace.id, term=f"Term {token} {index}", source_filename=filename,
                     source_row_number=index + 4, source_sha256=digest)
        for index in range(2)
    ]
    session.add_all(facts + terms)
    session.flush()
    fact_ids = [str(item.id) for item in facts]
    term_ids = [str(item.id) for item in terms]
    workspace_id = str(workspace.id)
    params = {"workspace_id": workspace_id}
    # Commit only the Session's savepoint; the enclosing connection transaction remains rollback-only.
    session.commit()

    def override_session():
        try:
            yield session
        finally:
            if session.in_transaction():
                session.rollback()

    app.dependency_overrides[get_import_review_db_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in ("facts", "terms"):
                listed = await client.get(f"/api/v1/{path}", params={**params, "status": "pending_review", "limit": 1})
                assert listed.status_code == 200, listed.text
                assert listed.json()["limit"] == 1
                assert listed.json()["total"] == 2
                assert len(listed.json()["items"]) == 1

            fact_detail = await client.get(f"/api/v1/facts/{fact_ids[0]}", params=params)
            assert fact_detail.status_code == 200, fact_detail.text
            fact_before = fact_detail.json()
            assert fact_before["review_status"] == "pending_review"
            assert fact_before["source_filename"] == filename
            assert fact_before["source_row_number"] == 2
            assert fact_before["source_sha256"] == digest

            term_detail = await client.get(f"/api/v1/terms/{term_ids[0]}", params=params)
            assert term_detail.status_code == 200, term_detail.text
            term_before = term_detail.json()
            assert term_before["review_status"] == "pending_review"
            assert term_before["source_filename"] == filename
            assert term_before["source_row_number"] == 4
            assert term_before["source_sha256"] == digest

            for path, record_id, target in (
                ("facts", fact_ids[0], "approve"),
                ("facts", fact_ids[1], "reject"),
                ("terms", term_ids[0], "approve"),
                ("terms", term_ids[1], "reject"),
            ):
                response = await client.post(f"/api/v1/{path}/{record_id}/{target}", params=params)
                assert response.status_code == 200, response.text
                assert response.json()["review_status"] == ("approved" if target == "approve" else "rejected")
                repeat = await client.post(f"/api/v1/{path}/{record_id}/{target}", params=params)
                assert repeat.status_code == 409
                opposite = "reject" if target == "approve" else "approve"
                assert (await client.post(f"/api/v1/{path}/{record_id}/{opposite}", params=params)).status_code == 409

            fact_after = (await client.get(f"/api/v1/facts/{fact_ids[0]}", params=params)).json()
            term_after = (await client.get(f"/api/v1/terms/{term_ids[0]}", params=params)).json()
            for before, after in ((fact_before, fact_after), (term_before, term_after)):
                for field in ("source_filename", "source_row_number", "source_sha256", "imported_at"):
                    assert after[field] == before[field]
                assert after["review_status"] == "approved"

            # A fresh list request (the same contract used when reopening Step 2)
            # must include reviewed rows and their persisted server status.
            refreshed_facts = (await client.get("/api/v1/facts", params={**params, "limit": 100})).json()["items"]
            refreshed_terms = (await client.get("/api/v1/terms", params={**params, "limit": 100})).json()["items"]
            facts_by_id = {row["id"]: row["review_status"] for row in refreshed_facts}
            terms_by_id = {row["id"]: row["review_status"] for row in refreshed_terms}
            assert facts_by_id[fact_ids[0]] == "approved"
            assert facts_by_id[fact_ids[1]] == "rejected"
            assert terms_by_id[term_ids[0]] == "approved"
            assert terms_by_id[term_ids[1]] == "rejected"

            missing = str(uuid4())
            assert (await client.get(f"/api/v1/facts/{missing}", params=params)).status_code == 404
            assert (await client.post(f"/api/v1/terms/{missing}/approve", params=params)).status_code == 404
            assert (await client.get("/api/v1/facts/not-a-uuid")).status_code == 422

        persisted = session.scalars(select(ImportedFact).where(ImportedFact.id.in_([item.id for item in facts]))).all()
        assert {item.review_status for item in persisted} == {"approved", "rejected"}
        assert connection.execute(
            text("select count(*) from imported_terms where source_filename = :filename"),
            {"filename": filename},
        ).scalar_one() == 2
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()
        session.close()
        connection.close()
        app.dependency_overrides.pop(get_import_review_db_session, None)
        with engine.connect() as check:
            assert check.execute(
                text("select count(*) from imported_facts where source_filename = :filename"),
                {"filename": filename},
            ).scalar_one() == 0
            assert check.execute(
                text("select count(*) from imported_terms where source_filename = :filename"),
                {"filename": filename},
            ).scalar_one() == 0
        engine.dispose()
