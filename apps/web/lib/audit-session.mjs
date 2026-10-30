/** @param {{ submittedText?: unknown } | null} audit @param {string} currentText */
export function matchesAuditedCopy(audit, currentText) {
  return Boolean(
    audit
    && typeof audit.submittedText === "string"
    && audit.submittedText.trim().length > 0
    && audit.submittedText === currentText,
  );
}
