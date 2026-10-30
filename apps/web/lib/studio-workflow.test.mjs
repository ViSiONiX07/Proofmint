import assert from "node:assert/strict";
import test from "node:test";

import {
  getWorkspaceLatestAuditId,
  getClearanceReadiness,
  getCompletedStudioStages,
  getStageHeading,
  getWorkflowProgress,
  resolveExistingWorkspaceAudit,
  isPersistedAuditResponse,
  resolveWorkflowNavigation,
  STUDIO_STAGES,
  STUDIO_STEPPER_SHORT_LABELS,
} from "./studio-workflow.mjs";

test("canonical workflow has seven ordered stages and stable headings", () => {
  assert.deepEqual(STUDIO_STAGES.map(({ number }) => number), [1, 2, 3, 4, 5, 6, 7]);
  assert.deepEqual(STUDIO_STAGES.map(({ label }) => label), [
    "Configure approved brand knowledge",
    "Review and approve the rules",
    "Submit marketing content",
    "Run the content audit",
    "Verify the findings",
    "Correct and review",
    "Evaluation and Ambiguity Radar",
  ]);
});

test("downstream correction and clearance stages require a persisted audit", () => {
  assert.deepEqual(resolveWorkflowNavigation(6, false), { stage: 4, blocked: true });
  assert.deepEqual(resolveWorkflowNavigation(7, false), { stage: 4, blocked: true });
  assert.deepEqual(resolveWorkflowNavigation(5, false), { stage: 5, blocked: false });
  assert.deepEqual(resolveWorkflowNavigation(6, true), { stage: 6, blocked: false });
  assert.deepEqual(resolveWorkflowNavigation(6, true, false), { stage: 4, blocked: true });
  assert.equal(getStageHeading(6), "6. Correct and review");
  assert.equal(getWorkflowProgress(6, new Set()).find(({ number }) => number === 6).state, "active");
});

test("clearance readiness follows persisted pending and flagged statuses, not uncertain evidence labels", () => {
  assert.equal(getClearanceReadiness([{ status: "pending_review", verification_status: "verified" }], true).canIssueClearance, false);
  assert.equal(getClearanceReadiness([{ status: "flagged", verification_status: "uncertain" }], true).canIssueClearance, false);
  assert.equal(getClearanceReadiness([
    { status: "dismissed", verification_status: "uncertain" },
    { status: "informational", verification_status: "verified" },
  ], true).canIssueClearance, true);
  assert.equal(getClearanceReadiness([{ status: "dismissed" }], false).canIssueClearance, false);
});

test("active and completed indicators come from real workflow state", () => {
  const progress = getWorkflowProgress(3, new Set([1, 2]));
  assert.deepEqual(progress.map(({ state }) => state), ["complete", "complete", "active", "upcoming", "upcoming", "upcoming", "upcoming"]);
});

test("visited stages keep their styling after navigation forward", () => {
  const visited = new Set([5, 6]);
  const progress = getWorkflowProgress(7, new Set(), visited);
  const states = progress.map(({ number, state }) => [number, state]);
  assert.deepEqual(states, [
    [1, "upcoming"],
    [2, "upcoming"],
    [3, "upcoming"],
    [4, "upcoming"],
    [5, "visited"],
    [6, "visited"],
    [7, "active"],
  ]);
});

test("step 1 remains upcoming when another step is active", () => {
  const progress = getWorkflowProgress(3, new Set());
  const stage1 = progress.find(({ number }) => number === 1);
  assert.equal(stage1.state, "upcoming");
});

test("step 6 stays visited when navigating from step 5 to step 7", () => {
  const visited = new Set([6]);
  const progress = getWorkflowProgress(7, new Set(), visited);
  const stage6 = progress.find(({ number }) => number === 6);
  const stage7 = progress.find(({ number }) => number === 7);
  assert.equal(stage6.state, "visited");
  assert.equal(stage7.state, "active");
});

test("step 1 stays upcoming after navigating away via visited stage", () => {
  const visited = new Set([1]);
  const progress = getWorkflowProgress(3, new Set(), visited);
  const stage1 = progress.find(({ number }) => number === 1);
  const stage3 = progress.find(({ number }) => number === 3);
  assert.equal(stage1.state, "visited");
  assert.equal(stage3.state, "active");
});

