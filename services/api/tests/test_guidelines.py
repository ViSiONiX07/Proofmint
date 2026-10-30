import hashlib
from types import SimpleNamespace
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.audits import get_audit_session
from app.api.guidelines import get_guideline_db_session
from app.core.config import settings
from app.models import AuditFinding, AuditRun, Base, CandidateRule, GuidelineDocument, User, Workspace
from app.main import app
from app.services.source_document_store import SourceDocumentStore, page_text
from tests.auth_fixtures import install_authenticated_user


class FakeSession:
    """Small transaction-aware unit-test session; live PostgreSQL is verified separately."""

    def __init__(self):
        self.records = []
        self.fail_transaction = False
        self.rolled_back = False

    @contextmanager
    def begin(self):
        starting_count = len(self.records)
        try:
            yield
            if self.fail_transaction:
                raise SQLAlchemyError("simulated database write failure")
        except Exception:
            del self.records[starting_count:]
            raise

    def add_all(self, records):
        self.records.extend(records)

    def add(self, _record):
        # The workspace is represented by its UUID in this in-memory route fixture.
        pass

    def flush(self):
        for record in self.records:
            if record.id is None:
                record.id = uuid4()
            if record.created_at is None:
                record.created_at = datetime.now(timezone.utc)

    def refresh(self, record, attribute_names=None):
        pass

    def rollback(self):
        self.records.clear()
        self.rolled_back = True


@pytest.fixture(autouse=True)
def guideline_database_session(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SOURCE_DOCUMENT_STORAGE_DIR", tmp_path / "source-documents")
    session = FakeSession()
    auth_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(auth_engine)
    app.dependency_overrides[get_guideline_db_session] = lambda: session
    original_enter = AsyncClient.__aenter__
    async def authenticated_enter(client):
        result = await original_enter(client)
        engine = auth_engine
        for override in app.dependency_overrides.values():
            closure = getattr(override, "__closure__", None) or ()
            for cell in closure:
                value = cell.cell_contents
                candidate = value if isinstance(value, type(auth_engine)) else getattr(value, "bind", None)
                if candidate is not None and candidate is not auth_engine:
                    engine = candidate
                    break
        install_authenticated_user(engine, client, email="guideline-user@example.test")
        return result
    monkeypatch.setattr(AsyncClient, "__aenter__", authenticated_enter)
    yield session
    app.dependency_overrides.pop(get_guideline_db_session, None)
    auth_engine.dispose()


def make_pdf(*pages: str) -> bytes:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def make_image_only_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), 0)
    pixmap.clear_with(255)
    page.insert_image(page.rect, pixmap=pixmap)
    data = document.tobytes()
    document.close()
    return data


async def post_files(files):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/guidelines/ingest", files=files)


@pytest.mark.asyncio
async def test_extract_single_page_sha_and_span_offsets(guideline_database_session):
    original = make_pdf("Brand voice stays measured.")
    response = await post_files([("files", ("guide.pdf", original, "application/pdf"))])
    assert response.status_code == 200
    body = response.json()
    item = body["results"][0]["extraction"]
    assert item["sha256"] == hashlib.sha256(original).hexdigest()
    assert item["page_count"] == 1
    document = guideline_database_session.records[0]
    assert item["document_id"] == str(document.id)
    assert item["created_at"] is not None
    assert document.source_filename == "guide.pdf"
    assert document.source_sha256 == hashlib.sha256(original).hexdigest()
    assert document.file_size_bytes == len(original)
    assert document.page_count == 1
    page = item["pages"][0]
    assert page["page_number"] == 1
    assert "Brand voice stays measured." in page["text"]
    assert page["spans"]
    for span in page["spans"]:
        assert page["text"][span["start_offset"]:span["end_offset"]] == span["text"]
        assert span["page_number"] == 1
    assert item["retention_status"] == "retained"
    assert SourceDocumentStore().read_verified(document) == original


