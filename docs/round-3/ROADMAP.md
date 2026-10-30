# Proofmint — Product Roadmap

## Completed in this local Round 3 pass

- Independent verification of retained source PDFs, exact page spans, evidence records, and immutable document-version relationships with verified, uncertain, and rejected outcomes.
- Hash-bound, preview-only repairs for approved preferred terminology, with human decision records and re-audit flow.
- Versioned synthetic evaluation cases and computed metrics.
- Workspace-scoped, rule-level ambiguity aggregates with recorded review reasons and minimum evidence.
- Studio integration for verification outcomes, editable repair previews, review notes, and real radar data.
- Forward-only migrations and local isolated-schema migration validation.
- Latest local source-retention verification results are recorded in `TESTING_REPORT.md`; opt-in PostgreSQL integration tests remain separately configured and are not claimed by the SQLite suite.
- Round 3 submission documentation and a final report PDF prepared locally. Browser E2E remains incomplete and is not counted as delivered verification.

## Next, before external deployment

1. Add authentication, workspace authorization, reviewer identity, and per-workspace access controls.
2. Add durable revision identifiers and a privacy-reviewed way to audit the transition from accepted repair to re-audited content without storing complete copy.
3. Add representative approved rule and term fixtures and broaden labeled evaluation cases across multiple source/offset patterns; publish score confidence and limitations alongside metrics.
4. Before external deployment, configure and validate durable private object storage, backup/restore, retention, malware scanning, and authenticated access; the current local filesystem backend is not a production storage service.
5. Review reason retention, access, and redaction requirements before making free-text reasons generally available.
6. Add observability, rate limits, backup/restore procedures, and production PostgreSQL integration coverage in an isolated deployment environment.
7. Test assistive technology and browser-level journeys across supported desktop and mobile browsers.
8. Confirm cleanup of the specifically named temporary UI-test schema `pm_r3_ui_6f22bc02fb77` before reusing the local database; it was found to exist by a read-only check and was intentionally not changed during closeout.

## Longer term

- Optional semantic retrieval or model-assisted checks behind explicit provenance, evaluation gates, and human review.
- Minimal token repair optimization with measurable intent/cadence constraints and a labeled human-rated evaluation set.
- Organization-specific rule health analytics after reviewer identities and access controls exist.
- Jurisdiction-specific guidance only when sourced from reviewed legal materials and clearly separated from legal advice.

No LLM analysis, production-grade regulatory judgment, automatic publishing, or automatic clearance is claimed by the current implementation.
