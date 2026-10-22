"use client";

import React, { useState } from "react";
import { Navbar } from "@/components/Navbar";
import { Hero } from "@/components/Hero";
import { VerificationStudio } from "@/components/VerificationStudio";
import { WorkspaceStudio } from "@/components/WorkspaceStudio";
import { AssetGapMatrix } from "@/components/AssetGapMatrix";
import { Differentiators } from "@/components/Differentiators";
import { PipelineWorkflow } from "@/components/PipelineWorkflow";
import { GovernanceArchitecture } from "@/components/GovernanceArchitecture";
import { InteractionSpecsDrawer } from "@/components/InteractionSpecsDrawer";
import { Footer } from "@/components/Footer";
import { useScrollReveal } from "@/hooks/useScrollReveal";

export default function Home() {
  const [activeView, setActiveView] = useState<"landing" | "workspace">("landing");

  // Activate scroll-reveal Intersection Observer
  useScrollReveal();

  const handleOpenWorkspace = () => {
    setActiveView("workspace");
    const el = document.getElementById("workspace-hub");
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-graphite-base text-on-surface">
      <Navbar
        onOpenWorkspace={handleOpenWorkspace}
        activeView={activeView}
        setActiveView={setActiveView}
      />

      <main className="flex-1 w-full">
        {/* Hero Section */}
        <Hero onOpenWorkspace={handleOpenWorkspace} />

        {/* Live In-Flight Verification Studio */}
        <VerificationStudio />

        {/* Frontify-Inspired Brand Workspace Hub */}
        <WorkspaceStudio />

        {/* The Architectural Asset Gap Matrix */}
        <AssetGapMatrix />

        {/* Three Core Differentiators */}
        <Differentiators />

        {/* 5-Step Continuous Assurance Pipeline */}
        <PipelineWorkflow />

        {/* Institutional Trust & Sovereign Governance */}
        <GovernanceArchitecture />

        {/* Engineering Motion & Scroll Specification Panel */}
        <InteractionSpecsDrawer />
      </main>

      <Footer />
    </div>
  );
}
