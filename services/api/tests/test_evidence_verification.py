import hashlib
from pathlib import Path
from uuid import uuid4

import pymupdf
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, CandidateRule, GuidelineDocument, ImportedFact, ImportedTerm, Workspace
from app.core.config import settings
from app.services.audit_engine import evaluate_copy
from app.services.evidence_verification import verify_finding, verify_findings
from app.services.repair_engine import build_repair_preview
from app.services.source_document_store import SourceDocumentStore, page_text


def test_verifier_checks_spans_workspace_approval_and_persisted_source_provenance():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    workspace_id, other_workspace_id = uuid4(), uuid4()
    try:
        with Session(engine, expire_on_commit=False) as session:
            workspace = Workspace(id=workspace_id, kind="session")
            other = Workspace(id=other_workspace_id, kind="session")
            session.add_all([workspace, other])
            session.flush()
            rule_text = 'Never say “guaranteed”.'
            document = GuidelineDocument(workspace_id=workspace_id, source_filename="brand.pdf",
                source_sha256="a" * 64, file_size_bytes=100, page_count=1)
            session.add(document)
            session.flush()
            rule = CandidateRule(document_id=document.id, rule_text=rule_text, category="restriction",
                source_page=1, source_start_offset=10, source_end_offset=10 + len(rule_text),
                source_excerpt=rule_text, review_status="approved")
            pending_rule = CandidateRule(document_id=document.id, rule_text=rule_text, category="restriction",
                source_page=1, source_start_offset=50, source_end_offset=50 + len(rule_text),
                source_excerpt=rule_text, review_status="pending_review")
            fact = ImportedFact(workspace_id=workspace_id, claim_type="capability",
                approved_statement="The service supports CSV exports.", source_filename="facts.csv",
                source_row_number=2, source_sha256="b" * 64, review_status="approved")
            term = ImportedTerm(workspace_id=workspace_id, term="ProofMint", preferred_form="Proofmint",
                source_filename="terms.csv", source_row_number=2, source_sha256="c" * 64,
                review_status="approved")
            session.add_all([rule, pending_rule, fact, term])
            session.commit()

            content = "A guaranteed service."
            findings, *_ = evaluate_copy(content, [rule], [], [])
            verified = verify_findings(session, findings, content, workspace_id)[0]
            assert (verified["verification_status"], verified["verification_reason"]) == (
                "uncertain", "source_document_not_retained")

            bad_offsets = {**findings[0], "match_start": -1}
            assert verify_finding(session, bad_offsets, content, workspace_id).reason_code == "invalid_offsets"
            span_mismatch = {**findings[0], "matched_phrase": "unrelated"}
            assert verify_finding(session, span_mismatch, content, workspace_id).reason_code == "span_mismatch"
            bad_source = {**findings[0], "source_page": None}
            assert verify_finding(session, bad_source, content, workspace_id).reason_code == "source_reference_invalid"
            assert verify_finding(session, findings[0], content, other_workspace_id).reason_code == "workspace_mismatch"
            assert verify_finding(session, {**findings[0], "rule_id": uuid4()}, content, workspace_id).reason_code == "source_reference_missing"

            pending_finding = {**findings[0], "rule_id": pending_rule.id}
            assert verify_finding(session, pending_finding, content, workspace_id).reason_code == "rule_not_approved"

            fact_text = "The service supports CSV exports."
            fact_findings, *_ = evaluate_copy(fact_text, [], [fact], [])
            assert verify_findings(session, fact_findings, fact_text, workspace_id)[0]["verification_status"] == "verified"
            term_text = "Our ProofMint platform."
            term_findings, *_ = evaluate_copy(term_text, [], [], [term])
            verified_term_finding = verify_findings(session, term_findings, term_text, workspace_id)[0]
            assert verified_term_finding["verification_status"] == "verified"
            repair_finding = type("Finding", (), {**verified_term_finding, "id": uuid4()})()
            repaired, replacements = build_repair_preview(session, term_text, workspace_id, [repair_finding])
            assert repaired == "Our Proofmint platform."
            assert len(replacements) == 1 and replacements[0]["start"] == 4
            try:
                build_repair_preview(session, "Our stale ProofMint platform.", workspace_id, [repair_finding])
            except ValueError as exc:
                assert "stale or invalid source span" in str(exc)
            else:
                raise AssertionError("Stale repair span was not rejected.")

            term.review_status = "pending_review"
            session.flush()
            assert verify_finding(session, term_findings[0], term_text, workspace_id).reason_code == "term_not_approved"

            unsupported, *_ = evaluate_copy("It doubles every customer's revenue.", [], [], [])
            assert unsupported == []
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_retained_pdf_independent_verification_and_integrity_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SOURCE_DOCUMENT_STORAGE_DIR", tmp_path / "private-sources")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    workspace_id, other_workspace_id = uuid4(), uuid4()
    pdf_doc = pymupdf.open()
    page = pdf_doc.new_page()
    page.insert_text((72, 72), 'Never say "guaranteed".')
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()
    parsed = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    excerpt = page_text(parsed[0])
    parsed.close()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    store = SourceDocumentStore()
    try:
        with Session(engine, expire_on_commit=False) as session:
            workspace = Workspace(id=workspace_id, kind="session")
            other = Workspace(id=other_workspace_id, kind="session")
            document = GuidelineDocument(workspace_id=workspace_id, source_filename="Northstar.pdf",
                source_sha256=digest, file_size_bytes=len(pdf_bytes), page_count=1)
            session.add_all([workspace, other, document]); session.flush()
            rule = CandidateRule(document_id=document.id, rule_text=excerpt, category="restriction",
                source_page=1, source_start_offset=0, source_end_offset=len(excerpt),
                source_excerpt=excerpt, review_status="approved")
            session.add(rule); session.commit()

            content = "A guaranteed platform."
            findings, *_ = evaluate_copy(content, [rule], [], [])
            finding = findings[0]
            assert finding["source_document_id"] == document.id
            assert finding["source_document_sha256"] == digest
            missing = verify_finding(session, finding, content, workspace_id)
            assert (missing.status, missing.reason_code) == ("uncertain", "source_document_not_retained")

            assert store.retain(workspace_id, document.id, digest, pdf_bytes) == "retained"
            valid = verify_finding(session, finding, content, workspace_id)
            assert (valid.status, valid.reason_code) == ("verified", None)

            source_path = store.path_for(workspace_id, document.id, digest)
            original_read_bytes = Path.read_bytes
            def inaccessible(path):
                if path == source_path:
                    raise PermissionError("test-only simulated source access denial")
                return original_read_bytes(path)
            monkeypatch.setattr(Path, "read_bytes", inaccessible)
            denied = verify_finding(session, finding, content, workspace_id)
            assert (denied.status, denied.reason_code) == ("uncertain", "source_document_inaccessible")
            monkeypatch.setattr(Path, "read_bytes", original_read_bytes)

            cross_workspace = verify_finding(session, finding, content, other_workspace_id)
            assert (cross_workspace.status, cross_workspace.reason_code) == ("rejected", "workspace_mismatch")
            wrong_version = verify_finding(session, {**finding, "source_document_sha256": "b" * 64}, content, workspace_id)
            assert wrong_version.reason_code == "source_version_mismatch"

            wrong_page = {**finding, "source_page": 2}
            assert verify_finding(session, wrong_page, content, workspace_id).reason_code == "source_reference_invalid"
            rule.source_page = 2
            session.flush()
            assert verify_finding(session, {**finding, "source_page": 2}, content, workspace_id).reason_code == "source_page_invalid"
            rule.source_page = 1
            session.flush()

            original_start, original_end = rule.source_start_offset, rule.source_end_offset
            rule.source_start_offset += 1
            rule.source_end_offset += 1
            session.flush()
            wrong_span = {**finding, "source_start_offset": rule.source_start_offset,
                "source_end_offset": rule.source_end_offset}
            assert verify_finding(session, wrong_span, content, workspace_id).reason_code == "source_span_mismatch"
            rule.source_start_offset, rule.source_end_offset = original_start, original_end
            session.flush()

            source_path.write_bytes(b"corrupted PDF bytes")
            corrupted = verify_finding(session, finding, content, workspace_id)
            assert (corrupted.status, corrupted.reason_code) == ("rejected", "source_hash_mismatch")
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
