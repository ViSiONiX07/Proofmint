"""Regression coverage for human-authored manual repair decisions."""

import hashlib
import json
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.audits import get_audit_session
from app.core.database import get_db_session
from app.main import app
from app.models import AuditFinding, AuditRun, Base, Workspace
from tests.auth_fixtures import install_authenticated_user


def test_manual_repair_persists_provenance_and_rejects_closed_findings(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def db_override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[get_audit_session] = db_override
    monkeypatch.setattr("app.main.get_session_factory", lambda: factory)
    with Session(engine) as db:
        workspace = Workspace(kind="session")
        db.add(workspace); db.flush()
        original = "Our revolutionary platform delivers results."
        audit = AuditRun(workspace_id=workspace.id, content_sha256=hashlib.sha256(original.encode()).hexdigest(), character_count=len(original), approved_rules_considered=1, supported_checks_performed=1, rules_unevaluated=0, scope_limitations=json.dumps([]), review_status="pending_review")
        db.add(audit); db.flush()
        finding = AuditFinding(audit_id=audit.id, finding_type="restricted_phrase", status="pending_review", matched_phrase="revolutionary", match_start=4, match_end=17, explanation="Unsupported promotional claim.", verification_status="verified")
        db.add(finding); db.commit()
        audit_id, finding_id, workspace_id = audit.id, finding.id, workspace.id
    try:
        async def run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                user_id, _ = install_authenticated_user(engine, client, email="manual-repair@example.test")
                revised = "Our proven platform delivers results."
                response = await client.post(f"/api/v1/audits/{audit_id}/findings/{finding_id}/repair-decisions", params={"workspace_id": workspace_id}, json={"action": "manual", "content": original, "revised_content": revised, "reason": "Human-authored correction"}, headers={"X-CSRF-Token": client.cookies.get("proofmint_csrf")})
                assert response.status_code == 200, response.text
                body = response.json()
                decision = body["repair_decisions"][-1]
                assert decision["action"] == "manual"
                assert decision["provenance"] == "human_authored"
                assert decision["original_text"] == original
                assert decision["revised_text"] == revised
                assert decision["workspace_id"] == str(workspace_id)
                assert decision["reviewer_user_id"] == str(user_id)
                assert body["content_sha256"] == hashlib.sha256(original.encode()).hexdigest()
                with Session(engine) as db:
                    db.get(AuditFinding, finding_id).status = "resolved"
                    db.commit()
                denied = await client.post(f"/api/v1/audits/{audit_id}/findings/{finding_id}/repair-decisions", params={"workspace_id": workspace_id}, json={"action": "manual", "content": original, "revised_content": revised}, headers={"X-CSRF-Token": client.cookies.get("proofmint_csrf")})
                assert denied.status_code == 409
        import asyncio
        asyncio.run(run())
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
