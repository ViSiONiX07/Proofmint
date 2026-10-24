from types import SimpleNamespace
from uuid import uuid4

from app.services.audit_engine import evaluate_copy


def test_approved_restricted_rule_matches_exact_quoted_phrase_with_offsets_and_source():
    document = SimpleNamespace(source_filename="Brand.pdf")
    rule = SimpleNamespace(id=uuid4(), rule_text='Never use “unlimited protection”.', document=document,
                           source_page=4, source_start_offset=8, source_end_offset=42, source_excerpt='Never use “unlimited protection”.')
    findings, supported, unevaluated, _ = evaluate_copy("Get unlimited protection today", [rule], [], [])
    assert supported == 1 and unevaluated == 0
    assert len(findings) == 1
    assert findings[0]["matched_phrase"] == "unlimited protection"
    assert findings[0]["match_start"] == 4 and findings[0]["match_end"] == 24
    assert findings[0]["source_filename"] == "Brand.pdf" and findings[0]["source_page"] == 4


def test_approved_rule_without_explicit_quoted_restriction_is_unevaluated():
    rule = SimpleNamespace(rule_text="Claims should reflect the current product experience.")
    findings, supported, unevaluated, _ = evaluate_copy("We do great things", [rule], [], [])
    assert findings == [] and supported == 0 and unevaluated == 1


def test_preferred_terminology_and_exact_approved_fact_are_evidence_grounded():
    term = SimpleNamespace(id=uuid4(), term="ProofMint", preferred_form="Proofmint", source_filename="terms.csv")
    fact = SimpleNamespace(id=uuid4(), approved_statement="The service supports CSV exports.", source_filename="facts.csv")
    findings, supported, unevaluated, limits = evaluate_copy(
        "ProofMint. The service supports CSV exports.", [], [fact], [term]
    )
    assert supported == 2 and unevaluated == 0
    assert {item["finding_type"] for item in findings} == {"preferred_terminology", "approved_fact_match"}
    term_finding = next(item for item in findings if item["finding_type"] == "preferred_terminology")
    assert term_finding["suggested_correction"] == "Proofmint" and term_finding["source_filename"] == "terms.csv"
    assert any("No approved guideline rules" in item for item in limits)


def test_no_approved_evidence_returns_limits_without_success_claim():
    findings, supported, unevaluated, limits = evaluate_copy("Any text", [], [], [])
    assert findings == [] and supported == 0 and unevaluated == 0
    assert len(limits) >= 3
