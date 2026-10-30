# Proofmint API: PostgreSQL setup

The API can start and serve its root and health routes without PostgreSQL configuration. PDF ingestion persists document metadata and therefore requires PostgreSQL; CSV import and Alembic migrations also require PostgreSQL.

## Configure a local database

Install PostgreSQL locally and create a dedicated database user and database. For example, from an administrator `psql` session:

```sql
CREATE ROLE proofmint LOGIN PASSWORD 'replace_with_a_local_password';
CREATE DATABASE proofmint OWNER proofmint;
```

Use your own local password value; it is not needed in this repository. Then from `services/api/` copy the safe root template:

```powershell
Copy-Item ..\..\.env.example .env
```

Edit the ignored `services/api/.env` and set either `DATABASE_URL` or all of `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`. The template values are blank by design. For a URL, use the `postgresql+psycopg://` scheme and URL-encode reserved characters in the username or password. Never commit `.env` or put real credentials in source files.

You can use environment variables instead of a `.env` file. For example, in PowerShell set each `POSTGRES_*` value for your own local database session; do not paste your password into source control or shared logs.

The settings layer does not connect during FastAPI import or startup. The first database-dependent operation creates the engine lazily. Without configuration, that operation raises `DatabaseNotConfiguredError` with the required variable names.

## Apply and inspect migrations

Run these commands from `services/api/` after configuring PostgreSQL:

```powershell
alembic upgrade head
alembic current
alembic history
```

The initial schema revisions created guideline document metadata, pending candidate rules, imported facts, and imported terminology tables. Current PDF ingestion retains the original bytes in the private source store while persisting provenance metadata and candidate rules; full extracted page text is not stored. This repository does not apply migrations automatically; a reachable PostgreSQL server is required for `upgrade head`.

## Candidate rules and human review

During PDF ingestion, a deterministic pattern extractor identifies plausible statements containing signals such as `must`, `shall`, `required`, `must not`, `do not`, `prohibited`, `never`, `avoid`, or `only`. It preserves the original source statement and page-local offsets, removes duplicate statements within a document, and persists candidates linked to the document in the same transaction. These are unverified suggestions; no semantic model is called and no candidate is automatically approved. The PDF response includes `candidate_rule_count`, which may be zero.

Review endpoints are:

```text
GET  /api/v1/guidelines/{document_id}/rules?status=pending_review&limit=50&offset=0
GET  /api/v1/rules/pending?document_id={document_id}&limit=50&offset=0
GET  /api/v1/rules/{candidate_id}
POST /api/v1/rules/{candidate_id}/approve
POST /api/v1/rules/{candidate_id}/reject
```

Only `pending_review` candidates can transition to `approved` or `rejected`; a repeated or opposite transition returns `409`. Missing records return `404`. Responses include the source document filename and hash, excerpt, page, and offsets. The current schema does not store reviewer identity or an approval audit trail, and these endpoints do not authenticate users or enforce tenant access. Do not treat a review response as proof of who made the decision.

## Session-scoped workspaces

`POST /api/v1/guidelines/ingest` starts a fresh workspace for each successful PDF-ingestion request unless an existing `workspace_id` multipart field is supplied. Existing workspaces can receive new immutable document versions. Re-uploading identical bytes to an existing workspace restores a missing source under the original document ID; matching is by exact SHA-256 and recorded size/page metadata, never filename alone. The browser retains the active ID in `sessionStorage`; `GET /api/v1/workspaces/{workspace_id}` restores the workspace's documents and latest audit after refresh. Starting a new session clears the active browser state; the next PDF upload creates the next persistent workspace.

Original PDFs are stored outside the web application in a private filesystem directory. The default is `services/api/.data/source-documents`; override it with `SOURCE_DOCUMENT_STORAGE_DIR` (see `.env.example`). Objects are keyed by workspace ID, document ID, and SHA-256, written atomically, and are never exposed through a public/static URL. Do not point this at a public asset directory. Production must configure a durable, access-restricted, backed-up storage volume and define retention/access controls; the local filesystem implementation does not provide cloud object-store durability or user authentication.

Every subsequent request must pass this ID: CSV imports include multipart `workspace_id`, list/review and candidate-rule APIs use a `workspace_id` query parameter, audit creation includes it in JSON, and audit retrieval, decisions, and clearance include it as a query parameter. Missing IDs fail validation; unknown or legacy IDs are not accepted as active sessions. Candidate rules inherit workspace ownership from their source document. Findings, decisions, and clearances inherit it through the audit.

