import assert from "node:assert/strict";
import test from "node:test";

import { describeRadarRule, parseAmbiguityRadar, summarizeAmbiguityRadar } from "./ambiguity-radar.mjs";

const workspaceId = "9b0df2de-b72e-4589-a51e-a407a9e1eb7e";
const firstText = "Avoid unsupported uptime guarantees and preserve the complete source rule without truncation.";
const radar = {
  workspace_id: workspaceId,
  minimum_decisions: 3,
  rules: [
    { rule_id: "rule-a", rule_text: firstText, source_filename: "guide.pdf", source_page: 2, decision_count: 1, dismissals: 1, flags: 0, accepted_suggestions: 0, review_reasons: ["Context matters."], dismissal_rate: 1, ambiguity_score: null, signal: "insufficient_data" },
    { rule_id: "rule-b", rule_text: "Never claim absolute security.", source_filename: "guide.pdf", source_page: 4, decision_count: 3, dismissals: 1, flags: 0, accepted_suggestions: 2, review_reasons: [], dismissal_rate: 1 / 3, ambiguity_score: 1 / 3, signal: "no_repeated_signal" },
  ],
  limitations: [],
};

const parsed = () => parseAmbiguityRadar(radar, workspaceId);

test("radar mapping preserves separate rule IDs, full text, and traceability fields", () => {
  const parsed = parseAmbiguityRadar(radar, workspaceId);
  assert.ok(parsed);
  assert.equal(parsed.rules.length, 2);
  assert.equal(parsed.rules[0].rule_id, "rule-a");
  assert.equal(parsed.rules[0].rule_text, firstText);
  assert.equal(parsed.rules[1].rule_id, "rule-b");
  assert.equal(parsed.rules[1].source_page, 4);
});

test("radar summary exposes coverage and keeps below-threshold score unavailable", () => {
  const parsed = parseAmbiguityRadar(radar, workspaceId);
  assert.deepEqual(summarizeAmbiguityRadar(parsed), {
    threshold: 3,
    totalRules: 2,
    sufficientRules: 1,
    belowThresholdRules: 1,
    totalDecisions: 4,
    repeatedSignalRules: 0,
    rulesWithReasons: 1,
  });
  assert.deepEqual(describeRadarRule(parsed.rules[0], parsed.minimum_decisions), {
    ruleId: "rule-a",
    ruleText: firstText,
    sourceFilename: "guide.pdf",
    sourcePage: 2,
    sourceLabel: "guide.pdf · page 2",
    countsLabel: "1 decision",
    signalLabel: "No score yet — needs 2 more decisions",
    decisionCount: 1,
    dismissedCount: 1,
    flaggedCount: 0,
    acceptedCount: 0,
    thresholdMet: false,
    thresholdLabel: "1 of 3 decisions · More review data needed",
    score: null,
    signal: "insufficient_data",
    reviewReasons: ["Context matters."],
  });
});

test("radar keeps the three-decision threshold and reports only actual counts", () => {
  assert.equal(parsed().minimum_decisions, 3);
  const below = describeRadarRule(parsed().rules[0], 3);
  assert.equal(below.thresholdMet, false);
  assert.equal(below.score, null);
  assert.equal(below.signalLabel, "No score yet — needs 2 more decisions");

  const met = describeRadarRule(parsed().rules[1], 3);
  assert.equal(met.thresholdMet, true);
  assert.equal(met.thresholdLabel, "3 decisions · threshold met");
  assert.equal(met.score, 1 / 3);
  assert.equal(met.signalLabel, "At or below the review threshold");
  assert.equal(met.countsLabel, "3 decisions");
});

test("radar summary is safe before any radar response arrives", () => {
  assert.deepEqual(summarizeAmbiguityRadar(null), {
    threshold: 0,
    totalRules: 0,
    sufficientRules: 0,
    belowThresholdRules: 0,
    totalDecisions: 0,
    repeatedSignalRules: 0,
    rulesWithReasons: 0,
  });
});

test("radar rejects duplicate IDs, inconsistent threshold signals, and wrong workspace", () => {
  assert.equal(parseAmbiguityRadar({ ...radar, workspace_id: "another" }, workspaceId), null);
  assert.equal(parseAmbiguityRadar({ ...radar, rules: [radar.rules[0], radar.rules[0]] }, workspaceId), null);
  assert.equal(parseAmbiguityRadar({ ...radar, rules: [{ ...radar.rules[0], ambiguity_score: 0.5 }] }, workspaceId), null);
});
