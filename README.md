# SmartLOTO

Industrial Lockout/Tagout (LOTO) assistance platform — OSHA 29 CFR 1910.147 compliant.

SmartLOTO automates the authoring, validation, and execution of energy-isolation procedures for industrial equipment. AI-generated procedure drafts are reviewed by a qualified HSE engineer before any deployment to field operators, enforcing a mandatory human-in-the-loop gate.

---

## Architecture

SmartLOTO is a monorepo composed of four independently deployable services.

```
LOTO_PROJECT/
├── apps/
│   ├── authoring-service/   # FastAPI — procedure authoring, LLM generation, HSE review
│   ├── field-service/       # FastAPI — runtime execution engine, vision validation
│   └── hse-dashboard/       # React/Vite/Tailwind — HSE review console
└── infra/                   # Shared infrastructure configuration
```

### Services

| Service | Stack | Responsibility |
|---|---|---|
| `authoring-service` | Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic v2 | Procedure lifecycle: creation, LLM-assisted draft generation, versioning, HSE approval workflow, audit trail |
| `field-service` | Python 3.12, FastAPI, Supabase-py | Runtime execution: intervention tracking, step-by-step validation, visual verification (YOLO-World), PDF audit report generation |
| `hse-dashboard` | React 18, Vite, Tailwind CSS, TanStack Query | HSE review console: draft review, workflow editing, approval, QR code generation, intervention monitoring |

### Infrastructure

| Component | Role |
|---|---|
| **Supabase (PostgreSQL)** | Primary data store. `authoring` schema for procedure/version/approval tables; `public` schema for field-service intervention data |
| **Supabase Storage** | Binary asset store: evidence images, operator signatures, PDF audit reports |
| **PgBouncer (transaction mode)** | Connection pooler in front of Supabase; requires `NullPool` + `statement_cache_size=0` for asyncpg compatibility |

### AI Pipeline

Procedure generation runs a two-stage pipeline inside `authoring-service`:

1. **Structured LLM extraction** — machine metadata and component descriptions are submitted to a configurable LLM provider (OpenRouter, Mistral, Groq, or self-hosted vLLM). The model returns a canonical `WorkflowDefinition` JSON document.
2. **Zero-shot visual validation** — YOLO-World performs object detection on machine photos to verify that described isolation components are physically present and correctly labeled.

All generated drafts receive a `draft_pending_review` status. A published procedure requires explicit HSE approval; no draft can be activated without it.

---

## Data Flow

```
HSE Dashboard
    │
    ├─► POST /api/v1/generate          →  LLM provider (structured extraction)
    │                                      ↓
    │                                  YOLO-World (visual verification)
    │                                      ↓
    │                                  Authoring DB (draft_pending_review)
    │
    ├─► PATCH /api/v1/procedures/{id}  →  HSE edits workflow definition
    ├─► POST  /api/v1/approvals        →  HSE approves (4-eyes rule enforced)
    └─► POST  /api/v1/procedures/{id}/publish  →  status: published

Field operator device
    │
    ├─► GET  /v1/procedures/{machine_id}/active-version   (field-service)
    ├─► POST /v1/interventions/start
    ├─► POST /v1/interventions/validate-step              (YOLO-World)
    └─► POST /v1/interventions/close                      (PDF audit report)
```

---

## Setup

### Prerequisites

- Python 3.12
- Node.js 20+
- A Supabase project with credentials

### Authoring Service

```bash
cd apps/authoring-service
cp .env.example .env          # fill in DATABASE_URL, SUPABASE_*, LLM API keys
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Key environment variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | asyncpg connection string (PgBouncer port 6543 for Supabase) |
| `OPENROUTER_API_KEY` | Default LLM provider |
| `GROQ_API_KEY` | Alternative: Groq (LLaMA 3) |
| `MISTRAL_API_KEY` | Alternative: Mistral |
| `VLLM_BASE_URL` | Alternative: self-hosted vLLM endpoint |

### Field Service

```bash
cd apps/field-service
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### HSE Dashboard

```bash
cd apps/hse-dashboard
cp .env.example .env          # set VITE_PROXY_TARGET if backend is not on localhost:8002
npm install
npm run dev                   # serves on http://localhost:5173
```

---

## API Reference

Interactive documentation is available at `/docs` on each service when running in development mode.

### Authoring Service — Key Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/generate` | Submit machine metadata; returns a `draft_pending_review` procedure |
| `GET` | `/api/v1/procedures` | List all procedures with current status |
| `GET` | `/api/v1/procedures/{id}` | Full procedure detail including version history |
| `PATCH` | `/api/v1/procedures/{id}/versions/{vid}` | Edit workflow definition of a draft version |
| `POST` | `/api/v1/procedures/{id}/approvals` | Submit HSE approval or rejection |
| `POST` | `/api/v1/procedures/{id}/publish` | Publish an approved version |
| `DELETE` | `/api/v1/procedures/{id}` | Archive (soft-delete) a procedure |
| `GET` | `/api/v1/audit` | Query the immutable audit trail |

### Field Service — Key Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/procedures/{machine_id}/active-version` | Retrieve the published procedure for a machine |
| `POST` | `/v1/interventions/start` | Begin a new intervention |
| `POST` | `/v1/interventions/validate-step` | Validate an isolation step (YOLO-World inference) |
| `POST` | `/v1/interventions/override-step` | Manual override with documented justification |
| `POST` | `/v1/interventions/close` | Close intervention and generate PDF audit report |
| `GET` | `/v1/interventions/{id}` | Full intervention log |

---

## Key Design Decisions

**Schema isolation** — `authoring-service` ORM tables live in the `authoring` PostgreSQL schema; `field-service` tables live in `public`. Both services share the same Supabase instance without naming conflicts.

**Human-in-the-loop enforcement** — The state machine (`draft_pending_review → approved → published`) is enforced at the service layer. A version cannot transition to `published` without a prior `approved` record from a reviewer who is not the original author (4-eyes rule).

**LLM provider abstraction** — Generation requests specify a `provider` field. The pipeline is provider-agnostic; swapping the LLM requires only a different API key and model identifier, not a code change.

**Immutable audit trail** — All state transitions emit append-only audit events. Approved and published versions are immutable; edits require creating a new draft version.

**QR codes** — Each published procedure is associated with a QR code encoding the `machine_id`. Field operators scan the code to retrieve the active procedure version from the field service without manual lookup.

---

## Compliance

SmartLOTO is designed to support compliance with **OSHA 29 CFR 1910.147** (The Control of Hazardous Energy). The audit trail, 4-eyes approval rule, version history, and immutable intervention logs are intended to satisfy documentation requirements for energy-isolation programs. This software does not constitute legal compliance advice; consult your safety officer.

---

## License

Proprietary. All rights reserved.
