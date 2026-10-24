"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { BrandLogo } from "./BrandLogo";

const TOUR_STEPS = [
  {
    title: "Overview & Telemetry",
    description: "Start with the overview dashboard: it introduces Proofmint’s verification workspace and the signals teams use to understand review activity.",
    href: "/#overview",
    linkLabel: "View the overview",
  },
  {
    title: "Brand Space",
    description: "A brand space brings guidelines, approved facts, terminology, and candidate rules together. Imported records remain pending until a reviewer approves them.",
    href: "/#workspace-hub",
    linkLabel: "Explore the brand space",
  },
  {
    title: "Differentiators",
    description: "Proofmint focuses on evidence-linked findings, intent-preserving copy repair, and an ambiguity radar for rules that need human attention.",
    href: "/differentiators",
    linkLabel: "See the differentiators",
  },
  {
    title: "Pipeline",
    description: "Follow the verification path from source materials and rule review through copy checks, findings, and a human clearance decision.",
    href: "/pipeline",
    linkLabel: "View the pipeline",
  },
  {
    title: "Sovereign Trust",
    description: "Audit runs and review decisions are persisted by the API, and clearance remains an explicit human decision. This demo has no connected authentication or production identity controls; workspace separation uses session-scoped identifiers.",
    href: "/trust",
    linkLabel: "Review governance and trust",
  },
  {
    title: "Brand Workspace",
    description: "Open the workspace to organize brand materials and review the current workspace experience. This demo workspace includes illustrative content, so treat displayed examples as samples rather than verified company records.",
    href: "/brand-workspace",
    linkLabel: "Open Brand Workspace",
  },
  {
    title: "Launch Studio",
    description: "Run the operational workflow: upload a guideline PDF, import facts and terminology CSVs, review rules, audit marketing copy, inspect findings, and make a human clearance decision.",
    href: "/studio",
    linkLabel: "Open Launch Studio",
  },
] as const;

type View = "welcome" | "tour";

export function WelcomeModal() {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>("welcome");
  const [step, setStep] = useState(0);
  const closeRef = useRef<HTMLButtonElement>(null);
  const router = useRouter();

  useEffect(() => {
    setOpen(true);
    setView("tour");
    setStep(0);
    const restartTour = () => {
      setStep(0);
      setView("tour");
      setOpen(true);
    };
    window.addEventListener("proofmint:restart-tour", restartTour);
    return () => window.removeEventListener("proofmint:restart-tour", restartTour);
  }, []);

  useEffect(() => { if (open) closeRef.current?.focus(); }, [open]);

  const dismiss = () => {
    try { localStorage.setItem("proofmint_visited", "true"); } catch {}
    setOpen(false);
  };
  const startTour = () => {
    setStep(0);
    setView("tour");
  };

  if (!open) return null;
  const currentStep = TOUR_STEPS[step];

  return <div role="dialog" aria-modal="true" aria-labelledby="welcome-title" className="fixed inset-0 z-[100] grid place-items-center bg-black/75 p-6 backdrop-blur-sm" onKeyDown={(event) => { if (event.key === "Escape") dismiss(); }}>
    <div className="relative w-full max-w-lg border border-border-structural bg-charcoal-elevated p-8 shadow-2xl sm:p-12">
      <button ref={closeRef} type="button" onClick={dismiss} aria-label="Close welcome screen" className="absolute right-5 top-5 rounded p-1 text-secondary hover:text-off-white focus:outline-none focus-visible:ring-2 focus-visible:ring-verification-mint"><X /></button>
      <BrandLogo size="md" className="mb-8" />
      {view === "welcome" ? <>
        <h2 id="welcome-title" className="text-3xl font-semibold text-off-white">Welcome to Proofmint</h2>
        <p className="mt-3 leading-relaxed text-secondary">See how Proofmint checks brand guidelines and evidence before marketing content goes live.</p>
        <div className="mt-8 flex flex-col gap-3">
          <button type="button" onClick={startTour} className="rounded bg-verification-mint px-6 py-3 text-center font-semibold text-graphite-base">Take the guided tour</button>
          <button type="button" onClick={() => { dismiss(); router.push("/"); }} className="rounded border border-border-structural px-6 py-3 font-medium text-off-white hover:border-verification-mint hover:text-verification-mint">Explore the website</button>
          <Link href="/brand-workspace" onClick={dismiss} className="py-2 text-center text-sm text-secondary hover:text-off-white">Or open brand workspace directly</Link>
        </div>
      </> : <>
        <p className="font-mono text-xs uppercase tracking-widest text-verification-mint">Step {step + 1} of {TOUR_STEPS.length}</p>
        <h2 id="welcome-title" className="mt-3 text-3xl font-semibold text-off-white">{currentStep.title}</h2>
        <p className="mt-3 leading-relaxed text-secondary">{currentStep.description}</p>
        <Link href={currentStep.href} onClick={() => setOpen(false)} className="mt-5 inline-flex text-sm font-semibold text-verification-mint underline underline-offset-4 hover:text-off-white">{currentStep.linkLabel}</Link>
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-border-structural pt-5">
          <button type="button" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0} className="rounded border border-border-structural px-4 py-2 text-sm text-off-white disabled:opacity-40">Previous</button>
          <button type="button" onClick={dismiss} className="px-3 py-2 text-sm text-secondary hover:text-off-white">Skip Tour</button>
          {step < TOUR_STEPS.length - 1
            ? <button type="button" onClick={() => setStep((current) => Math.min(TOUR_STEPS.length - 1, current + 1))} className="rounded bg-verification-mint px-5 py-2 text-sm font-semibold text-graphite-base">Next</button>
            : <button type="button" onClick={dismiss} className="rounded bg-verification-mint px-5 py-2 text-sm font-semibold text-graphite-base">Finish</button>}
        </div>
      </>}
    </div>
  </div>;
}
