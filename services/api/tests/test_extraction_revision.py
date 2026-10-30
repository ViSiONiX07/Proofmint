"""Version-aware extraction refresh over malformed historical guideline rules.

These tests seed a workspace holding a pre-refresh extraction (merged heading text and a
fabricated two-column table fragment, exactly as the old segmenter produced) together with
its retained original PDF, then exercise the refresh API against real SQLite rows.
"""

import hashlib
from uuid import UUID

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.audits import get_audit_session
from app.api.candidate_rules import get_review_db_session
from app.api.guidelines import get_guideline_db_session
from app.api.workspaces import get_workspace_session
from app.core.config import settings
from app.main import app
from app.models import Base, CandidateRule, GuidelineDocument, Workspace
from app.services.source_document_store import SourceDocumentStore, page_text
from tests.auth_fixtures import install_authenticated_user

UNQUOTED_RULE = "Never promise guaranteed business outcomes."
QUOTED_RULE = 'Never use the exact phrase "guaranteed" in copy.'
IMPORTED_LINE_ONE = "Imported facts, terminology, and extracted candidate rules must remain"
IMPORTED_LINE_TWO = "pending review until a human approves them."
IMPORTED_RULE = f"{IMPORTED_LINE_ONE}\n{IMPORTED_LINE_TWO}"
MERGED_RULE = f"Human review and clearance\n{IMPORTED_RULE}"
FABRICATED_RULE = "Avoid\ntargets 99.9% monthly service availability"
AUDITED_COPY = "Our guaranteed platform."
GUIDELINE_PAGE = "\n".join([
    UNQUOTED_RULE,
    QUOTED_RULE,
    "5. Writing patterns",
    "Prefer",
    "Avoid",
    "targets 99.9% monthly service availability",
    "6. Human review and clearance",
    IMPORTED_LINE_ONE,
    IMPORTED_LINE_TWO,
])

DEPENDENCIES = (get_guideline_db_session, get_review_db_session, get_audit_session, get_workspace_session)


def make_pdf(*pages: str) -> bytes:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def canonical_page_text(data: bytes) -> str:
    parsed = pymupdf.open(stream=data, filetype="pdf")
    text = page_text(parsed[0])
    parsed.close()
    return text


def span_of(text: str, needle: str) -> tuple[int, int]:
    start = text.index(needle)
    return start, start + len(needle)


