from app.services.candidate_extraction import extract_candidate_rules


def test_extracts_requirement_prohibition_and_restriction_candidates():
    candidates = extract_candidate_rules([(
        1,
        "Marketing claims must be supported by current evidence. "
        "Never imply guaranteed customer outcomes. Use only approved product names.",
    )])
    assert [candidate.category for candidate in candidates] == [
        "requirement", "prohibition", "restriction"
    ]
    assert candidates[0].rule_text == "Marketing claims must be supported by current evidence."


def test_ignores_non_rule_prose_empty_text_and_short_noise():
    candidates = extract_candidate_rules([
        (1, ""),
        (2, "7\nBrand Voice\nWe build thoughtful products for modern teams."),
        (3, "Do not.") ,
        (4, "This is not only a useful example for product teams."),
        (5, "The use of this color is not required for all layouts."),
    ])
    assert candidates == []


def test_valid_requirement_is_not_hidden_by_unrelated_negative_phrase():
    candidates = extract_candidate_rules([(
        1,
        "This optional color is not required, but marketing claims must cite reliable evidence.",
    )])
    assert len(candidates) == 1
    assert candidates[0].category == "requirement"


def test_deduplicates_repeated_statements_and_keeps_first_source_location():
    statement = "Marketing copy must cite evidence for every claim."
    candidates = extract_candidate_rules([
        (1, f"{statement}\n{statement.upper()}"),
        (2, statement),
    ])
    assert len(candidates) == 1
    assert candidates[0].source_page == 1
    assert candidates[0].source_start_offset == 0
    assert candidates[0].source_excerpt == statement


def test_offsets_are_exact_page_local_spans_and_pages_do_not_merge():
    first = "Normal introduction. Claims must cite source evidence on this page."
    second = "Descriptions shall use approved terminology in every channel."
    candidates = extract_candidate_rules([(1, first), (2, second)])
    assert len(candidates) == 2
    for candidate, expected_page in zip(candidates, (first, second)):
        assert candidate.source_page in (1, 2)
        source = first if candidate.source_page == 1 else second
        assert candidate.source_page == (1 if expected_page == first else 2)
        assert source[candidate.source_start_offset:candidate.source_end_offset] == candidate.rule_text
        assert candidate.source_excerpt == candidate.rule_text


def test_normative_bullets_are_separate_candidates_and_keep_offsets():
    text = "- Teams must cite current sources\n- Never promise guaranteed results"
    candidates = extract_candidate_rules([(3, text)])
    assert len(candidates) == 2
    assert [candidate.source_page for candidate in candidates] == [3, 3]
    assert [text[c.source_start_offset:c.source_end_offset] for c in candidates] == [
        c.source_excerpt for c in candidates
    ]


def test_two_column_prefer_avoid_table_yields_no_fabricated_rule():
    """A two-column "Prefer | Avoid" table is not a rule and must not produce one.

    The retained Northstar guideline renders this table line by line, so PDF text
    order places the "Avoid" column label directly above the first cell of the other
    column. A text-only segmenter cannot recover the row pairing, so neither the
    label nor a label-plus-cell fragment may be extracted as brand policy.
    """
    page_text = (
        "Prefer\n"
        "Avoid\n"
        "targets 99.9% monthly service availability\n"
        "guarantees 100% uptime\n"
        "helps administrators export reports to CSV\n"
        "revolutionary reporting for everyone\n"
        "encrypts stored customer data using AES-256\n"
        "impossible to breach / protects against every threat\n"
        "Northstar Cloud\n"
        "NorthStarCloud / northstar cloud"
    )

    assert extract_candidate_rules([(4, page_text)]) == []


def test_numbered_section_heading_does_not_merge_into_the_following_rule():
    """A numbered section heading must never become part of the rule that follows it."""
    page_text = (
        "6. Writing patterns\n"
        "Prefer\n"
        "Avoid\n"
        "7. Human review and clearance\n"
        "Imported facts, terminology, and extracted candidate rules must remain pending review "
        "until a human approves them.\n"
        "Findings should cite their source and matched text. Actionable findings must be resolved "
        "before publication clearance\n"
        "can be recorded.\n"
    )

    candidates = extract_candidate_rules([(4, page_text)])

    assert [candidate.rule_text for candidate in candidates] == [
        "Imported facts, terminology, and extracted candidate rules must remain "
        "pending review until a human approves them.",
        "Actionable findings must be resolved before publication clearance\ncan be recorded.",
    ]
    for candidate in candidates:
        assert "Human review" not in candidate.rule_text
        assert "Writing patterns" not in candidate.rule_text
        assert candidate.source_page == 4
        assert candidate.source_excerpt == candidate.rule_text
        assert page_text[candidate.source_start_offset:candidate.source_end_offset] == candidate.rule_text


