from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.audits import get_audit_session
from app.api.workspaces import get_workspace_session
from app.main import app
from app.models import Base, CandidateRule, GuidelineDocument, ImportedFact, ImportedTerm, Workspace
from app.models.audit import AuditFinding, AuditRun
from tests.auth_fixtures import install_authenticated_user


@pytest.fixture
def audit_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        workspace = Workspace(kind="session")
        session.add(workspace); session.flush()
        document = GuidelineDocument(workspace_id=workspace.id, source_filename="brand.pdf", source_sha256="a" * 64, file_size_bytes=12, page_count=1)
        session.add(document); session.flush()
        rule_text = 'Never use “guaranteed”.'
        pending_text = 'Never use “pending-only”.'
        rule = CandidateRule(document_id=document.id, rule_text=rule_text, category="restriction",
            source_page=1, source_start_offset=0, source_end_offset=len(rule_text), source_excerpt=rule_text, review_status="approved")
        pending = CandidateRule(document_id=document.id, rule_text=pending_text, category="restriction",
            source_page=1, source_start_offset=31, source_end_offset=31 + len(pending_text), source_excerpt=pending_text, review_status="pending_review")
        fact = ImportedFact(workspace_id=workspace.id, claim_type="capability", approved_statement="The platform supports CSV exports.", source_filename="facts.csv", source_row_number=2, source_sha256="b" * 64, review_status="approved")
        term = ImportedTerm(workspace_id=workspace.id, term="ProofMint", preferred_form="Proofmint", source_filename="terms.csv", source_row_number=2, source_sha256="c" * 64, review_status="approved")
        rejected = ImportedFact(workspace_id=workspace.id, claim_type="capability", approved_statement="Rejected statement.", source_filename="facts.csv", source_row_number=3, source_sha256="b" * 64, review_status="rejected")
        session.add_all([rule, pending, fact, term, rejected]); session.commit()
        doc_id = document.id
        workspace_id = workspace.id
    def override():
        with Session(engine, expire_on_commit=False) as session:
            yield session
    app.dependency_overrides[get_audit_session] = override
    app.dependency_overrides[get_workspace_session] = override
    original_enter = AsyncClient.__aenter__
    async def authenticated_enter(client):
        result = await original_enter(client)
        install_authenticated_user(engine, client, email="audit-user@example.test")
        return result
    monkeypatch.setattr(AsyncClient, "__aenter__", authenticated_enter)
    yield doc_id, workspace_id, engine
    app.dependency_overrides.pop(get_audit_session, None)
    app.dependency_overrides.pop(get_workspace_session, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.mark.asyncio
async def test_audit_api_persists_run_findings_decision_and_clearance_with_hash(audit_db):
    document_id, workspace_id, _engine = audit_db
    content = "Our guaranteed platform is ProofMint. The platform supports CSV exports."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={"document_id": str(document_id), "workspace_id": str(workspace_id), "content": content})
        assert created.status_code == 201, created.text
        audit = created.json()
        assert audit["character_count"] == len(content)
        assert audit["approved_rules_considered"] == 1
        assert len(audit["findings"]) == 3
        assert {f["finding_type"] for f in audit["findings"]} == {"restricted_phrase", "preferred_terminology", "approved_fact_match"}
        assert any(f["source_filename"] == "brand.pdf" and f["source_page"] == 1 for f in audit["findings"])
        rule_finding = next(f for f in audit["findings"] if f["finding_type"] == "restricted_phrase")
        assert rule_finding["verification_status"] == "uncertain"
        assert rule_finding["verification_reason"] == "source_document_not_retained"
        assert all(f["verification_status"] == "verified" for f in audit["findings"] if f["finding_type"] != "restricted_phrase")
        run_id = audit["id"]
        unsupported_fact = next(f for f in audit["findings"] if f["finding_type"] == "approved_fact_match")
        assert unsupported_fact["verification_status"] == "verified"
        assert unsupported_fact["suggested_correction"] is None
        with Session(_engine) as session:
            session.query(AuditFinding).filter_by(id=UUID(unsupported_fact["id"])).update({"status": "pending_review"})
            session.commit()
        refetched = await client.get(f"/api/v1/audits/{run_id}", params={"workspace_id": str(workspace_id)})
        assert refetched.status_code == 200, refetched.text
        assert refetched.json()["id"] == run_id
        audit = refetched.json()
        unsupported_fact = next(f for f in audit["findings"] if f["id"] == unsupported_fact["id"])
        assert unsupported_fact["status"] == "pending_review"
        workspace = await client.get(f"/api/v1/workspaces/{workspace_id}")
        assert workspace.status_code == 200, workspace.text
        assert workspace.json()["latest_audit_id"] == run_id
        repair = await client.post(f"/api/v1/audits/{run_id}/repair", params={"workspace_id": str(workspace_id)}, json={"content": content})
        assert repair.status_code == 200, repair.text
        assert repair.json()["status"] == "preview_available"
        assert repair.json()["findings_reviewed"] == 3
        assert repair.json()["repaired_content"] == "Our guaranteed platform is Proofmint. The platform supports CSV exports."
        assert len(repair.json()["replacements"]) == 1
        assert repair.json()["findings_before"] == 3
        assert repair.json()["findings_after"] == 2
        assert unsupported_fact["status"] == "pending_review"
        assert unsupported_fact["id"] not in {item["finding_id"] for item in repair.json()["replacements"]}
        mismatch = await client.post(f"/api/v1/audits/{run_id}/repair", params={"workspace_id": str(workspace_id)}, json={"content": content + " changed"})
        assert mismatch.status_code == 409
        assert "run a new audit" in mismatch.json()["detail"].lower()
        unchanged = await client.get(f"/api/v1/audits/{run_id}", params={"workspace_id": str(workspace_id)})
        assert unchanged.json()["content_sha256"] == audit["content_sha256"]
        assert unchanged.json()["findings"] == audit["findings"]
        actionable = [f for f in audit["findings"] if f["status"] == "pending_review"]
        params = {"workspace_id": str(workspace_id)}
        blocked = await client.post(f"/api/v1/audits/{run_id}/clearance", params=params, json={"decision": "cleared"})
        assert blocked.status_code == 409
        for finding in actionable:
            decision = await client.post(f"/api/v1/audits/{run_id}/findings/{finding['id']}/decisions", params=params, json={"action": "dismiss"})
            assert decision.status_code == 200 and "dismissed" in [f["status"] for f in decision.json()["findings"]]
        refreshed = await client.get(f"/api/v1/audits/{run_id}", params=params)
        assert refreshed.status_code == 200
        assert {finding["status"] for finding in refreshed.json()["findings"] if finding["status"] != "informational"} == {"dismissed"}
        closed_preview = await client.post(
            f"/api/v1/audits/{run_id}/repair",
            params=params,
            json={"content": content},
        )
        assert closed_preview.status_code == 200
        assert closed_preview.json()["status"] == "no_open_findings"
        assert closed_preview.json()["replacements"] == []
        still_dismissed = await client.get(f"/api/v1/audits/{run_id}", params=params)
        assert {finding["status"] for finding in still_dismissed.json()["findings"] if finding["status"] != "informational"} == {"dismissed"}
        assert {decision["action"] for decision in refreshed.json()["decisions"]} == {"dismiss"}
        radar = await client.get("/api/v1/ambiguity-radar", params=params)
        assert radar.status_code == 200, radar.text
        rule_signal = next(item for item in radar.json()["rules"] if item["decision_count"])
        assert rule_signal["dismissals"] == rule_signal["decision_count"] == 1
        assert rule_signal["ambiguity_score"] is None
        assert rule_signal["signal"] == "insufficient_data"
        assert rule_signal["review_reasons"] == []
        clearance = await client.post(f"/api/v1/audits/{run_id}/clearance", params=params, json={"decision": "cleared"})
        assert clearance.status_code == 200 and clearance.json()["review_status"] == "cleared"
        assert clearance.json()["clearance"]["content_sha256"] == audit["content_sha256"]
        retrieved = await client.get(f"/api/v1/audits/{run_id}", params=params)
        assert retrieved.status_code == 200 and retrieved.json()["clearance"]["decision"] == "cleared"


