export const STUDIO_STAGES = Object.freeze([
  Object.freeze({ number: 1, id: "knowledge", label: "Configure approved brand knowledge" }),
  Object.freeze({ number: 2, id: "rules", label: "Review and approve the rules" }),
  Object.freeze({ number: 3, id: "content", label: "Submit marketing content" }),
  Object.freeze({ number: 4, id: "audit", label: "Run the content audit" }),
  Object.freeze({ number: 5, id: "findings", label: "Verify the findings" }),
  Object.freeze({ number: 6, id: "repair", label: "Correct and review" }),
  Object.freeze({ number: 7, id: "evaluation", label: "Evaluation and Ambiguity Radar" }),
]);

const UUID_PATTERN = /^[a-f\d]{8}-[a-f\d]{4}-[1-8][a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i;

/** @param {unknown} value @returns {{valid: boolean, auditId: string | null}} */
export function getWorkspaceLatestAuditId(value) {
  if (
    !value
    || typeof value !== "object"
    || !Array.isArray(value.documents)
    || !("latest_audit_id" in value)
    || !(value.latest_audit_id === null || (typeof value.latest_audit_id === "string" && UUID_PATTERN.test(value.latest_audit_id)))
  ) return { valid: false, auditId: null };
  return { valid: true, auditId: value.latest_audit_id };
}

/** @param {unknown} value @param {string} workspaceId */
export function isPersistedAuditResponse(value, workspaceId) {
  return Boolean(
    value
    && typeof value === "object"
    && typeof value.id === "string"
    && UUID_PATTERN.test(value.id)
    && typeof workspaceId === "string"
    && UUID_PATTERN.test(workspaceId)
    && value.workspace_id === workspaceId
    && typeof value.content_sha256 === "string"
    && /^[a-f\d]{64}$/i.test(value.content_sha256)
    && typeof value.created_at === "string"
    && !Number.isNaN(Date.parse(value.created_at))
    && Number.isInteger(value.character_count)
    && value.character_count >= 0
    && Number.isInteger(value.approved_rules_considered)
    && Number.isInteger(value.supported_checks_performed)
    && Number.isInteger(value.rules_unevaluated)
    && Array.isArray(value.findings)
    && value.findings.every((finding) => finding && typeof finding === "object" && finding.audit_id === value.id && typeof finding.id === "string" && UUID_PATTERN.test(finding.id) && typeof finding.finding_type === "string" && Number.isInteger(finding.match_start) && Number.isInteger(finding.match_end))
    && Array.isArray(value.decisions)
    && Array.isArray(value.scope_limitations),
  );
}

/** Validate the explicit existing-workspace opener against its latest audit. */
export function resolveExistingWorkspaceAudit(workspace, audit) {
  const workspaceId = workspace && typeof workspace === "object" && typeof workspace.id === "string" ? workspace.id : null;
  const latest = getWorkspaceLatestAuditId(workspace);
  if (!workspaceId || !latest.valid || !latest.auditId || !isPersistedAuditResponse(audit, workspaceId) || audit.id !== latest.auditId) return null;
  return { workspaceId, auditId: audit.id, auditHash: audit.content_sha256 };
}

export function resolveWorkflowNavigation(target, hasPersistedAudit, auditedCopyIsCurrent = hasPersistedAudit) {
  if (!Number.isInteger(target) || target < 1 || target > STUDIO_STAGES.length) {
    return { stage: 1, blocked: true };
  }
  if (target >= 6 && (!hasPersistedAudit || !auditedCopyIsCurrent)) {
    return { stage: 4, blocked: true };
  }
  return { stage: target, blocked: false };
}

export function getStageHeading(activeStage) {
  const stage = STUDIO_STAGES.find(({ number }) => number === activeStage);
  return stage ? `${stage.number}. ${stage.label}` : "";
}

export function getClearanceReadiness(findings, auditCopyIsCurrent) {
  if (!auditCopyIsCurrent) {
    return {
      canIssueClearance: false,
      unresolvedCount: 0,
      reason: "The editor no longer matches the persisted audit. Run a new audit before clearance.",
    };
  }
  const unresolvedCount = (Array.isArray(findings) ? findings : [])
    .filter(({ status }) => status === "pending_review" || status === "flagged").length;
  return {
    canIssueClearance: unresolvedCount === 0,
    unresolvedCount,
    reason: unresolvedCount
      ? `Resolve or dismiss all ${unresolvedCount} pending or flagged finding${unresolvedCount === 1 ? "" : "s"} before issuing clearance.`
      : "All actionable findings have a persisted review decision.",
  };
}

export function getWorkflowProgress(activeStage, completedStages, visitedStages) {
  visitedStages = visitedStages || new Set();
  return STUDIO_STAGES.map((stage) => ({
    ...stage,
    state: stage.number === activeStage
      ? "active"
      : completedStages.has(stage.number)
        ? "complete"
      : visitedStages.has(stage.number)
        ? "visited"
        : "upcoming",
  }));
}

export const STUDIO_STEPPER_SHORT_LABELS = Object.freeze({
  1: "Guidelines",
  2: "Evidence",
  3: "Rules",
  4: "Copy",
  5: "Findings",
  6: "Repair",
  7: "Evaluation",
});

/** Completed steps come from persisted actions, never from merely visiting a screen. */
export function getCompletedStudioStages({
  hasGuidelineDocument = false,
  hasActiveCsvImport = false,
  hasRuleReviewDecision = false,
  hasPersistedAudit = false,
  hasPersistedRepairDecision = false,
} = {}) {
  const completed = new Set();
  if (hasGuidelineDocument) completed.add(1);
  if (hasActiveCsvImport) completed.add(2);
  if (hasRuleReviewDecision) completed.add(3);
  if (hasPersistedAudit) {
    completed.add(4);
    completed.add(5);
  }
  if (hasPersistedRepairDecision) completed.add(6);
  return completed;
}
