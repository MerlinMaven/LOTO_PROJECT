# SmartLOTO — Architecture Overview

## Two-Service Boundary

SmartLOTO is split into two distinct services with **different audiences, data models, and deployment lifecycles**.  
They share the same Supabase database but must never be merged into one process.

```
┌─────────────────────────────────┐         ┌──────────────────────────────────────┐
│       FIELD SERVICE             │         │          AUTHORING SERVICE            │
│   uvicorn backend:app           │         │   uvicorn backend/app/main:app        │
│                                 │         │                                       │
│  Audience: AR operators         │         │  Audience: HSE engineers             │
│  Client:   Quest 2 headset      │         │  Client:   Web dashboard             │
│  Status:   PRODUCTION           │         │  Status:   Development               │
│                                 │         │                                       │
│  Source:   backend.py           │         │  Source:   backend/app/              │
│            ↕ (thin launcher)    │         │            ├── api/                  │
│            runtime/             │         │            ├── models/               │
│            ├── config.py        │         │            ├── services/             │
│            ├── database.py      │         │            └── tests/                │
│            ├── models.py        │         │                                       │
│            ├── api/             │         │  PK type:   UUID                     │
│            │   ├── procedures   │         │  Workflow:  {phases:[{stages:[steps}]}│
│            │   └── interventions│         │                                       │
│            └── services/        │         │                                       │
│                ├── vision.py    │         │                                       │
│                ├── storage.py   │         │                                       │
│                └── pdf.py       │         │                                       │
│                                 │         │                                       │
│  PK type:   TEXT (machine_id)   │         │                                       │
│  Workflow:  {lockout:[],        │         │                                       │
│              restoration:[],    │         │                                       │
│              anchors:{}}        │         │                                       │
└─────────────────────────────────┘         └──────────────────────────────────────┘
                │                                           │
                └──────────────────┬────────────────────────┘
                                   │
                           ┌───────▼───────┐
                           │   Supabase    │
                           │  procedures   │
                           │ interventions │
                           │smartloto-asset│
                           └───────────────┘
```

---

## Frozen Unity API Contracts

The following 7 endpoints are called by `unity-app/Assets/Scripts/SmartLOTOClient.cs`.  
**Do NOT change their paths, HTTP methods, or response shapes** without recompiling the Quest app.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/procedures` | List approved procedures |
| GET | `/procedures/{machine_id}` | Load a single procedure |
| POST | `/procedures/{machine_id}/anchors` | Save calibrated AR anchors |
| POST | `/interventions/start` | Start a new LOTO intervention |
| POST | `/interventions/validate-step` | Validate a step via YOLO-World |
| POST | `/interventions/override-step` | Manual override with evidence photo |
| POST | `/interventions/close` | Close intervention + generate PDF |

---

## Field Service — Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `backend.py` | Entry-point only. Loads `.env`, imports `app` from `runtime.main`. |
| `runtime/config.py` | All environment variables and constants in one place. |
| `runtime/database.py` | Initialises Supabase client and YOLO-World model at import time. |
| `runtime/models.py` | Pydantic request/response schemas (identical to original `backend.py` models). |
| `runtime/main.py` | FastAPI app factory — CORS middleware, router registration, health check. |
| `runtime/api/procedures.py` | `GET /procedures`, `GET /procedures/{id}`, `POST /procedures/{id}/anchors`. |
| `runtime/api/interventions.py` | `POST /interventions/*` — start, validate, override, close. |
| `runtime/services/vision.py` | Base64 decode + YOLO-World zero-shot detection. |
| `runtime/services/storage.py` | Upload to Supabase Storage, return public URL. |
| `runtime/services/pdf.py` | Generate OSHA-style PDF audit report via ReportLab. |

---

## Authoring Service — High-Level Structure

The authoring service (`backend/app/`) implements the full LOTO authoring lifecycle:

- **Procedure CRUD**: create, edit, submit, approve/reject procedures
- **Intervention Runtime Engine** (Phase 5): FSM-based step execution with validation strategies
- **Validation Strategies**: `ManualConfirmation`, `VisionDetectionStub`, `InverseVisionAbsenceStub`, `SensorThresholdStub`
- **Audit Events**: full audit trail for every state transition
- **Override System**: HSE-review flagging with photo evidence

See `backend/app/` for full implementation and `backend/tests/` for 302+ unit + integration tests.

---

## Key Constraints

1. **`unity-app/` is read-only.** The XR app cannot be hot-patched. Any incompatible API change requires a full Quest app rebuild and redistribution.
2. **Two data models must not be merged.** The Field Service uses TEXT `machine_id` PKs and a flat `{lockout, restoration, anchors}` workflow schema. The Authoring Service uses UUID PKs and a hierarchical `{phases → stages → steps}` schema.
3. **No LLM calls at runtime.** All step validation happens via YOLO-World or manual confirmation. LLM assistance is reserved for the authoring-time `GENERATE` workflow.
4. **Only APPROVED procedures can start an intervention.** Both services enforce `status = "APPROVED"` on procedure fetch.
