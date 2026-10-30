import hashlib
from contextlib import contextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.audits import get_audit_session
from app.api.import_review import get_import_review_db_session
from app.api.imports import get_import_db_session
from app.main import app
from app.models import Base
from app.models.audit import AuditFinding, AuditRun
from app.models.imports import ImportedFact, ImportedTerm
from app.models.workspace import Workspace
from uuid import UUID, uuid4


class FakeSession:
    def __init__(self, fail=False):
        self.records = []
        self.did_rollback = False
        self.fail = fail
        self.bind = None
        self.workspace = Workspace(id=uuid4(), kind="session")

    def get(self, model, identity):
        return self.workspace if model is Workspace and identity == self.workspace.id else None

    @contextmanager
    def begin(self):
        try:
            yield
            if self.fail:
                raise SQLAlchemyError("simulated database failure")
        except Exception:
            self.records.clear()
            raise

    def add_all(self, records):
        self.records.extend(records)

    def scalars(self, _statement):
        class EmptyResult:
            @staticmethod
            def all():
                return []

        return EmptyResult()

    def flush(self):
        pass

    def rollback(self):
        self.did_rollback = True
        self.records.clear()


async def upload(path, data, filename="records.csv"):
    fake = FakeSession()
    app.dependency_overrides[get_import_db_session] = lambda: fake
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path, data={"workspace_id": str(fake.workspace.id)}, files={"file": (filename, data, "text/csv")})
        return response, fake
    finally:
        app.dependency_overrides.pop(get_import_db_session, None)


@pytest.mark.asyncio
async def test_facts_import_partially_persists_valid_rows_with_pending_status_and_provenance():
    data = (
        "fact_id,claim_type,approved_statement,source_document,page_span,verified_date,status\n"
        "FACT-001,availability,99.99% availability,Master.pdf,p12,2025-01-15,VERIFIED\n"
        "FACT-002,,Missing type,Master.pdf,p13,2025-01-15,VERIFIED\n"
    ).encode()
    response, session = await upload("/api/v1/facts/import", data, "facts.csv")
    assert response.status_code == 200
    body = response.json()
    assert body["processing_mode"] == "partial_success"
    assert body["review_status"] == "pending_review"
    assert body["summary"] == {"rows_read": 2, "rows_imported": 1, "rows_skipped": 0, "rows_rejected": 1}
    assert body["errors"][0]["row_number"] == 3
    row = session.records[0]
    assert row.external_fact_id == "FACT-001"
    assert row.source_filename == "facts.csv"
    assert row.source_row_number == 2
    assert row.source_sha256 == hashlib.sha256(data).hexdigest()
    assert row.review_status == "pending_review"
    assert row.source_page_span == "p12"


@pytest.mark.asyncio
async def test_terms_import_persists_model_fields_and_review_default():
    data = b"term,preferred_form,category,usage_notes\nProofMint,Proofmint,Brand,Capitalize product\n"
    response, session = await upload("/api/v1/terms/import", data)
    assert response.status_code == 200
    assert response.json()["summary"]["rows_imported"] == 1
    row = session.records[0]
    assert (row.term, row.preferred_form, row.category, row.usage_notes) == (
        "ProofMint", "Proofmint", "Brand", "Capitalize product"
    )
    assert row.review_status == "pending_review"


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", [b"", bytes.fromhex("efbbbf")])
async def test_facts_sample_headers_import_without_or_with_utf8_bom(prefix):
    # Supplied sample's verified header and representative data row.
    data = prefix + (
        "approved_statement,claim_type\n"
        "The product supports secure data processing,security\n"
    ).encode("utf-8")
    response, session = await upload("/api/v1/facts/import", data, "sample_facts_utf8_no_bom.csv")
    assert response.status_code == 200, response.text
    assert response.json()["summary"] == {"rows_read": 1, "rows_imported": 1, "rows_skipped": 0, "rows_rejected": 0}
    assert response.json()["review_status"] == "pending_review"
    assert len(session.records) == 1
    assert session.records[0].approved_statement == "The product supports secure data processing"
    assert session.records[0].claim_type == "security"
    assert session.records[0].review_status == "pending_review"


