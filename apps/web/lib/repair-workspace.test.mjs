import test from "node:test";
import assert from "node:assert/strict";
import { summarizeRepairWorkspace } from "./repair-workspace.mjs";
import { getRepairIneligibilityReason } from "./repair-preview.mjs";

const finding = (id, overrides = {}) => ({ id, status: "pending_review", finding_type: "preferred_terminology", term_id: `term-${id}`, rule_id: null, fact_id: null, verification_status: "verified", suggested_correction: "Preferred", matched_phrase: "Original", ...overrides });
const decision = (id, action, created_at) => ({ id: `decision-${id}-${action}`, finding_id: id, action, proposed_replacement: action === "reject" ? null : "Preferred", created_at });

test("summarizes live proposals, latest persisted decisions, and ineligible findings", () => {
  const audit = { findings: [finding("a"), finding("b"), finding("c", { finding_type: "restricted_phrase", term_id: null })], repair_decisions: [decision("a", "accept", "2026-01-01T00:00:00Z"), decision("a", "edit", "2026-01-02T00:00:00Z"), decision("b", "reject", "2026-01-03T00:00:00Z")] };
  const result = summarizeRepairWorkspace(audit, { replacements: [{ finding_id: "a" }, { finding_id: "b" }] });
  assert.deepEqual({ total: result.totalFindings, eligible: result.eligibleFindings, awaiting: result.awaitingDecision, accepted: result.accepted, edited: result.edited, rejected: result.rejected, ineligible: result.withoutEligibleRepair }, { total: 3, eligible: 2, awaiting: 0, accepted: 0, edited: 1, rejected: 1, ineligible: 1 });
});

test("empty or absent preview does not fabricate proposals or decision outcomes", () => {
  const result = summarizeRepairWorkspace({ findings: [finding("a")] }, null);
  assert.equal(result.totalFindings, 1);
  assert.equal(result.eligibleFindings, 0);
  assert.equal(result.awaitingDecision, 0);
  assert.equal(result.accepted + result.edited + result.rejected, 0);
});

test("dismissed findings stay closed and are not counted as proposals or unsupported open work", () => {
  const audit = { findings: [finding("dismissed", { status: "dismissed" })], repair_decisions: [] };
  const result = summarizeRepairWorkspace(audit, { status: "no_open_findings", replacements: [] });
  assert.equal(result.totalFindings, 1);
  assert.equal(result.dismissedFindings, 1);
  assert.equal(result.eligibleFindings, 0);
  assert.equal(result.awaitingDecision, 0);
  assert.equal(result.withoutEligibleRepair, 0);
  assert.equal(result.closedFindings[0].status, "dismissed");
});

test("open findings without a server proposal are separately returned with persisted status", () => {
  const audit = { findings: [finding("proposal"), finding("unsupported", { finding_type: "approved_fact_match", term_id: null, suggested_correction: null })], repair_decisions: [] };
  const result = summarizeRepairWorkspace(audit, { status: "preview_available", replacements: [{ finding_id: "proposal" }] });
  assert.equal(result.eligibleFindings, 1);
  assert.equal(result.withoutEligibleRepair, 1);
  assert.deepEqual(result.unsupportedFindings.map(({ id }) => id), ["unsupported"]);
  assert.match(getRepairIneligibilityReason(result.unsupportedFindings[0]), /No deterministic repair is defined for approved fact match/);
});
