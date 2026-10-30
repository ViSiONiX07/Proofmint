const ACTIONS = new Set(["accept", "edit", "reject"]);

/** Validate the append-only repair history returned when an audit is refreshed. */
export function getRepairDecisionHistory(audit) {
  if (!audit || typeof audit !== "object" || !Array.isArray(audit.repair_decisions)) return [];
  return audit.repair_decisions.filter((decision) =>
    decision
    && typeof decision === "object"
    && typeof decision.id === "string"
    && typeof decision.finding_id === "string"
    && ACTIONS.has(decision.action)
    && (decision.proposed_replacement === null || typeof decision.proposed_replacement === "string")
    && typeof decision.created_at === "string"
    && !Number.isNaN(Date.parse(decision.created_at))
  );
}

/** A successful server preview classifies every open finding; proposals still need persisted review. */
export function hasPersistedRepairCompletion(audit, preview, { loading = false, error = "" } = {}) {
  if (loading || error || !audit || typeof audit !== "object" || !Array.isArray(audit.findings) || !preview) return false;
  const successfulStates = new Set(["no_findings", "no_open_findings", "no_supported_repairs", "preview_available"]);
  if (!successfulStates.has(preview.status) || !Array.isArray(preview.replacements)) return false;
  const decided = new Set(getRepairDecisionHistory(audit).map((decision) => decision.finding_id));
  return preview.replacements.every((replacement) =>
    replacement && typeof replacement.finding_id === "string" && decided.has(replacement.finding_id),
  );
}
