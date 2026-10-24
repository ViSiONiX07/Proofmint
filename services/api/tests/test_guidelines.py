import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.guidelines import get_guideline_db_session
from app.models.guideline import CandidateRule, GuidelineDocument
from app.main import app


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
def guideline_database_session():
    session = FakeSession()
    app.dependency_overrides[get_guideline_db_session] = lambda: session
    yield session
    app.dependency_overrides.pop(get_guideline_db_session, None)


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
    coroutine = ingest_guidelines([upload], guideline_database_session)
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