def open_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def refresh_db(tmp_path, monkeypatch):
    """Real SQLite rows with a per-request session, matching the production dependency."""
    monkeypatch.setattr(settings, "SOURCE_DOCUMENT_STORAGE_DIR", tmp_path / "source-documents")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def override():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    for dependency in DEPENDENCIES:
        app.dependency_overrides[dependency] = override
    original_enter = AsyncClient.__aenter__
    async def authenticated_enter(client):
        result = await original_enter(client)
        install_authenticated_user(engine, client, email="revision-user@example.test")
        return result
    monkeypatch.setattr(AsyncClient, "__aenter__", authenticated_enter)
    yield engine
    for dependency in DEPENDENCIES:
        app.dependency_overrides.pop(dependency, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


def _rule(document_id, text, span, category, review_status):
    return CandidateRule(
        document_id=document_id, rule_text=text, category=category, source_page=1,
        source_start_offset=span[0], source_end_offset=span[1], source_excerpt=text,
        review_status=review_status,
    )


def malformed_workspace(engine, page: str = GUIDELINE_PAGE):
    """Seed one revision holding the pre-refresh rules and the retained original PDF."""
    data = make_pdf(page)
    digest = hashlib.sha256(data).hexdigest()
    text = canonical_page_text(data)
    with Session(engine, expire_on_commit=False) as session:
        workspace = Workspace(kind="session")
        session.add(workspace)
        session.flush()
        document = GuidelineDocument(
            workspace_id=workspace.id, source_filename="Northstar.pdf", source_sha256=digest,
            file_size_bytes=len(data), page_count=1, extraction_revision=1,
        )
        session.add(document)
        session.flush()
        rows = {
            "rejected": _rule(document.id, UNQUOTED_RULE, span_of(text, UNQUOTED_RULE), "prohibition", "rejected"),
            "approved": _rule(document.id, QUOTED_RULE, span_of(text, QUOTED_RULE), "prohibition", "approved"),
            "merged": _rule(document.id, MERGED_RULE, span_of(text, MERGED_RULE), "prohibition", "approved"),
            "fabricated": _rule(document.id, FABRICATED_RULE, span_of(text, FABRICATED_RULE), "restriction", "pending_review"),
        }
        session.add_all(list(rows.values()))
        session.commit()
        ids = {name: rule.id for name, rule in rows.items()}
        workspace_id, document_id = workspace.id, document.id
    SourceDocumentStore().retain(workspace_id, document_id, digest, data)
    return {"data": data, "digest": digest, "text": text, "workspace_id": workspace_id,
            "document_id": document_id, "rule_ids": ids}


def set_review_status(engine, document_id, text, status):
    with Session(engine) as session:
        session.query(CandidateRule).filter(
            CandidateRule.document_id == document_id, CandidateRule.rule_text == text
        ).update({"review_status": status})
        session.commit()


def rules_for(engine, document_id) -> dict:
    with Session(engine) as session:
        rows = session.scalars(select(CandidateRule).where(CandidateRule.document_id == document_id)
                               .order_by(CandidateRule.source_start_offset)).all()
        return {(rule.source_page, rule.source_start_offset, rule.source_end_offset): rule for rule in rows}


def revision_row(engine, document_id):
    with Session(engine) as session:
        return session.get(GuidelineDocument, UUID(str(document_id)))


def row_counts(engine) -> dict:
    with Session(engine) as session:
        return {
            "documents": session.scalar(select(func.count()).select_from(GuidelineDocument)),
            "rules": session.scalar(select(func.count()).select_from(CandidateRule)),
        }


async def ingest(client, data, workspace_id=None, filename="Northstar.pdf"):
    form = {"workspace_id": str(workspace_id)} if workspace_id is not None else None
    return await client.post("/api/v1/guidelines/ingest", data=form or {},
                             files=[("files", (filename, data, "application/pdf"))])


@pytest.mark.asyncio
async def test_preview_reports_merged_and_fabricated_rules_without_writing(refresh_db):
    """A malformed historical rule set is compared by page and span, and nothing is written."""
    seeded = malformed_workspace(refresh_db)
    before = row_counts(refresh_db)
    async with open_client() as client:
        response = await client.get(
            f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
            params={"workspace_id": str(seeded["workspace_id"])},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_revision"] == 1
    assert body["next_revision"] == 2
    assert body["already_current"] is False
    assert body["existing_rule_count"] == 4
    assert body["extracted_rule_count"] == 3
    assert (body["unchanged_count"], body["changed_count"], body["added_count"], body["removed_count"]) == (2, 0, 1, 2)
    assert body["source_sha256"] == seeded["digest"]
    assert body["document_id"] == str(seeded["document_id"])

    comparisons = body["comparisons"]
    merged_span = span_of(seeded["text"], MERGED_RULE)
    removed_spans = {(item["source_page"], item["source_start_offset"], item["source_end_offset"])
                     for item in comparisons if item["comparison"] == "removed"}
    assert removed_spans == {(1, *merged_span), (1, *span_of(seeded["text"], FABRICATED_RULE))}
    # The stored merged text is reported verbatim beside the corrected rule, never rewritten.
    merged = next(item for item in comparisons if item["comparison"] == "removed"
                  and item["source_start_offset"] == merged_span[0])
    assert merged["existing_rule_text"] == MERGED_RULE
    assert merged["existing_rule_id"] == str(seeded["rule_ids"]["merged"])
    assert merged["existing_review_status"] == "approved"
    assert merged["extracted_rule_text"] is None

    added = next(item for item in comparisons if item["comparison"] == "added")
    assert added["extracted_rule_text"] == IMPORTED_RULE
    assert added["source_start_offset"] == span_of(seeded["text"], IMPORTED_RULE)[0]
    assert added["source_end_offset"] == span_of(seeded["text"], IMPORTED_RULE)[1]

    unchanged = [item for item in comparisons if item["comparison"] == "unchanged"]
    assert {item["existing_review_status"] for item in unchanged} == {"approved", "rejected"}
    assert all(item["decision_carried_forward"] for item in unchanged)
    assert {item["extracted_rule_text"] for item in unchanged} == {UNQUOTED_RULE, QUOTED_RULE}
    # Every span addresses the page it came from.
    for item in comparisons:
        assert item["source_page"] == 1
        assert item["source_start_offset"] < item["source_end_offset"]
    assert row_counts(refresh_db) == before


@pytest.mark.asyncio
async def test_apply_creates_immutable_revision_and_preserves_prior_revision(refresh_db):
    """Refresh writes a new revision that keeps provenance and leaves revision 1 untouched."""
    seeded = malformed_workspace(refresh_db)
    before_revision = rules_for(refresh_db, seeded["document_id"])
    async with open_client() as client:
        response = await client.post(
            f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
            params={"workspace_id": str(seeded["workspace_id"])},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    revision_id = UUID(body["document_id"])
    assert body["already_existed"] is False
    assert body["extraction_revision"] == 2
    assert body["supersedes_document_id"] == str(seeded["document_id"])
    assert body["source_sha256"] == seeded["digest"]
    assert body["source_filename"] == "Northstar.pdf"
    assert body["page_count"] == 1
    assert body["candidate_rule_count"] == 3
    assert body["approved_rule_count"] == 1
    assert body["rejected_rule_count"] == 1
    assert body["pending_rule_count"] == 1
    assert body["carried_forward_decisions"] == 2
    assert body["removed_rule_count"] == 2
    assert body["document_id"] != str(seeded["document_id"])

    revision = revision_row(refresh_db, revision_id)
    assert revision.extraction_revision == 2
    assert revision.supersedes_document_id == seeded["document_id"]
    assert revision.workspace_id == seeded["workspace_id"]
    assert revision.page_count == 1
    assert revision.file_size_bytes == len(seeded["data"])
    assert revision.extraction_signature is not None
    # The refreshed revision carries its own verifiable copy of the identical source bytes.
    assert SourceDocumentStore().read_verified(revision) == seeded["data"]

    refreshed = rules_for(refresh_db, revision_id)
    assert len(refreshed) == 3
    assert {rule.rule_text: rule.review_status for rule in refreshed.values()} == {
        QUOTED_RULE: "approved", UNQUOTED_RULE: "rejected", IMPORTED_RULE: "pending_review",
    }
    # The malformed rules are not carried into the new revision.
    assert not any(rule.rule_text in (MERGED_RULE, FABRICATED_RULE) for rule in refreshed.values())
    for rule in refreshed.values():
        assert rule.id not in set(seeded["rule_ids"].values())

    # Revision 1 keeps its exact rows, IDs, and human decisions.
    after_revision = rules_for(refresh_db, seeded["document_id"])
    assert after_revision.keys() == before_revision.keys()
    assert {rule.id for rule in after_revision.values()} == set(seeded["rule_ids"].values())
    for rule in after_revision.values():
        assert rule.rule_text == before_revision[(rule.source_page, rule.source_start_offset, rule.source_end_offset)].rule_text
        assert rule.review_status == before_revision[(rule.source_page, rule.source_start_offset, rule.source_end_offset)].review_status


@pytest.mark.asyncio
async def test_repeating_the_refresh_creates_no_duplicate_revision_or_rules(refresh_db):
    """A second refresh of the same source and extractor is a no-op replay."""
    seeded = malformed_workspace(refresh_db)
    async with open_client() as client:
        first = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                  params={"workspace_id": str(seeded["workspace_id"])})
        assert first.status_code == 201, first.text
        after_first = row_counts(refresh_db)
        assert after_first == {"documents": 2, "rules": 7}

        preview = await client.get(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                   params={"workspace_id": str(seeded["workspace_id"])})
        assert preview.status_code == 200, preview.text
        assert preview.json()["already_current"] is True
        assert preview.json()["current_revision"] == 2
        # next_revision is always current + 1: the number a refresh would take if it were needed.
        assert preview.json()["next_revision"] == 3
        assert preview.json()["removed_count"] == 0

        # Naming the older revision still resolves to the newest revision of the lineage.
        second = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                   params={"workspace_id": str(seeded["workspace_id"])})
        assert second.status_code == 200, second.text
        assert second.json()["already_existed"] is True
        assert second.json()["document_id"] == first.json()["document_id"]
        assert second.json()["extraction_revision"] == 2

        third = await client.post(f"/api/v1/guidelines/{first.json()['document_id']}/extraction-revision",
                                  params={"workspace_id": str(seeded["workspace_id"])})
        assert third.status_code == 200, third.text
        assert third.json()["already_existed"] is True
    assert row_counts(refresh_db) == after_first


@pytest.mark.asyncio
async def test_a_freshly_ingested_document_is_already_current(refresh_db):
    """A document extracted by the corrected extractor needs no refresh."""
    async with open_client() as client:
        ingested = await ingest(client, make_pdf(GUIDELINE_PAGE))
        assert ingested.status_code == 200, ingested.text
        workspace_id = ingested.json()["workspace_id"]
        document_id = ingested.json()["results"][0]["extraction"]["document_id"]
        assert ingested.json()["results"][0]["extraction"]["candidate_rule_count"] == 3
        before = row_counts(refresh_db)

        preview = await client.get(f"/api/v1/guidelines/{document_id}/extraction-revision",
                                   params={"workspace_id": workspace_id})
        assert preview.status_code == 200, preview.text
        assert preview.json()["already_current"] is True
        assert preview.json()["current_revision"] == 1
        assert preview.json()["next_revision"] == 2
        assert preview.json()["extracted_rule_count"] == 3
        assert preview.json()["removed_count"] == 0

        applied = await client.post(f"/api/v1/guidelines/{document_id}/extraction-revision",
                                    params={"workspace_id": workspace_id})
        assert applied.status_code == 200, applied.text
        assert applied.json()["already_existed"] is True
        assert applied.json()["document_id"] == document_id
        assert applied.json()["extraction_revision"] == 1
    assert row_counts(refresh_db) == before


@pytest.mark.asyncio
async def test_missing_retained_pdf_refuses_refresh_and_explains_recovery(refresh_db):
    """A missing source is refused with the recovery path instead of guessing."""
    seeded = malformed_workspace(refresh_db)
    SourceDocumentStore().path_for(seeded["workspace_id"], seeded["document_id"], seeded["digest"]).unlink()
    before = row_counts(refresh_db)
    async with open_client() as client:
        preview = await client.get(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                   params={"workspace_id": str(seeded["workspace_id"])})
        assert preview.status_code == 409
        assert "not in private server-side storage" in preview.json()["detail"]
        assert "Re-upload the exact original PDF" in preview.json()["detail"]

        applied = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                    params={"workspace_id": str(seeded["workspace_id"])})
        assert applied.status_code == 409
        assert "not in private server-side storage" in applied.json()["detail"]
        assert "Re-upload the exact original PDF" in applied.json()["detail"]
    assert row_counts(refresh_db) == before