@pytest.mark.asyncio
async def test_northstar_preferred_term_produces_verified_span_limited_repair(audit_db):
    document_id, workspace_id, engine = audit_db
    content = "NorthStarCloud helps workspace administrators export reports to CSV."
    with Session(engine) as session:
        term = ImportedTerm(
            workspace_id=workspace_id,
            term="NorthStarCloud",
            preferred_form="Northstar Cloud",
            source_filename="northstar_terms.csv",
            source_row_number=2,
            source_sha256="d" * 64,
            review_status="approved",
        )
        session.add(term)
        session.commit()
        term_id = term.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": content,
        })
        assert created.status_code == 201, created.text
        audit = created.json()
        finding = next(item for item in audit["findings"] if item["finding_type"] == "preferred_terminology")
        assert finding["term_id"] == str(term_id)
        assert finding["matched_phrase"] == "NorthStarCloud"
        assert content[finding["match_start"]:finding["match_end"]] == "NorthStarCloud"
        assert finding["verification_status"] == "verified"
        assert finding["status"] == "pending_review"
        assert finding["source_filename"] == "northstar_terms.csv"
        assert finding["evidence_excerpt"] == "NorthStarCloud → Northstar Cloud"

        preview = await client.post(
            f"/api/v1/audits/{audit['id']}/repair",
            params={"workspace_id": str(workspace_id)},
            json={"content": content},
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["status"] == "preview_available"
        assert body["repaired_content"] == "Northstar Cloud helps workspace administrators export reports to CSV."
        assert len(body["replacements"]) == 1
        replacement = body["replacements"][0]
        assert replacement["finding_id"] == finding["id"]
        assert replacement["original"] == "NorthStarCloud"
        assert replacement["replacement"] == "Northstar Cloud"
        assert replacement["start"] == finding["match_start"]
        assert replacement["end"] == finding["match_end"]
        assert replacement["source_filename"] == "northstar_terms.csv"
        assert replacement["source_label"] == "Approved terminology: NorthStarCloud → Northstar Cloud"

        unchanged = await client.get(f"/api/v1/audits/{audit['id']}", params={"workspace_id": str(workspace_id)})
        assert unchanged.status_code == 200
        assert unchanged.json()["content_sha256"] == audit["content_sha256"]
        assert unchanged.json()["character_count"] == len(content)
        assert next(item for item in unchanged.json()["findings"] if item["id"] == finding["id"])["status"] == "pending_review"


@pytest.mark.asyncio
async def test_repair_preview_distinguishes_no_findings_from_no_supported_repair(audit_db):
    document_id, workspace_id, _engine = audit_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        no_findings_audit = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": "A calm product update.",
        })
        assert no_findings_audit.status_code == 201, no_findings_audit.text
        no_findings = await client.post(
            f"/api/v1/audits/{no_findings_audit.json()['id']}/repair",
            params={"workspace_id": str(workspace_id)},
            json={"content": "A calm product update."},
        )
        assert no_findings.status_code == 200
        assert no_findings.json()["status"] == "no_findings"
        assert no_findings.json()["findings_reviewed"] == 0

        copy = "A guaranteed result."
        restricted_audit = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": copy,
        })
        assert restricted_audit.status_code == 201, restricted_audit.text
        restricted_body = restricted_audit.json()
        assert restricted_body["findings"][0]["verification_status"] == "uncertain"
        unsupported = await client.post(
            f"/api/v1/audits/{restricted_body['id']}/repair",
            params={"workspace_id": str(workspace_id)},
            json={"content": copy},
        )
        assert unsupported.status_code == 200
        assert unsupported.json()["status"] == "no_supported_repairs"
        assert unsupported.json()["findings_reviewed"] == 1
        assert unsupported.json()["replacements"] == []
        assert unsupported.json()["repaired_content"] == copy
        assert unsupported.json()["findings_before"] == unsupported.json()["findings_after"] == 1