@pytest.mark.asyncio
async def test_canonical_illustrative_facts_sample_imports_through_api():
    from pathlib import Path

    sample_path = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "web"
        / "public"
        / "templates"
        / "proofmint_facts_illustrative_sample.csv"
    )
    data = sample_path.read_bytes()
    response, session = await upload(
        "/api/v1/facts/import", data, sample_path.name
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"] == {
        "rows_read": 2,
        "rows_imported": 2,
        "rows_skipped": 0,
        "rows_rejected": 0,
    }
    assert body["review_status"] == "pending_review"
    assert [record.claim_type for record in session.records] == [
        "product_capability",
        "availability",
    ]
    assert all(record.review_status == "pending_review" for record in session.records)


@pytest.mark.asyncio
async def test_facts_import_skips_only_completely_empty_leading_line():
    response, session = await upload(
        "/api/v1/facts/import",
        b"\napproved_statement,claim_type\nA verified statement,security\n",
    )
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["rows_imported"] == 1
    assert session.records[0].claim_type == "security"


@pytest.mark.asyncio
@pytest.mark.parametrize("data,detail", [
    (b",claim_type\na,security\n", "CSV header names cannot be blank."),
    (b"approved_statement\na\n", "CSV is missing required headers:"),
    (b"approved_statement,claim_type,other\na,b,c\n", "CSV contains unsupported headers:"),
    (b"\n", "CSV must contain a header row."),
])
async def test_facts_import_rejects_invalid_headers_and_blank_file(data, detail):
    response, session = await upload("/api/v1/facts/import", data)
    assert response.status_code == 400
    assert detail in response.json()["detail"]
    assert session.records == []


@pytest.mark.asyncio
async def test_empty_multipart_file_is_rejected():
    response, session = await upload("/api/v1/facts/import", b"")
    assert response.status_code == 400
    assert response.json()["detail"] == "CSV file is empty."
    assert session.records == []