def test_wrapped_directive_split_onto_its_own_line_keeps_its_normative_sentence():
    """A directive verb alone on a line must stay with the sentence it begins."""
    page_text = (
        "Rule NS-02 - Evidence for quantitative claims\n"
        "Quantitative claims must match an approved fact. Do not\n"
        "convert a target into a guarantee.\n"
    )

    candidates = extract_candidate_rules([(2, page_text)])

    assert [candidate.rule_text for candidate in candidates] == [
        "Quantitative claims must match an approved fact.",
        "Do not\nconvert a target into a guarantee.",
    ]
    for candidate in candidates:
        assert page_text[candidate.source_start_offset:candidate.source_end_offset] == candidate.rule_text


def test_all_caps_directive_line_is_treated_as_a_rule_not_a_heading():
    """An all-caps line that opens with a normative signal is rule text, not a heading."""
    page_text = "NEVER\nuse an unverifiable claim in customer copy.\n"

    candidates = extract_candidate_rules([(1, page_text)])

    assert [candidate.rule_text for candidate in candidates] == [
        "NEVER\nuse an unverifiable claim in customer copy.",
    ]
    assert page_text[candidates[0].source_start_offset:candidates[0].source_end_offset] == candidates[0].rule_text


def test_retained_northstar_page_four_extracts_only_the_two_real_rules():
    """Real-corpus regression: the retained guideline's final page yields exactly two rules.

    Page 4 holds a terminology pointer, a link-free "Prefer | Avoid" table, a numbered
    heading, and three prose sentences. Only the two normative sentences may be extracted,
    each with its own page-local span and no heading or table text merged into it.
    """
    page_text = (
        "NORTHSTAR CLOUD  |  FICTIONAL BRAND GUIDELINES  |  PROOFMINT TEST DATA\n"
        "Page 4\n"
        "5. Terminology policy\n"
        "Use the companion terminology CSV with the exact headers term,category. The categories "
        "in this example are\n"
        "preferred, banned, and context-dependent.\n"
        "6. Writing patterns\n"
        "Prefer\n"
        "Avoid\n"
        "targets 99.9% monthly service availability\n"
        "guarantees 100% uptime\n"
        "helps administrators export reports to CSV\n"
        "revolutionary reporting for everyone\n"
        "encrypts stored customer data using AES-256\n"
        "impossible to breach / protects against every threat\n"
        "Northstar Cloud\n"
        "NorthStarCloud / northstar cloud\n"
        "7. Human review and clearance\n"
        "Imported facts, terminology, and extracted candidate rules must remain pending review "
        "until a human approves them.\n"
        "Findings should cite their source and matched text. Actionable findings must be resolved "
        "before publication clearance\n"
        "can be recorded.\n"
        "Clearance records a human decision; it is not a statement that content is free from "
        "all risk.\n"
        "End of sample guidelines. This fictional document is provided solely for local product "
        "testing and contains deliberately seeded issues.\n"
    )

    candidates = extract_candidate_rules([(4, page_text)])

    assert [candidate.source_page for candidate in candidates] == [4, 4]
    assert [candidate.category for candidate in candidates] == ["requirement", "requirement"]
    assert [candidate.rule_text for candidate in candidates] == [
        "Imported facts, terminology, and extracted candidate rules must remain "
        "pending review until a human approves them.",
        "Actionable findings must be resolved before publication clearance\ncan be recorded.",
    ]
    for candidate in candidates:
        assert candidate.source_excerpt == candidate.rule_text
        assert page_text[candidate.source_start_offset:candidate.source_end_offset] == candidate.rule_text
        for leaked in ("Terminology policy", "Writing patterns", "Prefer", "Avoid", "Human review"):
            assert leaked not in candidate.rule_text


def test_no_candidates_is_a_valid_empty_result():
    assert extract_candidate_rules([(1, "Our brand speaks with clarity and warmth.")]) == []


def test_excludes_explicit_sample_copy_and_expected_review_instruction_context():
    example = (
        "Expected review directions\n"
        "Sample marketing copy: Our platform must guarantee complete protection.\n\n"
        "Marketing claims must be supported by current evidence."
    )
    candidates = extract_candidate_rules([(4, example)])
    assert [candidate.rule_text for candidate in candidates] == [
        "Marketing claims must be supported by current evidence."
    ]
    kept = candidates[0]
    assert example[kept.source_start_offset:kept.source_end_offset] == kept.source_excerpt


def test_ordinary_example_reference_does_not_suppress_normative_rule():
    statement = "Teams must document claims; for example, include the source and date."
    candidates = extract_candidate_rules([(1, statement)])
    assert len(candidates) == 1
    assert candidates[0].rule_text == statement