@pytest.mark.asyncio
async def test_exact_pdf_reupload_recovers_same_workspace_document_and_historical_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SOURCE_DOCUMENT_STORAGE_DIR", tmp_path / "private-sources")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    workspace_id, document_id, audit_id = uuid4(), uuid4(), uuid4()
    original = make_pdf('Never say "guaranteed".')
    parsed = pymupdf.open(stream=original, filetype="pdf")
    excerpt = page_text(parsed[0])
    parsed.close()
    digest = hashlib.sha256(original).hexdigest()
    store = SourceDocumentStore()
    try:
        with Session(engine, expire_on_commit=False) as session:
            workspace = Workspace(id=workspace_id, kind="session")
            document = GuidelineDocument(id=document_id, workspace_id=workspace_id, source_filename="Northstar.pdf",
                source_sha256=digest, file_size_bytes=len(original), page_count=1)
            rule = CandidateRule(document_id=document_id, rule_text=excerpt, category="restriction", source_page=1,
                source_start_offset=0, source_end_offset=len(excerpt), source_excerpt=excerpt, review_status="approved")
            content = "Our guaranteed platform."
            audit = AuditRun(id=audit_id, workspace_id=workspace_id, document_id=document_id,
                content_sha256=hashlib.sha256(content.encode()).hexdigest(), character_count=len(content),
                approved_rules_considered=1, supported_checks_performed=1, rules_unevaluated=0,
                scope_limitations="[]", review_status="pending_review")
            session.add_all([workspace, document, rule, audit]); session.flush()
            start = content.index("guaranteed")
            finding = AuditFinding(audit_id=audit_id, rule_id=rule.id, source_document_id=document_id,
                source_document_sha256=digest, finding_type="restricted_phrase", status="pending_review",
                matched_phrase="guaranteed", match_start=start, match_end=start + len("guaranteed"),
                explanation="This literal phrase appears in an approved rule that explicitly prohibits or restricts it.",
                suggested_correction=None, source_filename="Northstar.pdf", source_page=1,
                source_start_offset=0, source_end_offset=len(excerpt), evidence_excerpt=excerpt,
                verification_status="uncertain", verification_reason="source_document_not_retained",
                verification_explanation="The exact source PDF is unavailable for independent verification.")
            session.add(finding); session.commit()
            original_finding_id, original_rule_id = finding.id, rule.id

            def db_override():
                yield session

            app.dependency_overrides[get_guideline_db_session] = db_override
            app.dependency_overrides[get_audit_session] = db_override
            data = {"workspace_id": str(workspace_id)}
            files = [("files", ("Northstar.pdf", original, "application/pdf"))]
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                install_authenticated_user(engine, client, email="guideline-reupload@example.test")
                with Session(engine) as auth_db:
                    user_id = auth_db.query(User).filter_by(email="guideline-reupload@example.test").one().id
                session.get(Workspace, workspace_id).owner_user_id = user_id
                session.commit()
                wrong_copy = await client.post(f"/api/v1/audits/{audit_id}/verify-source-evidence?workspace_id={workspace_id}",
                    json={"content": content + " changed"})
                assert wrong_copy.status_code == 409
                missing_source = await client.post(f"/api/v1/audits/{audit_id}/verify-source-evidence?workspace_id={workspace_id}",
                    json={"content": content})
                assert missing_source.status_code == 200
                assert missing_source.json()["findings"][0]["verification_reason"] == "source_document_not_retained"

                restored = await client.post("/api/v1/guidelines/ingest", data=data, files=files)
                assert restored.status_code == 200, restored.text
                extraction = restored.json()["results"][0]["extraction"]
                assert restored.json()["workspace_id"] == str(workspace_id)
                assert extraction["document_id"] == str(document_id)
                assert extraction["retention_status"] == "restored"
                assert session.scalar(select(func.count()).select_from(GuidelineDocument).where(
                    GuidelineDocument.workspace_id == workspace_id)) == 1
                assert session.scalar(select(func.count()).select_from(CandidateRule).where(
                    CandidateRule.document_id == document_id)) == 1
                assert store.read_verified(document) == original
                session.commit()

                duplicate_source = await client.post("/api/v1/guidelines/ingest", data=data,
                    files=[("files", ("Northstar.pdf", original, "application/pdf"))])
                assert duplicate_source.status_code == 200
                assert duplicate_source.json()["results"][0]["extraction"]["document_id"] == str(document_id)
                assert duplicate_source.json()["results"][0]["extraction"]["retention_status"] == "already_retained"
                assert session.scalar(select(func.count()).select_from(CandidateRule).where(
                    CandidateRule.document_id == document_id)) == 1
                session.commit()

                rechecked = await client.post(f"/api/v1/audits/{audit_id}/verify-source-evidence?workspace_id={workspace_id}",
                    json={"content": content})
                assert rechecked.status_code == 200, rechecked.text
                result = rechecked.json()
                assert result["id"] == str(audit_id)
                saved_finding = result["findings"][0]
                assert saved_finding["id"] == str(original_finding_id)
                assert saved_finding["rule_id"] == str(original_rule_id)
                assert saved_finding["source_document_id"] == str(document_id)
                assert saved_finding["source_document_sha256"] == digest
                assert saved_finding["verification_status"] == "verified"
                assert result["content_sha256"] == hashlib.sha256(content.encode()).hexdigest()

                # A different PDF in the same workspace is a new source version;
                # the historical audit remains tied to its original document.
                newer_pdf = make_pdf("New guideline version.")
                new_upload = await client.post("/api/v1/guidelines/ingest", data=data,
                    files=[("files", ("Northstar.pdf", newer_pdf, "application/pdf"))])
                assert new_upload.status_code == 200, new_upload.text
                newer_document_id = new_upload.json()["results"][0]["extraction"]["document_id"]
                assert newer_document_id != str(document_id)
                unchanged_history = await client.get(f"/api/v1/audits/{audit_id}?workspace_id={workspace_id}")
                assert unchanged_history.status_code == 200
                assert unchanged_history.json()["document_id"] == str(document_id)
                assert unchanged_history.json()["findings"][0]["source_document_id"] == str(document_id)
    finally:
        app.dependency_overrides.pop(get_guideline_db_session, None)
        app.dependency_overrides.pop(get_audit_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()

@pytest.mark.asyncio
async def test_guideline_remove_is_workspace_scoped_and_fails_closed_without_lifecycle_column(tmp_path, monkeypatch):
    from app.api.guidelines import get_guideline_db_session
    from app.models import Workspace, AuditRun
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def database_session():
        with factory() as session:
            yield session
    app.dependency_overrides[get_guideline_db_session] = database_session
    with factory() as session:
        own_workspace, foreign_workspace = Workspace(kind="session"), Workspace(kind="session")
        session.add_all([own_workspace, foreign_workspace]); session.flush()
        document = GuidelineDocument(workspace_id=own_workspace.id, source_filename="preserved.pdf", source_sha256="a" * 64, file_size_bytes=100, page_count=1)
        session.add(document); session.flush()
        historical = AuditRun(workspace_id=own_workspace.id, document_id=document.id, content_sha256="b" * 64, character_count=1, approved_rules_considered=0, supported_checks_performed=0, rules_unevaluated=0, scope_limitations="[]", review_status="pending_review")
        session.add(historical); session.commit()
        document_id, workspace_id = str(document.id), str(own_workspace.id)
        historical_id = historical.id
        foreign_workspace_id = str(foreign_workspace.id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            install_authenticated_user(engine, client, email="guideline-remove@example.test")
            foreign = await client.post(f"/api/v1/guidelines/{document_id}/remove", params={"workspace_id": foreign_workspace_id})
            assert foreign.status_code == 404
            blocked = await client.post(f"/api/v1/guidelines/{document_id}/remove", params={"workspace_id": workspace_id})
            assert blocked.status_code == 501
        with factory() as session:
            assert session.get(GuidelineDocument, UUID(document_id)) is not None
            assert session.query(AuditRun).filter_by(id=historical_id).count() == 1
    finally:
        app.dependency_overrides.pop(get_guideline_db_session, None)
        Base.metadata.drop_all(engine); engine.dispose()


@pytest.mark.asyncio
async def test_reuploading_same_pdf_starts_a_distinct_workspace(guideline_database_session):
    data = make_pdf("Never claim guaranteed revenue.")
    first = await post_files([("files", ("same.pdf", data, "application/pdf"))])
    second = await post_files([("files", ("same.pdf", data, "application/pdf"))])
    assert first.status_code == second.status_code == 200
    assert first.json()["workspace_id"] != second.json()["workspace_id"]
    assert first.json()["results"][0]["extraction"]["document_id"] != second.json()["results"][0]["extraction"]["document_id"]


@pytest.mark.asyncio
async def test_multi_page_and_blank_page():
    response = await post_files([("files", ("multi.pdf", make_pdf("First page", "", "Third page"), "application/pdf"))])
    item = response.json()["results"][0]["extraction"]
    assert item["page_count"] == 3
    assert [page["page_number"] for page in item["pages"]] == [1, 2, 3]
    assert item["pages"][1]["text"] == ""
    assert item["pages"][1]["spans"] == []


@pytest.mark.asyncio
async def test_batch_partial_success_and_content_type_does_not_override_content(guideline_database_session):
    response = await post_files([
        ("files", ("a.pdf", make_pdf("valid"), "application/pdf")),
        ("files", ("bad.pdf", b"not a pdf", "application/pdf")),
        ("files", ("misnamed.bin", make_pdf("still a PDF"), "application/octet-stream")),
    ])
    body = response.json()
    assert body["processing_mode"] == "partial_success"
    assert [r["status"] for r in body["results"]] == ["success", "error", "success"]
    assert body["summary"]["files_received"] == 3
    assert body["summary"]["files_succeeded"] == 2
    assert body["summary"]["files_rejected"] == 1
    assert {record.source_filename for record in guideline_database_session.records} == {"a.pdf", "misnamed.bin"}
    assert {item["extraction"]["document_id"] for item in body["results"] if item["status"] == "success"} == {
        str(record.id) for record in guideline_database_session.records
    }


@pytest.mark.asyncio
async def test_multiple_successful_pdfs_have_correctly_associated_records(guideline_database_session):
    first = make_pdf("first document")
    second = make_pdf("second document", "second page")
    response = await post_files([
        ("files", ("first.pdf", first, "application/pdf")),
        ("files", ("second.pdf", second, "application/pdf")),
    ])
    assert response.status_code == 200
    results = response.json()["results"]
    by_name = {record.source_filename: record for record in guideline_database_session.records}
    assert set(by_name) == {"first.pdf", "second.pdf"}
    assert results[0]["extraction"]["document_id"] == str(by_name["first.pdf"].id)
    assert results[1]["extraction"]["document_id"] == str(by_name["second.pdf"].id)
    assert by_name["first.pdf"].source_sha256 == hashlib.sha256(first).hexdigest()
    assert by_name["first.pdf"].file_size_bytes == len(first)
    assert by_name["first.pdf"].page_count == 1
    assert by_name["second.pdf"].source_sha256 == hashlib.sha256(second).hexdigest()
    assert by_name["second.pdf"].file_size_bytes == len(second)
    assert by_name["second.pdf"].page_count == 2


@pytest.mark.asyncio
async def test_pdf_upload_persists_candidate_source_and_pending_review(guideline_database_session):
    source = make_pdf("Marketing claims must be supported by current evidence.")
    response = await post_files([("files", ("rules.pdf", source, "application/pdf"))])
    assert response.status_code == 200
    extraction = response.json()["results"][0]["extraction"]
    document = next(record for record in guideline_database_session.records if isinstance(record, GuidelineDocument))
    candidate = next(record for record in guideline_database_session.records if isinstance(record, CandidateRule))
    page_text = extraction["pages"][0]["text"]
    assert extraction["candidate_rule_count"] == 1
    assert candidate.document_id == document.id == UUID(extraction["document_id"])
    assert candidate.source_page == 1
    assert page_text[candidate.source_start_offset:candidate.source_end_offset] == candidate.source_excerpt
    assert candidate.rule_text == candidate.source_excerpt
    assert candidate.review_status == "pending_review"


@pytest.mark.asyncio
async def test_pdf_without_normative_text_persists_document_with_zero_candidates(guideline_database_session):
    response = await post_files([(
        "files", ("neutral.pdf", make_pdf("Our brand speaks with clarity and warmth."), "application/pdf")
    )])
    assert response.status_code == 200
    extraction = response.json()["results"][0]["extraction"]
    assert extraction["candidate_rule_count"] == 0
    assert len([record for record in guideline_database_session.records if isinstance(record, GuidelineDocument)]) == 1
    assert not any(isinstance(record, CandidateRule) for record in guideline_database_session.records)


@pytest.mark.asyncio
async def test_candidate_extraction_failure_creates_no_document_or_rules(monkeypatch, guideline_database_session):
    from app.api import guidelines

    def fail_extraction(_pages):
        raise RuntimeError("internal extraction detail")

    monkeypatch.setattr(guidelines, "extract_candidate_rules", fail_extraction)
    response = await post_files([("files", ("failure.pdf", make_pdf("A useful brand statement."), "application/pdf"))])
    outcome = response.json()["results"][0]
    assert response.status_code == 200
    assert outcome["status"] == "error"
    assert outcome["error_code"] == "candidate_extraction_failed"
    assert "internal extraction detail" not in outcome["message"]
    assert guideline_database_session.records == []


@pytest.mark.asyncio
@pytest.mark.parametrize("filename,data,code", [
    ("empty.pdf", b"", "empty_file"),
    ("spoof.pdf", b"not really a pdf", "invalid_pdf"),
    ("broken.pdf", b"%PDF-1.7 broken", "invalid_pdf"),
])
async def test_invalid_inputs_have_safe_file_level_errors(filename, data, code, guideline_database_session):
    response = await post_files([("files", (filename, data, "application/pdf"))])
    result = response.json()["results"][0]
    assert result["status"] == "error"
    assert result["error_code"] == code
    assert "Traceback" not in result["message"]
    assert result["extraction"] is None
    assert guideline_database_session.records == []


@pytest.mark.asyncio
async def test_image_only_pdf_is_not_reported_as_text_extracted():
    response = await post_files([("files", ("scanned.pdf", make_image_only_pdf(), "application/pdf"))])
    result = response.json()["results"][0]
    assert result["error_code"] == "no_extractable_text"
    assert result["extraction"] is None


@pytest.mark.asyncio
async def test_file_size_limit_is_enforced(monkeypatch):
    from app.api import guidelines

    monkeypatch.setattr(guidelines.settings, "GUIDELINE_MAX_FILE_BYTES", 64)
    response = await post_files([("files", ("large.pdf", make_pdf("x" * 200), "application/pdf"))])
    assert response.json()["results"][0]["error_code"] == "file_too_large"


@pytest.mark.asyncio
async def test_request_size_limit_and_file_count(monkeypatch):
    from app.api import guidelines

    monkeypatch.setattr(guidelines.settings, "GUIDELINE_MAX_FILE_BYTES", 1024 * 1024)
    monkeypatch.setattr(guidelines.settings, "GUIDELINE_MAX_REQUEST_BYTES", 1500)
    pdf = make_pdf("valid")
    response = await post_files([
        ("files", ("one.pdf", pdf, "application/pdf")),
        ("files", ("two.pdf", pdf, "application/pdf")),
    ])
    assert response.json()["results"][0]["status"] == "success"
    assert response.json()["results"][1]["error_code"] == "request_too_large"

    monkeypatch.setattr(guidelines.settings, "GUIDELINE_MAX_FILES", 1)
    response = await post_files([
        ("files", ("one.pdf", pdf, "application/pdf")),
        ("files", ("two.pdf", pdf, "application/pdf")),
    ])
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_raw_multipart_body_limit_rejects_before_file_parsing(monkeypatch):
    from app.core import upload_limits

    monkeypatch.setattr(upload_limits.settings, "GUIDELINE_MAX_REQUEST_BYTES", 1)
    monkeypatch.setattr(upload_limits.settings, "GUIDELINE_MAX_MULTIPART_OVERHEAD_BYTES", 0)
    response = await post_files([("files", ("guide.pdf", make_pdf("body cap"), "application/pdf"))])
    assert response.status_code == 413
    assert response.json()["detail"] == "Multipart request body exceeds the configured upload limit."


@pytest.mark.asyncio
async def test_page_limit_and_password_protection(monkeypatch):
    from app.api import guidelines

    monkeypatch.setattr(guidelines.settings, "GUIDELINE_MAX_PAGES", 1)
    response = await post_files([("files", ("many.pdf", make_pdf("page 1", "page 2"), "application/pdf"))])
    assert response.json()["results"][0]["error_code"] == "too_many_pages"

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "locked")
    locked = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    document.close()
    response = await post_files([("files", ("locked.pdf", locked, "application/pdf"))])
    assert response.json()["results"][0]["error_code"] == "password_protected"


@pytest.mark.asyncio
async def test_upload_file_objects_are_closed(guideline_database_session):
    from starlette.datastructures import UploadFile as StarletteUploadFile
    from io import BytesIO

    upload = StarletteUploadFile(filename="guide.pdf", file=BytesIO(make_pdf("close me")), headers={"content-type": "application/pdf"})
    from app.api.guidelines import ingest_guidelines
    request = SimpleNamespace(state=SimpleNamespace(
        principal=SimpleNamespace(
            role="user",
            session=SimpleNamespace(role="user", id=uuid4()),
            user=SimpleNamespace(id=uuid4()),
        )
    ))
    coroutine = ingest_guidelines(request=request, files=[upload], session=guideline_database_session, workspace_id=None)
    with pytest.raises(StopIteration):
        coroutine.send(None)
    assert upload.file.closed


@pytest.mark.asyncio
async def test_database_failure_returns_503_and_rolls_back_all_records(guideline_database_session):
    guideline_database_session.fail_transaction = True
    response = await post_files([
        ("files", ("first.pdf", make_pdf("first"), "application/pdf")),
        ("files", ("second.pdf", make_pdf("second"), "application/pdf")),
    ])
    assert response.status_code == 503
    assert "no documents from this request were committed" in response.json()["detail"]
    assert guideline_database_session.rolled_back
    assert guideline_database_session.records == []


@pytest.mark.asyncio
async def test_existing_root_and_health_routes_still_work():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/")).status_code == 200
        assert (await client.get("/api/v1/health")).json()["status"] == "healthy"
        schema = (await client.get("/openapi.json")).json()
        assert "/api/v1/guidelines/ingest" in schema["paths"]
