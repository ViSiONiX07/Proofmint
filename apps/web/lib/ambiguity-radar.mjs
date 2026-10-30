/** @typedef {{rule_id:string, rule_text:string, source_filename:string, source_page:number, decision_count:number, dismissals:number, flags:number, accepted_suggestions:number, review_reasons:string[], dismissal_rate:number, ambiguity_score:number|null, signal:"insufficient_data"|"no_repeated_signal"|"repeated_review_signal"}} AmbiguityRadarRule */
/** @typedef {{workspace_id:string, minimum_decisions:number, rules:AmbiguityRadarRule[], limitations:string[]}} AmbiguityRadar */

/** @param {unknown} value @param {string} workspaceId @returns {AmbiguityRadar|null} */
export function parseAmbiguityRadar(value, workspaceId) {
  if (!value || typeof value !== "object" || value.workspace_id !== workspaceId
      || !Number.isInteger(value.minimum_decisions) || value.minimum_decisions < 1
      || !Array.isArray(value.rules) || !Array.isArray(value.limitations)) return null;
  const ids = new Set();
  for (const rule of value.rules) {
    if (!rule || typeof rule !== "object"
        || typeof rule.rule_id !== "string" || ids.has(rule.rule_id)
        || typeof rule.rule_text !== "string"
        || typeof rule.source_filename !== "string"
        || !Number.isInteger(rule.source_page)
        || !["decision_count", "dismissals", "flags", "accepted_suggestions"].every((field) => Number.isInteger(rule[field]) && rule[field] >= 0)
        || !Array.isArray(rule.review_reasons) || !rule.review_reasons.every((reason) => typeof reason === "string")
        || typeof rule.dismissal_rate !== "number"
        || !(rule.ambiguity_score === null || typeof rule.ambiguity_score === "number")
        || !["insufficient_data", "no_repeated_signal", "repeated_review_signal"].includes(rule.signal)) return null;
    if (rule.decision_count < value.minimum_decisions) {
      if (rule.ambiguity_score !== null || rule.signal !== "insufficient_data") return null;
    } else if (rule.ambiguity_score === null || rule.signal === "insufficient_data") {
      return null;
    }
    ids.add(rule.rule_id);
  }
  return /** @type {AmbiguityRadar} */ (value);
}

/** @param {AmbiguityRadar|null} radar */
export function summarizeAmbiguityRadar(radar) {
  const rules = radar?.rules ?? [];
  const sufficientRules = rules.filter((rule) => rule.decision_count >= radar.minimum_decisions).length;
  return {
    threshold: radar?.minimum_decisions ?? 0,
    totalRules: rules.length,
    sufficientRules,
    belowThresholdRules: rules.length - sufficientRules,
    totalDecisions: rules.reduce((total, rule) => total + rule.decision_count, 0),
    repeatedSignalRules: rules.filter((rule) => rule.signal === "repeated_review_signal").length,
    rulesWithReasons: rules.filter((rule) => rule.review_reasons.length > 0).length,
  };
}

/** @param {AmbiguityRadarRule} rule @param {number} minimumDecisions */
export function describeRadarRule(rule, minimumDecisions) {
  const enoughData = rule.decision_count >= minimumDecisions;
  return {
    ruleId: rule.rule_id,
    ruleText: rule.rule_text,
    sourceFilename: rule.source_filename,
    sourcePage: rule.source_page,
    sourceLabel: `${rule.source_filename} · page ${rule.source_page}`,
    countsLabel: `${rule.decision_count} decision${rule.decision_count === 1 ? "" : "s"}`,
    signalLabel: rule.signal === "insufficient_data"
      ? `No score yet — needs ${Math.max(minimumDecisions - rule.decision_count, 0)} more decision${Math.max(minimumDecisions - rule.decision_count, 0) === 1 ? "" : "s"}`
      : rule.signal === "no_repeated_signal"
        ? "At or below the review threshold"
        : "Repeated review signal",
    decisionCount: rule.decision_count,
    dismissedCount: rule.dismissals,
    flaggedCount: rule.flags,
    acceptedCount: rule.accepted_suggestions,
    thresholdMet: enoughData,
    thresholdLabel: enoughData
      ? `${rule.decision_count} decisions · threshold met`
      : `${rule.decision_count} of ${minimumDecisions} decisions · More review data needed`,
    score: enoughData ? rule.ambiguity_score : null,
    signal: rule.signal,
    reviewReasons: rule.review_reasons,
  };
}