@pytest.mark.asyncio
async def test_repair_preview_skips_uncertain_rejected_and_nonterminology_suggestions(audit_db):
    document_id, workspace_id, engine = audit_db
    content = "Our guaranteed platform is ProofMint."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": content,
        })
        assert created.status_code == 201, created.text
        body = created.json()
        term_finding = next(item for item in body["findings"] if item["finding_type"] == "preferred_terminology")
        rule_finding = next(item for item in body["findings"] if item["finding_type"] == "restricted_phrase")
        with Session(engine) as session:
            session.query(AuditFinding).filter_by(id=UUID(term_finding["id"])).update({"verification_status": "uncertain"})
            session.query(AuditFinding).filter_by(id=UUID(rule_finding["id"])).update({"suggested_correction": "a safe-sounding claim", "verification_status": "verified"})
            session.commit()

        uncertain = await client.post(f"/api/v1/audits/{body['id']}/repair", params={"workspace_id": str(workspace_id)}, json={"content": content})
        assert uncertain.status_code == 200
        assert uncertain.json()["replacements"] == []
        assert uncertain.json()["status"] == "no_supported_repairs"

        with Session(engine) as session:
            session.query(AuditFinding).filter_by(id=UUID(term_finding["id"])).update({"verification_status": "rejected"})
            session.commit()
        rejected = await client.post(f"/api/v1/audits/{body['id']}/repair", params={"workspace_id": str(workspace_id)}, json={"content": content})
        assert rejected.status_code == 200
        assert rejected.json()["replacements"] == []

        with Session(engine) as session:
            session.query(AuditFinding).filter_by(id=UUID(term_finding["id"])).update({"verification_status": "verified"})
            session.commit()
        restricted = await client.post(f"/api/v1/audits/{body['id']}/repair", params={"workspace_id": str(workspace_id)}, json={"content": content})
        assert restricted.status_code == 200
        replacements = restricted.json()["replacements"]
        assert [item["original"] for item in replacements] == ["ProofMint"]
        assert all(item["original"] != "guaranteed" for item in replacements)
        assert restricted.json()["repaired_content"] == content.replace("ProofMint", "Proofmint")


