# Proofmint Design System Reference

## 1. Overview & Visual Philosophy
Proofmint is an AI-powered brand verification workspace designed to ensure that **nothing ships unproven**. 
The visual identity and design system are drawn directly from the verified Stitch projects:
- **Project 2233544058637253341**: *Proofmint Interactive Brand Verification Website* (Desktop & Mobile)
- **Project 4103046008557339500**: *Proofmint Enterprise Brand System*

The design balances **Frontify-inspired brand governance discipline** with the surgical precision of an enterprise verification terminal. It eliminates decorative gimmicks, heavy glowing halos, and generic dashboard cards in favor of structured architectural grids, hairline borders, and luminous status signals.

---

## 2. Core Color Palette & Design Tokens

| Token | Hex / Value | Usage & Meaning |
|---|---|---|
| `graphite-base` / `background` | `#111417` / `#171A1D` | Deep substrate canvas; zero chromatic glare |
| `charcoal-elevated` / `surface` | `#242A2D` | Primary cards, panels, and inspection surfaces |
| `charcoal-subtle` | `#2F363A` | Hover states, secondary action buttons, elevated trays |
| `surface-container-lowest` | `#0B0F11` | Deep well areas, code blocks, diff containers |
| `surface-container-high` | `#272A2D` | Window chrome, headers, partition accents |
| `verification-mint` / `primary` | `#A7F3D0` | Cryptographic lock, verified findings, primary action |
| `verification-mint-dim` | `rgba(167, 243, 208, 0.12)` | Subtle highlight backgrounds for verified spans |
| `warning-copper` / `tertiary` | `#F2A65A` | Regulatory alerts, unverified claims, drift detection |
| `warning-copper-dim` | `rgba(242, 166, 90, 0.12)` | Intercepted claim background and alert badges |
| `off-white` / `text-primary` | `#F5F5F0` | High-contrast editorial typography and hero headings |
| `secondary` / `text-muted` | `#C1C7CB` / `#89938C` | Explanations, metadata, citations, secondary labels |
| `border-structural` / `hairline` | `rgba(245, 245, 240, 0.08)` | 1px hairline partitioning across panels & cards |
| `border-focus` | `rgba(167, 243, 208, 0.40)` | Interactive focus ring and verified card states |

---

## 3. Typographic Scale & Font Families

The typographic hierarchy uses a tripartite structure:
1. **Headlines (`Geist` / `Inter` / `sans-serif`)**:
   - `display`: 56px / 64px, weight 600, letterSpacing -0.03em
   - `headline-lg`: 40px / 48px, weight 600, letterSpacing -0.025em
   - `headline-md`: 28px / 36px, weight 500, letterSpacing -0.02em
   - `headline-sm`: 20px / 28px, weight 500, letterSpacing -0.015em
2. **Prose & Work Surface (`Plus Jakarta Sans` / `system-ui`)**:
   - `body-lg`: 18px / 28px, weight 400
   - `body-md`: 15px / 24px, weight 400
   - `body-sm`: 13px / 20px, weight 400
3. **Audit Telemetry & Code (`JetBrains Mono` / monospace)**:
   - `label-lg`: 14px / 20px, weight 600
   - `label-md`: 12px / 16px, weight 500
   - `label-sm`: 11px / 14px, weight 500
   - `code-tabular`: Strict tabular figures (`tnum`) for rule IDs, SHA-256 hashes, timestamps, token spans.

---

## 4. Frontify-Inspired Brand Management Principles
Proofmint adheres to Frontify's architectural clarity:
- **Guideline Ledger:** Guidelines are first-class assets, partitioned into approved rules and source PDF evidence citations.
- **Source Verification:** Every reported finding links to a specific document span (e.g. `Master_SLA.pdf#p12`).
- **Human Authority:** The system never publishes or modifies copy autonomously. Human sign-off is gated and records an immutable cryptographic audit receipt.
- **Intent-Preserving Repair:** Suggested edits make the minimum token change required to resolve guideline non-compliance without altering tone or cadence.

---

## 5. Animation & Motion Standards
- **Zero Framer / Zero Framer Motion**: All animations are implemented with native CSS transforms and Intersection Observer triggers.
- **Scroll Reveals**: Progressive reveal of cards (`opacity: 0 -> 1`, `translateY(12px) -> 0`) over 300ms using `cubic-bezier(0.16, 1, 0.3, 1)`.
- **Micro-interactions**:
  - Button hover: subtle brightness lift and `box-shadow: 0 0 16px rgba(167, 243, 208, 0.25)`.
  - Claim token triggers: instantaneous telemetry swap with smooth crossfade.
  - Reduced Motion: complete bypass of transitions when `@media (prefers-reduced-motion: reduce)` is active.
