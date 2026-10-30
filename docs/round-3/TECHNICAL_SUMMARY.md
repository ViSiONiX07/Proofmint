# Proofmint Round 3 — Technical Summary

## Architecture

- **Web:** Next.js App Router, React, TypeScript, Tailwind CSS. The Studio uses the existing Proofmint graphite, mint, copper, and off-white visual system.
- **API:** FastAPI with Pydantic v2 request/response models.
- **Persistence:** SQLAlchemy 2 and PostgreSQL/Psycopg 3. `get_engine()` is lazy and raises a clear error when PostgreSQL is not configured. SQLite is used only when a test or evaluation harness explicitly creates an SQLite engine.
- **Migrations:** Alembic revisions `0001` through `0006`; R3 adds finding verification outcomes and explanations, review reasons, and snapshots the exact source document ID and SHA-256 on historical findings.
- **PDF:** PyMuPDF extracts bounded text; immutable source PDFs are retained under a private filesystem root outside web assets. Document metadata, candidates, excerpts, and page-local source spans persist; complete extracted page text does not.
- **Audit:** A deterministic literal engine finds explicitly quoted restricted phrases, incorrectly used imported terminology, and exact approved-fact matches. A separate verifier checks submitted-content spans, approved workspace-scoped rule references, exact source-version snapshots, stored PDF hashes, page counts, and exact cited page text.

## Evidence semantics

`verified` means the submitted text and supported literal evidence check passed. For rule findings this includes the exact retained PDF hash, workspace, approved rule, cited page, and page-local source span. It does not mean an arbitrary claim is semantically true. `uncertain` means a supported finding cannot currently be independently rechecked, such as when its PDF is missing or inaccessible. `rejected` means the evidence reference, span, source hash, page, workspace, or metadata failed validation. The machine-readable reason is stored separately from the human-readable explanation.

## Repair semantics

The repair endpoint requires the original text whose hash was audited, validates the exact finding span and current evidence, and changes only verified terminology spans. It returns replacement metadata, an editable revision preview, and before/after literal counts. No revision text is stored by the API. Accepting a suggestion is a separate human decision record; it does not mutate text or automatically clear the run. The user must intentionally use a revision and submit a new audit.

## Ambiguity methodology

The workspace endpoint groups persisted decisions by currently approved rule. It includes event counts and recorded reasons only. `ambiguity_score = (dismissals + flags) / all recorded decisions`. At least three events and a score of `0.5` are required to emit `repeated_review_signal`; otherwise score is null and the result is `insufficient_data`. There are no distinct reviewer identities, so the metric does not claim disagreement.

## Evaluation methodology

`python -m app.services.evaluation` runs an eight-case labeled synthetic JSON dataset using a dedicated in-memory SQLite database. Precision and recall use normalized finding signatures `(finding type, matched phrase, source filename)`. Run consistency compares stable signatures plus verification outcome over two runs; random IDs and timestamps are excluded. Evidence outcomes are counted and compared with dataset labels. Repair validity compares the actual proposed output to each expected output, including unchanged text when no safe repair exists. Undefined precision/recall denominators yield `null`.

## Local setup and migration

Install `services/api/requirements.txt`, configure a local PostgreSQL URL or the four `POSTGRES_*` settings, then from `services/api` run:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --port 8000
python -m pytest -q
python -m app.services.evaluation
```

From `apps/web`, install dependencies, set `NEXT_PUBLIC_API_URL` when needed, then use `npm run dev`, `npm run test:workspace`, `npm run lint`, and `npm run build`.

The local source store defaults to `services/api/.data/source-documents`; override `SOURCE_DOCUMENT_STORAGE_DIR` to use a private durable volume. Re-upload to the existing workspace restores a missing file only when bytes match the original hash and recorded metadata. A different PDF receives a separate document ID and never replaces a historical source. The active desktop environment has a loopback PostgreSQL URL, but the app role cannot create databases. The four opt-in integration tests therefore ran after all five migrations were applied to the uniquely named schema `pm_r3_test_80cfa58fed73`; a later read-only query confirmed that schema no longer exists. A separate schema `pm_r3_ui_6f22bc02fb77` was created for a planned local browser run. After the API server received a stop signal, a read-only check confirmed that this second schema still exists. It was left untouched. No default/public schema or production Neon host was migrated or modified.

## Security boundaries

The application currently has no authentication or tenant authorization. UUID workspaces provide request scoping but are not security principals. Submitted copy is not stored in PostgreSQL, though hashes, matched phrases, excerpts, decision reasons, and audit history are. Decision reasons must not contain confidential copy. Production use requires identity, authorization, durable private storage, backup/restore, retention review, and operational monitoring. The 8-case synthetic evaluation is a reproducibility check, not a measure of real-world accuracy. Browser E2E did not complete; the API-level workflow tests are not a substitute for it. The local R3 submission report is `PROOFMINT_R3_FINAL_REPORT.pdf` in this directory.