@pytest.mark.asyncio
async def test_hash_mismatched_retained_pdf_refuses_refresh(refresh_db):
    """Bytes that no longer match the recorded hash are refused, and the fixed recovery works."""
    seeded = malformed_workspace(refresh_db)
    path = SourceDocumentStore().path_for(seeded["workspace_id"], seeded["document_id"], seeded["digest"])
    path.write_bytes(seeded["data"] + b"tampered")
    before = row_counts(refresh_db)
    async with open_client() as client:
        response = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                     params={"workspace_id": str(seeded["workspace_id"])})
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "no longer match the SHA-256" in detail
        assert "never overwrites an object whose bytes do not match its recorded hash" in detail
        assert row_counts(refresh_db) == before

        # An upload never silently replaces a mismatched object, even with the exact original.
        refused = await ingest(client, seeded["data"], workspace_id=seeded["workspace_id"])
        assert refused.status_code == 200
        assert refused.json()["results"][0]["status"] == "error"
        assert refused.json()["results"][0]["error_code"] == "stored_source_hash_mismatch"
        assert path.read_bytes() == seeded["data"] + b"tampered"

        # The documented path: an operator clears the corrupted object, then the exact original restores it.
        path.unlink()
        restored = await ingest(client, seeded["data"], workspace_id=seeded["workspace_id"])
        assert restored.status_code == 200, restored.text
        assert restored.json()["results"][0]["status"] == "success"
        assert restored.json()["results"][0]["extraction"]["retention_status"] == "restored"
        assert path.read_bytes() == seeded["data"]

        applied = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                    params={"workspace_id": str(seeded["workspace_id"])})
        assert applied.status_code == 201, applied.text
    assert row_counts(refresh_db) == {"documents": 2, "rules": 7}


