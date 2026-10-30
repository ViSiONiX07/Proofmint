import assert from "node:assert/strict";
import test from "node:test";

import {
  clearWorkflowSession,
  createFreshStudioContext,
  createFreshWorkflowSession,
  getExistingAuditCopyError,
  readWorkflowSession,
  resolveWorkflowSession,
  saveWorkflowSession,
  WORKFLOW_SESSION_STORAGE_KEY,
} from "./workflow-session.mjs";

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

const auditHash = "a".repeat(64);

test("same-session steps 2, 5, 6 and 7 restore with their workspace and exact audit context", () => {
  const session = storage();
  for (const step of [2, 5, 6, 7]) {
    saveWorkflowSession(session, { workspaceId: "workspace-a", auditId: "audit-a", auditHash, step, copy: "audited copy" });
    const restored = readWorkflowSession(session);
    const decision = resolveWorkflowSession(restored, {
      workspaceId: "workspace-a", auditId: "audit-a", auditHash, hasDocument: true, copyMatchesAudit: true,
    });
    assert.deepEqual(decision, { step, restored: true, reason: null });
  }
});

test("visited stages persist separately from completion and malformed visit lists are rejected", () => {
  const session = storage();
  saveWorkflowSession(session, { workspaceId: "workspace-a", auditId: null, auditHash: null, step: 4, copy: "draft", visitedStages: [1, 2, 4] });
  assert.deepEqual(readWorkflowSession(session).visitedStages, [1, 2, 4]);
  assert.equal(saveWorkflowSession(session, { workspaceId: "workspace-a", auditId: null, auditHash: null, step: 4, copy: "draft", visitedStages: [0, 9] }), false);
});

test("stale workspace or audit context falls back to the earliest valid stage", () => {
  const session = storage();
  saveWorkflowSession(session, { workspaceId: "workspace-a", auditId: "audit-a", auditHash, step: 6, copy: "audited copy" });
  assert.equal(resolveWorkflowSession(readWorkflowSession(session), {
    workspaceId: "workspace-b", auditId: "audit-b", auditHash, hasDocument: true, copyMatchesAudit: false,
  }).step, 4);
  assert.equal(resolveWorkflowSession(readWorkflowSession(session), {
    workspaceId: "workspace-a", auditId: "audit-b", auditHash: "b".repeat(64), hasDocument: true, copyMatchesAudit: false,
  }).step, 4);
});

test("missing document and invalid stored values safely fall back", () => {
  const session = storage();
  saveWorkflowSession(session, { workspaceId: "workspace-a", auditId: null, auditHash: null, step: 3, copy: "" });
  assert.equal(resolveWorkflowSession(readWorkflowSession(session), {
    workspaceId: "workspace-a", auditId: null, auditHash: null, hasDocument: false, copyMatchesAudit: false,
  }).step, 2);
  session.setItem(WORKFLOW_SESSION_STORAGE_KEY, "not-json");
  assert.equal(readWorkflowSession(session), null);
  session.setItem(WORKFLOW_SESSION_STORAGE_KEY, JSON.stringify({ version: 1, workspaceId: null, auditId: null, auditHash: null, step: 99, copy: "" }));
  assert.equal(readWorkflowSession(session), null);
});

test("an edited Step 4 draft can restore, but cannot reopen later audit stages", () => {
  const session = storage();
  saveWorkflowSession(session, { workspaceId: "workspace-a", auditId: "audit-a", auditHash, step: 4, copy: "edited draft" });
  const saved = readWorkflowSession(session);
  assert.deepEqual(resolveWorkflowSession(saved, {
    workspaceId: "workspace-a", auditId: "audit-a", auditHash, hasDocument: true, copyMatchesAudit: false,
  }), { step: 4, restored: true, reason: null });
  saveWorkflowSession(session, { workspaceId: "workspace-a", auditId: "audit-a", auditHash, step: 6, copy: "edited draft" });
  assert.equal(resolveWorkflowSession(readWorkflowSession(session), {
    workspaceId: "workspace-a", auditId: "audit-a", auditHash, hasDocument: true, copyMatchesAudit: false,
  }).step, 4);
});

test("starting a fresh session removes the workflow snapshot", () => {
  const session = storage();
  saveWorkflowSession(session, { workspaceId: null, auditId: null, auditHash: null, step: 2, copy: "" });
  clearWorkflowSession(session);
  assert.equal(readWorkflowSession(session), null);
});

test("starting fresh after opening an existing audit persists no old workspace, audit, hash, or copy", () => {
  const session = storage();
  const existing = { workspaceId: "workspace-old", auditId: "audit-old", auditHash, step: 4, copy: "old submitted copy", visitedStages: [1, 2, 3, 4] };
  saveWorkflowSession(session, existing);
  saveWorkflowSession(session, createFreshWorkflowSession());
  assert.deepEqual(readWorkflowSession(session), { version: 1, ...createFreshWorkflowSession() });
  assert.deepEqual(resolveWorkflowSession(readWorkflowSession(session), {
    workspaceId: null, auditId: null, auditHash: null, hasDocument: false, copyMatchesAudit: false,
  }), { step: 1, restored: true, reason: null });
});

test("fresh studio context clears existing-audit mode and all previous audit-owned state", () => {
  const fresh = createFreshStudioContext();
  assert.equal(fresh.selectedExistingAudit, null);
  assert.equal(fresh.workspaceId, null);
  assert.equal(fresh.auditId, null);
  assert.equal(fresh.auditHash, null);
  assert.equal(fresh.auditResult, null);
  assert.equal(fresh.auditRestored, false);
  assert.equal(fresh.repairResult, null);
  assert.deepEqual(fresh.findings, []);
  assert.deepEqual(fresh.repairDecisions, []);
  assert.deepEqual(fresh.importedEvidence, []);
});

test("fresh audit submissions are not blocked; explicit existing-audit opens still require the same copy hash", () => {
  const selected = { id: "audit-existing", hash: auditHash };
  assert.equal(getExistingAuditCopyError(null, "different-hash"), null);
  assert.equal(getExistingAuditCopyError(selected, auditHash.toUpperCase()), null);
  assert.match(getExistingAuditCopyError(selected, "different-hash"), /existing audit.*exact original copy/);
});
