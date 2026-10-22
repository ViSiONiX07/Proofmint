import React from "react";

interface HeroProps {
  onOpenWorkspace?: () => void;
}

export function Hero({ onOpenWorkspace }: HeroProps) {
  return (
    <section className="relative w-full pt-20 pb-20 md:pt-28 md:pb-28 overflow-hidden bg-graphite-base border-b border-border-structural" id="overview">
      {/* Ambient architectural grid background */}
      <div className="absolute inset-0 pointer-events-none opacity-20">
        <div className="absolute inset-0 [background-image:linear-gradient(to_right,#242A2D_1px,transparent_1px),linear-gradient(to_bottom,#242A2D_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
      </div>

      {/* Mint glowing flare highlight */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[720px] h-[280px] bg-verification-mint/10 blur-[130px] rounded-full pointer-events-none"></div>

      <div className="relative max-w-7xl mx-auto px-6 lg:px-12 flex flex-col items-center text-center">
        {/* Eyebrow Badge */}
        <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-charcoal-elevated border border-border-structural shadow-sm mb-8 hover:border-verification-mint/40 transition-colors">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-verification-mint opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-verification-mint"></span>
          </span>
          <span className="font-mono text-xs text-off-white tracking-widest uppercase font-medium">
            AI-POWERED PRE-PUBLICATION BRAND VERIFICATION
          </span>
        </div>

        {/* Main Headline */}
        <div className="flex flex-col items-center max-w-4xl mx-auto mb-6">
          <h1 className="font-display text-4xl sm:text-6xl lg:text-[68px] lg:leading-[76px] tracking-tight text-off-white font-semibold">
            Nothing ships{" "}
            <span className="text-verification-mint italic font-serif">unproven.</span>
          </h1>
        </div>

        {/* Subtitle Description */}
        <p className="text-base sm:text-lg text-secondary max-w-2xl mx-auto mb-10 leading-relaxed font-normal">
          Proofmint continuously scans staging copy against cryptographic brand contracts and verified evidence vaults. It exposes unsubstantiated superlatives, computes minimal surgical repairs, and maintains decisive human governance before export.
        </p>

        {/* Dual Action CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full sm:w-auto mb-16">
          <a
            href="#simulator"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-7 py-3.5 rounded-lg bg-verification-mint text-graphite-base font-sans text-sm font-semibold hover:brightness-105 hover:shadow-mint-glow transition-all active:scale-[0.99]"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
            Explore Interactive Verification
          </a>

          <button
            type="button"
            onClick={onOpenWorkspace}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-lg bg-charcoal-elevated text-off-white border border-border-structural font-sans text-sm font-medium hover:border-verification-mint/50 hover:text-verification-mint transition-all"
          >
            <svg className="w-5 h-5 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Open Brand Workspace Hub
          </button>
        </div>

        {/* Trust Assurance Strip */}
        <div className="w-full max-w-4xl pt-8 border-t border-border-structural/80 flex flex-col md:flex-row items-center justify-between gap-4 text-left">
          <div className="flex items-center gap-3">
            <svg className="w-6 h-6 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <p className="text-xs text-on-surface-variant max-w-md">
              Audited brand integrity across enterprise marketing, legal compliance suites, and global agency distribution pipelines.
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-secondary tracking-wider uppercase font-semibold">
            <span>SOC-2 Type II</span>
            <span className="text-border-structural">/</span>
            <span>ISO 27001</span>
            <span className="text-border-structural">/</span>
            <span>EU AI ACT AUDITED</span>
          </div>
        </div>
      </div>
    </section>
  );
}
