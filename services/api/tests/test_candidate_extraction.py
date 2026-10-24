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
