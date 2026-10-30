"""Repeatable, labelled synthetic benchmark for findings, evidence and repairs.

Run with ``python -m app.services.evaluation`` from ``services/api``. The command
uses an isolated in-memory SQLite database and never reads configured databases.
"""

import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid5

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, CandidateRule, GuidelineDocument, ImportedFact, ImportedTerm, Workspace
from app.services.audit_engine import evaluate_copy
from app.services.evidence_verification import verify_findings
from app.services.repair_engine import build_repair_preview

DATASET_PATH = Path(__file__).with_name("evaluation_cases.json")
NAMESPACE = UUID("2c4fc435-5b14-4c1e-93b3-36a56c578d00")


def _id(case_id: str, kind: str, index: int) -> UUID:
    return uuid5(NAMESPACE, f"{case_id}:{kind}:{index}")


def _finding_signature(finding: dict) -> tuple[str, str, str]:
    return (finding["finding_type"], finding["matched_phrase"].casefold(),
            finding.get("source_filename") or "")


def _stable_signature(finding: dict) -> tuple[str, str, str, str]:
    return (*_finding_signature(finding), finding["verification_status"])


def run_evaluation(dataset_path: Path = DATASET_PATH) -> dict:
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    workspace_id = _id("evaluation", "workspace", 0)
    expected_by_case: dict[str, Counter] = {}
    try:
        with Session(engine, expire_on_commit=False) as session:
            session.add(Workspace(id=workspace_id, kind="session"))
            session.flush()
            for case in cases:
                case_id = case["id"]
                expected_by_case[case_id] = Counter(
                    (item["finding_type"], item["phrase"].casefold(), item.get("source_filename", ""))
                    for item in case["expected_findings"]
                )
                for index, rule_data in enumerate(case.get("rules", [])):
                    document = GuidelineDocument(id=_id(case_id, "document", index), workspace_id=workspace_id,
                        source_filename=rule_data["source_filename"], source_sha256="a" * 64,
                        file_size_bytes=10, page_count=1)
                    session.add(document)
                    session.add(CandidateRule(id=_id(case_id, "rule", index), document_id=document.id,
                        rule_text=rule_data["rule_text"], category="restriction", source_page=rule_data.get("source_page", 1),
                        source_start_offset=rule_data.get("source_start_offset", 0),
                        source_end_offset=rule_data.get("source_end_offset", rule_data.get("source_start_offset", 0) + len(rule_data["source_excerpt"])),
                        source_excerpt=rule_data["source_excerpt"], review_status=rule_data.get("review_status", "approved")))
                for index, fact_data in enumerate(case.get("facts", [])):
                    session.add(ImportedFact(id=_id(case_id, "fact", index), workspace_id=workspace_id,
                        claim_type="evaluation", approved_statement=fact_data["approved_statement"],
                        source_filename=fact_data.get("source_filename", "evaluation-facts.csv"), source_row_number=index + 2,
                        source_sha256="b" * 64, review_status=fact_data.get("review_status", "approved")))
                for index, term_data in enumerate(case.get("terms", [])):
                    session.add(ImportedTerm(id=_id(case_id, "term", index), workspace_id=workspace_id,
                        term=term_data["term"], preferred_form=term_data.get("preferred_form"),
                        source_filename=term_data.get("source_filename", "evaluation-terms.csv"),
                        source_row_number=index + 2, source_sha256="c" * 64,
                        review_status=term_data.get("review_status", "approved")))
            session.commit()

            def run_once():
                output = {}
                for case in cases:
                    case_id = case["id"]
                    rules = [session.get(CandidateRule, _id(case_id, "rule", i)) for i, _ in enumerate(case.get("rules", []))]
                    rules = [rule for rule in rules if rule.review_status == "approved"]
                    facts = [session.get(ImportedFact, _id(case_id, "fact", i)) for i, _ in enumerate(case.get("facts", []))]
                    facts = [fact for fact in facts if fact.review_status == "approved"]
                    terms = [session.get(ImportedTerm, _id(case_id, "term", i)) for i, _ in enumerate(case.get("terms", []))]
                    terms = [term for term in terms if term.review_status == "approved"]
                    findings, checks, unevaluated, limitations = evaluate_copy(case["content"], rules, facts, terms)
                    findings = verify_findings(session, findings, case["content"], workspace_id)
                    output[case_id] = (findings, checks, unevaluated, limitations, rules, facts, terms)
                return output

            first = run_once()
            second = run_once()
            actual = Counter(signature for findings, *_ in first.values() for signature in map(_finding_signature, findings))
            expected = Counter(signature for values in expected_by_case.values() for signature, count in values.items() for _ in range(count))
            true_positive = sum((actual & expected).values())
            false_positive = sum((actual - expected).values())
            false_negative = sum((expected - actual).values())
            precision_denominator = true_positive + false_positive
            recall_denominator = true_positive + false_negative
            evidence_counts = Counter(finding["verification_status"] for values in first.values() for finding in values[0])
            expected_evidence_counts = Counter(
                item["verification_status"] for case in cases for item in case["expected_findings"]
            )
            expected_evidence = Counter(
                (*_finding_signature({"finding_type": item["finding_type"], "matched_phrase": item["phrase"],
                                      "source_filename": item.get("source_filename")}), item["verification_status"])
                for case in cases for item in case["expected_findings"]
            )
            observed_evidence = Counter(
                (*_finding_signature(finding), finding["verification_status"])
                for values in first.values() for finding in values[0]
            )
            consistent_cases = 0
            repair_cases = valid_repairs = safe_repair_refusals = 0
            for case in cases:
                a = first[case["id"]][0]
                b = second[case["id"]][0]
                if Counter(map(_stable_signature, a)) == Counter(map(_stable_signature, b)):
                    consistent_cases += 1
                if "expected_repaired_content" not in case:
                    continue
                repair_cases += 1
                findings = first[case["id"]][0]
                adapters = [SimpleNamespace(id=_id(case["id"], "repair-finding", i),
                    finding_type=f["finding_type"],
                    source_document_id=f.get("source_document_id"),
                    source_document_sha256=f.get("source_document_sha256"),
                    match_start=f["match_start"], match_end=f["match_end"], matched_phrase=f["matched_phrase"],
                    suggested_correction=f["suggested_correction"], verification_status=f["verification_status"],
                    rule_id=f["rule_id"], fact_id=f["fact_id"], term_id=f["term_id"],
                    evidence_excerpt=f["evidence_excerpt"], source_filename=f["source_filename"],
                    source_page=f["source_page"], source_start_offset=f["source_start_offset"],
                    source_end_offset=f["source_end_offset"], explanation=f["explanation"])
                    for i, f in enumerate(findings) if f["suggested_correction"]]
                repaired, replacements = build_repair_preview(session, case["content"], workspace_id, adapters)
                expected_repair = case["expected_repaired_content"]
                if repaired == expected_repair and (replacements or expected_repair == case["content"]):
                    valid_repairs += 1
                if case.get("expect_no_safe_repair") and not replacements and repaired == case["content"]:
                    safe_repair_refusals += 1

            return {
                "dataset": dataset_path.name,
                "synthetic_cases": len(cases),
                "finding_metrics": {
                    "true_positives": true_positive,
                    "false_positives": false_positive,
                    "false_negatives": false_negative,
                    "precision": true_positive / precision_denominator if precision_denominator else None,
                    "recall": true_positive / recall_denominator if recall_denominator else None,
                },
                "evidence_verification": {
                    "observed": {name: evidence_counts.get(name, 0) for name in ("verified", "uncertain", "rejected")},
                    "expected": {name: expected_evidence_counts.get(name, 0) for name in ("verified", "uncertain", "rejected")},
                    "outcome_matches": sum((expected_evidence & observed_evidence).values()),
                    "outcome_mismatches": sum((expected_evidence - observed_evidence).values()) + sum((observed_evidence - expected_evidence).values()),
                },
                "run_consistency": {"consistent_cases": consistent_cases, "cases": len(cases),
                    "rate": consistent_cases / len(cases) if cases else None},
                "repair_validity": {"valid_repairs": valid_repairs, "repair_cases": repair_cases,
                    "safe_repair_refusals": safe_repair_refusals},
                "empty_data_behavior": "precision and recall are null when their denominators are zero; consistency is null for zero cases.",
            }
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), indent=2, sort_keys=True))
