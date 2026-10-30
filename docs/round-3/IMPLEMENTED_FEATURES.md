# Proofmint Round 3 — Implemented Features

## Product workflow

The Launch Studio retains the ordered seven-stage workflow:

1. Configure approved brand knowledge.
2. Review and approve rules.
3. Submit marketing content.
4. Run the content audit.
5. Verify the findings.
6. Correct and review.
7. Record clearance and improve the guidelines.

PDF ingestion extracts bounded text, retains the original PDF in private server-side storage, and stores immutable document metadata and candidate rules. Full page text is not persisted. Candidate rules and imported facts/terms remain pending until a person approves them. Workspace associations are checked by API routes. Duplicate CSV imports are handled idempotently in a workspace.

## R3 improvement 1: evidence-locked findings

Each generated finding passes a separate backend verification service before persistence. It checks content offsets and exact matched span, requires exactly one evidence reference, loads the corresponding current record, checks workspace and approval status, validates source metadata, and checks the finding explanation against the established literal behavior.

Statuses are `verified`, `uncertain`, and `rejected`. `verification_reason` contains a machine-readable code, and `verification_explanation` explains the outcome. Fact matches explicitly establish only a literal match to an approved record, not semantic truth. Rule findings are verified only after the verifier reopens the exact retained PDF version and checks the workspace, document hash, approved rule, cited page, page-local span, and source excerpt. Missing or inaccessible PDFs remain uncertain; corrupted, mismatched, or insufficient citations are rejected. Invalid spans, references, status, workspace, or source metadata are rejected and are not represented as verified.

## R3 improvement 2: human-controlled repair

`POST /api/v1/audits/{audit_id}/repair` checks that the submitted text has the same SHA-256 as the audit, revalidates current evidence and exact spans, and produces a before/after preview. Current automatic replacements are limited to verified preferred terminology. All surrounding content is copied unchanged. Invalid or stale spans and changed evidence are refused. If no safe change exists, the API returns the unchanged copy with no replacement entries.

The studio presents the repair source and reason, an editable proposed revision, and explicit user controls. Accepting a finding suggestion requires original text and a second backend verification. It records a review event; it does not rewrite the submission, publish content, or clear an audit. An edited revision must be intentionally moved to the copy editor and audited again. Complete copy remains client-side; the API stores its hash and limited finding metadata.

## R3 improvement 3: synthetic evaluation and Ambiguity Radar

`services/api/app/services/evaluation_cases.json` is a version-controlled synthetic dataset with compliant copy, a restricted phrase, terminology, exact approved facts, an unsupported semantic claim, inconsistent source metadata, an ambiguous guideline, and repairable/no-safe-repair cases. Run it with `python -m app.services.evaluation` from `services/api`. The runner creates its own in-memory SQLite database and reports measured precision, recall, false positives/negatives, evidence outcomes and expected-label agreement, two-run signature consistency, and repair validity.

`GET /api/v1/ambiguity-radar?workspace_id=...` aggregates actual persisted decisions by currently approved rule. It reports counts of dismissals, flags and accepted suggestions, stored review reasons, a minimum of three decisions for a score, and the source rule. The score is `(dismissals + flags) / total decisions`; a repeated signal requires a score of at least `0.5`. Low-volume rules have a null score and `insufficient_data`. Events are not distinct reviewers. No reviewer identities, disagreement, jurisdictional judgments, or sample compliance grid are fabricated.

## Existing product capabilities

- Workspace-scoped PDF extraction, private source retention, document hashes, and immutable rule-to-document version references.
- Candidate rule extraction with human approval/rejection.
- Approved facts and terminology CSV import, review, and duplicate handling.
- Deterministic literal auditing and limited evidence-backed findings.
- Persisted audit runs, finding decisions, review reasons, and clearance history.
- Explicit clearance gate for pending and flagged actionable findings.
- Browser session workspace restoration and new-session isolation.
- Responsive Next.js interface and FastAPI/OpenAPI backend.

## Known limits

- No semantic or legal analysis; no LLM provider is called.
- Full extracted page text is not retained. Source PDFs use the local private filesystem store by default; external deployments must configure a durable, access-restricted volume.
- No safe automatic repair is offered for restricted phrases or unsupported claims.
- Repair does not score persuasive intent or cadence; preserving all untouched text is the current deterministic intent-preservation boundary.
- Ambiguity aggregates are review-friction signals, not proof a rule is ambiguous or that reviewers disagree.
- Authentication and tenant authorization are not implemented.
- The Round 2 PDF was supplied as historical reference and is not treated as evidence of current feature status. The new R3 report is based on current source, R3 documentation, and recorded test results.
- The evaluation measures only eight synthetic cases; it does not demonstrate real-world or production accuracy.
- Browser E2E did not run to completion. PostgreSQL integration passed only in a loopback disposable schema. A separate planned-UI-run schema remains present after its cleanup could not be confirmed and was left untouched.
- The self-contained local submission report is `PROOFMINT_R3_FINAL_REPORT.pdf`; it uses the Round 2 PDF for historical problem framing, branding, and documented team roles only.