@pytest.mark.asyncio
async def test_unknown_or_cross_workspace_document_is_not_found(refresh_db):
    """Refresh never reaches outside its workspace."""
    seeded = malformed_workspace(refresh_db)
    from uuid import uuid4

    foreign_workspace = uuid4()
    async with open_client() as client:
        missing = await client.get(f"/api/v1/guidelines/{foreign_workspace}/extraction-revision",
                                   params={"workspace_id": str(seeded["workspace_id"])})
        assert missing.status_code == 404
        cross = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                  params={"workspace_id": str(foreign_workspace)})
        assert cross.status_code == 404
        assert row_counts(refresh_db) == {"documents": 1, "rules": 4}


@pytest.mark.asyncio
async def test_historical_audit_keeps_its_rule_and_source_version_after_refresh(refresh_db):
    """Existing audits keep the exact rule IDs and source version they originally used."""
    seeded = malformed_workspace(refresh_db)
    workspace_id = str(seeded["workspace_id"])
    async with open_client() as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(seeded["document_id"]), "workspace_id": workspace_id, "content": AUDITED_COPY,
        })
        assert created.status_code == 201, created.text
        audit = created.json()
        finding = audit["findings"][0]
        assert finding["rule_id"] == str(seeded["rule_ids"]["approved"])
        assert finding["source_document_id"] == str(seeded["document_id"])
        assert finding["source_document_sha256"] == seeded["digest"]
        assert finding["verification_status"] == "verified"
        audit_id = audit["id"]

        applied = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                    params={"workspace_id": workspace_id})
        assert applied.status_code == 201, applied.text

        historical = await client.get(f"/api/v1/audits/{audit_id}", params={"workspace_id": workspace_id})
        assert historical.status_code == 200, historical.text
        assert historical.json() == audit
        assert historical.json()["document_id"] == str(seeded["document_id"])
        assert historical.json()["findings"][0]["rule_id"] == str(seeded["rule_ids"]["approved"])
        assert historical.json()["findings"][0]["source_document_id"] == str(seeded["document_id"])

        # The audit still reloads through the workspace history pointer.
        workspace = await client.get(f"/api/v1/workspaces/{workspace_id}")
        assert workspace.status_code == 200, workspace.text
        assert workspace.json()["latest_audit_id"] == audit_id


