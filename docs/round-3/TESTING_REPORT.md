# Proofmint Round 3 — Testing Report

## Environment

- Python 3.13.5 at `C:\Users\trix4\AppData\Local\Programs\Python\Python313\python.exe`.
- Backend tests run from `services/api` with `python -m pytest`.
- Frontend uses the checked-in Node test script, Next.js lint/build, and existing installed workspace dependencies.
- Automated API tests use explicitly injected in-memory SQLite engines. Evaluation creates its own in-memory database. PostgreSQL integration tests used a uniquely named loopback-only disposable schema; a separate UI-server schema is still present and is intentionally left untouched after the server cleanup could not be confirmed.

## Final exact results

Commands were run from the directories shown below on 26 October 2026.

| Check | Command | Result |
| --- | --- | --- |
| Backend imports | `python -c "import app.main, app.api.audits, app.schemas.audit, app.models.audit; print('imports: OK'); print('app.main:', app.main.__file__)"` (`services/api`) | Passed; all imports resolved from `services/api/app`. |
| Backend collection | `python -m pytest --collect-only -vv` (`services/api`) | Standalone collection did not finish: output stopped at `collecting ...` for over 30 seconds, with no item-level output. The full verbose test run independently collected 84 items and completed. |
| R3/API targeted regression set | `python -m pytest -q tests/test_evidence_verification.py tests/test_audit_engine.py tests/test_evaluation.py tests/test_audits.py tests/test_database.py tests/test_workspaces.py` (`services/api`) | 24 passed. |
| Specific persisted audit workflow | `python -m pytest -vv -s tests/test_audits.py::test_audit_api_persists_run_findings_decision_and_clearance_with_hash` (`services/api`) | 1 passed, including GET reload of findings and workspace latest-audit linkage. |
| Audit persistence failure regression | `python -m pytest -vv -s tests/test_audits.py::test_audit_persistence_failure_returns_safe_error_and_logs_database_code` (`services/api`) | 1 passed; simulated PostgreSQL undefined-column failure returns a safe 503, logs SQLSTATE 42703 without SQL/content, and rolls back the pending run. |
| Full backend suite | `python -m pytest -q tests` (`services/api`) | **81 passed, 4 skipped** in 9.25 seconds; exit code 0. The four skips are PostgreSQL integration tests that are opt-in and require a configured test PostgreSQL database. |
| PostgreSQL integration suite | With `PROOFMINT_RUN_POSTGRES_INTEGRATION=1` and `DATABASE_URL` scoped to a unique disposable schema: `python -m pytest -vv -s tests/test_audits_postgres.py tests/test_candidate_rules_postgres.py tests/test_imported_review_postgres.py tests/test_imports_postgres.py` (`services/api`) | **4 passed** in 4.03 seconds after Alembic revisions `0001` through `0005` were applied in schema `pm_r3_test_80cfa58fed73`. A later read-only query confirmed this named schema no longer exists. No default/public schema or production Neon was used. |
| Deterministic evaluation | `python -m app.services.evaluation` (`services/api`) | 8 synthetic cases; TP 4, FP 0, FN 0; precision 1.0, recall 1.0; evidence outcomes: 2 verified, 1 uncertain, 1 rejected, 4/4 expected outcome matches; repairs 5/5 valid (2 safe refusals); run consistency 8/8 (1.0). |
| Frontend workspace tests | `npm run test:workspace` (`apps/web`) | **11 passed, 0 failed** across workspace-session, audit-copy, canonical workflow, response validation, and audit-history state tests. |
| Frontend lint | `npm run lint` (`apps/web`) | Passed; no ESLint warnings or errors. |
| Frontend TypeScript | `npx tsc --noEmit` (`apps/web`) | Passed with exit code 0. |
| Frontend production build | `npm run build` (`apps/web`) | **Passed** with normal local filesystem permissions: compile, lint/type checks, static generation (9/9), build tracing, route summary, exit code 0. |

The sandboxed Next.js build failed with `EPERM: operation not permitted, mkdir` for `.next/server/app/studio`. That directory did not exist at inspection time, and the `.next` ACL grants the sandbox group read/execute only. This indicates a filesystem-permission boundary rather than a stale generated directory. The latest build was retried with normal local filesystem permissions and completed successfully, including build tracing and the route summary.

The full backend run collected 84 tests and is separate from the four opt-in PostgreSQL tests, which were then explicitly run against the disposable schema. The focused R3/API set and specific audit workflow passed after a workspace-isolation test fixture was aligned with actual extraction behavior. No test was weakened to accept unverified evidence.

