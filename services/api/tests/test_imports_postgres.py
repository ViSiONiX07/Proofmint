"""Opt-in PostgreSQL CSV idempotency test; all fixture writes are rolled back."""

import os
from hashlib import sha256
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.import_review import get_import_review_db_session
from app.api.imports import get_import_db_session
from app.core.database import DatabaseNotConfiguredError, get_engine
from app.main import app
from app.models.workspace import Workspace


pytestmark = pytest.mark.skipif(
    os.getenv("PROOFMINT_RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set PROOFMINT_RUN_POSTGRES_INTEGRATION=1 to run the rollback-only CSV idempotency test.",
)


@pytest.mark.asyncio
async def test_csv_repeat_import_is_idempotent_and_preserves_review_decisions_on_postgres():
    engine = get_engine()
    try:
        connection = engine.connect()
    except (DatabaseNotConfiguredError, SQLAlchemyError):
        engine.dispose()
        pytest.skip("Configured PostgreSQL server is not reachable.")

    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    workspace = Workspace(kind="session")
    session.add(workspace); session.commit()
    workspace_id = str(workspace.id)
    workspace_params = {"workspace_id": workspace_id}
    token = uuid4().hex
    facts_filename = f"dedup-facts-{token}.csv"
    terms_filename = f"dedup-terms-{token}.csv"
    facts_data = (
        "approved_statement,claim_type\n"
        f"The {token} service supports exports,capability\n"
        f"The {token} service supports exports,capability\n"
        f"The {token} service supports imports,capability\n"
        ",\n"
    ).encode("utf-8")
    terms_data = (
        "term,preferred_form,category,usage_notes\n"
        f"Product-{token},Product-{token},preferred,Use the product name\n"
        f"Product-{token},Product-{token},preferred,Use the product name\n"
        f"Product-{token},Legacy-{token},banned,Do not use the legacy form\n"
    ).encode("utf-8")
    facts_digest = sha256(facts_data).hexdigest()
    terms_digest = sha256(terms_data).hexdigest()

    def override_session():
        try:
            yield session
        finally:
            if session.in_transaction():
                session.rollback()

    app.dependency_overrides[get_import_db_session] = override_session
    app.dependency_overrides[get_import_review_db_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first_facts = await client.post(
                "/api/v1/facts/import", data=workspace_params, files={"file": (facts_filename, facts_data, "text/csv")}
            )
            assert first_facts.status_code == 200, first_facts.text
            assert first_facts.json()["summary"] == {
                "rows_read": 4, "rows_imported": 2, "rows_skipped": 1, "rows_rejected": 1,
            }
            facts = (await client.get("/api/v1/facts", params={**workspace_params, "limit": 100})).json()["items"]
            facts = [row for row in facts if row["source_sha256"] == facts_digest]
            assert len(facts) == 2
            approved = await client.post(f"/api/v1/facts/{facts[0]['id']}/approve", params=workspace_params)
            assert approved.status_code == 200 and approved.json()["review_status"] == "approved"

            first_terms = await client.post(
                "/api/v1/terms/import", data=workspace_params, files={"file": (terms_filename, terms_data, "text/csv")}
            )
            assert first_terms.status_code == 200, first_terms.text
            assert first_terms.json()["summary"] == {
                "rows_read": 3, "rows_imported": 2, "rows_skipped": 1, "rows_rejected": 0,
            }
            terms = (await client.get("/api/v1/terms", params={**workspace_params, "limit": 100})).json()["items"]
            terms = [row for row in terms if row["source_sha256"] == terms_digest]
            assert len(terms) == 2
            assert {row["category"] for row in terms} == {"preferred", "banned"}
            rejected = await client.post(f"/api/v1/terms/{terms[0]['id']}/reject", params=workspace_params)
            assert rejected.status_code == 200 and rejected.json()["review_status"] == "rejected"

            again_facts = await client.post(
                "/api/v1/facts/import", data=workspace_params, files={"file": (facts_filename, facts_data, "text/csv")}
            )
            assert again_facts.status_code == 200
            assert again_facts.json()["summary"] == {
                "rows_read": 4, "rows_imported": 0, "rows_skipped": 3, "rows_rejected": 1,
            }
            again_terms = await client.post(
                "/api/v1/terms/import", data=workspace_params, files={"file": (terms_filename, terms_data, "text/csv")}
            )
            assert again_terms.status_code == 200
            assert again_terms.json()["summary"] == {
                "rows_read": 3, "rows_imported": 0, "rows_skipped": 3, "rows_rejected": 0,
            }

            refreshed_facts = (await client.get("/api/v1/facts", params={**workspace_params, "limit": 100})).json()["items"]
            refreshed_facts = [row for row in refreshed_facts if row["source_sha256"] == facts_digest]
            assert sorted(row["review_status"] for row in refreshed_facts) == ["approved", "pending_review"]
            refreshed_terms = (await client.get("/api/v1/terms", params={**workspace_params, "limit": 100})).json()["items"]
            refreshed_terms = [row for row in refreshed_terms if row["source_sha256"] == terms_digest]
            assert sorted(row["review_status"] for row in refreshed_terms) == ["pending_review", "rejected"]
    finally:
        app.dependency_overrides.pop(get_import_db_session, None)
        app.dependency_overrides.pop(get_import_review_db_session, None)
        if outer.is_active:
            outer.rollback()
        session.close()
        connection.close()
        with engine.connect() as check:
            assert check.execute(
                text("select count(*) from imported_facts where source_sha256 = :digest"),
                {"digest": facts_digest},
            ).scalar_one() == 0
            assert check.execute(
                text("select count(*) from imported_terms where source_sha256 = :digest"),
                {"digest": terms_digest},
            ).scalar_one() == 0
        engine.dispose()
