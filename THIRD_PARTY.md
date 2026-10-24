# Proofmint — Third-Party Dependencies

This document records the core third-party packages used across the Proofmint monorepo, their purpose, and licenses.

---

## 1. Frontend (`apps/web`)

| Package | Purpose | Justification |
|---|---|---|
| `next` | React application framework | Standard framework for React App Router, hybrid rendering, and routing. |
| `react` & `react-dom` | Core UI library | Declarative component architecture. |
| `typescript` | Static type checking | Robust enterprise type safety and contract definition. |
| `tailwindcss` | Utility-first CSS | High-precision styling matching the Stitch design tokens without runtime overhead. |
| `postcss` & `autoprefixer` | CSS toolchain | Vendor prefixing and modern CSS compatibility. |
| `clsx` & `tailwind-merge` | Class name utility | Clean conditional class name joining for reusable components. |

*Note: Framer and Framer Motion are strictly excluded in accordance with the project specification. All animations utilize native CSS transforms and Intersection Observer.*

---

## 2. Backend (`services/api`)

| Package | Purpose | Justification |
|---|---|---|
| `fastapi` | Modern asynchronous web framework | High-performance Python REST API with automatic OpenAPI documentation. |
| `pydantic` | Data validation and serialization | Runtime schema enforcement for findings, evidence, and audit telemetry. |
| `pydantic-settings` | Environment settings management | Type-safe configuration loaded from `.env`. |
| `SQLAlchemy` | PostgreSQL ORM and session management | Typed declarative models and lazy, request-scoped sessions. |
| `alembic` | Database migrations | Versioned PostgreSQL schema changes with a checked-in baseline migration. |
| `psycopg[binary]` | PostgreSQL driver | PostgreSQL connectivity for SQLAlchemy and Alembic using Psycopg 3. |
| `uvicorn` | ASGI web server | Production-grade asynchronous server for FastAPI. |
| `httpx` | Asynchronous HTTP client | Test client for ASGI applications (`ASGITransport`). |
| `pytest` & `pytest-asyncio` | Automated testing framework | Unit and integration testing for API endpoints. |
