import { getRepairViewState, summarizeRepairEligibility } from "../../lib/repair-preview.mjs";

export type RepairReplacement = {
  finding_id: string;
  start: number;
  end: number;
  original: string;
  replacement: string;
  source_filename: string;
  source_label: string;
  reason: string;
};

export type RepairPreviewData = {
  audit_id: string;
  original_sha256: string;
  status: "no_findings" | "no_open_findings" | "review_required" | "no_supported_repairs" | "preview_available";
  findings_reviewed: number;
  repaired_content: string;
  replacements: RepairReplacement[];
  checks_before: number;
  checks_after: number;
  findings_before: number;
  findings_after: number;
  limitations: string[];
};

type RepairFinding = { status: string; finding_type: string };

type Props = {
  auditId: string;
  auditFindings: RepairFinding[];
  originalCopy: string;
  auditCopyIsCurrent: boolean;
  preview: RepairPreviewData | null;
  draft: string;
  loading: boolean;
  error: string;
  onPreview: () => void;
  onDraftChange: (value: string) => void;
  onUseRevision: () => void;
  onDiscard: () => void;
  onEditCopy: () => void;
};

export function RepairReviewPanel({
  auditId,
  auditFindings,
  originalCopy,
  auditCopyIsCurrent,
  preview,
  draft,
  loading,
  error,
  onPreview,
  onDraftChange,
  onUseRevision,
  onDiscard,
  onEditCopy,
}: Props) {
  const state = getRepairViewState({ loading, error, result: preview });
  const counts = summarizeRepairEligibility(auditFindings);
  const replacementsReturned = preview?.replacements.length ?? null;

  return (
    <section id="repair-stage" aria-labelledby="repair-heading" className="mt-6 min-w-0 rounded border border-border-structural bg-[#111417] p-5 font-sans sm:p-6">
      <div className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-verification-mint">Step 6 · Human-reviewed preview</p>
        <h3 id="repair-heading" className="mt-2 text-xl font-semibold leading-tight text-off-white">Review a supported copy revision</h3>
        <p className="mt-2 text-base leading-relaxed text-secondary">
          The preview checks approved terminology and proposes only verified literal substitutions. It never changes the saved audit or original copy.
        </p>
      </div>

      <dl className="mt-5 grid gap-x-8 gap-y-4 border-y border-border-structural py-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="min-w-0">
          <dt className="text-sm text-secondary">Total findings in this audit</dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-off-white">{counts.total}</dd>
          <p className="mt-1 text-xs leading-relaxed text-secondary">Every finding the persisted audit returned.</p>
        </div>
        <div className="min-w-0">
          <dt className="text-sm text-secondary">Dismissed</dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-off-white">{counts.dismissed}</dd>
          <p className="mt-1 text-xs leading-relaxed text-secondary">Closed by a recorded human decision.</p>
        </div>
        <div className="min-w-0">
          <dt className="text-sm text-secondary">Unresolved</dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-warning-copper">{counts.unresolved}</dd>
          <p className="mt-1 text-xs leading-relaxed text-secondary">{counts.pending} pending · {counts.flagged} flagged. These still block clearance.</p>
        </div>
        <div className="min-w-0">
          <dt className="text-sm text-secondary">Repair-eligible</dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-verification-mint">{counts.repairEligible}</dd>
          <p className="mt-1 text-xs leading-relaxed text-secondary">Verified approved-terminology findings with a deterministic replacement.</p>
        </div>
      </dl>

      <p className="mt-3 text-sm leading-relaxed text-secondary">
        {counts.resolved} resolved · {counts.informational} informational.
        {counts.unresolvedWithoutSupportedRepair > 0
          && ` ${counts.unresolvedWithoutSupportedRepair} unresolved finding${counts.unresolvedWithoutSupportedRepair === 1 ? " has" : "s have"} no supported automatic repair and must be revised by hand.`}
        {replacementsReturned !== null && preview
          && ` The API re-checked ${preview.findings_reviewed} pending finding${preview.findings_reviewed === 1 ? "" : "s"} and returned ${replacementsReturned} verified replacement${replacementsReturned === 1 ? "" : "s"}.`}
      </p>

      {!auditCopyIsCurrent && (
        <div role="alert" className="mt-4 border border-warning-copper/50 p-4 text-base leading-relaxed text-off-white">
          This editor copy no longer matches the persisted audit. Return to Step 3, then run a new audit before requesting repairs.
          <button type="button" onClick={onEditCopy} className="ml-2 font-semibold text-verification-mint underline underline-offset-4">Edit the copy</button>
        </div>
      )}

      {error && <p role="alert" className="mt-4 border border-warning-copper/50 p-4 text-base leading-relaxed text-off-white">Repair preview failed: {error}</p>}

      <button
        type="button"
        onClick={onPreview}
        disabled={loading || !auditId || !auditCopyIsCurrent}
        className="mt-5 inline-flex min-h-12 items-center justify-center rounded bg-verification-mint px-5 py-3 text-base font-semibold text-graphite-base transition hover:brightness-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-verification-mint focus-visible:ring-offset-2 focus-visible:ring-offset-[#111417] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Checking approved terminology…" : "Preview supported repairs"}
      </button>

      {state === "idle" && <p className="mt-4 text-base leading-relaxed text-secondary">Run a preview to check whether approved terminology supports an exact, safe replacement.</p>}
      {state === "loading" && <p role="status" aria-live="polite" className="mt-4 text-base text-secondary">Revalidating the audited text and approved evidence…</p>}
      {state === "no_findings" && <p role="status" className="mt-4 border border-border-structural p-4 text-base leading-relaxed text-secondary">This audit returned no findings. There is no repair to preview; this does not itself grant clearance.</p>}
      {state === "no_open_findings" && <p role="status" className="mt-4 border border-border-structural p-4 text-base leading-relaxed text-secondary">This audit has findings, but none remain open for repair. Existing decisions stay attached to the saved audit.</p>}
      {state === "review_required" && <p role="status" className="mt-4 border border-warning-copper/50 p-4 text-base leading-relaxed text-off-white">A finding is flagged for human review. Resolve or dismiss it in Step 5; a flagged finding is not an automatic repair instruction.</p>}
      {state === "no_supported_repairs" && preview && (
        <div role="status" className="mt-4 border border-border-structural p-4 sm:p-5">
          <h4 className="text-base font-semibold text-off-white">No supported automatic repair</h4>
          <p className="mt-2 text-base leading-relaxed text-secondary">
            {preview.findings_reviewed} pending finding{preview.findings_reviewed === 1 ? " was" : "s were"} checked, and none had a current verified approved-terminology replacement. Restricted phrases and unsupported claims are not rewritten by deleting or inventing language.
          </p>
          <p className="mt-2 text-base leading-relaxed text-off-white">
            No copy changed, so the literal finding count remains {preview.findings_before}. Revise the copy yourself, then run a new audit before clearance.
          </p>
          <button type="button" onClick={onEditCopy} className="mt-3 font-semibold text-verification-mint underline underline-offset-4">Revise copy in Step 3</button>
        </div>
      )}

      {state === "preview_available" && preview && preview.replacements.length > 0 && (
        <div className="mt-5 min-w-0 border-t border-border-structural pt-5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            <h4 className="text-lg font-semibold text-off-white">{preview.replacements.length} verified replacement{preview.replacements.length === 1 ? "" : "s"} available</h4>
            <p className="text-sm tabular-nums text-secondary">Literal findings {preview.findings_before} → {preview.findings_after}</p>
          </div>
          <ul className="mt-4 space-y-3">
            {preview.replacements.map((replacement) => (
              <li key={replacement.finding_id} className="min-w-0 border-l-2 border-verification-mint pl-4">
                <p className="break-words text-base leading-relaxed text-off-white"><del>{replacement.original}</del><span aria-hidden="true"> → </span><strong className="text-verification-mint">{replacement.replacement}</strong></p>
                <p className="mt-1 break-words text-sm leading-relaxed text-secondary">{replacement.source_label} · {replacement.source_filename}</p>
                <p className="mt-1 break-words text-sm leading-relaxed text-secondary">{replacement.reason}</p>
              </li>
            ))}
          </ul>

          <div className="mt-5 grid min-w-0 gap-4 lg:grid-cols-2">
            <div className="min-w-0">
              <h5 className="mb-2 text-sm font-semibold text-secondary">Before · original audited copy</h5>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded border border-border-structural bg-[#111417] p-4 font-sans text-base leading-relaxed text-off-white">{originalCopy}</pre>
            </div>
            <div className="min-w-0">
              <label htmlFor="repair-draft" className="mb-2 block text-sm font-semibold text-secondary">After · inspect and edit the proposed revision</label>
              <textarea id="repair-draft" value={draft} onChange={(event) => onDraftChange(event.target.value)} className="min-h-56 w-full resize-y rounded border border-border-focus bg-[#111417] p-4 font-sans text-base leading-relaxed text-off-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-verification-mint" />
            </div>
          </div>

          <p className="mt-4 text-sm leading-relaxed text-secondary">Using this revision only places it in the editor. The original audit stays unchanged; run a new audit on the revised copy before clearance.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" onClick={onUseRevision} disabled={!draft.trim()} className="min-h-11 rounded bg-verification-mint px-4 py-2 text-base font-semibold text-graphite-base disabled:cursor-not-allowed disabled:opacity-50">Use this revision for a new audit</button>
            <button type="button" onClick={onDiscard} className="min-h-11 rounded border border-border-structural px-4 py-2 text-base font-medium text-off-white hover:border-warning-copper focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-verification-mint">Reject and discard preview</button>
          </div>
          {preview.limitations.length > 0 && <details className="mt-4 text-sm text-secondary"><summary className="cursor-pointer underline underline-offset-4">Preview limitations</summary><ul className="mt-2 list-disc space-y-1 pl-5">{preview.limitations.map((item) => <li key={item}>{item}</li>)}</ul></details>}
        </div>
      )}
    </section>
  );
}
