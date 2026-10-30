import { describeRadarRule, summarizeAmbiguityRadar } from "../../lib/ambiguity-radar.mjs";

type Radar = { workspace_id: string; minimum_decisions: number; rules: { rule_id: string; rule_text: string; source_filename: string; source_page: number; decision_count: number; dismissals: number; flags: number; accepted_suggestions: number; review_reasons: string[]; dismissal_rate: number; ambiguity_score: number | null; signal: "insufficient_data" | "no_repeated_signal" | "repeated_review_signal" }[]; limitations: string[] };

function Stat({ label, value, hint, emphasis }: { label: string; value: number; hint: string; emphasis?: "mint" | "copper" }) {
  const tone = emphasis === "mint" ? "text-verification-mint" : emphasis === "copper" ? "text-warning-copper" : "text-off-white";
  return (
    <div className="min-w-0">
      <dt className="text-sm text-secondary">{label}</dt>
      <dd className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</dd>
      <p className="mt-1 text-xs leading-relaxed text-secondary">{hint}</p>
    </div>
  );
}

export function AmbiguityRadarPanel({ radar, loading, error, onRefresh }: { radar: Radar | null; loading: boolean; error: string; onRefresh: () => void }) {
  const summary = summarizeAmbiguityRadar(radar);
  const signalTone = (signal: string) => signal === "repeated_review_signal"
    ? "border-warning-copper/50 text-warning-copper"
    : signal === "no_repeated_signal"
      ? "border-verification-mint/40 text-verification-mint"
      : "border-border-structural text-secondary";
  return (
    <section aria-labelledby="ambiguity-heading" className="mt-8 rounded border border-border-structural bg-[#111417] p-5 font-sans sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-verification-mint">Guideline feedback</p>
          <h3 id="ambiguity-heading" className="mt-2 text-xl font-semibold text-off-white">Ambiguity Radar</h3>
          <p className="mt-2 text-base leading-relaxed text-secondary">
            Shows repeated review patterns for approved rules. It counts saved decisions; it does not infer reviewer disagreement or decide whether a rule is wrong.
          </p>
        </div>
        <button type="button" onClick={onRefresh} disabled={loading} className="min-h-11 rounded border border-border-structural px-4 py-2 text-sm font-semibold text-off-white hover:border-verification-mint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-verification-mint disabled:cursor-wait disabled:opacity-50">
          {loading ? "Refreshing radar…" : "Refresh radar"}
        </button>
      </div>

      {error && (
        <div role="alert" className="mt-5 border border-warning-copper/50 p-4 text-base leading-relaxed text-off-white">
          Ambiguity analysis could not be loaded: {error}
          <button type="button" onClick={onRefresh} disabled={loading} className="ml-2 font-semibold text-verification-mint underline underline-offset-4">Retry</button>
        </div>
      )}

      {loading && !radar && <p role="status" className="mt-5 text-base text-secondary">Loading recorded review data…</p>}

      {radar && (
        <>
          <p className="mt-5 border-l-2 border-verification-mint bg-graphite-base py-3 pl-4 pr-3 text-sm leading-relaxed text-secondary">
            <strong className="font-semibold text-off-white">Threshold:</strong> a rule needs at least {radar.minimum_decisions} saved decision{radar.minimum_decisions === 1 ? "" : "s"} before any score appears. The score is (dismissals + flags) ÷ recorded decisions, so {radar.minimum_decisions} decisions span {radar.minimum_decisions === 1 ? "" : "roughly "}0.00–1.00 and a score of 0.5 or higher is flagged as a repeated review signal.
          </p>

          <dl className="mt-5 grid gap-x-8 gap-y-4 border-y border-border-structural py-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Approved rules tracked" value={summary.totalRules} hint="Every currently approved rule in this workspace." />
            <Stat label="Scored rules" value={summary.sufficientRules} hint={`At or above ${radar.minimum_decisions} decisions.`} />
            <Stat label={`Below threshold`} value={summary.belowThresholdRules} hint="Not enough decisions to score yet." />
            <Stat label="Repeated review signals" value={summary.repeatedSignalRules} hint="Scored at 0.5 or higher." emphasis={summary.repeatedSignalRules > 0 ? "copper" : "mint"} />
          </dl>

          <p className="mt-3 text-sm leading-relaxed text-secondary">
            {summary.totalDecisions} recorded decision{summary.totalDecisions === 1 ? "" : "s"} across all tracked rules · {summary.rulesWithReasons} rule{summary.rulesWithReasons === 1 ? "" : "s"} with a recorded review reason.
          </p>

          {radar.rules.length === 0 ? (
            <p className="mt-5 border border-border-structural p-4 text-base leading-relaxed text-secondary">No approved rules are available for review-pattern analysis yet.</p>
          ) : (
            <ul className="mt-5 divide-y divide-border-structural">
              {radar.rules.map((raw) => {
                const rule = describeRadarRule(raw, radar.minimum_decisions);
                return (
                  <li key={rule.ruleId} className="py-5 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
                      <p className="min-w-0 flex-1 whitespace-pre-wrap break-words text-base font-medium leading-relaxed text-off-white">{rule.ruleText}</p>
                      <span className={`shrink-0 rounded border px-2 py-1 text-xs font-semibold ${signalTone(rule.signal)}`}>{rule.signalLabel}</span>
                    </div>

                    <p className="mt-2 break-words text-sm text-secondary">{rule.sourceLabel}</p>

                    <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
                      <div>
                        <dt className="text-xs uppercase tracking-wider text-secondary">Decisions</dt>
                        <dd className="mt-0.5 text-base font-semibold tabular-nums text-off-white">{rule.decisionCount}</dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-wider text-secondary">Dismissed</dt>
                        <dd className="mt-0.5 text-base font-semibold tabular-nums text-off-white">{rule.dismissedCount}</dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-wider text-secondary">Flagged</dt>
                        <dd className="mt-0.5 text-base font-semibold tabular-nums text-off-white">{rule.flaggedCount}</dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-wider text-secondary">Accepted</dt>
                        <dd className="mt-0.5 text-base font-semibold tabular-nums text-off-white">{rule.acceptedCount}</dd>
                      </div>
                    </dl>

                    <p className="mt-3 text-sm leading-relaxed text-secondary">
                      {rule.score === null
                        ? `${rule.thresholdLabel} — ${rule.signalLabel}.`
                        : `Score ${rule.score.toFixed(2)} from ${rule.countsLabel} (${rule.thresholdLabel}).`}
                    </p>

                    {rule.reviewReasons.length > 0 && (
                      <details className="mt-2 text-sm text-secondary">
                        <summary className="cursor-pointer underline underline-offset-4">Recorded reasons ({rule.reviewReasons.length})</summary>
                        <ul className="mt-2 list-disc space-y-1 pl-5">{rule.reviewReasons.map((reason, index) => <li key={`${rule.ruleId}-${index}`} className="break-words">{reason}</li>)}</ul>
                      </details>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          {radar.limitations.length > 0 && (
            <details className="mt-5 border-t border-border-structural pt-4 text-sm text-secondary">
              <summary className="cursor-pointer underline underline-offset-4">Analysis limitations</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5">{radar.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
            </details>
          )}
        </>
      )}
    </section>
  );
}
