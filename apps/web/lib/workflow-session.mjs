export const WORKFLOW_SESSION_STORAGE_KEY = "proofmint.workflowSession";
const MAX_COPY_LENGTH = 200_000;

/** Clean in-memory state shared by reset and regression tests. */
export function createFreshStudioContext() {
  return {
    workspaceId: null, auditId: null, auditHash: null, step: 1, copy: "", visitedStages: [1],
    selectedExistingAudit: null, auditResult: null, auditRestored: false, repairResult: null,
    document: null, rules: null, importedEvidence: [], findings: [], repairDecisions: [],
  };
}

/** A clean persisted workflow snapshot contains no prior workspace, audit, hash, or copy. */
export function createFreshWorkflowSession() {
  const { workspaceId, auditId, auditHash, step, copy, visitedStages } = createFreshStudioContext();
  return { workspaceId, auditId, auditHash, step, copy, visitedStages };
}

/** Fresh submissions have no existing-audit restriction; explicit opens require an exact hash. */
export function getExistingAuditCopyError(selectedAudit, submittedCopyHash) {
  if (!selectedAudit) return null;
  return typeof submittedCopyHash === "string" && submittedCopyHash.toLowerCase() === selectedAudit.hash?.toLowerCase()
    ? null
    : "This workspace is opened on an existing audit. Enter the exact original copy to reload it; no new audit was created.";
}

/** @param {Pick<Storage, "getItem">} storage */
export function readWorkflowSession(storage) {
  try {
    const raw = storage.getItem(WORKFLOW_SESSION_STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value || value.version !== 1
      || !(value.workspaceId === null || (typeof value.workspaceId === "string" && value.workspaceId.trim()))
      || !(value.auditId === null || (typeof value.auditId === "string" && value.auditId.trim()))
      || !Number.isInteger(value.step) || value.step < 1 || value.step > 7
      || typeof value.copy !== "string" || value.copy.length > MAX_COPY_LENGTH
      || !(value.auditHash === null || (typeof value.auditHash === "string" && /^[a-f\d]{64}$/i.test(value.auditHash)))
      || (value.visitedStages !== undefined && (!Array.isArray(value.visitedStages) || value.visitedStages.some((stage) => !Number.isInteger(stage) || stage < 1 || stage > 7)))) return null;
    return { ...value, visitedStages: [...new Set(value.visitedStages ?? [value.step])] };
  } catch {
    return null;
  }
}

/** @param {Pick<Storage, "setItem">} storage @param {{workspaceId: string|null, auditId: string|null, auditHash: string|null, step: number, copy: string, visitedStages?: number[]}} value */
export function saveWorkflowSession(storage, value) {
  if (!Number.isInteger(value.step) || value.step < 1 || value.step > 7 || value.copy.length > MAX_COPY_LENGTH
    || (value.visitedStages !== undefined && (!Array.isArray(value.visitedStages) || value.visitedStages.some((stage) => !Number.isInteger(stage) || stage < 1 || stage > 7)))) return false;
  try {
    storage.setItem(WORKFLOW_SESSION_STORAGE_KEY, JSON.stringify({ version: 1, ...value }));
    return true;
  } catch {
    return false;
  }
}

/** @param {Pick<Storage, "removeItem">} storage */
export function clearWorkflowSession(storage) {
  storage.removeItem(WORKFLOW_SESSION_STORAGE_KEY);
}

/** @param {ReturnType<typeof readWorkflowSession>} saved @param {{workspaceId: string|null, auditId: string|null, auditHash: string|null, hasDocument: boolean, copyMatchesAudit: boolean}} current */
export function resolveWorkflowSession(saved, current) {
  const fallback = (reason) => ({ step: current.hasDocument ? (current.auditId && current.copyMatchesAudit ? 5 : 4) : current.workspaceId ? 2 : 1, restored: false, reason });
  if (!saved) return { step: 1, restored: false, reason: null };
  if (saved.workspaceId !== current.workspaceId) return fallback("The saved stage belongs to a different workspace.");
  if (saved.step >= 2 && !current.workspaceId) return fallback("The workspace for the saved stage is no longer active.");
  if (saved.step >= 3 && !current.hasDocument) return fallback("The guideline document required by the saved stage is unavailable.");
  if (saved.step >= 5 && (!current.auditId || saved.auditId !== current.auditId || saved.auditHash !== current.auditHash || !current.copyMatchesAudit)) {
    return fallback("The saved audit or its exact submitted copy no longer matches this workspace.");
  }
  return { step: saved.step, restored: true, reason: null };
}
