"""Rule-level review-friction aggregates from persisted human decisions."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditFinding, FindingDecision
from app.models.guideline import CandidateRule, GuidelineDocument

MINIMUM_DECISIONS = 3


def get_workspace_ambiguity(session: Session, workspace_id: UUID) -> dict:
    rules = session.scalars(select(CandidateRule).join(GuidelineDocument).where(
        CandidateRule.review_status == "approved", GuidelineDocument.workspace_id == workspace_id,
    )).all()
    by_id = {rule.id: rule for rule in rules}
    events: dict[UUID, list[FindingDecision]] = defaultdict(list)
    if by_id:
        rows = session.execute(select(FindingDecision, AuditFinding.rule_id)
            .join(AuditFinding, FindingDecision.finding_id == AuditFinding.id)
            .where(AuditFinding.rule_id.in_(by_id))).all()
        for decision, rule_id in rows:
            if rule_id in by_id:
                events[rule_id].append(decision)

    output = []
    for rule_id, rule in by_id.items():
        decisions = events[rule_id]
        count = len(decisions)
        dismissals = sum(item.action == "dismiss" for item in decisions)
        flags = sum(item.action == "flag" for item in decisions)
        accepted = sum(item.action == "accept_suggestion" for item in decisions)
        score = (dismissals + flags) / count if count >= MINIMUM_DECISIONS else None
        output.append({
            "rule_id": rule.id,
            "rule_text": rule.rule_text,
            "source_filename": rule.document.source_filename,
            "source_page": rule.source_page,
            "decision_count": count,
            "dismissals": dismissals,
            "flags": flags,
            "accepted_suggestions": accepted,
            "review_reasons": [item.review_reason for item in decisions if item.review_reason],
            "dismissal_rate": dismissals / count if count else 0.0,
            "ambiguity_score": score,
            "signal": (
                "insufficient_data" if score is None
                else "repeated_review_signal" if score >= 0.5
                else "no_repeated_signal"
            ),
        })
    output.sort(key=lambda item: (item["ambiguity_score"] is None, -(item["ambiguity_score"] or 0), str(item["rule_id"])))
    return {
        "workspace_id": workspace_id,
        "minimum_decisions": MINIMUM_DECISIONS,
        "rules": output,
        "limitations": [
            "Ambiguity score = (dismissals + flags) / recorded decisions; decisions are events, not distinct reviewers.",
            "A repeated review signal requires at least three decisions and a score of 0.5 or greater.",
            "Only currently approved rules and persisted rule-linked decisions are included; no reasons are inferred.",
        ],
    }