@pytest.mark.asyncio
@pytest.mark.parametrize("action,replacement", [("accept", "Proofmint"), ("edit", "Proofmint Cloud"), ("reject", None)])
async def test_repair_decisions_are_workspace_scoped_append_only_and_survive_audit_refresh(audit_db, action, replacement):
    document_id, workspace_id, _engine = audit_db
    content = "Meet ProofMint today."
    params = {"workspace_id": str(workspace_id)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": content,
        })
        assert created.status_code == 201, created.text
        audit = created.json()
        finding = next(item for item in audit["findings"] if item["finding_type"] == "preferred_terminology")
        route = f"/api/v1/audits/{audit['id']}/findings/{finding['id']}/repair-decisions"
        payload = {"action": action, "content": content, "replacement": replacement}
        if action == "accept":
            unsupported = await client.post(route, params=params, json={**payload, "replacement": "unsupported"})
            assert unsupported.status_code == 409
        saved = await client.post(route, params=params, json=payload)
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["content_sha256"] == audit["content_sha256"]
        assert next(item for item in body["findings"] if item["id"] == finding["id"])["status"] == "pending_review"
        assert body["repair_decisions"][-1]["action"] == action
        assert body["repair_decisions"][-1]["proposed_replacement"] == replacement

        refreshed = await client.get(f"/api/v1/audits/{audit['id']}", params=params)
        assert refreshed.status_code == 200
        assert refreshed.json()["repair_decisions"] == body["repair_decisions"]
        assert refreshed.json()["content_sha256"] == audit["content_sha256"]
        if action == "reject":
            preview = await client.post(
                f"/api/v1/audits/{audit['id']}/repair",
                params=params,
                json={"content": content},
            )
            assert preview.status_code == 200, preview.text
            assert preview.json()["replacements"] == []
            assert preview.json()["status"] == "no_supported_repairs"
            reopened = await client.post(route, params=params, json={**payload, "action": "accept", "replacement": "Proofmint"})
            assert reopened.status_code == 409
            after_reject = await client.get(f"/api/v1/audits/{audit['id']}", params=params)
            assert after_reject.json()["repair_decisions"] == body["repair_decisions"]
            assert next(item for item in after_reject.json()["findings"] if item["id"] == finding["id"])["status"] == "pending_review"

        stale = await client.post(route, params=params, json={**payload, "content": content + " changed"})
        assert stale.status_code == 409
        wrong_workspace = await client.post(route, params={"workspace_id": str(uuid4())}, json=payload)
        assert wrong_workspace.status_code == 404
        wrong_finding = await client.post(f"/api/v1/audits/{audit['id']}/findings/{uuid4()}/repair-decisions", params=params, json=payload)
        assert wrong_finding.status_code == 404


