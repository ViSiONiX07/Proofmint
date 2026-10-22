import React from "react";

export function GovernanceArchitecture() {
  const sampleJsonReceipt = `{
  "proof_id": "prf_9829f0e1_prod",
  "timestamp": "2026-10-22T11:04:01.042Z",
  "tenant_partition": "enterprise-us-east-4",
  "guideline_manifest_hash": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
  "rules_evaluated": 142,
  "flags_detected": [
    {
      "code": "SEC-402",
      "severity": "ELEVATED_LEGAL_EXPOSURE",
      "token_span": [42, 71],
      "resolved_by": "HUMAN_OPERATOR_USER_81",
      "resolution": "SURGICAL_REPAIR_ACCEPTED",
      "evidence_anchor_id": "doc_sla_master_2024"
    }
  ],
  "zero_retention_purge": true,
  "ephemeral_signature": "SIG_ED25519_99bc301aef4021"
}`;

  return (
    <section className="w-full py-20 lg:py-28 bg-graphite-base border-b border-border-structural" id="governance">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          <div className="lg:col-span-5 flex flex-col gap-6 reveal-on-scroll">
            <span className="font-mono text-xs text-verification-mint uppercase tracking-widest font-semibold">
              Institutional Trust Architecture
            </span>
            <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl text-off-white font-semibold">
              Zero-retention private cloud with sovereign audit trails.
            </h2>
            <p className="text-base text-secondary leading-relaxed">
              Proofmint was engineered from the foundation for highly regulated enterprises: defense, fintech, healthcare, and consumer goods conglomerates.
            </p>

            <div className="space-y-4 pt-2">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-verification-mint mt-1 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                <div>
                  <h5 className="font-display text-sm font-semibold text-off-white">Zero Data Retention Policy</h5>
                  <p className="text-xs text-on-surface-variant mt-0.5">
                    In-flight copy is verified strictly in ephemeral memory. No client data trains foundational public models.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-verification-mint mt-1 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
                <div>
                  <h5 className="font-display text-sm font-semibold text-off-white">Dedicated Tenant Enclaves</h5>
                  <p className="text-xs text-on-surface-variant mt-0.5">
                    KMS key isolation where your organization controls the cryptographic root of trust at all times.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-verification-mint mt-1 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09A13.916 13.916 0 008 11a4 4 0 118 0c0 1.017-.07 2.019-.203 3m-2.118 6.844A21.88 21.88 0 0015.171 17m3.839 1.132c.645-2.266.99-4.659.99-7.132A8 8 0 008 4.07M3 15.364c.64-1.319 1-2.8 1-4.364 0-1.457.39-2.823 1.07-4" />
                </svg>
                <div>
                  <h5 className="font-display text-sm font-semibold text-off-white">Immutable Audit Logs</h5>
                  <p className="text-xs text-on-surface-variant mt-0.5">
                    Every approval, override, and surgical repair is timestamped in an append-only verifiable ledger.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7 bg-surface-container-lowest p-5 sm:p-6 rounded-xl border border-border-structural font-mono reveal-on-scroll">
            <div className="flex items-center justify-between pb-3 border-b border-border-structural text-xs text-secondary">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-verification-mint"></span>
                PROOFMINT_GOVERNANCE_LEDGER_RECEIPT
              </span>
              <span className="text-verification-mint font-semibold">SEC_AUDIT_OK</span>
            </div>

            <pre className="mt-4 text-[11px] sm:text-xs text-on-surface overflow-x-auto p-4 bg-graphite-base rounded-lg border border-border-structural leading-5">
              <code>{sampleJsonReceipt}</code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
