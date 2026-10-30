const REPAIR_STATES = new Set([
  "no_findings",
  "no_open_findings",
  "review_required",
  "no_supported_repairs",
  "preview_available",
]);

/** @param {unknown} value @param {string} auditId @param {string} contentSha256 */
export function isRepairPreviewResponse(value, auditId, contentSha256) {
  return Boolean(
    value
    && typeof value === "object"
    && value.audit_id === auditId
    && value.original_sha256 === contentSha256
    && REPAIR_STATES.has(value.status)
    && Number.isInteger(value.findings_reviewed)
    && value.findings_reviewed >= 0
    && typeof value.repaired_content === "string"
    && Array.isArray(value.replacements)
    && value.replacements.every((replacement) => replacement
      && typeof replacement.finding_id === "string"
      && Number.isInteger(replacement.start)
      && Number.isInteger(replacement.end)
      && typeof replacement.original === "string"
      && typeof replacement.replacement === "string"
      && typeof replacement.source_label === "string"
      && typeof replacement.source_filename === "string"
      && typeof replacement.reason === "string")
    && Number.isInteger(value.findings_before)
    && Number.isInteger(value.findings_after)
    && Array.isArray(value.limitations),
  );
}

/** @param {{loading?: boolean, error?: string, result?: {status: string}|null}} state */
export function getRepairViewState({ loading = false, error = "", result = null } = {}) {
  if (loading) return "loading";
  if (error) return "error";
  if (!result) return "idle";
  if (!REPAIR_STATES.has(result.status)) return "error";
  return result.status;
}

/**
 * Count persisted findings by review state and by whether a repair could be offered.
 *
 * `repairEligible` mirrors the server's deterministic repair filter exactly: a pending
 * preferred-terminology finding that carries approved terminology and a verified literal
 * replacement. It is a candidate count, not a promise: the repair route re-verifies the
 * evidence and returns "no_supported_repairs" when verification no longer holds.
 *
 * @param {Array<{status?: string, finding_type?: string, rule_id?: string|null, fact_id?: string|null,
 *   term_id?: string|null, verification_status?: string, suggested_correction?: string|null,
 *   matched_phrase?: string}>} findings
 */
export function summarizeRepairEligibility(findings) {
  const list = Array.isArray(findings) ? findings : [];
  const count = (predicate) => list.filter(predicate).length;
  const dismissed = count((finding) => finding?.status === "dismissed");
  const resolved = count((finding) => finding?.status === "resolved");
  const flagged = count((finding) => finding?.status === "flagged");
  const informational = count((finding) => finding?.status === "informational");
  const pending = count((finding) => finding?.status === "pending_review");
  const repairEligible = count((finding) => ["pending_review", "flagged"].includes(finding?.status)
    && finding.finding_type === "preferred_terminology"
    && finding.term_id != null
    && finding.rule_id == null
    && finding.fact_id == null
    && finding.verification_status === "verified"
    && typeof finding.suggested_correction === "string"
    && finding.suggested_correction.length > 0
    && finding.suggested_correction !== finding.matched_phrase);
  return {
    total: list.length,
    dismissed,
    resolved,
    flagged,
    informational,
    pending,
    unresolved: pending + flagged,
    repairEligible,
    unresolvedWithoutSupportedRepair: pending + flagged - repairEligible,
  };
}

/** @param {Record<string, any>|null|undefined} finding @param {string|null} [latestDecision]
 * Explain why a persisted finding cannot currently receive a safe repair.
 */
export function getRepairIneligibilityReason(finding, latestDecision = null) {
  if (!finding || typeof finding !== "object") return "Finding details are unavailable.";
  if (!["pending_review", "flagged"].includes(finding.status)) {
    return `This finding is ${finding.status || "not open"} and is not reopened by Repair.`;
  }
  if (latestDecision === "reject") return "The proposal was rejected and will not be offered again.";
  if (finding.verification_status !== "verified") {
    return `Evidence status is ${finding.verification_status || "unavailable"}; a correction is not supported.`;
  }
  if (finding.finding_type === "restricted_phrase" && finding.rule_id != null && finding.term_id == null && finding.fact_id == null) {
    return "This phrase is verified against an approved restriction, but no approved replacement text is recorded. Repair only proposes verified preferred-term substitutions.";
  }
  if (finding.finding_type !== "preferred_terminology" || finding.term_id == null || finding.rule_id != null || finding.fact_id != null) {
    return `No deterministic repair is defined for ${(finding.finding_type || "this finding type").replaceAll("_", " ")}.`;
  }
  if (typeof finding.suggested_correction !== "string" || !finding.suggested_correction.trim()) {
    return "The approved terminology has no preferred replacement form.";
  }
  if (finding.suggested_correction === finding.matched_phrase) {
    return "The proposed wording is identical to the submitted wording.";
  }
  return "The server did not return a currently supported proposal after rechecking the approved evidence.";
}
