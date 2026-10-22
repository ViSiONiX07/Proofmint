import React from "react";
import { BrandLogo } from "./BrandLogo";

export function Footer() {
  return (
    <footer className="w-full bg-surface-container-lowest border-t border-border-structural">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12 py-16">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 pb-16 border-b border-border-structural">
          {/* Brand Column */}
          <div className="md:col-span-5 flex flex-col gap-4">
            <BrandLogo size="md" />
            <p className="text-xs sm:text-sm text-on-surface-variant max-w-sm leading-relaxed">
              Enterprise pre-publication brand verification infrastructure. Continuous brand telemetry, visual contract enforcement, and sovereign compliance auditing.
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-verification-mint-dim text-verification-mint border border-verification-mint/25 font-mono text-xs">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                SOC 2 Type II Certified
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container text-on-surface-variant border border-border-structural font-mono text-xs">
                ISO 27001
              </span>
            </div>
          </div>

          {/* Nav Columns */}
          <div className="md:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-8">
            <div className="flex flex-col gap-2.5">
              <span className="font-mono text-xs text-off-white uppercase tracking-wider font-semibold">
                Architecture
              </span>
              <a href="#simulator" className="text-xs text-secondary hover:text-off-white transition-colors">
                Verification Engine
              </a>
              <a href="#pipeline" className="text-xs text-secondary hover:text-off-white transition-colors">
                CI/CD Pipeline
              </a>
              <a href="#differentiators" className="text-xs text-secondary hover:text-off-white transition-colors">
                Visual Contracts
              </a>
              <a href="#simulator" className="text-xs text-secondary hover:text-off-white transition-colors">
                Inspection Telemetry
              </a>
            </div>

            <div className="flex flex-col gap-2.5">
              <span className="font-mono text-xs text-off-white uppercase tracking-wider font-semibold">
                Trust &amp; Governance
              </span>
              <a href="#workspace-hub" className="text-xs text-secondary hover:text-off-white transition-colors">
                Evidence Vault
              </a>
              <a href="#governance" className="text-xs text-secondary hover:text-off-white transition-colors">
                Governance Charter
              </a>
              <a href="#differentiators" className="text-xs text-secondary hover:text-off-white transition-colors">
                Regulatory Filings
              </a>
              <a href="#governance" className="text-xs text-secondary hover:text-off-white transition-colors">
                Data Sovereignty
              </a>
            </div>

            <div className="flex flex-col gap-2.5">
              <span className="font-mono text-xs text-off-white uppercase tracking-wider font-semibold">
                Enterprise
              </span>
              <a href="#simulator" className="text-xs text-secondary hover:text-off-white transition-colors">
                Access Request
              </a>
              <a href="#governance" className="text-xs text-secondary hover:text-off-white transition-colors">
                Privacy Policy
              </a>
              <a href="#governance" className="text-xs text-secondary hover:text-off-white transition-colors">
                Terms of Service
              </a>
              <a href="#governance" className="text-xs text-secondary hover:text-off-white transition-colors">
                SLA Commitments
              </a>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-on-surface-variant">
          <div>&copy; 2026 Proofmint Inc. All rights reserved. Sovereign brand assurance.</div>
          <div className="flex items-center gap-6">
            <a href="#governance" className="hover:text-off-white transition-colors">Privacy</a>
            <a href="#governance" className="hover:text-off-white transition-colors">Terms</a>
            <a href="#differentiators" className="hover:text-off-white transition-colors">Compliance Index</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
