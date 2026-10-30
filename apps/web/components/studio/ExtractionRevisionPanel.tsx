"use client";

import { describeAppliedRevision, describeExtractionComparison, summarizeExtractionPreview } from "../../lib/extraction-revision.mjs";

export type ExtractionRevisionPreviewData = NonNullable<ReturnType<typeof import("../../lib/extraction-revision.mjs").parseExtractionRevisionPreview>>;
export type AppliedExtractionRevisionData = NonNullable<ReturnType<typeof import("../../lib/extraction-revision.mjs").parseExtractionRevision>>;

const COUNT_ORDER = [
  { key: "unchanged", label: "Unchanged" },
  { key: "changed", label: "Reworded" },
  { key: "added", label: "Newly extracted" },
  { key: "removed", label: "Omitted" },
] as const;

const COMPARISON_TONE: Record<string, string> = {
  unchanged: "border-border-structural text-secondary",
  changed: "border-warning-copper/40 text-warning-copper",
  added: "border-verification-mint/40 text-verification-mint",
  removed: "border-warning-copper/40 text-warning-copper",
};

export function ExtractionRevisionPanel({
  preview,
  loading,
  error,
  reviewed,
  applying,
  applyError,
  applied,
  onPreview,
  onToggleReviewed,
  onApply,
}: {
  preview: ExtractionRevisionPreviewData | null;
  loading: boolean;
  error: string;
  reviewed: boolean;
  applying: boolean;
  applyError: string;
  applied: AppliedExtractionRevisionData | null;
  onPreview: () => void;
  onToggleReviewed: (next: boolean) => void;
  onApply: () => void;
}) {
  const summary = preview ? summarizeExtractionPreview(preview) : null;
  const appliedView = applied ? describeAppliedRevision(applied) : null;
  return <section aria-labelledby="extraction-refresh-heading" className="mt-6 border border-border-structural bg-graphite-base p-5 font-sans">
    <h4 id="extraction-refresh-heading" className="font-semibold text-off-white">Refresh rules from the retained original PDF</h4>
    <p className="mt-2 text-sm leading-relaxed text-secondary">
      An earlier ingestion may hold malformed rules from the old extractor. Previewing re-runs the current deterministic
      extractor against this guideline&apos;s retained original PDF and compares the result with the stored rules by source
      page and character span. Nothing is written, no rule is approved, and no historical record is altered until you
      create a revision.
    </p>
    <button type="button" disabled={loading} onClick={onPreview} className="mt-4 min-h-11 border border-border-focus px-4 py-2 text-sm font-semibold text-verification-mint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-verification-mint disabled:cursor-not-allowed disabled:opacity-50">{loading ? "Comparing with the corrected extractor…" : preview ? "Preview again" : "Preview corrected re-extraction"}</button>
    {loading && <p role="status" className="mt-3 text-sm text-secondary">Re-reading the retained original PDF and comparing spans…</p>}
    {error && <p role="alert" className="mt-3 border border-warning-copper/40 p-3 text-sm text-warning-copper">Refresh preview failed: {error}</p>}
    {appliedView && <div className="mt-4 border border-verification-mint/40 p-4 text-sm">
      <p className="font-semibold text-verification-mint">{appliedView.headline}</p>
      <p className="mt-2 break-words text-secondary">{appliedView.provenanceLabel}</p>
      <p className="mt-2 text-off-white">{appliedView.detailLabel}</p>
      <p className="mt-2 text-secondary">{appliedView.carriedLabel}</p>
      <p className="mt-2 text-secondary">{appliedView.removalLabel}</p>
      <p className="mt-2 text-secondary">Newly extracted candidates are stored as <code className="font-mono text-xs">pending_review</code>. Audits keep using the previously approved rules until a human approves the refreshed candidates below.</p>
    </div>}
    {applyError && <p role="alert" className="mt-4 border border-warning-copper/50 p-3 text-sm text-warning-copper">Refresh was refused: {applyError}</p>}
    {preview && summary && <div className="mt-5 border-t border-border-structural pt-5">
      <p className="text-sm font-semibold text-off-white">{summary.headline}</p>
      <p className="mt-1 break-words text-xs text-secondary">{summary.revisionLabel} · {summary.sourceLabel}</p>
      <p className="mt-2 text-sm text-secondary">{summary.reviewNotice}</p>
      <p className="mt-1 text-sm text-secondary">{summary.removalNotice}</p>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{COUNT_ORDER.map(({ key, label }) => <div key={key} className="border border-border-structural p-3"><dt className="text-xs text-secondary">{label}</dt><dd className="mt-1 text-lg text-off-white">{summary.counts[key]}</dd></div>)}</dl>
      <p className="mt-3 text-xs text-secondary">{preview.existing_rule_count} stored rule(s) in revision {preview.current_revision} · {preview.extracted_rule_count} candidate(s) from the corrected extractor</p>
      <ol className="mt-5 space-y-3">{preview.comparisons.map((raw) => { const item = describeExtractionComparison(raw, preview.source_filename); return <li key={`${item.source_page}-${item.source_start_offset}`} className="border border-border-structural p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p className="text-xs uppercase tracking-wider text-secondary">{item.spanLabel}</p>
          <span className={`shrink-0 border px-2 py-1 text-xs ${COMPARISON_TONE[item.comparison]}`}>{item.comparisonLabel}</span>
        </div>
        {item.existingText !== null && <div className="mt-3"><p className="text-xs uppercase tracking-wider text-secondary">Stored rule{item.existingStatusLabel ? ` · ${item.existingStatusLabel}` : ""}</p><p className="mt-1 whitespace-pre-wrap break-words text-sm leading-relaxed text-off-white">{item.existingText}</p></div>}
        {item.extractedText !== null && <div className="mt-3"><p className="text-xs uppercase tracking-wider text-verification-mint">Corrected extraction</p><p className="mt-1 whitespace-pre-wrap break-words text-sm leading-relaxed text-off-white">{item.extractedText}</p>{item.extracted_category && <p className="mt-1 text-xs text-secondary">Category · {item.extracted_category}</p>}</div>}
        <p className="mt-3 break-words text-xs text-secondary">{item.decisionLabel}</p>
        {item.existing_rule_id && <p className="mt-1 break-all font-mono text-xs text-secondary">Existing rule ID {item.existing_rule_id}</p>}
      </li>; })}</ol>
      <details className="mt-4"><summary className="cursor-pointer text-xs text-secondary">Refresh limitations</summary><ul className="mt-2 list-disc pl-5 text-xs text-secondary">{preview.limitations.map((item) => <li key={item}>{item}</li>)}</ul></details>
      {preview.already_current
        ? <p role="status" className="mt-5 border border-border-structural p-3 text-sm text-secondary">These rules already match the corrected extractor, so a refresh would create no revision and change nothing.</p>
        : <div className="mt-5 border border-border-structural p-4">
          <label className="flex cursor-pointer items-start gap-3 text-sm text-off-white"><input type="checkbox" checked={reviewed} onChange={(event) => onToggleReviewed(event.target.checked)} className="mt-0.5 h-4 w-4 shrink-0 accent-[#A7F3D0]" /><span>I have reviewed this comparison and want to store these candidates as a new rule-set revision.</span></label>
          <p className="mt-2 text-xs text-secondary">Creating the revision copies the identical original PDF under a new revision. It never edits or deletes revision {preview.current_revision}, its approvals, or any historical audit reference, and it does not approve the new candidates.</p>
          <button type="button" disabled={!reviewed || applying} onClick={onApply} className="mt-3 min-h-11 rounded bg-verification-mint px-4 py-2 text-sm font-semibold text-graphite-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-verification-mint disabled:cursor-not-allowed disabled:opacity-50">{applying ? "Creating revision…" : "Create rule-set revision"}</button>
        </div>}
    </div>}
  </section>;
}