def test_sample_facts_header_is_accepted_by_parser():
    from app.api.imports import FACT_HEADERS, _parse_csv

    rows = _parse_csv(
        b"approved_statement,claim_type\nThe product supports secure data processing,security\n",
        "sample_facts_utf8_no_bom.csv",
        FACT_HEADERS,
        {"approved_statement", "claim_type"},
    )
    assert rows == [(2, {"approved_statement": "The product supports secure data processing", "claim_type": "security"}, None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("data,detail", [
    (b"", "CSV file is empty."),
    (b"claim_type,approved_statement\n", "CSV contains a header but no data rows."),
    (b"\xff\xfe", "CSV must be encoded as UTF-8."),
    (b"fact_id,claim_type\n1,test\n", "CSV is missing required headers:"),
    (b"term,term\na,b\n", "CSV contains duplicate header names."),
    (b'claim_type,approved_statement\n"unfinished', "CSV syntax is malformed."),
    (b"claim_type,approved_statement,unexpected\na,b,c\n", "CSV contains unsupported headers:"),
])
async def test_invalid_file_is_rejected_without_database_writes(data, detail):
    response, session = await upload("/api/v1/facts/import", data)
    assert response.status_code == 400
    assert detail in response.json()["detail"]
    assert session.records == []


@pytest.mark.asyncio
async def test_row_validation_reports_bad_date_blank_and_column_count():
    data = (
        b"claim_type,approved_statement,verified_date\n"
        b"performance,fast,2025-15-01\n"
        b" ,blank required,\n"
        b"extra,columns,2025-01-01,unexpected\n"
    )
    response, session = await upload("/api/v1/facts/import", data)
    assert response.status_code == 200
    assert response.json()["summary"] == {"rows_read": 3, "rows_imported": 0, "rows_skipped": 0, "rows_rejected": 3}
    assert [item["row_number"] for item in response.json()["errors"]] == [2, 3, 4]
    assert session.records == []


@pytest.mark.asyncio
async def test_non_iso_date_format_is_rejected():
    response, _ = await upload(
        "/api/v1/facts/import",
        b"claim_type,approved_statement,verified_date\nperformance,fast,20250115\n",
    )
    assert response.status_code == 200
    assert response.json()["errors"][0]["errors"]["verified_date"].endswith("YYYY-MM-DD format.")


@pytest.mark.asyncio
async def test_file_and_row_limits_reject_before_persistence(monkeypatch):
    from app.api import imports

    monkeypatch.setattr(imports.settings, "CSV_IMPORT_MAX_FILE_BYTES", 8)
    response, session = await upload("/api/v1/terms/import", b"term\nProofmint\n")
    assert response.status_code == 413
    assert session.records == []

    monkeypatch.setattr(imports.settings, "CSV_IMPORT_MAX_FILE_BYTES", 1024)
    monkeypatch.setattr(imports.settings, "CSV_IMPORT_MAX_ROWS", 1)
    response, session = await upload("/api/v1/terms/import", b"term\na\nb\n")
    assert response.status_code == 413
    assert session.records == []


@pytest.mark.asyncio
async def test_database_failure_returns_service_error_and_rolls_back():
    data = b"term\nProofmint\n"
    fake = FakeSession(fail=True)
    app.dependency_overrides[get_import_db_session] = lambda: fake
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/terms/import", data={"workspace_id": str(fake.workspace.id)}, files={"file": ("terms.csv", data)})
    finally:
        app.dependency_overrides.pop(get_import_db_session, None)
    assert response.status_code == 503
    assert fake.did_rollback
    assert fake.records == []


def test_openapi_registers_both_csv_import_endpoints():
    paths = app.openapi()["paths"]
    assert "/api/v1/facts/import" in paths
    assert "/api/v1/terms/import" in paths


def test_remove_import_batch_is_workspace_scoped_and_preserves_unrelated_rows():
    from app.api.imports import get_import_db_session
    from app.models.imports import ImportedFact
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def database_session():
        with factory() as session:
            yield session
    app.dependency_overrides[get_import_db_session] = database_session
    with factory() as session:
        first, other = Workspace(kind="session"), Workspace(kind="session")
        session.add_all([first, other]); session.flush()
        digest, other_digest = "a" * 64, "b" * 64
        first_record = ImportedFact(workspace_id=first.id, claim_type="capability", approved_statement="First", source_filename="facts.csv", source_row_number=2, source_sha256=digest, review_status="approved")
        same_batch = ImportedFact(workspace_id=first.id, claim_type="capability", approved_statement="Second", source_filename="facts.csv", source_row_number=3, source_sha256=digest)
        unrelated = ImportedFact(workspace_id=first.id, claim_type="capability", approved_statement="Unrelated", source_filename="other.csv", source_row_number=2, source_sha256=other_digest)
        foreign = ImportedFact(workspace_id=other.id, claim_type="capability", approved_statement="Foreign", source_filename="facts.csv", source_row_number=2, source_sha256="c" * 64)
        session.add_all([first_record, same_batch, unrelated, foreign]); session.commit()
        workspace_id, foreign_workspace_id = str(first.id), str(other.id)
    try:
        from fastapi import HTTPException
        from app.api.imports import _remove_import_batch
        with factory() as session:
            with pytest.raises(HTTPException) as denied:
                _remove_import_batch(ImportedFact, "a" * 64, uuid4(), session, "facts")
            assert denied.value.status_code == 404
        # A real second workspace exists, but the batch digest does not occur there.
        with factory() as session:
            with pytest.raises(HTTPException) as foreign_denied:
                _remove_import_batch(ImportedFact, digest, UUID(foreign_workspace_id), session, "facts")
            assert foreign_denied.value.status_code == 404
        with factory() as session:
            removed = _remove_import_batch(ImportedFact, digest, UUID(workspace_id), session, "facts")
            assert removed["removed_count"] == 2
        # A new session verifies both the committed status changes and retained content.
        with factory() as session:
            records = session.query(ImportedFact).order_by(ImportedFact.approved_statement).all()
            assert {r.approved_statement: r.review_status for r in records} == {
                "First": "rejected", "Second": "rejected", "Unrelated": "pending_review", "Foreign": "pending_review",
            }
            assert {r.approved_statement for r in records} == {"First", "Second", "Unrelated", "Foreign"}
        with factory() as session:
            assert _remove_import_batch(ImportedFact, digest, UUID(workspace_id), session, "facts")["removed_count"] == 0
    finally:
        app.dependency_overrides.pop(get_import_db_session, None)
        Base.metadata.drop_all(engine); engine.dispose()


@pytest.mark.asyncio
async def test_csv_import_deduplicates_file_rows_and_preserves_review_statuses():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def database_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_import_db_session] = database_session
    app.dependency_overrides[get_import_review_db_session] = database_session
    with factory() as session:
        workspace = Workspace(kind="session")
        session.add(workspace)
        session.commit()
        workspace_id = str(workspace.id)
    facts_csv = (
        b"approved_statement,claim_type\n"
        b"The service supports exports,capability\n"
        b"The service supports exports,capability\n"
        b"The service supports imports,capability\n"
        b",\n"
    )
    terms_csv = (
        b"term,preferred_form,category,usage_notes\n"
        b"CloudSync,CloudSync,preferred,Use the product name\n"
        b"CloudSync,CloudSync,preferred,Use the product name\n"
        b"CloudSync,Cloud Sync,legacy,Legacy spelling\n"
        b"deprecated,,banned,Do not use\n"
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first_facts = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_id}, files={"file": ("facts.csv", facts_csv, "text/csv")})
            assert first_facts.status_code == 200, first_facts.text
            assert first_facts.json()["summary"] == {
                "rows_read": 4, "rows_imported": 2, "rows_skipped": 1, "rows_rejected": 1,
            }
            listed_facts = (await client.get("/api/v1/facts", params={"workspace_id": workspace_id, "limit": 100})).json()["items"]
            assert len(listed_facts) == 2
            fact_approval = await client.post(f"/api/v1/facts/{listed_facts[0]['id']}/approve", params={"workspace_id": workspace_id})
            assert fact_approval.status_code == 200

            first_terms = await client.post("/api/v1/terms/import", data={"workspace_id": workspace_id}, files={"file": ("terms.csv", terms_csv, "text/csv")})
            assert first_terms.status_code == 200, first_terms.text
            assert first_terms.json()["summary"] == {
                "rows_read": 4, "rows_imported": 3, "rows_skipped": 1, "rows_rejected": 0,
            }
            listed_terms = (await client.get("/api/v1/terms", params={"workspace_id": workspace_id, "limit": 100})).json()["items"]
            assert len(listed_terms) == 3
            assert len([item for item in listed_terms if item["term"] == "CloudSync"]) == 2
            term_rejection = await client.post(f"/api/v1/terms/{listed_terms[0]['id']}/reject", params={"workspace_id": workspace_id})
            assert term_rejection.status_code == 200

            repeated_facts = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_id}, files={"file": ("facts.csv", facts_csv, "text/csv")})
            assert repeated_facts.status_code == 200, repeated_facts.text
            assert repeated_facts.json()["summary"] == {
                "rows_read": 4, "rows_imported": 0, "rows_skipped": 3, "rows_rejected": 1,
            }
            repeated_terms = await client.post("/api/v1/terms/import", data={"workspace_id": workspace_id}, files={"file": ("terms.csv", terms_csv, "text/csv")})
            assert repeated_terms.status_code == 200, repeated_terms.text
            assert repeated_terms.json()["summary"] == {
                "rows_read": 4, "rows_imported": 0, "rows_skipped": 4, "rows_rejected": 0,
            }

            refreshed_facts = (await client.get("/api/v1/facts", params={"workspace_id": workspace_id, "limit": 100})).json()["items"]
            refreshed_terms = (await client.get("/api/v1/terms", params={"workspace_id": workspace_id, "limit": 100})).json()["items"]
            assert len(refreshed_facts) == 2
            assert sorted(item["review_status"] for item in refreshed_facts) == ["approved", "pending_review"]
            assert len(refreshed_terms) == 3
            assert sorted(item["review_status"] for item in refreshed_terms) == [
                "pending_review", "pending_review", "rejected",
            ]
    finally:
        app.dependency_overrides.pop(get_import_db_session, None)
        app.dependency_overrides.pop(get_import_review_db_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def _import_database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def database_session():
        with factory() as session:
            yield session

    return engine, factory, database_session


@pytest.mark.asyncio
async def test_csv_batch_removal_is_selective_allows_reimport_and_preserves_history():
    engine, factory, database_session = _import_database()
    app.dependency_overrides[get_import_db_session] = database_session
    app.dependency_overrides[get_import_review_db_session] = database_session
    app.dependency_overrides[get_audit_session] = database_session
    with factory() as session:
        workspace = Workspace(kind="session")
        session.add(workspace)
        session.commit()
        workspace_id = str(workspace.id)
    facts_one = b"approved_statement,claim_type\nFirst batch claim,capability\n"
    facts_two = b"approved_statement,claim_type\nSecond batch claim,capability\n"
    terms_csv = b"term,preferred_form\nProofMint,Proofmint\n"
    corrected = b"approved_statement,claim_type\nCorrected claim,capability\n"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_id}, files={"file": ("facts-one.csv", facts_one, "text/csv")})
            second = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_id}, files={"file": ("facts-two.csv", facts_two, "text/csv")})
            terms = await client.post("/api/v1/terms/import", data={"workspace_id": workspace_id}, files={"file": ("terms.csv", terms_csv, "text/csv")})
            assert first.status_code == second.status_code == terms.status_code == 200
            listed_facts = (await client.get("/api/v1/facts", params={"workspace_id": workspace_id, "limit": 100})).json()["items"]
            listed_terms = (await client.get("/api/v1/terms", params={"workspace_id": workspace_id, "limit": 100})).json()["items"]
            first_item = next(item for item in listed_facts if item["approved_statement"] == "First batch claim")
            second_item = next(item for item in listed_facts if item["approved_statement"] == "Second batch claim")
            term_item = listed_terms[0]
            assert (await client.post(f"/api/v1/facts/{first_item['id']}/approve", params={"workspace_id": workspace_id})).status_code == 200
            assert (await client.post(f"/api/v1/terms/{term_item['id']}/approve", params={"workspace_id": workspace_id})).status_code == 200

            created = await client.post("/api/v1/audits", json={"workspace_id": workspace_id, "content": "First batch claim and ProofMint"})
            assert created.status_code == 201, created.text
            audit_id = created.json()["id"]
            finding_ids = {finding["id"] for finding in created.json()["findings"]}
            assert finding_ids

            removed_facts = await client.post(
                f"/api/v1/imports/facts/{first_item['source_sha256']}/remove",
                params={"workspace_id": workspace_id},
            )
            assert removed_facts.status_code == 200, removed_facts.text
            assert removed_facts.json()["removed_count"] == 1
            removed_terms = await client.post(
                f"/api/v1/imports/terms/{term_item['source_sha256']}/remove",
                params={"workspace_id": workspace_id},
            )
            assert removed_terms.status_code == 200
            assert removed_terms.json()["removed_count"] == 1

            remaining_facts = (await client.get("/api/v1/facts", params={"workspace_id": workspace_id, "limit": 100, "status": "pending_review"})).json()["items"]
            remaining_approved = (await client.get("/api/v1/facts", params={"workspace_id": workspace_id, "limit": 100, "status": "approved"})).json()["items"]
            assert [item["approved_statement"] for item in remaining_facts] == ["Second batch claim"]
            assert remaining_approved == []
            remaining_terms = (await client.get("/api/v1/terms", params={"workspace_id": workspace_id, "limit": 100, "status": "approved"})).json()["items"]
            assert remaining_terms == []

            replacement = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_id}, files={"file": ("facts-one.csv", facts_one, "text/csv")})
            assert replacement.status_code == 200, replacement.text
            assert replacement.json()["summary"]["rows_imported"] == 1
            corrected_import = await client.post("/api/v1/facts/import", data={"workspace_id": workspace_id}, files={"file": ("facts-one-corrected.csv", corrected, "text/csv")})
            assert corrected_import.json()["summary"]["rows_imported"] == 1

            later = await client.post("/api/v1/audits", json={"workspace_id": workspace_id, "content": "First batch claim and ProofMint"})
            assert later.status_code == 201
            assert later.json()["findings"] == [] or all(
                finding.get("fact_id") != first_item["id"] and finding.get("term_id") != term_item["id"]
                for finding in later.json()["findings"]
            )
            approved_later = await client.post(f"/api/v1/facts/{second_item['id']}/approve", params={"workspace_id": workspace_id})
            assert approved_later.status_code == 200
            with_unrelated = await client.post("/api/v1/audits", json={"workspace_id": workspace_id, "content": "Second batch claim"})
            assert with_unrelated.status_code == 201
            assert any(finding.get("fact_id") == second_item["id"] for finding in with_unrelated.json()["findings"])

            historical = await client.get(f"/api/v1/audits/{audit_id}", params={"workspace_id": workspace_id})
            assert historical.status_code == 200
            assert {finding["id"] for finding in historical.json()["findings"]} == finding_ids
            with factory() as session:
                assert session.get(AuditRun, UUID(audit_id)) is not None
                assert session.query(AuditFinding).filter(AuditFinding.audit_id == UUID(audit_id)).count() == len(finding_ids)
                assert session.get(ImportedFact, UUID(first_item["id"])) is not None
                assert session.get(ImportedTerm, UUID(term_item["id"])) is not None
                assert session.get(ImportedFact, UUID(second_item["id"])).review_status == "approved"
    finally:
        app.dependency_overrides.pop(get_import_db_session, None)
        app.dependency_overrides.pop(get_import_review_db_session, None)
        app.dependency_overrides.pop(get_audit_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_csv_removal_rejects_cross_workspace_and_failed_writes():
    engine, factory, database_session = _import_database()
    app.dependency_overrides[get_import_db_session] = database_session
    app.dependency_overrides[get_import_review_db_session] = database_session
    with factory() as session:
        own, other = Workspace(kind="session"), Workspace(kind="session")
        session.add_all([own, other])
        session.commit()
        own_id, other_id = str(own.id), str(other.id)
    data = b"approved_statement,claim_type\nScoped claim,capability\n"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            imported = await client.post("/api/v1/facts/import", data={"workspace_id": own_id}, files={"file": ("facts.csv", data, "text/csv")})
            digest = (await client.get("/api/v1/facts", params={"workspace_id": own_id})).json()["items"][0]["source_sha256"]
            cross = await client.post(f"/api/v1/imports/facts/{digest}/remove", params={"workspace_id": other_id})
            assert cross.status_code == 404
            invalid = await client.post(f"/api/v1/imports/facts/{'z' * 64}/remove", params={"workspace_id": own_id})
            assert invalid.status_code == 404
            listed = (await client.get("/api/v1/facts", params={"workspace_id": own_id, "status": "pending_review"})).json()["items"]
            assert len(listed) == 1
            assert listed[0]["review_status"] == "pending_review"
            assert imported.status_code == 200
    finally:
        app.dependency_overrides.pop(get_import_db_session, None)
        app.dependency_overrides.pop(get_import_review_db_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_csv_removal_database_failure_does_not_report_success():
    from fastapi import HTTPException
    from app.api.imports import _remove_import_batch

    engine, factory, _database_session = _import_database()
    with factory() as session:
        workspace = Workspace(kind="session")
        session.add(workspace)
        session.flush()
        record = ImportedFact(
            workspace_id=workspace.id, claim_type="capability", approved_statement="Keep me",
            source_filename="facts.csv", source_row_number=2, source_sha256="a" * 64,
            review_status="approved",
        )
        session.add(record)
        session.commit()
        workspace_id, record_id = workspace.id, record.id

    class FailingSession:
        def __init__(self, inner):
            self._inner = inner

        def in_transaction(self):
            return False

        def begin(self):
            class Begun:
                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return Begun()

        def get(self, model, identity):
            return self._inner.get(model, identity)

        def scalars(self, statement):
            return self._inner.scalars(statement)

        def flush(self):
            raise SQLAlchemyError("simulated removal failure")

        def rollback(self):
            self._inner.rollback()

    with factory() as session:
        failing = FailingSession(session)
        with pytest.raises(HTTPException) as error:
            _remove_import_batch(ImportedFact, "a" * 64, workspace_id, failing, "facts")
        assert error.value.status_code == 503
    with factory() as session:
        persisted = session.get(ImportedFact, record_id)
        assert persisted is not None
        assert persisted.review_status == "approved"
    engine.dispose()
    Base.metadata.drop_all(engine)