def test_standalone_sample_marketing_copy_label_is_scoped_to_its_paragraph():
    text = (
        "Sample marketing copy:\n"
        "Our platform must guarantee complete protection.\n\n"
        "Product claims must cite current evidence."
    )
    candidates = extract_candidate_rules([(2, text)])
    assert [candidate.rule_text for candidate in candidates] == [
        "Product claims must cite current evidence."
    ]
    candidate = candidates[0]
    assert text[candidate.source_start_offset:candidate.source_end_offset] == candidate.rule_text


def test_multiline_sentence_with_trailing_connector_is_not_chopped():
    """Verify sentences wrapped across lines at connectors (or/and/into) stay complete."""
    page_text = (
        'Rule NS-03 - Approved availability wording\n'
        'Use "targets 99.9% monthly service availability" when discussing availability. '
        'Never shorten this to "100% uptime" or\n'
        '"zero downtime".\n'
    )
    candidates = extract_candidate_rules([(2, page_text)])
    rules = [c.rule_text for c in candidates]
    expected = 'Never shorten this to "100% uptime" or\n"zero downtime".'
    assert expected in rules
    matched = next(c for c in candidates if c.rule_text == expected)
    assert matched.category == "prohibition"
    assert page_text[matched.source_start_offset:matched.source_end_offset] == expected
    assert matched.source_excerpt == expected


def test_multiline_sentence_with_unclosed_quotes_stays_intact():
    """Verify wrapped lines with open quotes across line breaks are not split."""
    page_text = (
        'Rule NS-05 - Product name\n'
        'Write the company name as Northstar Cloud. '
        'Do not use "NorthStarCloud" or "northstar\n'
        'cloud" as the product name.\n'
    )
    candidates = extract_candidate_rules([(2, page_text)])
    expected = 'Do not use "NorthStarCloud" or "northstar\ncloud" as the product name.'
    assert any(c.rule_text == expected for c in candidates)
    matched = next(c for c in candidates if c.rule_text == expected)
    assert matched.category == "prohibition"
    assert page_text[matched.source_start_offset:matched.source_end_offset] == expected


def test_multiline_lowercase_continuation_preserves_full_sentence():
    """Verify lowercase sentence wrapping across PDF line breaks is not truncated."""
    page_text = (
        'Never use the exact phrase "guaranteed 100% protection" in copy. '
        'Do not imply that any product\n'
        'blocks every threat or eliminates all risk.\n'
    )
    candidates = extract_candidate_rules([(1, page_text)])
    expected = 'Do not imply that any product\nblocks every threat or eliminates all risk.'
    assert any(c.rule_text == expected for c in candidates)
    matched = next(c for c in candidates if c.rule_text == expected)
    assert page_text[matched.source_start_offset:matched.source_end_offset] == expected


def test_rule_headings_do_not_merge_into_following_rule_and_are_not_extracted():
    """Verify heading labels like 'Rule NS-01 - ...' do not pollute rules or create fake candidates."""
    page_text = (
        '2. Non-negotiable language rules\n'
        'Rule NS-01 - Prohibited phrase\n'
        'Never use the exact phrase "guaranteed 100% protection" in customer-facing copy.\n'
        'Rule NS-02 - Evidence for quantitative claims\n'
        'Quantitative claims must match an approved fact and retain any stated qualifier or condition.\n'
    )
    candidates = extract_candidate_rules([(2, page_text)])
    rule_texts = [c.rule_text for c in candidates]
    # Headings themselves must not be extracted as rules
    assert not any("Rule NS-01" in r for r in rule_texts)
    assert not any("Rule NS-02" in r for r in rule_texts)
    assert not any("Non-negotiable" in r for r in rule_texts)
    # The actual rules must be present and distinct
    assert 'Never use the exact phrase "guaranteed 100% protection" in customer-facing copy.' in rule_texts
    assert 'Quantitative claims must match an approved fact and retain any stated qualifier or condition.' in rule_texts
    for c in candidates:
        assert page_text[c.source_start_offset:c.source_end_offset] == c.rule_text


def test_long_rule_text_preserves_full_span_without_truncation():
    """Verify long rule texts with multiple clauses maintain full source span integrity."""
    long_rule = (
        'Do not use "the most secure", "the fastest", or similar comparative/superlative '
        'claims unless an approved, current,\n'
        'directly relevant substantiation is available and independently verified by legal compliance.'
    )
    page_text = f"Overview.\n{long_rule}\nNext section."
    candidates = extract_candidate_rules([(1, page_text)])
    assert len(candidates) == 1
    c = candidates[0]
    assert c.rule_text == long_rule
    assert page_text[c.source_start_offset:c.source_end_offset] == long_rule
    assert c.source_excerpt == long_rule