The evaluation's 1.0 precision, 1.0 recall, and 1.0 run-consistency rate describe only the eight labeled synthetic cases. They are not estimates of real-world or production accuracy and do not establish performance on customer content.

## Evaluation dataset and formulas

The version-controlled `services/api/app/services/evaluation_cases.json` contains eight synthetic cases: compliant copy, restricted phrase, preferred terminology repair, exact approved fact, unsupported semantic claim, inconsistent source metadata, ambiguous guideline, and no approved evidence. Expected finding signatures and verification outcomes are declared in the dataset.

- Precision = true positive signatures / (true positive signatures + false positive signatures).
- Recall = true positive signatures / (true positive signatures + false negative signatures).
- A true positive requires matching finding type, case-folded phrase, and source filename.
- Verification results are counted as verified, uncertain, or rejected and compared against labeled case outcomes.
- Consistency compares normalized finding signatures plus verification outcome across two runs; random UUIDs and timestamps are excluded.
- Repair validity is an exact comparison with the labeled repaired output. Cases with no safe repair are expected to remain unchanged.
- Precision and recall are `null` for a zero denominator; consistency rate is `null` for an empty dataset.

The evaluation command reports observed values at execution time; values are not hardcoded into the report.

## Studio persistence diagnosis follow-up

A read-only inspection of the explicitly configured loopback PostgreSQL target found `alembic_version` at `0003_session_workspaces`, while the checked-in audit models and migrations require revisions `0004_evidence_locked_findings` and `0005_verification_review_reasons`. The local `audit_findings` table lacks `verification_status`, `verification_reason`, and `verification_explanation`; `finding_decisions` lacks `review_reason`. This explains the API audit insert failure against that local schema. No migration or write was performed against its shared `public` schema. The application now emits a sanitized SQLSTATE/constraint diagnostic and the UI keeps failed audits on the run stage, preserves the copy, and requires history refresh before retrying an uncertain request.

## Migration validation and scope

The four opt-in PostgreSQL integration tests ran after revisions `0001` through `0005` were applied to `pm_r3_test_80cfa58fed73`, a uniquely named temporary schema on loopback. The test wrapper reported dropping this schema at completion. The local database role could not create a new database, so isolation used a dedicated schema rather than a separate database. The `public` schema and production Neon were not migrated.

A separate local API-server schema, `pm_r3_ui_6f22bc02fb77`, was created for a planned browser run. The process received a stop signal, but its cleanup handler could not be confirmed. A read-only query found that exact schema still exists. It has been left untouched; no other schemas were enumerated or changed.

## Manual and browser workflow coverage

Automated ASGI integration tests exercise synthetic PDF ingestion, candidate-rule approval, facts/terms imports and review, auditing, evidence verification, hash-bound repair, decisions, clearance blocking and completion, workspace isolation, duplicate CSV handling, and the ambiguity endpoint. These are API-level workflow tests.

Browser E2E was **not run to completion**. The prior in-app browser attempt timed out reaching the local server (`net::ERR_CONNECTION_TIMED_OUT`). The Windows browser handoff then stopped because it could not determine the current browser URL with sufficient confidence. No browser workflow is reported as passed.

## Not run / unavailable

- No deployed production environment was queried or changed.
- Browser E2E remains incomplete; no deployed browser workflow was run.
- The Round 2 source report PDF was later supplied as reference. It is not a source for current feature status or test results; the new R3 report is based on current source and verified runs.
- The final R3 PDF is generated at `docs/round-3/PROOFMINT_R3_FINAL_REPORT.pdf`; local PDF metadata, text content, page count, and rendered pages were checked.

## Source-document retention and independent verification follow-up (26 October 2026)

### Root cause and scope

The earlier ingestion route read each uploaded PDF into memory, computed its SHA-256, extracted page text and candidate spans, persisted document metadata/rules, then closed the upload. It explicitly did not store PDF bytes or complete page text. The prior `source_document_not_retained` result therefore reflected an implementation gap, not a deleted or inaccessible configured object store. A read-only check found no `services/api/.data/source-documents` directory before this change. Historical records still contain their workspace, document, rule, hash, filename, page, and offsets; the missing binary cannot be reconstructed from those records. An old Northstar source remains uncertain until the exact original PDF is recovered and re-uploaded.

### Implemented path