Revision `0003_session_workspaces` adds workspace ownership and assigns all pre-existing records to one explicit `legacy` workspace. This preserves record IDs, source provenance, review statuses, and audit history while keeping legacy records out of fresh sessions. The workspace ID is a logical session-scoping value only: this demo has no authentication or tenant authorization and does not provide production-grade isolation.

## Import facts and terminology from CSV

Both import endpoints accept multipart fields `file` and `workspace_id` and require the configured PostgreSQL database:

```text
POST /api/v1/facts/import
POST /api/v1/terms/import
```

Files must be UTF-8 (an optional UTF-8 BOM is accepted), at most 5 MiB, and contain at most 10,000 data rows. CSV headers are case-insensitive and surrounding header whitespace is ignored. Unknown and duplicate headers are rejected. Fact CSVs require `claim_type` and `approved_statement`; supported optional headers are `fact_id`, `source_document`, `page_span`, `verified_date` (`YYYY-MM-DD`), and `status`. Terminology CSVs require `term`; supported optional headers are `preferred_form`, `category`, and `usage_notes`.

The import mode is partial success: every data row is validated, valid rows are written in one database transaction, and invalid rows are returned with their CSV row number and validation error. Invalid rows are not written or silently discarded. Empty files, invalid UTF-8, malformed CSV syntax, missing required headers, duplicate headers, and unsupported headers reject the entire file before persistence. Any database transaction failure returns a service error and rolls back the import batch. The response reports `rows_read`, `rows_imported`, `rows_skipped` (duplicate rows), and `rows_rejected`; the additive `rows_skipped` field defaults to zero in the schema, so existing response construction remains compatible. CSV ingestion uses `review_status: pending_review` only for new records and never changes an existing review decision.

Deduplication uses existing provenance within a workspace: for re-imports, workspace ID plus uploaded-byte SHA-256 plus CSV data-row number identifies a previously imported row. Identical validated payloads within one upload are also counted once; terminology identity includes `term`, `preferred_form`, `category`, and `usage_notes`, so entries sharing only the term remain distinct. A PostgreSQL transaction-scoped advisory lock serializes identical-file imports in the same workspace. The same file in another workspace is a fresh import. Byte-different copies of a file (for example, changed line endings or BOM) do not share the re-import identity; duplicates within each such upload are still skipped. Existing duplicate rows are not deleted or merged by import. Source filename, SHA-256 of the uploaded bytes, CSV data row number (header is row 1), and import timestamp remain persisted.

## Review imported facts and terminology

Imported records can be listed, filtered by review status, paginated, and viewed with their source provenance:

```text
GET  /api/v1/facts?workspace_id={uuid}&status=pending_review&limit=50&offset=0
GET  /api/v1/facts/{fact_id}?workspace_id={uuid}
POST /api/v1/facts/{fact_id}/approve?workspace_id={uuid}
POST /api/v1/facts/{fact_id}/reject?workspace_id={uuid}

GET  /api/v1/terms?workspace_id={uuid}&status=pending_review&limit=50&offset=0
GET  /api/v1/terms/{term_id}?workspace_id={uuid}
POST /api/v1/terms/{term_id}/approve?workspace_id={uuid}
POST /api/v1/terms/{term_id}/reject?workspace_id={uuid}
```

List status is optional and accepts `pending_review`, `approved`, or `rejected`; page size is 1–100. Missing records return `404`. Only pending records can be transitioned; repeated or opposite decisions return `409`. The transition locks the selected row and updates only its review status. Import filename, row number, hash, and timestamp remain unchanged. Import success is separate from approval. The current schema stores neither reviewer identity nor review history, and these endpoints do not authenticate users or enforce tenant access; deployment must add access controls and an audit trail before relying on review decisions operationally.

The opt-in live database API test uses a surrounding rollback transaction and does not leave its fixture rows behind:

```powershell
$env:PROOFMINT_RUN_POSTGRES_INTEGRATION = '1'
python -m pytest -q tests/test_imported_review_postgres.py
```

## Deterministic audits and explicit clearance

Revision `0002_persisted_audits` adds `audit_runs`, `audit_findings`, `finding_decisions`, and `clearance_records`. Apply it with `alembic upgrade head`; it does not modify or replace existing data.

`POST /api/v1/audits` accepts JSON `{ "content": "...", "workspace_id": "UUID", "document_id": "optional UUID" }`. It hashes the exact UTF-8 content and stores the hash and character count, never the full submitted copy. Evaluation uses only approved records in that workspace: explicitly quoted phrases inside an approved rule containing prohibition language, terminology rows with a distinct `preferred_form`, and exact approved-statement substring matches. Rules that cannot be parsed into that narrow prohibited-phrase check are counted as unevaluated. Facts provide only exact-match evidence; this does not establish that other claims are false or unsupported. The engine does not perform semantic or legal analysis.

