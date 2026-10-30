/**
 * Parsing and labeling for the version-aware extraction refresh.
 *
 * The API compares stored rules with a corrected re-extraction by source page and character
 * span. Everything here is read-only and refuses inconsistent payloads rather than rendering
 * a comparison a reviewer might act on: a shown diff must never overstate what would change.
 */

const COMPARISONS = new Set(["unchanged", "changed", "added", "removed"]);
const REVIEW_STATUSES = new Set(["pending_review", "approved", "rejected"]);

/** @typedef {"unchanged"|"changed"|"added"|"removed"} ComparisonKind */
/** @typedef {{comparison: ComparisonKind, source_page: number, source_start_offset: number, source_end_offset: number, existing_rule_id: string|null, existing_rule_text: string|null, existing_review_status: "pending_review"|"approved"|"rejected"|null, extracted_rule_text: string|null, extracted_category: string|null, decision_carried_forward: boolean}} RuleSpanComparison */
/** @typedef {{workspace_id: string, document_id: string, source_filename: string, source_sha256: string, page_count: number, current_revision: number, next_revision: number, already_current: boolean, existing_rule_count: number, extracted_rule_count: number, unchanged_count: number, changed_count: number, added_count: number, removed_count: number, comparisons: RuleSpanComparison[], limitations: string[]}} ExtractionRevisionPreview */

const isText = (value) => typeof value === "string" && value.length > 0;
const isCount = (value) => Number.isInteger(value) && value >= 0;

/** @param {unknown} value @returns {RuleSpanComparison|null} */
function parseComparison(value) {
  if (!value || typeof value !== "object") return null;
  if (!COMPARISONS.has(value.comparison)) return null;
  if (!Number.isInteger(value.source_page) || value.source_page < 1) return null;
  if (!isCount(value.source_start_offset) || !isCount(value.source_end_offset)) return null;
  if (value.source_end_offset <= value.source_start_offset) return null;
  // A span carries an existing side unless it is newly extracted, and an extracted side
  // unless the corrected extractor no longer produces it. A missing side must be null.
  const hasExisting = value.comparison !== "added";
  const hasExtracted = value.comparison !== "removed";
  if (hasExisting) {
    if (!isText(value.existing_rule_id) || !isText(value.existing_rule_text)) return null;
    if (!REVIEW_STATUSES.has(value.existing_review_status)) return null;
  } else if (value.existing_rule_id !== null || value.existing_rule_text !== null || value.existing_review_status !== null) {
    return null;
  }
  if (hasExtracted) {
    if (!isText(value.extracted_rule_text)) return null;
    if (value.extracted_category !== null && typeof value.extracted_category !== "string") return null;
  } else if (value.extracted_rule_text !== null || value.extracted_category !== null) {
    return null;
  }
  // A decision may only be carried forward onto a byte-identical rule a human already reviewed.
  if (value.decision_carried_forward !== (value.comparison === "unchanged" && value.existing_review_status !== "pending_review")) return null;
  return /** @type {RuleSpanComparison} */ (value);
}

/**
 * Validate a refresh preview and bind it to the document and workspace it was requested for.
 * Returns null when the payload is inconsistent, so the caller can refuse to render a diff.
 *
 * @param {unknown} value
 * @param {{documentId?: string|null, workspaceId?: string|null}} expected
 * @returns {ExtractionRevisionPreview|null}
 */