test("only a complete persisted audit response for this workspace is accepted", () => {
  const audit = {
    id: "9b0df2de-b72e-4589-a51e-a407a9e1eb7e",
    workspace_id: "5c62426f-a83d-4dd3-9f22-a53385bb412c",
    content_sha256: "a".repeat(64),
    created_at: "2026-10-26T00:00:00Z",
    character_count: 0,
    approved_rules_considered: 0,
    supported_checks_performed: 0,
    rules_unevaluated: 0,
    findings: [],
    decisions: [],
    scope_limitations: [],
  };
  assert.equal(isPersistedAuditResponse(audit, audit.workspace_id), true);
  assert.equal(isPersistedAuditResponse({ ...audit, id: "not-a-uuid" }, audit.workspace_id), false);
  assert.equal(isPersistedAuditResponse({ ...audit, workspace_id: "c7c58040-f8bf-4070-8c21-8419b1e1084b" }, audit.workspace_id), false);
  assert.equal(isPersistedAuditResponse({ ...audit, findings: undefined }, audit.workspace_id), false);
});

test("explicit existing-workspace selection accepts only its validated latest audit", () => {
  const workspaceId = "5c62426f-a83d-4dd3-9f22-a53385bb412c";
  const audit = {
    id: "9b0df2de-b72e-4589-a51e-a407a9e1eb7e", workspace_id: workspaceId, content_sha256: "a".repeat(64),
    created_at: "2026-10-26T00:00:00Z", character_count: 12, approved_rules_considered: 1,
    supported_checks_performed: 1, rules_unevaluated: 0, findings: [], decisions: [], scope_limitations: [],
  };
  const workspace = { id: workspaceId, documents: [], latest_audit_id: audit.id };
  assert.deepEqual(resolveExistingWorkspaceAudit(workspace, audit), { workspaceId, auditId: audit.id, auditHash: audit.content_sha256 });
  assert.equal(resolveExistingWorkspaceAudit(workspace, { ...audit, id: "c7c58040-f8bf-4070-8c21-8419b1e1084b" }), null);
  assert.equal(resolveExistingWorkspaceAudit({ ...workspace, latest_audit_id: null }, audit), null);
  assert.equal(resolveExistingWorkspaceAudit(workspace, { ...audit, workspace_id: "c7c58040-f8bf-4070-8c21-8419b1e1084b" }), null);
});

test("evaluation is stage 7 and is not completed by visiting another step", () => {
  assert.equal(STUDIO_STAGES[6].number, 7);
  assert.equal(STUDIO_STEPPER_SHORT_LABELS[7], "Evaluation");
  assert.deepEqual(resolveWorkflowNavigation(7, true), { stage: 7, blocked: false });
  const completed = getCompletedStudioStages({ hasGuidelineDocument: true, hasPersistedAudit: true });
  assert.equal(completed.has(1), true);
  assert.equal(completed.has(5), true);
  assert.equal(completed.has(6), false);
  assert.equal(completed.has(7), false);
  const progress = getWorkflowProgress(7, completed);
  assert.equal(progress.find(({ number }) => number === 7).state, "active");
  assert.equal(progress.find(({ number }) => number === 1).state, "complete");
});

test("Repair stays incomplete until persisted decisions cover every eligible finding", () => {
  const incomplete = getCompletedStudioStages({ hasGuidelineDocument: true, hasActiveCsvImport: true, hasRuleReviewDecision: true, hasPersistedAudit: true });
  assert.equal(incomplete.has(6), false);
  assert.deepEqual(getWorkflowProgress(6, incomplete).slice(5).map(({ state }) => state), ["active", "upcoming"]);

  const completed = getCompletedStudioStages({ hasPersistedAudit: true, hasPersistedRepairDecision: true });
  assert.equal(completed.has(6), true);
  assert.deepEqual(getWorkflowProgress(7, completed).slice(5).map(({ state }) => state), ["complete", "active"]);
});

test("returning to a completed step keeps it in the completed set", () => {
  const completed = getCompletedStudioStages({ hasGuidelineDocument: true, hasPersistedAudit: true });
  assert.equal(completed.has(1), true);
  assert.equal(completed.has(7), false);
  const onStep1 = getWorkflowProgress(1, completed);
  assert.equal(onStep1.find(({ number }) => number === 1).state, "active");
  assert.equal(onStep1.find(({ number }) => number === 7).state, "upcoming");
});

test("completed stages remain complete when visited; incomplete visited stages stay distinct", () => {
  const progress = getWorkflowProgress(4, new Set([1, 2]), new Set([1, 2, 3]));
  assert.deepEqual(progress.slice(0, 4).map(({ state }) => state), ["complete", "complete", "visited", "active"]);
});

test("workspace audit history distinguishes empty from malformed responses", () => {
  assert.deepEqual(getWorkspaceLatestAuditId({ documents: [], latest_audit_id: null }), { valid: true, auditId: null });
  assert.deepEqual(getWorkspaceLatestAuditId({ documents: [] }), { valid: false, auditId: null });
  assert.deepEqual(getWorkspaceLatestAuditId({ documents: [], latest_audit_id: "invalid" }), { valid: false, auditId: null });
});
