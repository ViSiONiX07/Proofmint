/** Build a review-only copy from persisted human decisions and the server's verified spans. */
export function buildReviewedCopy(original, findings, decisions, replacements) {
  if (typeof original !== "string" || !Array.isArray(findings) || !Array.isArray(decisions) || !Array.isArray(replacements)) {
    return { content: null, applied: 0, unavailable: true };
  }
  const latest = new Map();
  for (const decision of decisions) {
    const previous = latest.get(decision.finding_id);
    if (!previous || Date.parse(decision.created_at) >= Date.parse(previous.created_at)) latest.set(decision.finding_id, decision);
  }
  const manual = [...latest.values()]
    .filter((decision) => decision.action === "manual" && typeof decision.revised_text === "string" && decision.revised_text.trim())
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
  if (manual) return { content: manual.revised_text, applied: 1, unavailable: false };
  const findingIds = new Set(findings.map(({ id }) => id));
  const changes = replacements.flatMap((item) => {
    const decision = latest.get(item.finding_id);
    if (!findingIds.has(item.finding_id) || !decision || !["accept", "edit"].includes(decision.action)
      || !Number.isInteger(item.start) || !Number.isInteger(item.end)
      || original.slice(item.start, item.end) !== item.original) return [];
    const replacement = decision.action === "edit" ? decision.proposed_replacement : item.replacement;
    return typeof replacement === "string" && replacement.trim() ? [{ start: item.start, end: item.end, replacement }] : [];
  }).sort((a, b) => b.start - a.start);
  let content = original;
  for (const item of changes) content = content.slice(0, item.start) + item.replacement + content.slice(item.end);
  return { content, applied: changes.length, unavailable: false };
}
