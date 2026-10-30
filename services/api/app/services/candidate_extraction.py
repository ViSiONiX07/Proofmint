"""Conservative, deterministic candidate-rule extraction from in-memory PDF text."""

import hashlib
import json
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


def candidate_signature(candidates: Iterable[CandidateRuleText]) -> str:
    """Return a stable digest of a candidate set for one page-text input.

    Two extractions of identical source bytes with the same extractor produce the same
    signature, which is what makes a repeated extraction refresh a no-op instead of new
    duplicate rules. Human review decisions are deliberately excluded: they must not make
    an otherwise identical rule set look stale.
    """
    canonical = sorted(
        [candidate.source_page, candidate.source_start_offset, candidate.source_end_offset,
         candidate.rule_text, candidate.category]
        for candidate in candidates
    )
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_HEADING_LABEL = re.compile(
    r"^(?:(?:\d+\.)?\s*Rule\s+[A-Za-z0-9_-]+(?:\s*[-–—:]\s*[^\n]*)?|"
    r"\d+\.\s+[A-Za-z\s-]{3,60})$",
    re.IGNORECASE,
)
_RULE_HEADING = re.compile(
    r"(?:^|\r?\n)[ \t]*(?:(?:\d+\.)?\s*Rule\s+[A-Za-z0-9_-]+(?:\s*[-–—:][^\n]*)?)\r?\n",
    re.IGNORECASE,
)
# Sentence punctuation ends a statement, except when it terminates a line-start
# list or section marker such as "6." or "7)", which belongs to the heading that
# follows it. Treating that period as a sentence end orphans the number from its
# heading and glues the heading title onto the next rule's text.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])[ \t\r\n]+")
_LINE_MARKER_TAIL = re.compile(r"(?:^|\n)[ \t]*\d{1,3}[.)][ \t]*$")
_BLOCK_BOUNDARY = re.compile(
    r"\r?\n+(?=[ \t]*(?:[-*•▪]\s+|\d+[.)]\s+|"
    r"Rule\s+[A-Za-z0-9_-]+|"
    r"(?:must|shall|required|prohibited|never|avoid|only|do\s+not)\b))",
    re.IGNORECASE,
)
_LINE_BREAK = re.compile(r"\r?\n+")
_PARAGRAPH_BREAK = re.compile(r"\r?\n[ \t]*\r?\n+")
# A line that is a section/rule heading or an all-caps heading label. Headings are
# never rule text: they terminate their own line so the rule starts at its own words.
_HEADING_LINE = re.compile(
    r"^(?:\d+(?:\.\d+)*[.)][ \t]+\S[^\n]*"
    r"|Rule\s+[A-Za-z0-9_.-]+[^\n]*"
    r"|[A-Z][A-Z0-9 &/'’()-]{2,60})$"
)
# A one- or two-word title such as the "Prefer" / "Avoid" header of a two-column
# table. It labels content; it is not itself a normative statement. A two-word label
# must be a title (both words capitalized) so a wrapped directive such as "Do not"
# on its own line stays joined to the sentence it begins.
_LABEL_LINE = re.compile(r"^[A-Z][A-Za-z'’-]{0,20}(?:[ \t][A-Z][A-Za-z'’-]{0,20})?$")
# A line that opens with a normative signal is a rule, never a heading, even in caps.
_NORMATIVE_LINE_PREFIX = re.compile(
    r"^(?:never|do\s+not|must|shall|avoid|prohibited|only)\b", re.IGNORECASE
)
_TERMINAL_PUNCTUATION = re.compile(r"""[.!?]["'”’)\]]*$""")
_CONTINUATION_LINE = re.compile(
    r"^(?:and|or|but|nor|yet|so|because|as|if|when|while|where|which|that|who|whose|"
    r"to|of|for|from|in|on|at|by|with|without|through|after|before|under|over|between|than|into)\b",
    re.IGNORECASE,
)
_TRAILING_CONNECTOR = re.compile(
    r"\b(?:and|or|but|nor|yet|so|because|as|if|when|while|where|which|that|who|whose|"
    r"to|of|for|from|in|on|at|by|with|without|through|after|before|under|over|between|than|into)\b$",
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


def _breaks_after_heading(line_before: str, next_line: str) -> bool:
    """Return true when a newline ends a heading or label line rather than wrapping prose."""
    if _HEADING_LINE.match(line_before) and not _NORMATIVE_LINE_PREFIX.match(line_before):
        return True
    # A bare table label ("Prefer", "Avoid") is not rule text unless the next line
    # continues a sentence the label began. A following line with no terminal
    # punctuation is a table cell or list item, so the label is not the rule's words.
    return bool(_LABEL_LINE.match(line_before)) and not _TERMINAL_PUNCTUATION.search(next_line)


def _segments(text: str):
    boundaries: list[tuple[int, int, bool]] = [
        (item.start(), item.end(), True)
        for item in _SENTENCE_BOUNDARY.finditer(text)
        if not _LINE_MARKER_TAIL.search(text[:item.start()])
    ]
    for item in _BLOCK_BOUNDARY.finditer(text):
        if not any(item.start() < right and item.end() > left for left, right, _ in boundaries):
            boundaries.append((item.start(), item.end(), True))
    for item in _PARAGRAPH_BREAK.finditer(text):
        if not any(item.start() < right and item.end() > left for left, right, _ in boundaries):
            boundaries.append((item.start(), item.end(), True))
    for item in _RULE_HEADING.finditer(text):
        boundaries.append((item.end() - 1, item.end(), True))
        if item.start() > 0:
            boundaries.append((item.start(), item.start() + 1, True))

    boundaries.sort(key=lambda item: (item[0], item[1]))

    for item in _LINE_BREAK.finditer(text):
        if any(item.start() < right and item.end() > left for left, right, _ in boundaries):
            continue
        prev_bounds = [b[1] for b in boundaries if b[1] <= item.start()]
        seg_start = max(prev_bounds) if prev_bounds else 0
        seg_prefix = text[seg_start:item.start()].strip()
        line_before = text[:item.start()].splitlines()[-1].strip() if item.start() > 0 else ""
        rest_after = text[item.end():]
        next_line = rest_after.splitlines()[0].strip() if rest_after else ""
        if not line_before or not next_line:
            continue

        if _breaks_after_heading(line_before, next_line):
            boundaries.append((item.start(), item.end(), True))
            continue

        quote_count = seg_prefix.count('"') + seg_prefix.count('“') + seg_prefix.count('”')
        if quote_count % 2 != 0:
            continue

        if _TRAILING_CONNECTOR.search(line_before):
            continue
        if line_before.endswith((",", ":", "-", "—", ";")):
            continue
        if _CONTINUATION_LINE.match(next_line):
            continue

        first_char = next_line.lstrip('"\'“')[0] if next_line.lstrip('"\'“') else ''
        if first_char.islower() and not line_before.endswith((".", "!", "?")):
            continue

        words = re.findall(r"\b[\w'-]+\b", seg_prefix)
        complete_rule = (
            len(seg_prefix) >= _MINIMUM_CHARACTERS
            and len(words) >= _MINIMUM_WORDS
            and _category(seg_prefix) is not None
        )
        if complete_rule and not first_char.islower():
            boundaries.append((item.start(), item.end(), True))

    boundaries.sort(key=lambda item: (item[0], item[1]))
    start = 0
    for boundary_start, boundary_end, _ in boundaries:
        if boundary_start < start:
            continue
        yield start, boundary_start
        start = boundary_end
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
            if _HEADING_LABEL.match(statement):
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
