"""Conservative, deterministic literal checks for approved Proofmint evidence."""

import re


def evaluate_copy(content: str, rules: list, facts: list, terms: list) -> tuple[list[dict], int, int, list[str]]:
    findings: list[dict] = []
    supported = 0
    unevaluated = 0
    limitations = ["Literal matching only; no semantic, legal, or comprehensive compliance analysis is performed."]
    long_fact_count = 0

    for rule in rules:
        # Treat quoted phrases as restricted only when the source rule explicitly
        # states a prohibition. Other approved rules remain visible as unevaluated.
        if re.search(r"\b(never|do not|must not|prohibited|avoid|mustn't|cannot use)\b", rule.rule_text, re.I):
            phrases = re.findall(r"[“\"]([^”\"]{2,500})[”\"]", rule.rule_text)
            if not phrases:
                unevaluated += 1
                continue
            supported += 1
            for phrase in dict.fromkeys(phrases):
                for match in re.finditer(re.escape(phrase), content, re.I):
                    findings.append({
                        "finding_type": "restricted_phrase", "rule_id": rule.id,
                        "matched_phrase": match.group(), "match_start": match.start(), "match_end": match.end(),
                        "explanation": "This literal phrase appears in an approved rule that explicitly prohibits or restricts it.",
                        "suggested_correction": None, "source_filename": rule.document.source_filename,
                        "source_page": rule.source_page, "source_start_offset": rule.source_start_offset,
                        "source_end_offset": rule.source_end_offset, "evidence_excerpt": rule.source_excerpt,
                        "status": "pending_review", "fact_id": None, "term_id": None,
                    })
        else:
            unevaluated += 1

    for term in terms:
        # `preferred_form` supplies an explicit normalization direction.
        if term.preferred_form and term.preferred_form != term.term:
            supported += 1
            for match in re.finditer(re.escape(term.term), content, re.I):
                findings.append({
                    "finding_type": "preferred_terminology", "rule_id": None,
                    "matched_phrase": match.group(), "match_start": match.start(), "match_end": match.end(),
                    "explanation": "The submitted text uses the imported term instead of its explicitly configured preferred form.",
                    "suggested_correction": term.preferred_form, "source_filename": term.source_filename,
                    "source_page": None, "source_start_offset": None, "source_end_offset": None,
                    "evidence_excerpt": f"{term.term} → {term.preferred_form}", "status": "pending_review",
                    "fact_id": None, "term_id": term.id,
                })

    for fact in facts:
        normalized = fact.approved_statement.strip()
        if len(normalized) > 500:
            long_fact_count += 1
            continue
        supported += 1
        if normalized and normalized.casefold() in content.casefold():
            start = content.casefold().index(normalized.casefold())
            findings.append({
                "finding_type": "approved_fact_match", "rule_id": None, "matched_phrase": content[start:start + len(normalized)],
                "match_start": start, "match_end": start + len(normalized),
                "explanation": "Submitted text exactly contains this approved factual statement; this literal match does not verify claims by meaning.",
                "suggested_correction": None, "source_filename": fact.source_filename, "source_page": None,
                "source_start_offset": None, "source_end_offset": None,
                "evidence_excerpt": fact.approved_statement[:1000], "status": "informational", "fact_id": fact.id, "term_id": None,
            })
    if not facts:
        limitations.append("No approved factual statements were available for exact-match comparison.")
    if not terms:
        limitations.append("No approved terminology records were available for preferred-form checks.")
    if long_fact_count:
        limitations.append(f"{long_fact_count} approved factual statement(s) longer than 500 characters were not compared.")
    if not rules:
        limitations.append("No approved guideline rules were available for evaluation.")
    return findings, supported, unevaluated, limitations
