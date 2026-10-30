import assert from "node:assert/strict";
import test from "node:test";
import { getRepairDecisionHistory, hasPersistedRepairCompletion } from "./repair-decisions.mjs";

const eligibleFinding = (id) => ({
  id, status: "pending_review", finding_type: "preferred_terminology", term_id: `term-${id}`,
  rule_id: null, fact_id: null, verification_status: "verified",
  suggested_correction: "Northstar Cloud", matched_phrase: "NorthStarCloud",
});

test("persisted repair decisions returned after refresh retain accept, edit, and reject history", () => {
  const decisions = ["accept", "edit", "reject"].map((action, index) => ({
    id: `decision-${index}`,
    finding_id: "finding-1",
    action,
    proposed_replacement: action === "reject" ? null : `replacement-${index}`,
    review_reason: null,
    created_at: `2026-10-28T00:00:0${index}Z`,
  }));
  const refreshedAudit = { repair_decisions: decisions };
  assert.deepEqual(getRepairDecisionHistory(refreshedAudit), decisions);
});

test("persisted manual decisions retain provenance and revised copy for Step 7", () => {
  const manual = {
    id: "manual-1",
    finding_id: "finding-1",
    action: "manual",
    proposed_replacement: null,
    original_text: "The revolutionary product.",
    revised_text: "The verified product.",
    provenance: "human_authored",
    review_reason: "Human-authored correction",
    created_at: "2026-01-03T00:00:00Z",
  };
  assert.deepEqual(getRepairDecisionHistory({ repair_decisions: [manual] }), [manual]);
});

test("malformed or unsupported decision data is not rendered as persisted state", () => {
  assert.deepEqual(getRepairDecisionHistory(null), []);
  assert.deepEqual(getRepairDecisionHistory({ repair_decisions: [
    { id: "x", finding_id: "f", action: "apply", proposed_replacement: "x", created_at: "yesterday" },
    { id: "valid", finding_id: "f", action: "reject", proposed_replacement: null, created_at: "2026-10-28T00:00:00Z" },
  ] }), [{ id: "valid", finding_id: "f", action: "reject", proposed_replacement: null, created_at: "2026-10-28T00:00:00Z" }]);
});

test("Repair is incomplete when only visited and completes after decisions cover each eligible finding", () => {
  const first = eligibleFinding("finding-1");
  const second = eligibleFinding("finding-2");
  const decision = (id, action = "accept") => ({
    id: `decision-${id}`, finding_id: id, action, proposed_replacement: action === "reject" ? null : "Northstar Cloud", created_at: "2026-10-28T00:00:00Z",
  });
  const preview = { status: "preview_available", replacements: [{ finding_id: first.id }, { finding_id: second.id }] };
  assert.equal(hasPersistedRepairCompletion({ findings: [first, second], repair_decisions: [] }, preview), false);
  assert.equal(hasPersistedRepairCompletion({ findings: [first, second], repair_decisions: [decision(first.id)] }, preview), false);
  assert.equal(hasPersistedRepairCompletion({ findings: [first, second], repair_decisions: [decision(first.id), decision(second.id, "reject")] }, preview), true);
  assert.equal(hasPersistedRepairCompletion({ findings: [first, second], repair_decisions: [decision(first.id), decision(second.id, "reject")] }, preview, { loading: true }), false);
  assert.equal(hasPersistedRepairCompletion({ findings: [first, second], repair_decisions: [decision(first.id), decision(second.id, "reject")] }, preview, { error: "offline" }), false);
  assert.equal(hasPersistedRepairCompletion({ findings: [{ ...first, status: "dismissed" }], repair_decisions: [] }, { status: "no_open_findings", replacements: [] }), true);
  assert.equal(hasPersistedRepairCompletion({ findings: [], repair_decisions: [] }, { status: "no_findings", replacements: [] }), true);
  assert.equal(hasPersistedRepairCompletion({ findings: [{ ...first, finding_type: "restricted_phrase" }], repair_decisions: [] }, { status: "preview_available", replacements: [] }), true);
  assert.equal(hasPersistedRepairCompletion({ findings: [first], repair_decisions: [] }, { status: "review_required", replacements: [] }), false);
  assert.equal(hasPersistedRepairCompletion({ findings: [first], repair_decisions: [] }, null), false);
});
