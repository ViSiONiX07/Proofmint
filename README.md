# Proofmint

> **Nothing ships unproven.**

Proofmint is an AI-powered brand verification workspace that validates marketing copy against approved brand guidelines and verified claim evidence prior to publication. It intercepts unsubstantiated superlatives, computes minimal surgical repairs, and enforces human-governed clearance decisions.

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
| **Interactive Verification Studio** | ✅ Complete | Live telemetry, clickable claim spans, and dynamic inspector |
| **Evidence-Locked Findings** | ✅ Complete (Sample Mode) | Displays exact document anchors (`Core_SLA_Master_Annex_2024.pdf#p12`) |
| **Intent-Preserving Repair** | ✅ Complete (Sample Mode) | Computes and displays minimal semantic token delta |
| **Ambiguity Radar** | ✅ Complete (Sample Mode) | Multi-jurisdictional compliance grid (FTC, EU AI Act, UK CMA) |
| **Human Clearance Terminal** | ✅ Complete (UI/Interactive) | Accept Repair, Legal Escalate, Human Override with audit receipt |
| **Guidelines & Facts Management** | ✅ Complete (UI/Interactive) | Document ingestion simulator, candidate rules, and CSV facts preview |
| **Scroll-Triggered CSS Animations** | ✅ Complete | GPU-accelerated CSS reveals and Intersection Observer triggers; zero Framer Motion |
| **Responsive Layouts** | ✅ Complete | Tested for 1440×900 (Desktop), 1280×800 (Laptop), 390×844 (Mobile) |
| **PDF Text Extraction** | ✅ Foundation Complete | Bounded PyMuPDF ingestion with page-level text and source spans; guideline metadata is persisted, with no OCR or PDF binary storage |
| **PostgreSQL Persistence Foundation** | ✅ Schema Ready | SQLAlchemy models, lazy session management, and Alembic baseline; configure PostgreSQL before applying migrations |
| **Production LLM Engine** | ⏳ Later Phase | LLM provider agnostic interface planned for subsequent phase |

---

## 5. Security & Governance

- Zero-retention cloud architecture designed for confidential enterprise copy.
- Ephemeral in-memory verification.
- Human review is strictly mandatory before clearance.

For local PostgreSQL configuration and migration commands, see [services/api/README.md](services/api/README.md).
