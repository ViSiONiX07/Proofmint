import assert from "node:assert/strict";
import test from "node:test";

import { getRepairIneligibilityReason, getRepairViewState, isRepairPreviewResponse, summarizeRepairEligibility } from "./repair-preview.mjs";

const result = {
  audit_id: "9b0df2de-b72e-4589-a51e-a407a9e1eb7e",
  original_sha256: "a".repeat(64),
  status: "preview_available",
  findings_reviewed: 2,
  repaired_content: "A Proofmint product.",
  replacements: [{
    finding_id: "5c62426f-a83d-4dd3-9f22-a53385bb412c",
    start: 2,
    end: 11,
    original: "ProofMint",
    replacement: "Proofmint",
    source_filename: "terms.csv",
    source_label: "Approved terminology: ProofMint → Proofmint",
    reason: "Use preferred terminology.",
  }],
  findings_before: 1,
  findings_after: 0,
  limitations: [],
};

test("repair responses are bound to the original audit and hash", () => {
  assert.equal(isRepairPreviewResponse(result, result.audit_id, result.original_sha256), true);
  assert.equal(isRepairPreviewResponse(result, result.audit_id, "b".repeat(64)), false);
  assert.equal(isRepairPreviewResponse({ ...result, audit_id: "other" }, result.audit_id, result.original_sha256), false);
});

test("repair UI state distinguishes loading, errors, no findings, unsupported repair, and preview", () => {
  assert.equal(getRepairViewState({ loading: true }), "loading");
  assert.equal(getRepairViewState({ error: "stale audit" }), "error");
  assert.equal(getRepairViewState({ result: { status: "no_findings" } }), "no_findings");
  assert.equal(getRepairViewState({ result: { status: "no_supported_repairs" } }), "no_supported_repairs");
  assert.equal(getRepairViewState({ result }), "preview_available");
  assert.equal(getRepairViewState({ result: { status: "unknown" } }), "error");
});

test("finding counts separate total, dismissed, unresolved, and repair-eligible", () => {
  const findings = [
    { status: "dismissed", finding_type: "restricted_phrase", verification_status: "uncertain" },
    { status: "resolved", finding_type: "approved_fact_match", verification_status: "verified" },
    { status: "informational", finding_type: "unsupported_claim", verification_status: "verified" },
    { status: "flagged", finding_type: "restricted_phrase", verification_status: "verified" },
    { status: "pending_review", finding_type: "preferred_terminology", matched_phrase: "ProofMint", suggested_correction: "Proofmint", term_id: "term-1", verification_status: "verified" },
    { status: "pending_review", finding_type: "restricted_phrase", matched_phrase: "guaranteed", suggested_correction: "a safe-sounding claim", term_id: "term-2", verification_status: "verified" },
    { status: "pending_review", finding_type: "preferred_terminology", matched_phrase: "Mint ProofMint", suggested_correction: "Proofmint", term_id: "term-3", verification_status: "uncertain" },
  ];

  assert.deepEqual(summarizeRepairEligibility(findings), {
    total: 7,
    dismissed: 1,
    resolved: 1,
    flagged: 1,
    informational: 1,
    pending: 3,
    unresolved: 4,
    repairEligible: 1,
    unresolvedWithoutSupportedRepair: 3,
  });
});

test("only verified pending or flagged approved-terminology findings with a real replacement are repair-eligible", () => {
  const base = { status: "pending_review", finding_type: "preferred_terminology", matched_phrase: "ProofMint", suggested_correction: "Proofmint", verification_status: "verified" };
  const eligible = { ...base, term_id: "term-1" };
  assert.equal(summarizeRepairEligibility([eligible]).repairEligible, 1);
  assert.equal(summarizeRepairEligibility([{ ...eligible, rule_id: "rule-1" }]).repairEligible, 0);
  assert.equal(summarizeRepairEligibility([{ ...eligible, fact_id: "fact-1" }]).repairEligible, 0);
  assert.equal(summarizeRepairEligibility([{ ...eligible, term_id: null }]).repairEligible, 0);
  assert.equal(summarizeRepairEligibility([{ ...eligible, verification_status: "rejected" }]).repairEligible, 0);
  assert.equal(summarizeRepairEligibility([{ ...eligible, suggested_correction: null }]).repairEligible, 0);
  assert.equal(summarizeRepairEligibility([{ ...eligible, suggested_correction: "ProofMint" }]).repairEligible, 0);
  assert.equal(summarizeRepairEligibility([{ ...eligible, status: "flagged" }]).repairEligible, 1);
  assert.equal(summarizeRepairEligibility([{ ...eligible, status: "dismissed" }]).repairEligible, 0);
});

test("an empty or malformed finding list reports zeroes rather than inventing repairs", () => {
  assert.deepEqual(summarizeRepairEligibility([]), {
    total: 0, dismissed: 0, resolved: 0, flagged: 0, informational: 0, pending: 0, unresolved: 0, repairEligible: 0, unresolvedWithoutSupportedRepair: 0,
  });
  assert.equal(summarizeRepairEligibility(null).total, 0);
});

test("repair ineligibility reasons distinguish closed findings, unsupported evidence and rejected proposals", () => {
  assert.match(getRepairIneligibilityReason({ status: "dismissed" }), /dismissed.*not reopened/);
  assert.match(getRepairIneligibilityReason({ status: "pending_review", verification_status: "uncertain" }), /uncertain/);
  assert.match(getRepairIneligibilityReason({ status: "pending_review", verification_status: "verified", finding_type: "restricted_phrase" }), /No deterministic repair/);
  assert.match(getRepairIneligibilityReason({ status: "flagged", verification_status: "verified", finding_type: "restricted_phrase", rule_id: "rule-1", term_id: null, fact_id: null }), /approved restriction.*no approved replacement text.*preferred-term substitutions/);
  assert.match(getRepairIneligibilityReason({ status: "pending_review", verification_status: "verified", finding_type: "preferred_terminology", term_id: "term-1" }, "reject"), /rejected.*not be offered again/);
});