`GET /api/v1/audits/{audit_id}` retrieves the persisted run, findings, decisions, and latest clearance. `POST /api/v1/audits/{audit_id}/findings/{finding_id}/decisions` accepts `accept_suggestion`, `dismiss`, or `flag`; accepting is allowed only when a specific preferred terminology correction exists. Each action is appended to decision history. `POST /api/v1/audits/{audit_id}/clearance` accepts `cleared` or `hold`. Clearance is human-issued; a `cleared` decision is rejected while actionable findings remain pending or flagged. The stored hash binds clearance to the evaluated content fingerprint, but is not a cryptographic signature or publication gate.

Audit records do not store complete submission text. Findings retain only matched phrases, offsets, short evidence excerpts and source provenance needed for review. The current service has no authentication or tenant isolation; review and clearance decisions are not attributable to an authenticated reviewer and must not be treated as production-secure.

## Round 3 evidence verification, repair, and ambiguity analysis

`POST /api/v1/audits` runs the deterministic matcher and then the independent verifier before persisting findings. Verification outcomes are `verified`, `uncertain`, or `rejected`; `verification_reason` is a machine-readable code and `verification_explanation` describes the check. Rule findings snapshot the exact source document ID and hash; the verifier checks workspace ownership, current rule approval, retained PDF integrity, page count, cited page-local offsets, and exact source text. Missing or inaccessible sources remain uncertain; corrupted files, invalid citations, mismatched versions, and cross-workspace references are rejected. `POST /api/v1/audits/{audit_id}/verify-source-evidence` can recheck a historical finding after source recovery, but requires the exact original audited copy (SHA-256 match); it preserves the audit, finding, rule, source-version IDs, and review decisions. Facts and terminology are verified only as literal matches to approved workspace records with stored import provenance; this does not establish semantic truth.

Supported endpoints:

```text
POST /api/v1/audits
GET  /api/v1/audits/{audit_id}?workspace_id={uuid}
POST /api/v1/audits/{audit_id}/repair?workspace_id={uuid}
POST /api/v1/audits/{audit_id}/verify-source-evidence?workspace_id={uuid}
POST /api/v1/audits/{audit_id}/findings/{finding_id}/decisions?workspace_id={uuid}
POST /api/v1/audits/{audit_id}/clearance?workspace_id={uuid}
GET  /api/v1/ambiguity-radar?workspace_id={uuid}
```

Repair and suggestion acceptance require the exact original text, checked against the stored SHA-256. The service rechecks current approved evidence and span validity, then returns a preview only. Currently, only preferred terminology yields a supported automatic replacement. No original text is overwritten or stored, and a new audit is required for an edited revision. Acceptance records a human decision; it does not apply the text or clear the audit. Pending and flagged findings continue to block clearance.

Finding decisions can include an optional `reason` (maximum 500 characters). The workspace ambiguity aggregate groups persisted decisions by currently approved rule. It returns decision, dismissal, flag, and acceptance counts, recorded reasons, dismissal rate, and an ambiguity score defined as `(dismissals + flags) / decisions`. A repeated signal requires at least three events and a score of at least 0.5. Events are not distinct reviewers; no reviewer identities or disagreement are inferred. Rules below the threshold report `insufficient_data` and a null score.

The reproducible synthetic evaluation command uses a version-controlled JSON dataset and an isolated in-memory SQLite database. It does not read configured database credentials:

```powershell
python -m app.services.evaluation
```

The report computes finding precision/recall from normalized `(type, phrase, source)` signatures, evidence outcome counts and label agreement, two-run signature consistency, and safe-repair validity. Precision and recall are `null` when their denominators are zero. It is a synthetic deterministic benchmark, not a production performance estimate.

### Round 3 migrations

Revisions `0004_evidence_locked_findings` and `0005_verification_review_reasons` add verification fields, an allowed-outcomes constraint, review reasons, and an index for rule-linked review aggregation. Revision `0006_audit_source_version` snapshots the exact source document ID/hash on historical rule findings and prevents deleting a referenced source row. Upgrade a **local development database only** with:

```powershell
alembic upgrade head
alembic current
```

These migrations were validated in a uniquely named temporary schema on localhost. Do not run them against production Neon without explicit authorization and a separately reviewed release plan.
