# Proofmint

> **Nothing ships unproven.**

Proofmint is a brand verification workspace that compares marketing copy with human-approved guideline rules, facts, and terminology before publication. Its current audit checks are deterministic and literal; findings show how their evidence was checked, and human review controls repair and clearance.

---

## 1. Monorepo Structure

```text
proofmint/
├── apps/
│   └── web/                   # Next.js 14+ frontend with Tailwind CSS
├── services/
│   └── api/                   # FastAPI backend foundation
│       ├── app/
│       │   ├── api/           # Health and REST routes
│       │   ├── core/          # Pydantic Settings & environment config
│       │   ├── models/        # SQLAlchemy PostgreSQL models
│       │   ├── schemas/       # Findings, Evidence, and Decision schemas
│       │   ├── services/      # Service layer
│       │   └── main.py        # ASGI application entrypoint
│       ├── alembic/           # Versioned PostgreSQL migrations
│       ├── tests/             # Pytest suite
│       └── README.md          # PostgreSQL setup and migration commands
├── docs/
│   ├── architecture/          # Architecture blueprints
│   ├── design/                # Retrieved Stitch designs, SVG logos, and DESIGN_SYSTEM.md
│   └── round-2/               # FutureStack Round 2 submission notes
├── samples/
│   ├── brand-guidelines/      # Sample brand guidelines
│   ├── approved-facts/        # Sample facts CSV
│   └── marketing-content/     # Sample marketing campaign copy
├── tests/
│   └── evaluation/            # End-to-end evaluation tests
├── .env.example               # Documented environment template
├── .gitignore                 # Exclusions for node_modules, .venv, etc.
├── AGENTS.md                  # Instructions for AI pair programming agents
├── README.md                  # Project overview and setup guide
└── THIRD_PARTY.md             # Third-party dependency inventory
```

---

## 2. Prerequisites

- **Node.js**: v18.18+ (tested with v24.12.0)
- **npm**: v9+ (tested with v11.6.2)
- **Python**: 3.11+ (tested with 3.13.5)
- **Git**: 2.30+

---

## 3. Quick Start

### A. Frontend Setup & Development

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

To verify the production build:
```bash
npm run build
npm run lint
```

### B. Backend Setup & Development

```bash
cd services/api
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

To run the backend tests:
```bash
pytest
```

---

## 4. Current Implementation Status

| Feature / Area | Status | Notes |
|---|---|---|
| **Stitch Design System Integration** | ✅ Complete | Retrieved from Stitch projects `2233544058637253341` and `4103046008557339500`; assets in `docs/design/` |
| **Interactive Verification Studio** | ✅ Implemented | Workspace-scoped PDF metadata, CSV evidence, audit review, repair preview, and clearance flows |
| **Evidence-Locked Findings** | ✅ Implemented with explicit limits | Independent checks against the exact retained PDF version and cited page span; missing or inaccessible sources remain uncertain |
| **Intent-Preserving Repair** | ⚠️ Deterministic subset | Minimal verified terminology substitutions with editable before/after preview; no semantic cadence model |
| **Ambiguity Radar** | ✅ Implemented | Workspace-level decision aggregates, recorded reasons, a minimum-evidence threshold, and a disclosed score |
| **Human Clearance** | ✅ Implemented | Decisions are persisted; pending or flagged actionable findings block clearance |
| **Guidelines & Facts Management** | ✅ Implemented | Bounded PDF text extraction, pending candidate rules, CSV imports, and human review |
| **Scroll-Triggered CSS Animations** | ✅ Complete | GPU-accelerated CSS reveals and Intersection Observer triggers; zero Framer Motion |
| **Responsive Layouts** | ✅ Complete | Tested for 1440×900 (Desktop), 1280×800 (Laptop), 390×844 (Mobile) |
| **PDF Text Extraction** | ✅ Foundation Complete | Bounded PyMuPDF ingestion with page-level text and source spans; guideline metadata is persisted, with no OCR or PDF binary storage |
| **PostgreSQL Persistence** | ✅ Implemented | SQLAlchemy models, lazy session management, workspace scoping, and Alembic migrations |
| **Production LLM Engine** | ⏳ Later Phase | LLM provider agnostic interface planned for subsequent phase |

---

## 5. Security & Governance

- Submitted copy is not persisted by the audit API; hashes, matched spans, evidence excerpts, and review records are stored.
- Original PDFs are retained in a private local filesystem directory outside web assets; complete extracted page text is not retained. Deployments need durable, access-restricted storage. Missing historical PDFs remain uncertain until the identical source is recovered and rechecked.
- There is no authentication or tenant authorization in this demonstration. Workspace IDs provide logical scoping, not access control.
- Human review remains explicit before clearance; no repair is automatically applied or published.

For local PostgreSQL configuration and migration commands, see [services/api/README.md](services/api/README.md).

## 6. Round 3 submission and deployments

Round 3 implementation status, architecture, testing results, methodology, roadmap, and verified team attribution are documented in `docs/round-3/`.

- Frontend: https://proofmint-rust.vercel.app/
- Backend: https://proofmint-q9ss.onrender.com/
- Swagger: https://proofmint-q9ss.onrender.com/docs
- Health: https://proofmint-q9ss.onrender.com/api/v1/health

These links identify the existing deployment. This local Round 3 work has not been published or deployed.
