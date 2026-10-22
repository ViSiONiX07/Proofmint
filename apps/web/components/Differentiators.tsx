import React from "react";

export function Differentiators() {
  return (
    <section className="w-full py-20 lg:py-28 bg-graphite-base border-b border-border-structural" id="differentiators">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-20 reveal-on-scroll">
          <span className="font-mono text-xs text-verification-mint uppercase tracking-widest font-semibold block mb-2">
            Architecture Differentiators
          </span>
          <h2 className="font-display text-2xl sm:text-4xl lg:text-5xl text-off-white font-semibold">
            Engineered for certainty. Built against hallucinations.
          </h2>
          <p className="text-base sm:text-lg text-secondary mt-3 leading-relaxed">
            Traditional LLMs guess at guidelines. Proofmint locks every semantic decision against deterministic enterprise truth.
          </p>
        </div>

        {/* Showcase 1: Evidence-Locked Findings */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center mb-24 pb-20 border-b border-border-structural">
          <div className="lg:col-span-6 flex flex-col gap-5 reveal-on-scroll">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-verification-mint-dim text-verification-mint border border-verification-mint/30 w-fit font-mono text-xs">
              <span>DIFF_01</span>
              <span>/</span>
              <span>DETERMINISTIC_GROUNDING</span>
            </div>
            <h3 className="font-display text-2xl sm:text-3xl lg:text-4xl text-off-white font-semibold tracking-tight">
              Evidence-Locked Findings
            </h3>
            <p className="text-base text-secondary leading-relaxed">
              Every flag issued by Proofmint links to an exact cryptographic anchor in your enterprise corpus. No vague AI explanations. Your teams see the exact Legal Memo, PRD parameter, or ESG filing that invalidates the proposed copy.
            </p>
            <ul className="space-y-3 text-sm text-on-surface-variant">
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Direct URI hash anchoring to corporate Notion, PDF, or Confluence sources
              </li>
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                SHA-256 fingerprinting guarantees guidelines haven&apos;t mutated silently
              </li>
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Defensibility logs ready for external auditor or regulatory submission
              </li>
            </ul>
          </div>

          <div className="lg:col-span-6 bg-charcoal-elevated p-6 rounded-xl border border-border-structural shadow-xl reveal-on-scroll">
            <div className="flex items-center justify-between pb-4 border-b border-border-structural font-mono text-xs text-secondary">
              <span>EVIDENCE_TRACE_INSPECTOR</span>
              <span className="text-verification-mint">STATUS: 100% GROUNDED</span>
            </div>
            <div className="space-y-4 mt-5">
              <div className="p-3.5 rounded bg-graphite-base border border-border-structural">
                <span className="font-mono text-xs text-secondary uppercase block mb-1">Audit Trail Anchor</span>
                <div className="font-mono text-off-white text-xs sm:text-sm truncate">
                  corpus://legal-compliance/2024/us-ftc-claims.v4#sub-88
                </div>
              </div>
              <div className="p-4 rounded bg-surface-container-lowest border border-border-structural">
                <span className="font-mono text-xs text-verification-mint block mb-1.5 flex items-center gap-1.5">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Document Excerpt Matches
                </span>
                <p className="text-xs sm:text-sm text-secondary italic leading-relaxed">
                  &ldquo;...any reference to energy reduction metrics exceeding 30% must accompany baseline measurement methodology certified by third-party audit within the previous rolling 12 months...&rdquo;
                </p>
              </div>
              <div className="flex items-center justify-between pt-2 text-xs font-mono text-secondary">
                <span>Grounding Vector: 0.998</span>
                <span>Audit Digest: d4e6...91af</span>
              </div>
            </div>
          </div>
        </div>

        {/* Showcase 2: Intent-Preserving Repair */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center mb-24 pb-20 border-b border-border-structural">
          <div className="lg:col-span-6 order-2 lg:order-1 bg-charcoal-elevated p-6 rounded-xl border border-border-structural shadow-xl reveal-on-scroll">
            <div className="flex items-center justify-between pb-4 border-b border-border-structural font-mono text-xs text-secondary">
              <span>SURGICAL_TOKEN_BENCHMARK</span>
              <span className="text-verification-mint">MIN_LEW_DISTANCE</span>
            </div>
            <div className="space-y-4 mt-5">
              <div className="p-4 rounded bg-surface-container-lowest border border-border-structural">
                <span className="font-mono text-xs text-secondary uppercase block mb-1">
                  Standard Generic LLM (Destroys Punch)
                </span>
                <p className="text-xs sm:text-sm text-on-surface-variant line-through opacity-70">
                  &ldquo;Our software works well and helps computers connect with reliable performance in different places.&rdquo;
                </p>
                <span className="font-mono text-xs text-warning-copper mt-1 block">
                  Warning: Voice flattened into generic corporate boilerplate
                </span>
              </div>
              <div className="p-4 rounded bg-graphite-base border border-verification-mint/40">
                <span className="font-mono text-xs text-verification-mint uppercase block mb-1">
                  Proofmint Surgical Repair (Saves Voice)
                </span>
                <p className="text-xs sm:text-sm text-off-white font-medium">
                  &ldquo;Our purpose-built distributed architecture delivers 10x speed with 99.99% targeted availability worldwide.&rdquo;
                </p>
                <div className="flex items-center gap-4 mt-2 font-mono text-xs text-secondary">
                  <span className="text-verification-mint">Tokens Changed: 4</span>
                  <span>Voice Integrity: 98.4%</span>
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-6 order-1 lg:order-2 flex flex-col gap-5 reveal-on-scroll">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-verification-mint-dim text-verification-mint border border-verification-mint/30 w-fit font-mono text-xs">
              <span>DIFF_02</span>
              <span>/</span>
              <span>VOICE_PRESERVATION</span>
            </div>
            <h3 className="font-display text-2xl sm:text-3xl lg:text-4xl text-off-white font-semibold tracking-tight">
              Intent-Preserving Repair
            </h3>
            <p className="text-base text-secondary leading-relaxed">
              Legal redlines usually kill conversion copy. Proofmint’s constraint solver calculates the minimal token perturbation necessary to cure compliance and guideline exposure while maintaining persuasive punch, cadence, and brand tone.
            </p>
            <ul className="space-y-3 text-sm text-on-surface-variant">
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Minimal Levenshtein token distance calculation
              </li>
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Preserves rhythmic syllable cadence and marketing conversion intent
              </li>
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Instant single-click approval directly back into native composition tools
              </li>
            </ul>
          </div>
        </div>

        {/* Showcase 3: Ambiguity Radar */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          <div className="lg:col-span-6 flex flex-col gap-5 reveal-on-scroll">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-warning-copper-dim text-warning-copper border border-warning-copper/30 w-fit font-mono text-xs">
              <span>DIFF_03</span>
              <span>/</span>
              <span>MULTI_JURISDICTION_DEFENSE</span>
            </div>
            <h3 className="font-display text-2xl sm:text-3xl lg:text-4xl text-off-white font-semibold tracking-tight">
              Ambiguity &amp; Regulatory Radar
            </h3>
            <p className="text-base text-secondary leading-relaxed">
              Marketing copy doesn&apos;t get sued for what it deliberately stated—it gets sued for implicit claims and jurisdictional traps. Proofmint scans copy against FTC substantiation doctrine, the EU AI Act transparency rules, and UK CMA greenwashing rubrics.
            </p>
            <ul className="space-y-3 text-sm text-on-surface-variant">
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-warning-copper shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                Catches implied warranties and unspoken performance guarantees
              </li>
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-warning-copper shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                Active monitoring of green claim directives and ESG substantiation
              </li>
              <li className="flex items-center gap-3">
                <svg className="w-5 h-5 text-warning-copper shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                Zero-latency jurisdiction targeting (US-FTC, EU-GDPR, UK-CMA)
              </li>
            </ul>
          </div>

          <div className="lg:col-span-6 bg-charcoal-elevated p-6 rounded-xl border border-border-structural shadow-xl reveal-on-scroll">
            <div className="flex items-center justify-between pb-4 border-b border-border-structural font-mono text-xs text-secondary">
              <span>JURISDICTIONAL_COMPLIANCE_GRID</span>
              <span className="text-warning-copper font-medium">ACTIVE SURVEILLANCE</span>
            </div>
            <div className="space-y-3 mt-5">
              <div className="flex items-center justify-between p-3.5 rounded bg-graphite-base border border-border-structural">
                <div className="flex items-center gap-3">
                  <svg className="w-5 h-5 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="font-mono text-xs sm:text-sm text-off-white">EU AI Act (Art. 50 Transparency)</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-verification-mint-dim text-verification-mint font-mono text-xs font-semibold">
                  PASSED
                </span>
              </div>

              <div className="flex items-center justify-between p-3.5 rounded bg-graphite-base border border-border-structural">
                <div className="flex items-center gap-3">
                  <svg className="w-5 h-5 text-warning-copper shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span className="font-mono text-xs sm:text-sm text-off-white">FTC 16 CFR § 255 (Substantiation)</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-warning-copper-dim text-warning-copper font-mono text-xs font-semibold">
                  INTERCEPTED
                </span>
              </div>

              <div className="flex items-center justify-between p-3.5 rounded bg-graphite-base border border-border-structural">
                <div className="flex items-center gap-3">
                  <svg className="w-5 h-5 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="font-mono text-xs sm:text-sm text-off-white">UK CMA Green Claims Code</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-verification-mint-dim text-verification-mint font-mono text-xs font-semibold">
                  PASSED
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
