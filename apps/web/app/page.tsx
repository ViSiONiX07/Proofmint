"use client";

import React from "react";
import { Hero } from "@/components/Hero";
import { VerificationStudio } from "@/components/VerificationStudio";
import { WorkspaceStudio } from "@/components/WorkspaceStudio";
import { AssetGapMatrix } from "@/components/AssetGapMatrix";
import { Differentiators } from "@/components/Differentiators";
import { PipelineWorkflow } from "@/components/PipelineWorkflow";
import { GovernanceArchitecture } from "@/components/GovernanceArchitecture";
import { useScrollReveal } from "@/hooks/useScrollReveal";

export default function Home() {
  useScrollReveal();

  return (
    <div className="min-h-screen flex flex-col bg-graphite-base text-on-surface">
      <main className="flex-1 w-full">
        {/* Hero Section */}
        <Hero />

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

      </main>

    </div>
  );
}
