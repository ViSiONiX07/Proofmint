# Proofmint

> **Nothing ships unproven.**

Proofmint is a brand verification workspace designed to help teams check marketing content against approved brand guidelines, preferred terminology, and approved factual statements before publication.

The Round 2 implementation provides a deployed Next.js frontend, a FastAPI backend, PostgreSQL persistence, guideline PDF ingestion, terminology and approved-facts imports, configured text auditing, review decisions, and a clearance gate.

**Live Demo:** [https://proofmint-rust.vercel.app/](https://proofmint-rust.vercel.app/)

---

## 1. Project Links

| Resource | Link |
|---|---|
| Live application | [Proofmint Web App](https://proofmint-rust.vercel.app/) |
| Backend API root | [https://proofmint-q9ss.onrender.com/](https://proofmint-q9ss.onrender.com/) |
| Interactive API documentation (Swagger UI) | [https://proofmint-q9ss.onrender.com/docs](https://proofmint-q9ss.onrender.com/docs) |
| API health check | [https://proofmint-q9ss.onrender.com/api/v1/health](https://proofmint-q9ss.onrender.com/api/v1/health) |
| OpenAPI specification (JSON) | [https://proofmint-q9ss.onrender.com/openapi.json](https://proofmint-q9ss.onrender.com/openapi.json) |
| Alternative API documentation (ReDoc) | [https://proofmint-q9ss.onrender.com/redoc](https://proofmint-q9ss.onrender.com/redoc) |
| Source code | [GitHub Repository](https://github.com/ViSiONiX07/Proofmint) |
| Sample data used for testing | `place_holder` |

### Deployment Architecture

- **Frontend:** Next.js and React, hosted on Vercel.
- **Backend:** Python and FastAPI, hosted on Render.
- **Database:** PostgreSQL, hosted on Neon.
- **Database access:** SQLAlchemy with Psycopg 3.
- **Schema migrations:** Alembic.

The frontend communicates with the backend through the configured `NEXT_PUBLIC_API_URL`. PostgreSQL stores supported workflow records, imports, audit results, review decisions, and clearance records.

---

## 2. Monorepo Structure

```text
proofmint/
├── apps/
│   └── web/                       # Next.js frontend
│       ├── app/                   # Application routes and pages
│       ├── components/            # Reusable UI components
│       ├── lib/                   # Frontend utilities and workspace logic
│       ├── public/                # Static assets
│       └── package.json
│
├── services/
│   └── api/                       # FastAPI backend
│       ├── app/
│       │   ├── api/
│       │   │   ├── health.py
│       │   │   ├── guidelines.py
│       │   │   ├── imports.py
│       │   │   ├── candidate_rules.py
│       │   │   ├── import_review.py
│       │   │   ├── audits.py
│       │   │   └── workspaces.py
│       │   ├── core/              # Settings, database and upload limits
│       │   ├── models/            # SQLAlchemy database models
│       │   ├── schemas/           # API request and response schemas
│       │   ├── services/
│       │   │   └── audit_engine.py
│       │   └── main.py            # ASGI application entry point
│       ├── alembic/               # Versioned database migrations
│       ├── tests/                 # Backend tests
│       ├── requirements.txt
│       ├── alembic.ini
│       └── README.md
│
├── docs/
│   └── design/                    # Design system and design assets
│
├── .env.example                   # Environment-variable template
├── .gitignore
├── AGENTS.md                      # AI coding-agent instructions
├── THIRD_PARTY.md                 # Third-party dependency inventory
└── README.md
```

*This is a representative overview of the main project paths; consult the repository for the complete file tree.*

---

## 3. Prerequisites

- **Node.js:** 18.18 or newer.
- **npm:** 9 or newer.
- **Python:** 3.11 or newer.
- **Git:** 2.30 or newer.
- **PostgreSQL:** A local or hosted database for persistence-dependent backend operations.

The public deployment is available without a local database configuration. A local development environment requires its own environment variables and PostgreSQL configuration for ingestion, imports, audits, and other persistence-dependent operations.

---

## 4. Quick Start

### A. Frontend Setup

From the repository root:

```bash
cd apps/web
npm install
```

Create an `apps/web/.env.local` file containing:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Production frontend:** [https://proofmint-rust.vercel.app/](https://proofmint-rust.vercel.app/)

To verify the frontend:

```bash
npm run build
npm run lint
```

To run the workspace-session test:

```bash
npm run test:workspace
```

### B. Backend Setup

From the repository root:

```bash
cd services/api
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Create a local backend environment file from the safe template:

```powershell
Copy-Item ..\..\.env.example .env
```

Edit `services/api/.env` and configure either `DATABASE_URL` or the supported PostgreSQL connection variables. Use your own local or hosted PostgreSQL credentials; never commit secrets to Git.

Apply database migrations:

```bash
alembic upgrade head
```

Start the development API:

```bash
uvicorn app.main:app --reload --port 8000
```

Local API links:

- API root: [http://localhost:8000/](http://localhost:8000/)
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- OpenAPI specification: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

Run backend tests from `services/api/`:

```bash
pytest
```

**Note:** The local API must be configured with the appropriate CORS origins and database settings. The production database credentials must not be copied into frontend environment files.

---

## 5. Production API Reference

All versioned business endpoints use the `/api/v1` prefix.

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | API root and service information |
| `/api/v1/health` | GET | Health-check response |
| `/api/v1/guidelines/ingest` | POST | Extract text from guideline PDFs and persist supported document metadata and candidate rules |
| `/api/v1/rules/pending` | GET | List pending candidate rules |
| `/api/v1/rules/{candidate_id}/approve` | POST | Approve a pending candidate rule |
| `/api/v1/rules/{candidate_id}/reject` | POST | Reject a pending candidate rule |
| `/api/v1/facts/import` | POST | Import approved-facts CSV records |
| `/api/v1/terms/import` | POST | Import terminology CSV records |
| `/api/v1/facts` | GET | List imported facts for review |
| `/api/v1/terms` | GET | List imported terminology for review |
| `/api/v1/audits` | POST | Run a content audit and persist its results |
| `/api/v1/audits/{audit_id}` | GET | Retrieve a persisted audit |
| `/api/v1/audits/{audit_id}/findings/{finding_id}/decisions` | POST | Record a supported finding decision |
| `/api/v1/audits/{audit_id}/clearance` | POST | Record a clearance decision |
| `/api/v1/workspaces/{workspace_id}` | GET | Retrieve workspace information |

Use the live [Swagger UI](https://proofmint-q9ss.onrender.com/docs) for request schemas, required fields, response formats, and additional endpoints.

Some operations require a valid `workspace_id` and other identifiers returned by preceding workflow steps. Opening an endpoint directly in a browser does not execute a complete workflow.

---

## 6. Current Implementation Status

| Feature / Area | Status | Current implementation |
|---|---|---|
| **Deployed frontend** | ✅ Available | Next.js application hosted on Vercel. |
| **FastAPI backend** | ✅ Available | Deployed API with versioned routes and interactive documentation. |
| **PostgreSQL persistence** | ✅ Implemented | SQLAlchemy models, database sessions, and Alembic migrations. |
| **Guideline PDF ingestion** | ✅ Implemented | Bounded PDF text extraction using PyMuPDF, with persisted document metadata, candidate rules, and source information. PDF binaries and the complete extracted document text are not stored. |
| **Candidate-rule review** | ✅ Implemented | Candidate rules can be listed and explicitly approved or rejected. Reviewer identity and full reviewer audit history are not currently stored by this schema. |
| **Terminology CSV imports** | ✅ Implemented | Validates imported terminology, supports preferred forms, reports invalid rows, and skips applicable duplicates. |
| **Approved-facts CSV imports** | ✅ Implemented | Validates claim records, persists imported rows, and reports row-level errors. |
| **Imported-row review** | ✅ Implemented | Imported facts and terminology remain pending until explicitly approved or rejected. |
| **Configured text audits** | ✅ Implemented, limited scope | Uses deterministic literal checks against approved rules, preferred terminology, and imported approved-fact statements. |
| **Finding and decision persistence** | ✅ Implemented | Stores supported findings, their review states, and finding decisions. |
| **Workspace-scoped workflow** | ✅ Implemented | PDF ingestion creates a session workspace; the frontend retains its ID in browser session storage. |
| **Duplicate-import handling** | ✅ Implemented | Identical uploaded files and duplicate rows within an import are skipped under the supported deduplication rules. |
| **Clearance gate** | ✅ Implemented | Clearance is blocked while actionable findings remain pending or flagged. Supported decisions are persisted. |
| **Evidence-Locked Findings** | 🟡 Partial | Findings can include matched text spans and source-rule information. A comprehensive independent verifier for semantic evidence validity is not implemented. |
| **Intent-Preserving Repair** | 🟡 Partial | Configured preferred terminology can provide a correction. General semantic, model-generated minimal repairs are not implemented as a production LLM capability. |
| **Ambiguity Radar** | 🟡 Partial / planned | The complete analytics workflow for recurring reviewer disagreements and unclear rules remains future work. Visual demonstration elements should not be interpreted as proof of a complete analytics engine. |
| **Production LLM engine** | ⏳ Planned | A production provider-backed language-model analysis and repair engine is not currently implemented. |
| **Authentication and tenant authorization** | ⏳ Not implemented | Workspace IDs provide logical session separation, not authenticated-user or tenant-level access control. |

### Audit Behaviour and Limitations

The current audit engine is deliberately conservative and deterministic.

It supports:

- Matching explicitly prohibited or restricted quoted phrases in approved candidate rules.
- Checking configured terminology against its preferred form.
- Detecting exact matches to approved factual statements as informational evidence matches.
- Persisting finding statuses, supported review decisions, and clearance records.

An exact approved-statement match does **not** establish that a claim is true in every context, and a missing match does not automatically prove that a claim is false. The current engine does not perform comprehensive semantic, legal, or contextual compliance analysis.

The application therefore represents a working Round 2 implementation of the core verification workflow—not a fully autonomous AI-based brand verification system.

---

## 7. Workspace and Data Persistence

Proofmint uses workspace IDs to scope supported documents, imports, audits, review decisions, and clearance operations.

The implemented lifecycle is:

1. Upload a guideline PDF successfully to begin a new workspace.
2. Retain the active workspace ID in browser session storage.
3. Import terminology and approved-facts records into that workspace.
4. Review imported records and approve or reject candidate rules.
5. Run an audit using the applicable approved records.
6. Review findings and record supported decisions.
7. Apply the clearance gate and persist the resulting decision.

Starting a new session clears the active session state; it does not delete historical database records.

PostgreSQL persists the supported application records. Audit records store a content hash and character count rather than the complete submitted marketing copy. Finding records may retain matched phrases, explanations, source excerpts, and other finding metadata.

These storage behaviours are not equivalent to a zero-retention architecture: the database intentionally persists certain records needed for workflow continuity and review.

---

## 8. Security and Governance

Proofmint keeps final clearance decisions explicit, but the current implementation has important security boundaries.

- **Secrets:** Store `DATABASE_URL` and database credentials in Render environment settings or the linked environment group. Never commit credentials to Git or expose them through `NEXT_PUBLIC_` variables.
- **Frontend configuration:** `NEXT_PUBLIC_API_URL` identifies the public backend URL; it must not contain secrets.
- **CORS:** Configure `BACKEND_CORS_ORIGINS` for the deployed Vercel origin and the local development origins that are actually needed.
- **Database persistence:** Database records and supported review decisions persist across requests and sessions.
- **Workspace isolation:** Workspace IDs provide logical isolation for the supported workflow. They are not a substitute for authentication or authorization.
- **Human review:** Clearance is a separate decision from generating findings. Actionable findings must be resolved or dismissed before clearance can proceed.
- **Evidence integrity:** The current literal-match engine has documented limitations. Findings should not be represented as independently verified semantic or legal conclusions.
- **Confidential data:** Because authentication and tenant-level authorization are not implemented, do not use the current deployment for confidential or sensitive production brand content.

For local database setup and migration instructions, see [services/api/README.md](services/api/README.md).

---

## 9. Round 2 Achievements

Round 2 moved Proofmint from a planned product and interface concept to a deployed, database-backed application.

The main engineering outcomes include:

1. A deployed Next.js frontend and FastAPI backend.
2. PostgreSQL persistence with versioned schema migrations.
3. Guideline PDF ingestion and candidate-rule records with source information.
4. Validated terminology and approved-facts CSV imports.
5. Explicit review states for candidate rules and imported records.
6. Workspace-scoped workflow operations and duplicate-import handling.
7. Persistent audits, finding decisions, and clearance gating.
8. Public API documentation for integration and testing.

These capabilities form the foundation for completing stronger evidence verification, intent-preserving repair, and evaluation-driven guideline governance.

---

## 10. Round 3 Priorities

The next round will focus on the following three improvements.

### 1. Strengthen Evidence-Locked Findings

Improve source and rule traceability, validate the relationship between a finding and its supporting evidence, and handle unsupported or uncertain claims conservatively. Test invalid references and evidence gaps.

### 2. Complete Intent-Preserving Repair and Human Review

Improve minimal-edit suggestions, preserve the creator's intent, make review decisions and their reasons clearer, and retain explicit human control over any correction and clearance.

### 3. Improve Reliability, Evaluation, and Ambiguity Radar

Expand the labelled evaluation set, test run-to-run consistency and false-positive behaviour, improve error handling and regression coverage, and identify recurring guideline ambiguity from review outcomes.

These are planned improvements, not claims of completed Round 2 functionality. Any reported accuracy, reliability, or time-saving result must be based on measured test evidence.

---

## 11. Development Principles

Proofmint follows these principles throughout implementation:

- **Traceability:** Findings should identify the content and approved rule information behind them.
- **Conservative verification:** Literal matches must not be misrepresented as comprehensive semantic analysis.
- **Human accountability:** Review and clearance remain explicit decisions.
- **Persistent workflow:** Supported records and decisions are stored so the application can retrieve them across requests.
- **Incremental development:** New capabilities should be added only when their behaviour can be tested and their limitations explained.
- **Accurate reporting:** Implemented, partially implemented, planned, and future capabilities must remain distinct.

---

## 12. Third-Party Dependencies and Acknowledgements

Proofmint uses open-source frameworks and libraries for its frontend, API, database access, PDF processing, and testing.

See [`THIRD_PARTY.md`](THIRD_PARTY.md) for the project's third-party dependency inventory.

The project also maintains design-system documentation and visual assets under [`docs/design/`](docs/design/).

---

**Proofmint — Nothing ships unproven.**
