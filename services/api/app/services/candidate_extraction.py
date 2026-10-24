"""Conservative, deterministic candidate-rule extraction from in-memory PDF text."""

import re
from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class CandidateRuleText:
    rule_text: str
    category: str
    source_page: int
    source_start_offset: int
    source_end_offset: int
    source_excerpt: str


_BOUNDARY = re.compile(
    r"(?<=[.!?])[ \t\r\n]+|\r?\n+(?=[ \t]*(?:[-*•▪]\s+|\d+[.)]\s+|"
    r"(?:must|shall|required|prohibited|never|avoid|only|do\s+not)\b))",
    re.IGNORECASE,
)
_PROHIBITION = re.compile(r"\b(?:must\s+not|shall\s+not|do\s+not|prohibited|never)\b", re.IGNORECASE)
_MUST_OR_SHALL = re.compile(r"\b(?:must|shall)\b", re.IGNORECASE)
_REQUIRED = re.compile(r"\brequired\b", re.IGNORECASE)
_RESTRICTION = re.compile(r"\b(?:avoid|only)\b", re.IGNORECASE)
_NOT_ONLY = re.compile(r"\bnot\s+only\b", re.IGNORECASE)
_NOT_REQUIRED = re.compile(r"\bnot\s+(?:strictly\s+)?required\b", re.IGNORECASE)
_PAGE_MARKER = re.compile(r"^[\W_]*\d+[\W_]*$", re.UNICODE)
# Exclude only blocks explicitly labeled as sample copy or review instructions.
# Keep this tied to the original page text so candidate offsets remain unchanged.
_NON_POLICY_CONTEXT = re.compile(
    r"^\s*(?:sample\s+(?:(?:marketing\s+)?copy|content|claim|text)|"
    r"expected\s+review\s+directions?)(?:\s*[:\-]\s*|\s*$)|"
    r"\bexpected\s+review\s+directions?\b",
    re.IGNORECASE | re.MULTILINE,
)
_MINIMUM_CHARACTERS = 20
_MINIMUM_WORDS = 4


def _category(statement: str) -> str | None:
    if _PROHIBITION.search(statement):
        return "prohibition"
    if _MUST_OR_SHALL.search(statement) or (_REQUIRED.search(statement) and not _NOT_REQUIRED.search(statement)):
        return "requirement"
    if _RESTRICTION.search(statement) and not _NOT_ONLY.search(statement):
        return "restriction"
    return None


def _segments(text: str):
    start = 0
    for boundary in _BOUNDARY.finditer(text):
        yield start, boundary.start()
        start = boundary.end()
    yield start, len(text)


def _in_labeled_example_or_instruction_block(page_text: str, start: int, end: int) -> bool:
    """Return true only when a candidate shares a paragraph with an explicit label.

    This avoids promoting embedded sample marketing copy or fixture instructions
    as policy while leaving ordinary references to examples untouched.
    """
    previous_break = page_text.rfind("\n\n", 0, start)
    paragraph_start = previous_break + 2 if previous_break >= 0 else 0
    paragraph_end = page_text.find("\n\n", end)
    if paragraph_end == -1:
        paragraph_end = len(page_text)
    return _NON_POLICY_CONTEXT.search(page_text[paragraph_start:paragraph_end]) is not None


def extract_candidate_rules(pages: Iterable[tuple[int, str]]) -> list[CandidateRuleText]:
    """Extract plausible normative statements with page-local character offsets.

    The output is a list of review candidates, not validated brand policy. Sentence
    boundaries are punctuation based, with a small newline heuristic for bullets and
    lines that begin with a clear normative signal. Wrapped lines otherwise remain
    joined in a candidate so offsets continue to address the original page text.
    """
    candidates: list[CandidateRuleText] = []
    seen: set[str] = set()

    for page_number, page_text in pages:
        if not page_text:
            continue
        for raw_start, raw_end in _segments(page_text):
            start, end = raw_start, raw_end
            while start < end and page_text[start].isspace():
                start += 1
            while end > start and page_text[end - 1].isspace():
                end -= 1
            statement = page_text[start:end]
            if not statement or _PAGE_MARKER.fullmatch(statement):
                continue
            if _in_labeled_example_or_instruction_block(page_text, start, end):
                continue
            if len(statement) < _MINIMUM_CHARACTERS:
                continue
            if len(re.findall(r"\b[\w'-]+\b", statement)) < _MINIMUM_WORDS:
                continue
            category = _category(statement)
            if category is None:
                continue

            normalized = " ".join(statement.split()).casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(CandidateRuleText(
                rule_text=statement,
                category=category,
                source_page=page_number,
                source_start_offset=start,
                source_end_offset=end,
                source_excerpt=page_text[start:end],
            ))

    return candidates