@pytest.mark.asyncio
async def test_repair_decision_rejects_findings_without_supported_current_proposal(audit_db):
    document_id, workspace_id, engine = audit_db
    content = "Our guaranteed platform is ProofMint."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": content,
        })
        assert created.status_code == 201, created.text
        audit = created.json()
        finding = next(item for item in audit["findings"] if item["finding_type"] == "restricted_phrase")
        with Session(engine) as session:
            session.query(AuditFinding).filter_by(id=UUID(finding["id"])).update({"suggested_correction": None})
            session.commit()
        response = await client.post(
            f"/api/v1/audits/{audit['id']}/findings/{finding['id']}/repair-decisions",
            params={"workspace_id": str(workspace_id)},
            json={"action": "edit", "content": content, "replacement": "a claim"},
        )
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_audit_api_rejects_blank_copy_and_missing_document(audit_db):
    _, workspace_id, _engine = audit_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        blank = await client.post("/api/v1/audits", json={"content": "   ", "workspace_id": str(workspace_id)})
        assert blank.status_code == 422
        missing = await client.post("/api/v1/audits", json={"content": "copy", "document_id": str(uuid4()), "workspace_id": str(workspace_id)})
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_ambiguity_radar_uses_rule_linked_decisions_and_recorded_reasons(audit_db):
    document_id, workspace_id, _engine = audit_db
    content = "guaranteed guaranteed guaranteed"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": content,
        })
        assert created.status_code == 201, created.text
        findings = [item for item in created.json()["findings"] if item["finding_type"] == "restricted_phrase"]
        assert len(findings) == 3
        for item in findings:
            response = await client.post(
                f"/api/v1/audits/{created.json()['id']}/findings/{item['id']}/decisions",
                params={"workspace_id": str(workspace_id)},
                json={"action": "dismiss", "reason": "The surrounding copy qualifies this phrase."},
            )
            assert response.status_code == 200, response.text
        radar = await client.get("/api/v1/ambiguity-radar", params={"workspace_id": str(workspace_id)})
        assert radar.status_code == 200, radar.text
        rule = next(item for item in radar.json()["rules"] if item["decision_count"])
        assert rule["decision_count"] == rule["dismissals"] == 3
        assert rule["ambiguity_score"] == 1.0
        assert rule["signal"] == "repeated_review_signal"
        assert rule["review_reasons"] == ["The surrounding copy qualifies this phrase."] * 3


@pytest.mark.asyncio
async def test_ambiguity_radar_keeps_distinct_rule_records_and_decisions_separate(audit_db):
    document_id, workspace_id, engine = audit_db
    rule_texts = ['Never use "alpha".', 'Never use "beta".']
    with Session(engine) as session:
        rules = [CandidateRule(
            document_id=document_id,
            rule_text=rule_text,
            category="prohibition",
            source_page=2,
            source_start_offset=0,
            source_end_offset=len(rule_text),
            source_excerpt=rule_text,
            review_status="approved",
        ) for rule_text in rule_texts]
        session.add_all(rules)
        session.commit()
        rule_ids = [str(rule.id) for rule in rules]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": "alpha and beta",
        })
        assert created.status_code == 201, created.text
        findings = {item["rule_id"]: item for item in created.json()["findings"] if item["rule_id"] in rule_ids}
        assert set(findings) == set(rule_ids)
        for rule_id in rule_ids:
            response = await client.post(
                f"/api/v1/audits/{created.json()['id']}/findings/{findings[rule_id]['id']}/decisions",
                params={"workspace_id": str(workspace_id)},
                json={"action": "dismiss", "reason": f"Review for {rule_id}."},
            )
            assert response.status_code == 200, response.text

        response = await client.get("/api/v1/ambiguity-radar", params={"workspace_id": str(workspace_id)})
        assert response.status_code == 200, response.text
        by_id = {item["rule_id"]: item for item in response.json()["rules"]}
        assert by_id[rule_ids[0]]["rule_text"] == rule_texts[0]
        assert by_id[rule_ids[1]]["rule_text"] == rule_texts[1]
        assert by_id[rule_ids[0]]["source_page"] == by_id[rule_ids[1]]["source_page"] == 2
        assert by_id[rule_ids[0]]["decision_count"] == by_id[rule_ids[1]]["decision_count"] == 1
        assert by_id[rule_ids[0]]["review_reasons"] == [f"Review for {rule_ids[0]}."]
        assert by_id[rule_ids[1]]["review_reasons"] == [f"Review for {rule_ids[1]}."]


