import assert from "node:assert/strict";
import test from "node:test";

import { matchesAuditedCopy } from "./audit-session.mjs";

test("restored audit without retained copy is not actionable even when the editor is empty", () => {
  assert.equal(matchesAuditedCopy({ submittedText: "" }, ""), false);
});

test("new audit is actionable only while the exact audited copy remains in the editor", () => {
  const audit = { submittedText: "A claim with Proofmint." };
  assert.equal(matchesAuditedCopy(audit, "A claim with Proofmint."), true);
  assert.equal(matchesAuditedCopy(audit, "A revised claim with Proofmint."), false);
});

test("missing and whitespace-only audit copies cannot authorize decisions", () => {
  assert.equal(matchesAuditedCopy(null, "copy"), false);
  assert.equal(matchesAuditedCopy({ submittedText: "   " }, "   "), false);
});
