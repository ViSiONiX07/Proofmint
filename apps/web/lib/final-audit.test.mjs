import assert from "node:assert/strict";
import test from "node:test";
import { buildReviewedCopy } from "./final-audit.mjs";

const original = "NorthStarCloud helps teams.";
const finding = { id: "f1" };
const proposal = { finding_id: "f1", start: 0, end: 14, original: "NorthStarCloud", replacement: "Northstar Cloud" };
const decision = (action, proposed_replacement, created_at = "2026-10-30T00:00:00Z") => ({ finding_id: "f1", action, proposed_replacement, created_at });

test("final review preview applies only persisted accept/edit decisions to matching server spans", () => {
  assert.deepEqual(buildReviewedCopy(original, [finding], [decision("accept", "Northstar Cloud")], [proposal]), {
    content: "Northstar Cloud helps teams.", applied: 1, unavailable: false,
  });
  assert.equal(buildReviewedCopy(original, [finding], [decision("edit", "North Star")], [proposal]).content, "North Star helps teams.");
});

test("rejected, undecided, stale-span, or missing audit inputs never alter submitted copy", () => {
  assert.equal(buildReviewedCopy(original, [finding], [decision("reject", null)], [proposal]).content, original);
  assert.equal(buildReviewedCopy(original, [finding], [], [proposal]).applied, 0);
  assert.equal(buildReviewedCopy(original, [finding], [decision("accept", "x")], [{ ...proposal, original: "stale" }]).content, original);
  assert.equal(buildReviewedCopy(null, [finding], [], [] ).unavailable, true);
});