export function parseExtractionRevisionPreview(value, { documentId = null, workspaceId = null } = {}) {
  if (!value || typeof value !== "object") return null;
  if (!isText(value.workspace_id) || !isText(value.document_id)) return null;
  if (workspaceId !== null && value.workspace_id !== workspaceId) return null;
  if (documentId !== null && value.document_id !== documentId) return null;
  if (!isText(value.source_filename) || !/^[a-f\d]{64}$/i.test(value.source_sha256 ?? "")) return null;
  if (!Number.isInteger(value.page_count) || value.page_count < 1) return null;
  if (!Number.isInteger(value.current_revision) || value.current_revision < 1) return null;
  if (value.next_revision !== value.current_revision + 1) return null;
  if (typeof value.already_current !== "boolean") return null;
  for (const field of ["existing_rule_count", "extracted_rule_count", "unchanged_count", "changed_count", "added_count", "removed_count"]) {
    if (!isCount(value[field])) return null;
  }
  if (!Array.isArray(value.comparisons) || !Array.isArray(value.limitations)) return null;
  if (!value.limitations.every((item) => typeof item === "string")) return null;

  const comparisons = [];
  const seen = new Set();
  for (const raw of value.comparisons) {
    const item = parseComparison(raw);
    if (!item) return null;
    const key = `${item.source_page}:${item.source_start_offset}-${item.source_end_offset}`;
    if (seen.has(key)) return null;
    seen.add(key);
    comparisons.push(item);
  }
  // The reported counts are derived from the comparison list, so they must agree with it.
  const counted = (kind) => comparisons.filter((item) => item.comparison === kind).length;
  if (value.unchanged_count !== counted("unchanged") || value.changed_count !== counted("changed")) return null;
  if (value.added_count !== counted("added") || value.removed_count !== counted("removed")) return null;
  return /** @type {ExtractionRevisionPreview} */ ({ ...value, comparisons });
}

/**
 * Validate the response that records an applied (or already-present) revision.
 *
 * @param {unknown} value
 * @param {{workspaceId?: string|null}} expected
 * @returns {{workspace_id: string, document_id: string, supersedes_document_id: string|null, extraction_revision: number, already_existed: boolean, source_filename: string, source_sha256: string, page_count: number, file_size_bytes: number, candidate_rule_count: number, approved_rule_count: number, pending_rule_count: number, rejected_rule_count: number, carried_forward_decisions: number, removed_rule_count: number, created_at: string|null, limitations: string[]}|null}
 */
export function parseExtractionRevision(value, { workspaceId = null } = {}) {
  if (!value || typeof value !== "object") return null;
  if (!isText(value.workspace_id) || !isText(value.document_id)) return null;
  if (workspaceId !== null && value.workspace_id !== workspaceId) return null;
  if (typeof value.already_existed !== "boolean") return null;
  if (!Number.isInteger(value.extraction_revision) || value.extraction_revision < 1) return null;
  if (value.supersedes_document_id !== null && !isText(value.supersedes_document_id)) return null;
  // A fresh revision must name the revision it supersedes; a replay must report its own id.
  if (!value.already_existed && value.supersedes_document_id === null) return null;
  if (!isText(value.source_filename) || !/^[a-f\d]{64}$/i.test(value.source_sha256 ?? "")) return null;
  if (!Number.isInteger(value.page_count) || value.page_count < 1) return null;
  if (!Number.isInteger(value.file_size_bytes) || value.file_size_bytes <= 0) return null;
  for (const field of ["candidate_rule_count", "approved_rule_count", "pending_rule_count", "rejected_rule_count", "carried_forward_decisions", "removed_rule_count"]) {
    if (!isCount(value[field])) return null;
  }
  if (value.approved_rule_count + value.pending_rule_count + value.rejected_rule_count !== value.candidate_rule_count) return null;
  if (value.carried_forward_decisions > value.approved_rule_count + value.rejected_rule_count) return null;
  if (!Array.isArray(value.limitations) || !value.limitations.every((item) => typeof item === "string")) return null;
  if (value.created_at !== null && (typeof value.created_at !== "string" || Number.isNaN(Date.parse(value.created_at)))) return null;
  return value;
}