@pytest.mark.asyncio
async def test_clearance_denies_flagged_findings(audit_db):
    document_id, workspace_id, _engine = audit_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": "A guaranteed result.",
        })
        assert created.status_code == 201, created.text
        body = created.json()
        finding = body["findings"][0]
        flag = await client.post(
            f"/api/v1/audits/{body['id']}/findings/{finding['id']}/decisions",
            params={"workspace_id": str(workspace_id)},
            json={"action": "flag"},
        )
        assert flag.status_code == 200, flag.text
        blocked = await client.post(
            f"/api/v1/audits/{body['id']}/clearance",
            params={"workspace_id": str(workspace_id)},
            json={"decision": "cleared"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "Resolve or dismiss all actionable findings before clearance."


@pytest.mark.asyncio
async def test_acceptance_requires_original_verified_content_and_does_not_clear_audit(audit_db):
    document_id, workspace_id, _engine = audit_db
    content = "Meet ProofMint today."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id), "workspace_id": str(workspace_id), "content": content,
        })
        assert created.status_code == 201, created.text
        body = created.json()
        finding = next(item for item in body["findings"] if item["finding_type"] == "preferred_terminology")
        url = f"/api/v1/audits/{body['id']}/findings/{finding['id']}/decisions"
        params = {"workspace_id": str(workspace_id)}
        missing = await client.post(url, params=params, json={"action": "accept_suggestion"})
        assert missing.status_code == 422
        stale = await client.post(url, params=params, json={"action": "accept_suggestion", "content": content + " changed"})
        assert stale.status_code == 409
        accepted = await client.post(url, params=params, json={
            "action": "accept_suggestion", "reason": "Approved house style.", "content": content,
        })
        assert accepted.status_code == 200, accepted.text
        result = accepted.json()
        assert result["content_sha256"] == body["content_sha256"]
        assert result["review_status"] == "pending_review"
        assert next(item for item in result["findings"] if item["id"] == finding["id"])["status"] == "resolved"
        assert result["decisions"][-1]["review_reason"] == "Approved house style."


@pytest.mark.asyncio
async def test_audit_persistence_failure_returns_safe_error_and_logs_database_code(audit_db, monkeypatch, caplog):
    document_id, workspace_id, engine = audit_db
    content = "A private draft says guaranteed and must not appear in logs."
    original_flush = Session.flush

    class MissingColumnError(Exception):
        sqlstate = "42703"

    def fail_audit_insert(session, objects=None):
        if any(isinstance(item, AuditFinding) for item in session.new):
            raise OperationalError(
                "INSERT INTO audit_runs (private content omitted)",
                {},
                MissingColumnError("column verification_status does not exist"),
            )
        return original_flush(session, objects)

    monkeypatch.setattr(Session, "flush", fail_audit_insert)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/audits", json={
            "document_id": str(document_id),
            "workspace_id": str(workspace_id),
            "content": content,
        })

    assert response.status_code == 503
    assert response.json() == {"detail": "Audit results could not be persisted."}
    assert content not in caplog.text
    assert "sqlstate=42703" in caplog.text
    assert "verification_status does not exist" not in caplog.text
    with Session(engine) as session:
        assert session.query(AuditRun).filter_by(workspace_id=workspace_id).count() == 0


