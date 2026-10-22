"use client";

import React, { useState } from "react";

export function InteractionSpecsDrawer() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <section className="w-full py-16 bg-surface-container-low border-b border-border-structural">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div>
            <span className="font-mono text-xs text-secondary uppercase tracking-widest block mb-1">
              System Design Architecture
            </span>
            <h3 className="font-display text-xl sm:text-2xl text-off-white font-semibold">
              Scroll &amp; Interaction Engineering Specification
            </h3>
          </div>

          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-charcoal-elevated border border-border-structural text-off-white font-mono text-xs hover:border-verification-mint transition-all self-start md:self-auto"
          >
            <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            <span>{isOpen ? "Collapse Interaction Specs" : "Expand Interaction Specs"}</span>
          </button>
        </div>

        {/* Expandable Engineering Drawer */}
        {isOpen && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-charcoal-elevated p-6 rounded-xl border border-border-structural animate-fade-in">
            <div className="space-y-3 font-mono text-xs">
              <span className="text-verification-mint font-semibold block">01. SCROLL PHYSICS &amp; EASING</span>
              <div className="p-3 bg-graphite-base rounded border border-border-structural space-y-1 text-secondary">
                <div>Curve: cubic-bezier(0.16, 1, 0.3, 1)</div>
                <div>Pin Viewport: 80vh threshold</div>
                <div>Scrub Latency: 12ms lerp</div>
                <div>Overscroll behavior: contain-y</div>
              </div>
              <p className="text-xs text-on-surface-variant font-sans">
                Maintains steady typographic cadence while pinning telemetry sidebars during claim verification scans.
              </p>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <span className="text-verification-mint font-semibold block">02. VERIFICATION CHOREOGRAPHY</span>
              <div className="p-3 bg-graphite-base rounded border border-border-structural space-y-1 text-secondary">
                <div>T0: Intercept payload event</div>
                <div>T+150ms: Luminous wave scan</div>
                <div>T+300ms: Bounding box focus token</div>
                <div>T+450ms: Telemetry drawer slide-in</div>
              </div>
              <p className="text-xs text-on-surface-variant font-sans">
                Non-blocking GPU-accelerated CSS transforms paired with zero layout shift (CLS: 0.00).
              </p>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <span className="text-warning-copper font-semibold block">03. ACCESSIBILITY OVERRIDES</span>
              <div className="p-3 bg-graphite-base rounded border border-border-structural space-y-1 text-secondary">
                <div>prefers-reduced-motion: reduce</div>
                <div>Fallback: Instant state swaps</div>
                <div>Screen reader live regions: active</div>
                <div>Contrast metric: WCAG AAA 7:1</div>
              </div>
              <p className="text-xs text-on-surface-variant font-sans">
                Graceful fallback honoring enterprise accessibility mandates across all assistive interfaces.
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
