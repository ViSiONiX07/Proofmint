import React from "react";

export function PipelineWorkflow() {
  const steps = [
    {
      step: "STEP_01",
      title: "Evidence Ingestion",
      description: "PDFs, Notion guidelines, and legal memos parsed into verifiable semantic rules and graph edges.",
      tag: "Vector Parser",
      badgeColor: "text-verification-mint",
    },
    {
      step: "STEP_02",
      title: "Content Intake",
      description: "Direct hooks in Figma, CMS staging APIs, Google Docs, and CI/CD PR previews.",
      tag: "Webhook Ingest",
      badgeColor: "text-verification-mint",
    },
    {
      step: "STEP_03",
      title: "Multi-Vector Audit",
      description: "Parallel execution across brand rules, tone vectors, claim evidence, and regulatory frameworks.",
      tag: "82ms Evaluation",
      badgeColor: "text-warning-copper",
    },
    {
      step: "STEP_04",
      title: "Surgical Repair",
      description: "Constraint-based candidate generation ranked by minimal semantic token perturbation.",
      tag: "Intent Engine",
      badgeColor: "text-verification-mint",
    },
    {
      step: "STEP_05",
      title: "Human Sign-off",
      description: "Human reviewer authorizes repair; export gate mints a verifiable SHA-256 clearance audit token.",
      tag: "Signed Token",
      badgeColor: "text-verification-mint",
    },
  ];

  return (
    <section className="w-full py-20 lg:py-24 bg-surface-container-low border-b border-border-structural" id="pipeline">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
        <div className="max-w-3xl mb-16 reveal-on-scroll">
          <span className="font-mono text-xs text-verification-mint uppercase tracking-widest font-semibold block mb-2">
            Continuous Assurance Pipeline
          </span>
          <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl text-off-white font-semibold">
            The 5-Step Verification Architecture
          </h2>
          <p className="text-base sm:text-lg text-secondary mt-3 leading-relaxed">
            From legal memo ingestion to cryptographic clearance export, how Proofmint eliminates brand risk at machine speed.
          </p>
        </div>

        {/* Pipeline Steps Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {steps.map((s, idx) => (
            <div
              key={s.step}
              className={`bg-charcoal-elevated p-5 sm:p-6 rounded-lg border border-border-structural flex flex-col justify-between hover:border-verification-mint/40 transition-all reveal-on-scroll ${
                idx === 4 ? "border-verification-mint/30" : ""
              }`}
            >
              <div>
                <div className={`font-mono text-xs mb-3 font-semibold ${s.badgeColor}`}>
                  {s.step}
                </div>
                <h4 className="font-display text-base font-semibold text-off-white mb-2">
                  {s.title}
                </h4>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  {s.description}
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-border-structural/60 font-mono text-[11px] text-secondary flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-verification-mint"></span>
                {s.tag}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