- Original PDFs now go to a private filesystem root outside web assets. The default is `services/api/.data/source-documents`; `SOURCE_DOCUMENT_STORAGE_DIR` overrides it. Objects are addressed by workspace UUID, immutable document UUID, and SHA-256, created atomically, and are not exposed by a public/static endpoint.
- Uploads can name an existing workspace. An exact hash with consistent recorded size and page count restores the original document ID and existing rule rows. A different PDF gets a new document ID and separate rule records; it never replaces an older source version.
- Migration `0006_audit_source_version` adds nullable source-document ID/hash snapshots to findings and backfills rule-linked historical rows from their existing rule/document relations. The migration is forward-only and was **not applied to any database** in this verification pass.
- Verification reopens the retained PDF and checks its byte hash and size, readability/page count, workspace, source-document ID/hash snapshot, current approved rule, filename/page/offset references, and exact cited text at the page-local span. Missing or inaccessible files remain `uncertain`; mismatched hashes, versions, pages, spans, and insufficient source text are `rejected`.
- `POST /api/v1/audits/{audit_id}/verify-source-evidence` supports rechecking a historical finding after recovery. It requires the original submitted copy to hash to the audit's stored fingerprint. It updates only verification outcome/explanation fields; audit ID/hash, finding ID, rule ID, source-version snapshot, and human review decisions are preserved.
- Studio uploads in an active workspace retain that workspace, surface whether a source was retained/restored/already present, and offer the hash-bound historical source recheck when applicable.

### Exact verification results

Commands were run locally from the indicated directories. Backend tests used SQLite created by the test fixtures and temporary source-storage roots; no production or local PostgreSQL schema was changed.

| Check | Command | Result |
| --- | --- | --- |
| Focused source/audit set | `python -m pytest -q tests/test_evidence_verification.py tests/test_guidelines.py tests/test_audits.py tests/test_evaluation.py` (`services/api`) | 33 passed. |
| Full backend suite | `python -m pytest -q` (`services/api`) | **88 passed, 4 skipped** in 6.35 seconds. Skips are opt-in PostgreSQL integration tests. |
| Migration graph | `alembic history --verbose` (`services/api`) | Passed; linear head is `0006_audit_source_version` over `0005_verification_review_reasons`. No migration was run against a database. |
| Frontend workspace tests | `npm run test:workspace` (`apps/web`) | **17 passed, 0 failed**. |
| Frontend lint | `npm run lint` (`apps/web`) | Passed; no ESLint warnings or errors. |
| TypeScript | `npx tsc --noEmit` (`apps/web`) | Passed; exit code 0. |
| Sandboxed build attempt | `npm run build` (`apps/web`) | Failed with `EPERM` creating `.next/types/app/studio`; the generated `.next` tree is read-only to the sandbox. |
| Production build retry | `npm run build` (`apps/web`, with workspace write access) | Passed: compile, lint/type checks, all 9 static pages, tracing, and route summary; exit code 0. |
| Inaccessible source regression | `python -m pytest -q tests/test_evidence_verification.py` (`services/api`) | **2 passed**, including simulated filesystem access denial. |

The source-specific tests cover successful retained-PDF verification, missing files, corrupted stored bytes, mismatched source-version hashes, wrong workspace, incorrect page and page span, insufficient citation text, exact-hash recovery in the existing workspace, unchanged rule/document/audit IDs, different-PDF versioning, and rechecking only with the exact audited marketing copy.

### Remaining requirements and limits

- This is a local private filesystem backend, not a cloud object store. External deployments must explicitly configure durable private storage with access control, backup/restore, retention, monitoring, and malware-scanning procedures. There is no authentication/tenant authorization in this application, and source PDFs must not be placed under a public web root.
- No historical source bytes existed locally to verify the reported Northstar PDF during this pass. The existing finding was not fabricated or marked verified. Re-upload the identical original PDF into its existing workspace, then re-enter/provide the exact audited copy if it is not in browser state, and run the source recheck. A different PDF will remain a separate version and cannot satisfy that historical citation.
- PostgreSQL integration tests and migration `0006` were not run/applied in this pass. The Alembic migration graph was inspected, and all automated verification used isolated SQLite schemas and temporary filesystem roots.
- Earlier full-suite runs before the workspace test fixture was isolated created six small synthetic PDFs in the ignored private default store. They are not mapped to any surviving test database rows and were left untouched to preserve local files. The final full-suite run used a temporary storage root and did not add to that directory.
