import React from "react";

export function AssetGapMatrix() {
  return (
    <section className="w-full py-20 lg:py-24 bg-surface-container-low border-b border-border-structural">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
        {/* Section Headline */}
        <div className="max-w-3xl mb-16 reveal-on-scroll">
          <span className="font-mono text-xs text-warning-copper uppercase tracking-widest font-semibold block mb-3">
            The Architectural Asset Gap
          </span>
          <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl text-off-white font-semibold tracking-tight">
            Approved brand asset portals don&apos;t prevent unproven claims.
          </h2>
          <p className="text-base sm:text-lg text-secondary mt-4 leading-relaxed">
            Enterprises invest millions into Digital Asset Management systems that store high-res logos, typography packs, and color swatches. Yet catastrophic compliance fines and brand erosion happen in the sentences written around those assets.
          </p>
        </div>

        {/* 3-Column Contrast Matrix */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Matrix Card 1 */}
          <div className="bg-charcoal-elevated p-6 sm:p-8 rounded-xl border border-border-structural flex flex-col justify-between hover:border-border-focus transition-all group reveal-on-scroll">
            <div>
              <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-secondary mb-6 group-hover:text-verification-mint transition-colors">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              </div>
              <span className="font-mono text-[11px] text-secondary uppercase tracking-wider block mb-2">
                Scope of Assurance
              </span>
              <h3 className="font-display text-lg font-semibold text-off-white mb-6">
                Semantic vs Visual Assets
              </h3>

              <div className="space-y-4 pt-4 border-t border-border-structural">
                <div className="space-y-1">
                  <span className="font-mono text-[11px] text-secondary">DAM PORTALS:</span>
                  <p className="text-xs sm:text-sm text-on-surface-variant">
                    Store logos, vectors, and brand fonts in pristine multi-tenant buckets.
                  </p>
                </div>
                <div className="space-y-1 pt-3 border-t border-border-structural/50">
                  <span className="font-mono text-[11px] text-verification-mint">PROOFMINT ENGINE:</span>
                  <p className="text-xs sm:text-sm text-off-white font-medium">
                    Verifies whether the text surrounding the logo is legally defensible and grounded in evidence.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-8 pt-4 border-t border-border-structural flex items-center justify-between text-xs font-mono">
              <span className="text-secondary">Audit Depth</span>
              <span className="text-verification-mint">Deep Semantic Telemetry</span>
            </div>
          </div>

          {/* Matrix Card 2 */}
          <div className="bg-charcoal-elevated p-6 sm:p-8 rounded-xl border border-border-structural flex flex-col justify-between hover:border-border-focus transition-all group reveal-on-scroll">
            <div>
              <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-secondary mb-6 group-hover:text-verification-mint transition-colors">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <span className="font-mono text-[11px] text-secondary uppercase tracking-wider block mb-2">
                Policy Enforcement
              </span>
              <h3 className="font-display text-lg font-semibold text-off-white mb-6">
                Hex Codes vs Liability Traps
              </h3>

              <div className="space-y-4 pt-4 border-t border-border-structural">
                <div className="space-y-1">
                  <span className="font-mono text-[11px] text-secondary">DAM PORTALS:</span>
                  <p className="text-xs sm:text-sm text-on-surface-variant">
                    Validates contrast ratios, hex values, padding margins, and vector resolutions.
                  </p>
                </div>
                <div className="space-y-1 pt-3 border-t border-border-structural/50">
                  <span className="font-mono text-[11px] text-verification-mint">PROOFMINT ENGINE:</span>
                  <p className="text-xs sm:text-sm text-off-white font-medium">
                    Monitors superlative drift, unverified numerical benchmarks, ESG exaggerations, and FTC disclosure gaps.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-8 pt-4 border-t border-border-structural flex items-center justify-between text-xs font-mono">
              <span className="text-secondary">Risk Scope</span>
              <span className="text-warning-copper">Regulatory & Legal Shield</span>
            </div>
          </div>

          {/* Matrix Card 3 */}
          <div className="bg-charcoal-elevated p-6 sm:p-8 rounded-xl border border-border-structural flex flex-col justify-between hover:border-border-focus transition-all group reveal-on-scroll">
            <div>
              <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-secondary mb-6 group-hover:text-verification-mint transition-colors">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <span className="font-mono text-[11px] text-secondary uppercase tracking-wider block mb-2">
                Lifecycle Lifeline
              </span>
              <h3 className="font-display text-lg font-semibold text-off-white mb-6">
                Download vs Publication
              </h3>

              <div className="space-y-4 pt-4 border-t border-border-structural">
                <div className="space-y-1">
                  <span className="font-mono text-[11px] text-secondary">DAM PORTALS:</span>
                  <p className="text-xs sm:text-sm text-on-surface-variant">
                    Governance abruptly terminates the second an asset is downloaded by a creative contractor.
                  </p>
                </div>
                <div className="space-y-1 pt-3 border-t border-border-structural/50">
                  <span className="font-mono text-[11px] text-verification-mint">PROOFMINT ENGINE:</span>
                  <p className="text-xs sm:text-sm text-off-white font-medium">
                    Operates directly in Figma, Google Docs, and CI/CD pipelines right up to the final publish keystroke.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-8 pt-4 border-t border-border-structural flex items-center justify-between text-xs font-mono">
              <span className="text-secondary">Clearance Barrier</span>
              <span className="text-off-white">Continuous Pre-Flight Gate</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
