"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import React, { useState, useEffect, useRef, ChangeEvent, useCallback } from "react";

type WorkspaceTab = "guidelines" | "facts" | "submission" | "findings" | "ledger";

interface RuleItem {
  id: string;
  name: string;
  category: string;
  excerpt: string;
  status: "APPROVED" | "PENDING" | "REJECTED";
  source: string;
}

export function WorkspaceStudio() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("guidelines");

  const [rules, setRules] = useState<RuleItem[]>([
    {
      id: "SEC-402",
      name: "Absolute Uptime Representations",
      category: "Legal & SLA",
      excerpt: "Requires qualification with 'targeted availability' unless supported by explicit SLA Annex.",
      status: "APPROVED",
      source: "Core_SLA_Master_Annex_2024.pdf#p12",
    },
    {
      id: "STY-108",
      name: "Superlative & Cliché Avoidance",
      category: "Brand Voice",
      excerpt: "Prohibits 'revolutionary', 'game-changing', and 'unmatched' in technical B2B collateral.",
      status: "APPROVED",
      source: "Brand_Voice_Vocabulary_Guidelines_v3.pdf#p4",
    },
    {
      id: "REG-301",
      name: "ESG & Energy Metric Substantiation",
      category: "Regulatory",
      excerpt: "Energy reduction claims over 30% must cite a third-party audit conducted within 12 months.",
      status: "PENDING",
      source: "Sustainability_Compliance_Brief_2024.pdf#p8",
    },
    {
      id: "VOI-204",
      name: "Direct Competitor Comparison Restrictions",
      category: "Trademark & Legal",
      excerpt: "Named competitor benchmarks must reference publicly filed audited whitepapers.",
      status: "APPROVED",
      source: "Competitive_Positioning_Framework.pdf#p19",
    },
  ]);

  const [selectedChannel, setSelectedChannel] = useState("Enterprise Web Landing Page");
  const [submittedCopy, setSubmittedCopy] = useState(
    "Our revolutionary cloud architecture delivers 10x speed with 100% zero-downtime guaranteed worldwide."
  );
  const [isAuditing, setIsAuditing] = useState(false);
  const [auditComplete, setAuditComplete] = useState(false);

  const handleRunAudit = () => {
    setIsAuditing(true);
    setTimeout(() => {
      setIsAuditing(false);
      setAuditComplete(true);
      setActiveTab("findings");
    }, 850);
  };

  const handleApproveRule = (id: string) => {
    setRules((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: "APPROVED" } : r))
    );
  };

  return (
    <section className="w-full py-16 lg:py-24 bg-surface-container-low border-b border-border-structural" id="workspace-hub">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
        {/* Workspace Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-verification-mint-dim text-verification-mint border border-verification-mint/30 font-mono text-[11px] uppercase tracking-wider mb-2">
              <span className="w-1.5 h-1.5 rounded-full bg-verification-mint"></span>
              Frontify-Inspired Brand Governance Hub
            </div>
            <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl text-off-white font-semibold">
              Proofmint Brand Workspace
            </h2>
            <p className="text-sm text-secondary mt-1 max-w-xl">
              Organize verified brand materials, import approved factual claims, and review human-gated compliance candidates.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto">
            <span className="px-3 py-1 rounded bg-graphite-base border border-border-structural font-mono text-xs text-secondary">
              Tenant: <strong className="text-off-white font-medium">Acme Enterprise Core</strong>
            </span>
            <span className="px-2.5 py-1 rounded bg-verification-mint-dim border border-verification-mint/30 font-mono text-xs text-verification-mint">
              KMS Isolated
            </span>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 overflow-x-auto border-b border-border-structural pb-px mb-6 scrollbar-none">
          <button
            type="button"
            onClick={() => setActiveTab("guidelines")}
            className={`px-4 py-2.5 rounded-t-lg font-sans text-xs sm:text-sm font-medium transition-all shrink-0 flex items-center gap-2 ${
              activeTab === "guidelines"
                ? "bg-charcoal-elevated text-off-white border-t border-x border-border-structural border-b-2 border-b-verification-mint"
                : "text-secondary hover:text-off-white hover:bg-charcoal-elevated/40"
            }`}
          >
            <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Brand Guidelines & Rules ({rules.length})
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("facts")}
            className={`px-4 py-2.5 rounded-t-lg font-sans text-xs sm:text-sm font-medium transition-all shrink-0 flex items-center gap-2 ${
              activeTab === "facts"
                ? "bg-charcoal-elevated text-off-white border-t border-x border-border-structural border-b-2 border-b-verification-mint"
                : "text-secondary hover:text-off-white hover:bg-charcoal-elevated/40"
            }`}
          >
            <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2 1.5 3 3.5 3h9c2 0 3.5-1 3.5-3V7c0-2-1.5-3-3.5-3h-9C5.5 4 4 5 4 7z" />
            </svg>
            Approved Facts & Terms (CSV)
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("submission")}
            className={`px-4 py-2.5 rounded-t-lg font-sans text-xs sm:text-sm font-medium transition-all shrink-0 flex items-center gap-2 ${
              activeTab === "submission"
                ? "bg-charcoal-elevated text-off-white border-t border-x border-border-structural border-b-2 border-b-verification-mint"
                : "text-secondary hover:text-off-white hover:bg-charcoal-elevated/40"
            }`}
          >
            <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Content Submission & Audit
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("findings")}
            className={`px-4 py-2.5 rounded-t-lg font-sans text-xs sm:text-sm font-medium transition-all shrink-0 flex items-center gap-2 ${
              activeTab === "findings"
                ? "bg-charcoal-elevated text-off-white border-t border-x border-border-structural border-b-2 border-b-verification-mint"
                : "text-secondary hover:text-off-white hover:bg-charcoal-elevated/40"
            }`}
          >
            <svg className="w-4 h-4 text-warning-copper" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Evidence & Findings {auditComplete && <span className="w-2 h-2 rounded-full bg-warning-copper"></span>}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("ledger")}
            className={`px-4 py-2.5 rounded-t-lg font-sans text-xs sm:text-sm font-medium transition-all shrink-0 flex items-center gap-2 ${
              activeTab === "ledger"
                ? "bg-charcoal-elevated text-off-white border-t border-x border-border-structural border-b-2 border-b-verification-mint"
                : "text-secondary hover:text-off-white hover:bg-charcoal-elevated/40"
            }`}
          >
            <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Clearance Ledger
          </button>
        </div>

        {/* Tab 1: Guidelines & Rules */}
        {activeTab === "guidelines" && (
          <div className="space-y-6">
            {/* Guidelines Control Bar */}
            <div className="bg-charcoal-elevated p-6 rounded-xl border border-border-structural flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="space-y-1">
                <h3 className="font-display text-lg font-semibold text-off-white">
                  Brand Guidelines Documents Vault
                </h3>
                <p className="text-xs text-secondary">
                  Uploaded PDF guidelines are segmented into candidate verification rules. Human review is required before rules activate in the audit engine.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <Link href="/studio">
  <button
    type="button"
    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-verification-mint text-graphite-base font-sans text-xs font-semibold hover:brightness-105 transition-all"
  >
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
    </svg>
    Open Launch Studio to upload guidelines
  </button>
</Link>
              </div>
            </div>

            {/* Extracted Rules Matrix */}
            <div className="bg-charcoal-elevated rounded-xl border border-border-structural overflow-hidden">
              <div className="p-4 border-b border-border-structural flex items-center justify-between font-mono text-xs text-secondary">
                <span>Illustrative Sample Rules ({rules.length})</span>
                <span>HUMAN_APPROVAL_GATED</span>
              </div>

              <div className="divide-y divide-border-structural/60">
                {rules.map((rule) => (
                  <div key={rule.id} className="p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 hover:bg-charcoal-subtle/40 transition-colors">
                    <div className="space-y-1 max-w-2xl">
                      <div className="flex items-center gap-2.5">
                        <span className="font-mono text-xs font-bold text-off-white px-2 py-0.5 rounded bg-graphite-base border border-border-structural">
                          {rule.id}
                        </span>
                        <h4 className="font-sans text-sm font-medium text-off-white">{rule.name}</h4>
                        <span className="text-[10px] font-mono text-secondary px-2 py-0.5 rounded bg-surface-container">
                          {rule.category}
                        </span>
                      </div>
                      <p className="text-xs text-secondary">{rule.excerpt}</p>
                      <div className="font-mono text-[11px] text-verification-mint flex items-center gap-1">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                        Source: {rule.source}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {rule.status === "APPROVED" ? (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-verification-mint-dim text-verification-mint border border-verification-mint/30 font-mono text-xs">
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                          </svg>
                          Approved
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleApproveRule(rule.id)}
                          className="px-3 py-1 rounded bg-warning-copper text-graphite-base font-mono text-xs font-semibold hover:brightness-105 transition-all"
                        >
                          Approve Candidate
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Approved Facts CSV */}
        {activeTab === "facts" && (
          <div className="bg-charcoal-elevated p-6 rounded-xl border border-border-structural space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-border-structural gap-3">
              <div>
                <h3 className="font-display text-lg font-semibold text-off-white">
                  Approved Facts & Terminology Ledger
                </h3>
                <p className="text-xs text-secondary">
                  Imported from <code className="text-off-white">samples/approved-facts/approved_facts_q3.csv</code>. The verification engine matches statements against these verified rows.
                </p>
              </div>
              <span className="px-3 py-1 rounded bg-graphite-base border border-border-structural font-mono text-xs text-verification-mint self-start sm:self-auto">
                4 Verified Claims Loaded
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border-structural text-secondary">
                    <th className="py-2.5 px-3">FACT_ID</th>
                    <th className="py-2.5 px-3">CLAIM_TYPE</th>
                    <th className="py-2.5 px-3">APPROVED_STATEMENT</th>
                    <th className="py-2.5 px-3">SOURCE_DOCUMENT</th>
                    <th className="py-2.5 px-3">SPAN</th>
                    <th className="py-2.5 px-3">STATUS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-structural/50 text-on-surface">
                  <tr className="hover:bg-charcoal-subtle/30">
                    <td className="py-3 px-3 text-verification-mint font-bold">FACT-001</td>
                    <td className="py-3 px-3 text-secondary">availability</td>
                    <td className="py-3 px-3 text-off-white">99.99% targeted availability worldwide</td>
                    <td className="py-3 px-3 text-secondary">Core_SLA_Master_Annex_2024.pdf</td>
                    <td className="py-3 px-3">p12</td>
                    <td className="py-3 px-3"><span className="text-verification-mint">VERIFIED</span></td>
                  </tr>
                  <tr className="hover:bg-charcoal-subtle/30">
                    <td className="py-3 px-3 text-verification-mint font-bold">FACT-002</td>
                    <td className="py-3 px-3 text-secondary">performance</td>
                    <td className="py-3 px-3 text-off-white">delivers 10x speed relative to legacy single-node clusters</td>
                    <td className="py-3 px-3 text-secondary">Benchmark_Audit_Report_2024.pdf</td>
                    <td className="py-3 px-3">p4</td>
                    <td className="py-3 px-3"><span className="text-verification-mint">VERIFIED</span></td>
                  </tr>
                  <tr className="hover:bg-charcoal-subtle/30">
                    <td className="py-3 px-3 text-verification-mint font-bold">FACT-003</td>
                    <td className="py-3 px-3 text-secondary">architecture</td>
                    <td className="py-3 px-3 text-off-white">purpose-built distributed architecture</td>
                    <td className="py-3 px-3 text-secondary">System_Architecture_Overview.pdf</td>
                    <td className="py-3 px-3">p2</td>
                    <td className="py-3 px-3"><span className="text-verification-mint">VERIFIED</span></td>
                  </tr>
                  <tr className="hover:bg-charcoal-subtle/30">
                    <td className="py-3 px-3 text-verification-mint font-bold">FACT-004</td>
                    <td className="py-3 px-3 text-secondary">compliance</td>
                    <td className="py-3 px-3 text-off-white">SOC-2 Type II and ISO 27001 audited</td>
                    <td className="py-3 px-3 text-secondary">Security_Compliance_Brief_2024.pdf</td>
                    <td className="py-3 px-3">p8</td>
                    <td className="py-3 px-3"><span className="text-verification-mint">VERIFIED</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 3: Marketing Content Submission */}
        {activeTab === "submission" && (
          <div className="bg-charcoal-elevated p-6 rounded-xl border border-border-structural space-y-6">
            <div>
              <h3 className="font-display text-lg font-semibold text-off-white">
                Submit Marketing Content for Brand Verification
              </h3>
              <p className="text-xs text-secondary mt-1">
                Content is scanned in ephemeral memory against active brand rules and verified facts. Results require human review before clearance is granted.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-mono text-secondary mb-1">DISTRIBUTION_CHANNEL</label>
                <select
                  value={selectedChannel}
                  onChange={(e) => setSelectedChannel(e.target.value)}
                  className="w-full bg-graphite-base border border-border-structural rounded p-2.5 text-xs text-off-white font-sans focus:outline-none focus:ring-1 focus:ring-verification-mint"
                >
                  <option>Enterprise Web Landing Page</option>
                  <option>Press Release & Media Distribution</option>
                  <option>Paid Social & Google Ads</option>
                  <option>Product Marketing Brochure</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs font-mono text-secondary mb-1">AUDIT_PROFILE</label>
                <div className="flex items-center gap-2 text-xs font-mono text-on-surface-variant p-2 rounded bg-graphite-base border border-border-structural">
                  <span className="text-verification-mint">✓ Full Deterministic</span>
                  <span className="text-border-structural">|</span>
                  <span className="text-verification-mint">✓ RapidFuzz Terminology</span>
                  <span className="text-border-structural">|</span>
                  <span className="text-verification-mint">✓ Evidence Grounding</span>
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-mono text-secondary">STAGING_COPY_PAYLOAD (MARKDOWN / TEXT)</label>
                <button
                  type="button"
                  onClick={() =>
                    setSubmittedCopy(
                      "Our revolutionary cloud architecture delivers 10x speed with 100% zero-downtime guaranteed worldwide."
                    )
                  }
                  className="text-[11px] font-mono text-verification-mint hover:underline"
                >
                  Load Q3 Campaign Sample
                </button>
              </div>
              <textarea
                rows={4}
                value={submittedCopy}
                onChange={(e) => setSubmittedCopy(e.target.value)}
                className="w-full bg-graphite-base border border-border-structural rounded-lg p-4 font-mono text-xs sm:text-sm text-off-white focus:outline-none focus:ring-1 focus:ring-verification-mint leading-relaxed"
                placeholder="Paste marketing copy payload here..."
              />
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-between pt-2 border-t border-border-structural gap-4">
              <span className="text-xs font-mono text-secondary flex items-center gap-1.5">
                <svg className="w-4 h-4 text-verification-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                Zero-retention ephemeral verification. No data persists without explicit approval.
              </span>

              <button
                type="button"
                onClick={handleRunAudit}
                disabled={isAuditing}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-verification-mint text-graphite-base font-sans text-xs font-bold hover:brightness-105 transition-all shadow-mint-glow disabled:opacity-50"
              >
                {isAuditing ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                    </svg>
                    Executing Multi-Vector Audit (82ms)...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Run Pre-Flight Audit
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Tab 4: Findings & Evidence */}
        {activeTab === "findings" && (
          <div className="bg-charcoal-elevated p-6 rounded-xl border border-border-structural space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-border-structural">
              <div>
                <h3 className="font-display text-lg font-semibold text-off-white">
                  Audit Findings & Evidence Lockers
                </h3>
                <p className="text-xs text-secondary mt-0.5">
                  2 actionable findings detected. Every finding links to an exact cryptographic guideline source anchor.
                </p>
              </div>
              <span className="px-3 py-1 rounded bg-warning-copper-dim text-warning-copper font-mono text-xs border border-warning-copper/30">
                2 Items Require Human Action
              </span>
            </div>

            {/* Finding Item 1 */}
            <div className="p-5 rounded-lg bg-graphite-base border border-warning-copper/40 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-warning-copper/20 text-warning-copper font-mono text-xs font-bold">
                    SEC-402
                  </span>
                  <h4 className="font-sans text-sm font-semibold text-off-white">
                    Unsubstantiated Uptime Guarantee
                  </h4>
                </div>
                <span className="text-xs font-mono text-warning-copper">Severity: ELEVATED_REGULATORY_RISK</span>
              </div>

              <div className="text-xs font-mono text-secondary">
                Trigger Token: <span className="text-off-white bg-charcoal-elevated px-2 py-0.5 rounded">&ldquo;100% zero-downtime guaranteed&rdquo;</span>
              </div>

              <div className="p-3 rounded bg-surface-container-lowest border border-border-structural font-mono text-xs space-y-1">
                <div className="text-verification-mint flex items-center justify-between">
                  <span>EVIDENCE ANCHOR: Core_SLA_Master_Annex_2024.pdf#p12</span>
                  <span className="text-secondary">SHA-256 Verified</span>
                </div>
                <p className="text-secondary italic">
                  &ldquo;Published SLA specifies 99.99% availability limit with maintenance carve-outs. Marketing copy exceeds legally defensible thresholds.&rdquo;
                </p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-border-structural/50 text-xs font-mono">
                <span className="text-secondary">
                  Suggested Minimal Repair: <strong className="text-verification-mint">&ldquo;99.99% targeted availability&rdquo;</strong>
                </span>
                <span className="text-secondary">Distance: 0.042</span>
              </div>
            </div>

            {/* Finding Item 2 */}
            <div className="p-5 rounded-lg bg-graphite-base border border-verification-mint/40 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-verification-mint/20 text-verification-mint font-mono text-xs font-bold">
                    STY-108
                  </span>
                  <h4 className="font-sans text-sm font-semibold text-off-white">
                    Superlative & Cliché Avoidance
                  </h4>
                </div>
                <span className="text-xs font-mono text-verification-mint">Severity: BRAND_VOICE_DRIFT</span>
              </div>

              <div className="text-xs font-mono text-secondary">
                Trigger Token: <span className="text-off-white bg-charcoal-elevated px-2 py-0.5 rounded">&ldquo;revolutionary cloud architecture&rdquo;</span>
              </div>

              <div className="p-3 rounded bg-surface-container-lowest border border-border-structural font-mono text-xs space-y-1">
                <div className="text-verification-mint flex items-center justify-between">
                  <span>EVIDENCE ANCHOR: Brand_Voice_Vocabulary_Guidelines_v3.pdf#p4</span>
                  <span className="text-secondary">SHA-256 Verified</span>
                </div>
                <p className="text-secondary italic">
                  &ldquo;Prohibits &apos;revolutionary&apos;, &apos;game-changing&apos;, and &apos;disruptive&apos; in corporate B2B collateral. Replaces with measured architectural specifications.&rdquo;
                </p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-border-structural/50 text-xs font-mono">
                <span className="text-secondary">
                  Suggested Minimal Repair: <strong className="text-verification-mint">&ldquo;purpose-built distributed architecture&rdquo;</strong>
                </span>
                <span className="text-secondary">Distance: 0.038</span>
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Signed Clearance Ledger */}
        {activeTab === "ledger" && (
          <div className="bg-charcoal-elevated p-6 rounded-xl border border-border-structural space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-border-structural">
              <div>
                <h3 className="font-display text-lg font-semibold text-off-white">
                  Signed Clearance Audit Ledger
                </h3>
                <p className="text-xs text-secondary mt-0.5">
                  Append-only cryptographic audit record. Every publication gate requires a signed human authorization token.
                </p>
              </div>
              <span className="px-3 py-1 rounded bg-verification-mint-dim text-verification-mint font-mono text-xs border border-verification-mint/30">
                Ledger Sync: Active
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-4 rounded-lg bg-graphite-base border border-border-structural flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="space-y-1">
                  <div className="text-off-white font-bold flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-verification-mint"></span>
                    PRF_CLEARANCE_9829F0E1_CLEARED
                  </div>
                  <div className="text-secondary text-[11px]">
                    Payload: campaign-q3_homepage-hero.md // Operator: HUMAN_OPERATOR_USER_81
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-verification-mint font-semibold">SIG_ED25519_99BC30</span>
                  <div className="text-[10px] text-secondary">2026-10-22 11:04 UTC</div>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-graphite-base border border-border-structural flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="space-y-1">
                  <div className="text-off-white font-bold flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-warning-copper"></span>
                    PRF_ESCALATION_4412B_LEGAL_ROUTED
                  </div>
                  <div className="text-secondary text-[11px]">
                    Payload: terms-update-q3.md // Rule: REG-301 FTC Substantiation
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-warning-copper font-semibold">SIG_ED25519_8817AF</span>
                  <div className="text-[10px] text-secondary">2026-10-22 09:30 UTC</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
