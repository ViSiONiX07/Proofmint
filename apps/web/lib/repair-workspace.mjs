import { summarizeRepairEligibility } from "./repair-preview.mjs";
import { getRepairDecisionHistory } from "./repair-decisions.mjs";

/** Derive reviewer-facing totals from the audit, server preview, and persisted history. */
export function summarizeRepairWorkspace(audit, preview) {
  const findings = Array.isArray(audit?.findings) ? audit.findings : [];
  const replacements = Array.isArray(preview?.replacements) ? preview.replacements : [];
  const eligibility = summarizeRepairEligibility(findings);
  const latest = new Map();
  for (const decision of getRepairDecisionHistory(audit)) {
    const previous = latest.get(decision.finding_id);
    if (!previous || Date.parse(decision.created_at) >= Date.parse(previous.created_at)) latest.set(decision.finding_id, decision);
  }
  const currentProposalIds = new Set(replacements.map(({ finding_id }) => finding_id));
  const openFindings = findings.filter(({ status }) => status === "pending_review" || status === "flagged");
  const unsupportedFindings = preview
    ? openFindings.filter(({ id }) => !currentProposalIds.has(id))
    : [];
  const accepted = [...latest.values()].filter(({ action }) => action === "accept").length;
  const edited = [...latest.values()].filter(({ action }) => action === "edit").length;
  const rejected = [...latest.values()].filter(({ action }) => action === "reject").length;
  const awaiting = [...currentProposalIds].filter((id) => !latest.has(id)).length;
  return {
    totalFindings: eligibility.total,
    dismissedFindings: eligibility.dismissed,
    eligibleFindings: preview ? currentProposalIds.size : 0,
    awaitingDecision: awaiting,
    accepted,
    edited,
    rejected,
    withoutEligibleRepair: unsupportedFindings.length,
    unsupportedFindings,
    closedFindings: findings.filter(({ status }) => status === "dismissed" || status === "resolved"),
    latestByFinding: latest,
  };
}
