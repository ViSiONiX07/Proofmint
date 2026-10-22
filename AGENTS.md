# Proofmint — Agent & Engineering Guidelines

## 1. Project Context & Purpose
**Proofmint** is an AI-powered brand verification workspace that checks marketing content against approved brand guidelines and verified claim evidence before publication.
- **Tagline**: *Nothing ships unproven.*
- **Core Mission**: Prevent unproven brand claims, tone drift, and regulatory exposure before content ships.

### FutureStack Round 2 Differentiators
1. **Evidence-Locked Findings**: Every finding references verified guideline evidence and a supporting source span (e.g. `Master_SLA.pdf#p12`). Findings without valid evidence are never presented as verified.
2. **Intent-Preserving Repair**: Compute minimal token perturbations that cure guideline non-compliance while preserving persuasive punch and cadence.
3. **Ambiguity Radar**: Surface ambiguous rules, dismissed warnings, and jurisdictional traps (FTC, EU AI Act, UK CMA).

---

## 2. Fixed Technology Stack
- **Frontend**: Next.js (App Router), React, TypeScript, Tailwind CSS.
- **Backend Foundation**: Python 3.13+, FastAPI, Pydantic v2.
- **Database**: PostgreSQL (configuration prepared; live database not required for frontend rendering).
- **Animation Policy**: Native CSS transitions and Intersection Observer API for scroll-driven animations.
  - **CRITICAL PROHIBITION**: Do NOT use Framer, Framer Motion, or Framer website builders.

---

## 3. Visual Sources of Truth & Design Philosophy
- **Primary Visual Reference**: The Stitch designs retrieved from projects:
  - `projects/2233544058637253341` (Proofmint Interactive Brand Verification Website)
  - `projects/4103046008557339500` (Proofmint Enterprise Brand System)
  - Exports preserved in `docs/design/`.
- **UX Inspiration**: Frontify (clear brand architecture, evidence grounding, calm authority).
- **Palette**: Graphite base (`#171A1D`), Charcoal elevated (`#242A2D`), Verification Mint (`#A7F3D0`), Warning Copper (`#F2A65A`), Off-white (`#F5F5F0`), Hairline borders (`rgba(245, 245, 240, 0.08)`).

---

## 4. Directory Structure Responsibilities
- `apps/web/`: Next.js web application, UI components, interactive verification studio, layout, styles.
- `services/api/`: FastAPI service, Pydantic schemas, health checks, route foundation.
- `docs/`: Design system references, architecture specifications, round-2 documentation.
- `samples/`: Verified sample guidelines, approved facts CSV, marketing copy payloads.
- `tests/`: End-to-end and evaluation tests.

---

## 5. Scope Boundary (Initial Stage vs Later Phase)
In this initial stage:
- **Included**: Monorepo scaffolding, Stitch design retrieval, complete Next.js frontend implementation, CSS/Intersection Observer animations, responsive layouts, realistic sample states, FastAPI foundation & health checks.
- **Deferred to Codex Phase**: Real PyMuPDF PDF parsing, live RapidFuzz / LLM rule extraction, live vector/SQL full-text search, live production database persistence.
- **Honesty Rule**: Clearly disclose simulated or sample data in the UI. Never fake backend results or pretend a real audit ran when displaying sample flows.

---

## 6. Git & Version Control Discipline
- Local Git repository is initialized.
- **STRICT RULE**: Do NOT create a GitHub repository, configure remotes, push code, or create Git commits without explicit user approval.