@pytest.mark.asyncio
async def test_clearance_lifecycle_distinguishes_pending_flagged_dismissed_and_resolved(audit_db):
    """Verify clearance is strictly denied while findings remain pending or flagged, and permitted only once resolved or dismissed."""
    document_id, workspace_id, _engine = audit_db
    content = "Meet ProofMint today with guaranteed results."
    params = {"workspace_id": str(workspace_id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id),
            "workspace_id": str(workspace_id),
            "content": content,
        })
        assert created.status_code == 201
        audit = created.json()
        run_id = audit["id"]

        # 1. While any actionable findings are pending_review, clearance MUST be blocked (409)
        blocked_pending = await client.post(
            f"/api/v1/audits/{run_id}/clearance",
            params=params,
            json={"decision": "cleared"},
        )
        assert blocked_pending.status_code == 409
        assert blocked_pending.json()["detail"] == "Resolve or dismiss all actionable findings before clearance."

        term_finding = next(f for f in audit["findings"] if f["finding_type"] == "preferred_terminology")
        rule_finding = next(f for f in audit["findings"] if f["finding_type"] == "restricted_phrase")

        # 2. Flagging a finding writes a decision record but keeps status="flagged". Clearance MUST STILL be blocked (409)
        flag_resp = await client.post(
            f"/api/v1/audits/{run_id}/findings/{rule_finding['id']}/decisions",
            params=params,
            json={"action": "flag", "reason": "Needs legal review."},
        )
        assert flag_resp.status_code == 200
        assert flag_resp.json()["findings"][-1]["status"] in ("flagged", "pending_review")

        blocked_flagged = await client.post(
            f"/api/v1/audits/{run_id}/clearance",
            params=params,
            json={"decision": "cleared"},
        )
        assert blocked_flagged.status_code == 409
        assert blocked_flagged.json()["detail"] == "Resolve or dismiss all actionable findings before clearance."

        # 3. Accept suggestion for terminology finding (becomes status="resolved")
        accept_resp = await client.post(
            f"/api/v1/audits/{run_id}/findings/{term_finding['id']}/decisions",
            params=params,
            json={"action": "accept_suggestion", "content": content},
        )
        assert accept_resp.status_code == 200

        # Still blocked because rule_finding is flagged
        blocked_partially_resolved = await client.post(
            f"/api/v1/audits/{run_id}/clearance",
            params=params,
            json={"decision": "cleared"},
        )
        assert blocked_partially_resolved.status_code == 409

        # 4. Dismiss the flagged rule finding (becomes status="dismissed")
        dismiss_resp = await client.post(
            f"/api/v1/audits/{run_id}/findings/{rule_finding['id']}/decisions",
            params=params,
            json={"action": "dismiss", "reason": "Exception granted."},
        )
        assert dismiss_resp.status_code == 200

        # 5. Now that ALL actionable findings are resolved or dismissed, clearance succeeds (200 OK)
        cleared_resp = await client.post(
            f"/api/v1/audits/{run_id}/clearance",
            params=params,
            json={"decision": "cleared"},
        )
        assert cleared_resp.status_code == 200
        assert cleared_resp.json()["review_status"] == "cleared"
        assert cleared_resp.json()["clearance"]["decision"] == "cleared"


@pytest.mark.asyncio
async def test_clearance_hold_decision_records_blocked_status(audit_db):
    """Verify placing an audit on hold sets review_status to blocked without error."""
    document_id, workspace_id, _engine = audit_db
    params = {"workspace_id": str(workspace_id)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={
            "document_id": str(document_id),
            "workspace_id": str(workspace_id),
            "content": "A guaranteed result.",
        })
        assert created.status_code == 201
        run_id = created.json()["id"]

        hold_resp = await client.post(
            f"/api/v1/audits/{run_id}/clearance",
            params=params,
            json={"decision": "hold"},
        )
        assert hold_resp.status_code == 200
        assert hold_resp.json()["review_status"] == "blocked"
        assert hold_resp.json()["clearance"]["decision"] == "blocked"