@pytest.mark.asyncio
async def test_new_audits_use_approved_refreshed_rules_and_ignore_pending_ones(refresh_db):
    """New audits follow the refreshed revision once approved, and never the pending candidates."""
    seeded = malformed_workspace(refresh_db)
    workspace_id = str(seeded["workspace_id"])
    async with open_client() as client:
        applied = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                    params={"workspace_id": workspace_id})
        assert applied.status_code == 201, applied.text
        revision_id = applied.json()["document_id"]

        refreshed = rules_for(refresh_db, UUID(revision_id))
        carried_approved = next(rule for rule in refreshed.values() if rule.rule_text == QUOTED_RULE)
        pending_rule = next(rule for rule in refreshed.values() if rule.rule_text == IMPORTED_RULE)
        assert carried_approved.review_status == "approved"

        audit = await client.post("/api/v1/audits", json={
            "document_id": revision_id, "workspace_id": workspace_id, "content": AUDITED_COPY,
        })
        assert audit.status_code == 201, audit.text
        body = audit.json()
        assert body["document_id"] == revision_id
        assert body["approved_rules_considered"] == 1
        assert [item["rule_id"] for item in body["findings"]] == [str(carried_approved.id)]
        assert body["findings"][0]["source_document_id"] == revision_id
        assert body["findings"][0]["verification_status"] == "verified"
        assert not any(item["rule_id"] == str(pending_rule.id) for item in body["findings"])

        approved = await client.post(f"/api/v1/rules/{pending_rule.id}/approve",
                                     params={"workspace_id": workspace_id})
        assert approved.status_code == 200, approved.text
        assert approved.json()["review_status"] == "approved"

        after_approval = await client.post("/api/v1/audits", json={
            "document_id": revision_id, "workspace_id": workspace_id, "content": AUDITED_COPY,
        })
        assert after_approval.status_code == 201, after_approval.text
        assert after_approval.json()["id"] != body["id"]
        assert after_approval.json()["approved_rules_considered"] == 2


@pytest.mark.asyncio
async def test_refresh_without_approved_rules_does_not_leave_audits_checking_nothing(refresh_db):
    """While a refreshed revision is unreviewed, audits keep using the approved older revision."""
    seeded = malformed_workspace(refresh_db)
    workspace_id = str(seeded["workspace_id"])
    # The only approved rule is the malformed merged one, which the corrected extractor drops.
    set_review_status(refresh_db, seeded["document_id"], QUOTED_RULE, "rejected")
    set_review_status(refresh_db, seeded["document_id"], UNQUOTED_RULE, "pending_review")
    async with open_client() as client:
        applied = await client.post(f"/api/v1/guidelines/{seeded['document_id']}/extraction-revision",
                                    params={"workspace_id": workspace_id})
        assert applied.status_code == 201, applied.text
        assert applied.json()["approved_rule_count"] == 0
        revision_id = applied.json()["document_id"]

        audit = await client.post("/api/v1/audits", json={
            "document_id": revision_id, "workspace_id": workspace_id, "content": "A calm product update.",
        })
        assert audit.status_code == 201, audit.text
        body = audit.json()
        assert body["document_id"] == str(seeded["document_id"])
        assert body["approved_rules_considered"] == 1
        assert any("still in human review" in item for item in body["scope_limitations"])

        rerun = await client.post("/api/v1/audits", json={
            "document_id": revision_id, "workspace_id": workspace_id, "content": "A calm product update.",
        })
        assert rerun.status_code == 200, rerun.text
        assert rerun.json()["id"] == body["id"]