/** @param {ExtractionRevisionPreview} preview */
export function summarizeExtractionPreview(preview) {
  const counts = { unchanged: 0, changed: 0, added: 0, removed: 0 };
  for (const item of preview.comparisons) counts[item.comparison] += 1;
  const changingSpans = counts.changed + counts.added + counts.removed;
  const extracted = preview.comparisons.filter((item) => item.extracted_rule_text !== null);
  const newPending = extracted.filter((item) => !item.decision_carried_forward).length;
  const carriedDecisions = extracted.length - newPending;
  return {
    counts,
    totalSpans: preview.comparisons.length,
    changingSpans,
    carriedDecisions,
    newPending,
    revisionLabel: `Rule-set revision ${preview.current_revision} → ${preview.next_revision}`,
    sourceLabel: `${preview.source_filename} · ${preview.page_count} page${preview.page_count === 1 ? "" : "s"} · SHA-256 ${preview.source_sha256.slice(0, 12)}…`,
    headline: preview.already_current
      ? "The stored rules already match the corrected extractor, so a refresh would write nothing."
      : `${changingSpans} of ${preview.comparisons.length} source span${preview.comparisons.length === 1 ? "" : "s"} would change.`,
    reviewNotice: newPending
      ? `${newPending} refreshed candidate${newPending === 1 ? "" : "s"} would start as pending review and cannot affect audits until a human approves them.`
      : "No refreshed candidate would start unreviewed.",
    removalNotice: counts.removed
      ? `${counts.removed} malformed or superseded rule${counts.removed === 1 ? "" : "s"} would be omitted from the new revision. The current revision keeps them.`
      : "No stored rule would be omitted.",
  };
}

/** @param {RuleSpanComparison} item @param {string} sourceFilename */
export function describeExtractionComparison(item, sourceFilename) {
  const labels = {
    unchanged: "Unchanged",
    changed: "Reworded",
    added: "Newly extracted",
    removed: "Omitted from the new revision",
  };
  return {
    ...item,
    sourceLabel: `${sourceFilename} · page ${item.source_page}`,
    spanLabel: `page ${item.source_page} · characters ${item.source_start_offset}–${item.source_end_offset}`,
    comparisonLabel: labels[item.comparison],
    existingText: item.existing_rule_text,
    extractedText: item.extracted_rule_text,
    existingStatusLabel: item.existing_review_status ? item.existing_review_status.replaceAll("_", " ") : null,
    decisionLabel: item.decision_carried_forward
      ? "This human decision carries forward onto the identical refreshed rule."
      : item.extracted_rule_text !== null
        ? "Starts as pending review; it needs a human decision."
        : "The earlier revision keeps this rule and its human decision.",
  };
}

/** @param {ReturnType<typeof parseExtractionRevision>} revision */
export function describeAppliedRevision(revision) {
  return {
    reference: `revision ${revision.extraction_revision}`,
    documentId: revision.document_id,
    headline: revision.already_existed
      ? `No new revision was needed. Rule-set revision ${revision.extraction_revision} already matches the corrected extractor.`
      : `Rule-set revision ${revision.extraction_revision} created with ${revision.candidate_rule_count} extracted candidate${revision.candidate_rule_count === 1 ? "" : "s"}.`,
    detailLabel: `${revision.pending_rule_count} pending review · ${revision.approved_rule_count} approved · ${revision.rejected_rule_count} rejected`,
    carriedLabel: revision.already_existed
      ? "Nothing was written and no stored rule changed."
      : `${revision.carried_forward_decisions} identical rule${revision.carried_forward_decisions === 1 ? "" : "s"} kept an existing human decision; the rest need review.`,
    removalLabel: revision.removed_rule_count
      ? `${revision.removed_rule_count} stored rule${revision.removed_rule_count === 1 ? "" : "s"} were not carried into this revision; the superseded revision keeps them.`
      : "Every stored rule of the superseded revision is still recorded there.",
    provenanceLabel: `${revision.source_filename} · ${revision.page_count} page${revision.page_count === 1 ? "" : "s"} · SHA-256 ${revision.source_sha256.slice(0, 12)}…`,
  };
}