@pytest.mark.asyncio
@pytest.mark.parametrize("fmt,content_type,filename,signature", [
    ("pdf", "application/pdf", "proofmint_report.pdf", b"%PDF-"),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "proofmint_report.docx", b"PK"),
])
async def test_audit_report_downloads_persisted_records_with_mandatory_watermarks(audit_db, fmt, content_type, filename, signature):
    from io import BytesIO
    from zipfile import ZipFile
    from docx import Document
    import pymupdf
    from app.models.audit import FindingDecision, RepairDecision
    document_id, workspace_id, engine = audit_db
    content = "Our guaranteed platform is ProofMint."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={"document_id": str(document_id), "workspace_id": str(workspace_id), "content": content})
        assert created.status_code == 201, created.text
        audit = created.json()
        finding = audit["findings"][0]
        with Session(engine) as session:
            session.add(FindingDecision(finding_id=UUID(finding["id"]), action="dismiss", review_reason="Recorded synthetic review reason."))
            session.add(RepairDecision(finding_id=UUID(finding["id"]), action="edit", proposed_replacement="Reviewer-edited wording", review_reason="Preserve intent."))
            session.commit()
        response = await client.post(f"/api/v1/audits/{audit['id']}/report?workspace_id={workspace_id}", json={"format": fmt})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].split(";")[0] == content_type
        assert response.headers["content-disposition"] == f'attachment; filename="{filename}"'
        assert response.content.startswith(signature)
        with Session(engine) as session:
            persisted = session.get(AuditRun, UUID(audit["id"]))
            persisted_finding = session.get(AuditFinding, UUID(finding["id"]))
            assert persisted is not None and persisted.review_status == audit["review_status"]
            assert persisted_finding is not None and persisted_finding.status == finding["status"]
            assert session.query(FindingDecision).filter_by(finding_id=UUID(finding["id"])).count() == 1
        if fmt == "pdf":
            pdf = pymupdf.open(stream=response.content, filetype="pdf")
            text = "\n".join(page.get_text() for page in pdf)
            assert "Proofmint Audit Decision Report" in text
            assert "PROOFMINT" in text
            assert "guaranteed" in text
            assert "dismissed" in text
            assert "Recorded synthetic review reason." in text
            assert "Reviewer-edited wording" in text and "Persisted repair" in text
            assert pdf.page_count >= 1
            image_count = sum(len(page.get_images()) for page in pdf)
            assert image_count >= 1
            assert all("PROOFMINT" in page.get_text() for page in pdf)
            pix = pdf[0].get_pixmap(matrix=pymupdf.Matrix(0.7, 0.7), alpha=False)
            assert len(pix.samples) > 0
            pdf.close()
        else:
            package = ZipFile(BytesIO(response.content))
            assert package.testzip() is None
            header_xml = package.read("word/header1.xml").decode()
            assert "ProofmintTextWatermark" in header_xml and "PROOFMINT" in header_xml and "v:shape" in header_xml
            assert any(name.startswith("word/media/") for name in package.namelist())
            doc = Document(BytesIO(response.content))
            fulltext = "\n".join(p.text for p in doc.paragraphs) + "\n" + "\n".join(c.text for table in doc.tables for row in table.rows for c in row.cells)
            assert "Audit Decision Report" in fulltext and "guaranteed" in fulltext and "dismissed" in fulltext
            assert "Recorded synthetic review reason." in fulltext
            assert "Reviewer-edited wording" in fulltext and "Persisted repair decisions" in fulltext
            from lxml import etree
            root = etree.fromstring(header_xml.encode())
            ns = {"v": "urn:schemas-microsoft-com:vml", "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            vml_watermark = root.xpath(".//v:shape[@id='ProofmintTextWatermark']/v:textpath[@string='PROOFMINT']", namespaces=ns)
            drawing_images = root.xpath(".//a:blip", namespaces=ns)
            assert vml_watermark and drawing_images
            assert any(name.startswith("word/media/") and package.read(name).startswith(bytes((137, 80, 78, 71)) ) for name in package.namelist())
            assert Document(BytesIO(response.content)).sections[0].header.paragraphs[0].text.strip() == "PROOFMINT"


@pytest.mark.asyncio
async def test_audit_report_rejects_cross_workspace_invalid_and_missing_requests(audit_db):
    document_id, workspace_id, _engine = audit_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/audits", json={"document_id": str(document_id), "workspace_id": str(workspace_id), "content": "Audit copy."})
        audit_id = created.json()["id"]
        cross = await client.post(f"/api/v1/audits/{audit_id}/report?workspace_id={uuid4()}", json={"format": "pdf"})
        assert cross.status_code == 404
        missing = await client.post(f"/api/v1/audits/{uuid4()}/report?workspace_id={workspace_id}", json={"format": "pdf"})
        assert missing.status_code == 404
        invalid = await client.post(f"/api/v1/audits/{audit_id}/report?workspace_id={workspace_id}", json={"format": "pdf", "watermark": "none"})
        assert invalid.status_code == 422
        unsupported = await client.post(f"/api/v1/audits/{audit_id}/report?workspace_id={workspace_id}", json={"format": "txt"})
        assert unsupported.status_code == 422
