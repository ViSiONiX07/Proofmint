"use client";

import React, { useState } from "react";

type FlagId = "sec-402" | "sty-108";
type DecisionState = "PENDING" | "ACCEPTED" | "ESCALATED" | "OVERRIDDEN";

interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: string;
  actor: string;
  token: string;
  ruleId: string;
}

export function VerificationStudio() {
  const [activeFlag, setActiveFlag] = useState<FlagId>("sec-402");
  const [decision, setDecision] = useState<DecisionState>("PENDING");
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([
    {
      id: "log-1",
      timestamp: "11:04:12 UTC",
      action: "TELEMETRY_SCAN_INTERCEPT",
      actor: "ENGINE_V4.8",
      token: "SHA256:7f83b165...9069",
      ruleId: "SEC-402",
    },
  ]);

  const flagData = {
    "sec-402": {
      ruleId: "SEC-402",
      badgeLabel: "SEC-402 Violation",
      badgeColor: "bg-warning-copper-dim text-warning-copper border-warning-copper/40",
      triggerSegment: '"100% zero-downtime guaranteed"',
      contractAssertion:
        "Rule SEC-402: Absolute uptime representations require formal external SLA Schedule annex citation or must be qualified with 'targeted availability' under FTC 16 CFR § 255.",
      evidenceSource: "Core_SLA_Master_Annex_2024.pdf#p12",
      evidenceHash: "SHA-256:e3b0c442...a495",
      evidenceExcerpt:
        "Published SLA specifies 99.99% availability limit with maintenance carve-outs. Marketing copy exceeds legally defensible thresholds.",
      suggestedCorrection: '"99.99% targeted availability"',
      tokenDelta: 2,
      semanticDistance: 0.042,
    },
    "sty-108": {
      ruleId: "STY-108",
      badgeLabel: "STY-108 Suggestion",
      badgeColor: "bg-verification-mint-dim text-verification-mint border-verification-mint/40",
      triggerSegment: '"revolutionary cloud architecture"',
      contractAssertion:
        "Rule STY-108: Superlative & Cliché Avoidance. Unqualified hype descriptors degrade institutional trust and fail enterprise brand voice contracts.",
      evidenceSource: "Brand_Voice_Vocabulary_Guidelines_v3.pdf#p4",
      evidenceHash: "SHA-256:8f2a910d...11b2",
      evidenceExcerpt:
        "Prohibits 'revolutionary', 'game-changing', and 'disruptive' in corporate B2B collateral. Replaces with measured architectural specifications.",
      suggestedCorrection: '"purpose-built distributed architecture"',
      tokenDelta: 2,
      semanticDistance: 0.038,
    },
  };

  const current = flagData[activeFlag];

  const handleDecision = (type: DecisionState) => {
    setDecision(type);
    const newLog: AuditLogEntry = {
      id: `log-${Date.now()}`,
      timestamp: new Date().toLocaleTimeString() + " UTC",
      action:
        type === "ACCEPTED"
          ? "HUMAN_SURGICAL_REPAIR_ACCEPTED"
          : type === "ESCALATED"
          ? "LEGAL_ESCALATION_DISPATCHED"
          : "OVERRIDE_SIGNED_WITH_AUDIT_TRAIL",
      actor: "HUMAN_OPERATOR_USER_81",
      token: `ED25519:${Math.random().toString(36).substring(2, 10)}...${Math.random().toString(36).substring(2, 6)}`,
      ruleId: current.ruleId,
    };
    setAuditLogs((prev) => [newLog, ...prev.slice(0, 3)]);
  };

  return (
    <section className="relative w-full py-16 lg:py-24 bg-graphite-base border-b border-border-structural" id="simulator">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
        {/* Stage Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
          <div>
            <div className="flex items-center gap-2 text-verification-mint font-mono text-xs uppercase tracking-wider mb-2">
              <span className="inline-block w-2 h-2 rounded-full bg-verification-mint animate-pulse"></span>
              Live Telemetry Engine v4.8
            </div>
            <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl text-off-white font-semibold">
              In-Flight Verification Studio
            </h2>
          </div>

          <div className="flex items-center gap-3 bg-charcoal-elevated px-3.5 py-2 rounded-lg border border-border-structural self-start md:self-auto">
            <span className="text-xs text-secondary">Asset State:</span>
            <span className="inline-flex items-center gap-1.5 text-xs font-mono text-warning-copper font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-warning-copper animate-ping"></span>
              2 Violations Intercepted
            </span>
          </div>
        </div>

        {/* Main Stage Split Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 bg-surface-container-lowest p-4 sm:p-6 lg:p-8 rounded-xl border border-border-structural shadow-2xl">
          {/* Left Column: Copy Canvas & Surgical Diff (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-6">
            <div className="bg-charcoal-elevated rounded-lg border border-border-structural p-5 sm:p-6 flex flex-col h-full justify-between">
              <div>
                {/* File Header */}
                <div className="flex items-center justify-between pb-4 mb-5 border-b border-border-structural/60">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-surface-container-high"></span>
                    <span className="w-3 h-3 rounded-full bg-surface-container-high"></span>
                    <span className="w-3 h-3 rounded-full bg-surface-container-high"></span>
                    <span className="ml-2 font-mono text-xs text-secondary truncate">
                      campaign-q3_homepage-hero.md
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-surface-container text-on-surface-variant font-mono text-[11px]">
                      Markdown Stream
                    </span>
                  </div>
                </div>

                <div className="mb-3 flex items-center justify-between">
                  <span className="font-mono text-xs text-secondary uppercase tracking-wider">
                    Submitted Copy Payload:
                  </span>
                  <span className="text-xs text-secondary/60">Click underlined tokens to inspect</span>
                </div>

                {/* Interactive Highlight Copy Box */}
                <div className="p-5 sm:p-6 rounded-lg bg-graphite-base border border-border-structural text-base sm:text-lg text-off-white leading-relaxed select-none">
                  &ldquo;Our{" "}
                  {/* Flag 2: Style STY-108 */}
                  <button
                    type="button"
                    onClick={() => setActiveFlag("sty-108")}
                    className={`group relative inline-flex items-center px-2 py-0.5 rounded mx-1 text-left transition-all cursor-pointer ${
                      activeFlag === "sty-108"
                        ? "bg-verification-mint/20 text-verification-mint ring-1 ring-verification-mint"
                        : "bg-verification-mint-dim text-verification-mint/90 hover:bg-verification-mint/20 border border-verification-mint/30"
                    }`}
                  >
                    <span className="underline decoration-dotted underline-offset-4 decoration-verification-mint font-medium">
                      revolutionary cloud architecture
                    </span>
                    <span className="ml-1.5 px-1 py-0.2 rounded text-[10px] font-mono bg-verification-mint/30 text-off-white font-semibold">
                      STY-108
                    </span>
                  </button>{" "}
                  delivers 10x speed with{" "}
                  {/* Flag 1: Warning SEC-402 */}
                  <button
                    type="button"
                    onClick={() => setActiveFlag("sec-402")}
                    className={`group relative inline-flex items-center px-2 py-0.5 rounded mx-1 text-left transition-all cursor-pointer ${
                      activeFlag === "sec-402"
                        ? "bg-warning-copper/20 text-warning-copper ring-1 ring-warning-copper"
                        : "bg-warning-copper-dim text-warning-copper/90 hover:bg-warning-copper/20 border border-warning-copper/30"
                    }`}
                  >
                    <span className="underline decoration-wavy underline-offset-4 decoration-warning-copper font-medium">
                      100% zero-downtime guaranteed
                    </span>
                    <span className="ml-1.5 px-1 py-0.2 rounded text-[10px] font-mono bg-warning-copper/30 text-off-white font-semibold">
                      SEC-402
                    </span>
                  </button>{" "}
                  worldwide.&rdquo;
                </div>

                <p className="text-xs text-secondary mt-3 flex items-center gap-1.5 font-mono">
                  <svg className="w-4 h-4 text-verification-mint shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Selected Rule: <strong className="text-off-white">{current.ruleId}</strong>. Switch rules above to verify citations.
                </p>
              </div>

              {/* Surgical Minimal Diff Visualization */}
              <div className="mt-8 pt-6 border-t border-border-structural">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-3 gap-2">
                  <span className="font-mono text-xs text-off-white flex items-center gap-2">
                    <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                    </svg>
                    SURGICAL_REPAIR_DIFF (Target: Zero Meaning Loss)
                  </span>
                  <span className="font-mono text-xs text-verification-mint">
                    Semantic Distance: {current.semanticDistance}
                  </span>
                </div>

                <div className="p-4 rounded-lg bg-surface-container-lowest font-mono text-xs sm:text-sm space-y-2 border border-border-structural">
                  <div className="flex items-start gap-2 text-warning-copper/80">
                    <span className="select-none font-bold text-warning-copper">-</span>
                    <span className="line-through">
                      revolutionary cloud architecture delivers 10x speed with 100% zero-downtime guaranteed worldwide.
                    </span>
                  </div>
                  <div className="flex items-start gap-2 text-verification-mint">
                    <span className="select-none font-bold text-verification-mint">+</span>
                    <span>
                      purpose-built distributed architecture delivers 10x speed with 99.99% targeted availability worldwide.
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-4 mt-2 font-mono text-xs text-secondary">
                  <span className="text-verification-mint">Tokens Changed: 4</span>
                  <span>Voice Integrity: 98.4%</span>
                  <span>Cadence Preserved: Yes</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Inspector Panel & Evidence Citation (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            <div className="bg-charcoal-elevated rounded-lg border border-border-structural p-5 sm:p-6 flex flex-col justify-between h-full">
              <div>
                {/* Inspector Header */}
                <div className="flex items-center justify-between pb-4 mb-4 border-b border-border-structural">
                  <div className="flex items-center gap-2">
                    <svg className="w-5 h-5 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <h3 className="font-display text-base font-semibold text-off-white">Contract Telemetry</h3>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded-full border font-mono text-xs font-medium ${current.badgeColor}`}>
                    {current.badgeLabel}
                  </span>
                </div>

                {/* Dynamic Detail Content */}
                <div className="space-y-4">
                  <div>
                    <span className="font-mono text-xs text-secondary uppercase tracking-wider block mb-1">
                      Trigger Segment
                    </span>
                    <div className="font-mono text-off-white bg-graphite-base p-2.5 rounded border border-border-structural text-xs sm:text-sm">
                      {current.triggerSegment}
                    </div>
                  </div>

                  <div>
                    <span className="font-mono text-xs text-secondary uppercase tracking-wider block mb-1">
                      Contract Assertion
                    </span>
                    <p className="text-xs sm:text-sm text-on-surface leading-normal bg-charcoal-subtle/50 p-2.5 rounded border border-border-structural/50">
                      {current.contractAssertion}
                    </p>
                  </div>

                  {/* Evidence Locker Drawer */}
                  <div className="p-4 rounded-lg bg-surface-container border border-border-structural space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-off-white flex items-center gap-1.5">
                        <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                        Evidence-Locked Citation
                      </span>
                      <span className="font-mono text-[11px] text-verification-mint">Cryptographic Proof</span>
                    </div>

                    <div className="font-mono text-xs text-on-surface-variant flex items-center justify-between bg-surface-container-lowest p-2 rounded">
                      <span className="truncate mr-2 text-off-white">{current.evidenceSource}</span>
                      <span className="text-verification-mint shrink-0 text-[11px] font-mono">
                        {current.evidenceHash}
                      </span>
                    </div>

                    <p className="text-xs text-secondary italic">
                      &ldquo;{current.evidenceExcerpt}&rdquo;
                    </p>
                  </div>

                  <div>
                    <span className="font-mono text-xs text-secondary uppercase tracking-wider block mb-1">
                      Suggested Surgical Correction
                    </span>
                    <div className="font-mono text-verification-mint bg-verification-mint-dim p-2.5 rounded border border-verification-mint/30 text-xs sm:text-sm font-semibold">
                      {current.suggestedCorrection}
                    </div>
                  </div>
                </div>
              </div>

              {/* Human Reviewer Decision Bar */}
              <div className="mt-8 pt-5 border-t border-border-structural">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-mono text-xs text-off-white font-medium flex items-center gap-1.5">
                    <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Human Clearance Terminal
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded font-mono text-[11px] ${
                      decision === "ACCEPTED"
                        ? "bg-verification-mint-dim text-verification-mint border border-verification-mint/30"
                        : decision === "ESCALATED"
                        ? "bg-warning-copper-dim text-warning-copper border border-warning-copper/30"
                        : decision === "OVERRIDDEN"
                        ? "bg-charcoal-subtle text-off-white border border-border-structural"
                        : "bg-surface-container-highest text-secondary"
                    }`}
                  >
                    {decision === "ACCEPTED"
                      ? "Signed & Cleared"
                      : decision === "ESCALATED"
                      ? "Sent to Legal"
                      : decision === "OVERRIDDEN"
                      ? "Override Logged"
                      : "Export Gated"}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => handleDecision("ACCEPTED")}
                    className={`px-2 py-2.5 rounded text-xs font-mono font-semibold transition-all flex items-center justify-center gap-1 text-center active:scale-95 ${
                      decision === "ACCEPTED"
                        ? "bg-off-white text-graphite-base shadow-mint-glow"
                        : "bg-verification-mint text-graphite-base hover:brightness-105"
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                    </svg>
                    Accept Repair
                  </button>

                  <button
                    type="button"
                    onClick={() => handleDecision("ESCALATED")}
                    className={`px-2 py-2.5 rounded text-xs font-mono font-medium border border-border-structural transition-all flex items-center justify-center gap-1 text-center active:scale-95 ${
                      decision === "ESCALATED"
                        ? "bg-warning-copper/20 text-warning-copper border-warning-copper"
                        : "bg-charcoal-subtle text-off-white hover:text-warning-copper hover:border-warning-copper/50"
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                    </svg>
                    Legal Escalate
                  </button>

                  <button
                    type="button"
                    onClick={() => handleDecision("OVERRIDDEN")}
                    className={`px-2 py-2.5 rounded text-xs font-mono font-medium border border-border-structural transition-all flex items-center justify-center gap-1 text-center active:scale-95 ${
                      decision === "OVERRIDDEN"
                        ? "bg-graphite-base text-off-white border-off-white/40"
                        : "bg-surface-container-highest text-secondary hover:text-off-white"
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Override
                  </button>
                </div>

                <p className="font-mono text-[11px] text-secondary text-center mt-2.5">
                  Every decision appends a signed cryptographic audit token before CDN deployment.
                </p>

                {/* Live Append-Only Audit Telemetry Feed */}
                <div className="mt-3 pt-3 border-t border-border-structural/60 space-y-1">
                  <div className="text-[10px] font-mono text-secondary uppercase tracking-wider">
                    Recent Cryptographic Receipts:
                  </div>
                  {auditLogs.map((log) => (
                    <div
                      key={log.id}
                      className="text-[10px] font-mono text-on-surface-variant flex items-center justify-between bg-graphite-base/80 p-1.5 rounded border border-border-structural/40"
                    >
                      <span className="text-verification-mint">{log.action}</span>
                      <span className="text-secondary/80">{log.timestamp}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
