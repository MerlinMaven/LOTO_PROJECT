# SmartLOTO

Industrial Lockout/Tagout (LOTO) assistance platform.

SmartLOTO automates the authoring, validation, and execution of energy-isolation procedures for industrial equipment. AI-generated procedure drafts are reviewed by a qualified HSE engineer before any deployment to field operators, enforcing a mandatory human-in-the-loop gate.

---

## Architecture

SmartLOTO is a monorepo composed of three services and a Unity operator client.

```
LOTO_PROJECT/
├── apps/
│   ├── authoring-service/   # FastAPI — procedure authoring, LLM generation, HSE review
│   ├── field-service/       # FastAPI — runtime execution engine, vision validation
│   └── hse-dashboard/       # React/Vite/Tailwind — HSE review console
├── unity-app/               # Unity client sources and StreamingAssets contracts
├── scripts/                 # Launchers, database maintenance, contract/API checks
├── data/                    # Shared local SQLite database and backups (gitignored)
├── docs/
│   ├── assets/branding/     # Original SmartLOTO branding images
│   └── contracts/           # SL-POC-01 Unity contract
└── infra/                   # Shared infrastructure configuration
```

### Services

| Service | Stack | Responsibility |
|---|---|---|
| `authoring-service` | Python 3.10+, FastAPI, SQLAlchemy 2 (async), Pydantic v2 | Procedure lifecycle: creation, LLM-assisted draft generation, versioning, HSE approval workflow, audit trail |
| `field-service` | Python 3.10+, FastAPI, SQLite | Runtime execution: intervention tracking, step-by-step validation, visual verification (YOLO-World), PDF audit report generation |
| `hse-dashboard` | React 18, Vite, Tailwind CSS, TanStack Query | HSE review console: draft review, workflow editing, approval, QR code generation, intervention monitoring |

### Infrastructure

| Component | Role |
|---|---|
| **SQLite (local default)** | `data/smartloto.db`, shared by authoring-service and field-service |
| **Local file storage** | Imported PDFs in `apps/authoring-service/data/documents/`; evidence, signatures and reports in `apps/field-service/storage/` |
| **Supabase / PostgreSQL** | Infrastructure definitions retained in `infra/`; the current local field-service uses SQLite |

### AI Pipeline

PDF procedure generation runs as a persistent background job inside `authoring-service`:

1. **Document analysis** — the source PDF is stored, fingerprinted and extracted with PDFium/OCR, then analyzed by the configured Groq or Gemini provider.
2. **Draft validation** — the canonical workflow and its evidence references are validated and saved for HSE review. YOLO-World runs separately in field-service for operator image checks.

All generated drafts receive a `draft_pending_review` status. A published procedure requires explicit HSE approval; no draft can be activated without it.

---

## Data Flow

```
HSE Dashboard
    │
    ├─► POST /api/v1/generation/documents → Persistent PDF analysis job
    │                                      ↓
    │                                  PDF extraction + Groq / Gemini analysis
    │                                      ↓
    │                                  Authoring DB (draft_pending_review)
    │
    ├─► PATCH /api/v1/procedures/{id}/draft → HSE edits workflow definition
    ├─► POST /api/v1/procedures/{id}/versions/{vid}/approve → HSE approval
    └─► POST /api/v1/procedures/{id}/versions/{vid}/publish → status: published

Field operator device
    │
    ├─► GET  /procedures/{machine_id}         (field-service)
    ├─► POST /interventions/start
    ├─► POST /interventions/validate-step     (YOLO-World)
    └─► POST /interventions/close             (PDF audit report)
```

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 20+

Par défaut, les deux API partagent la base SQLite locale `data/smartloto.db` et le
stockage des preuves reste local. Elles démarrent sans compte Supabase. L'analyse
réelle d'un PDF nécessite une clé Groq ou Gemini.

Le guide [LAUNCH.md](LAUNCH.md) contient les commandes PowerShell complètes,
la préparation de `.venv`, la remise à zéro et le parcours `SL-POC-01`.
Copier `.env.example` vers `.env` s'il n'existe pas encore, puis conserver
`DATABASE_URL=sqlite+aiosqlite:///data/smartloto.db` pour les deux API.
Les chemins SQLite sont relatifs à la racine du workspace, quel que soit le dossier
de lancement. Ne pas écraser un `.env` existant contenant vos clés.

### 1. Authoring Service (Génération LLM & Validation HSE)

```bash
python -m pip install -r apps/authoring-service/requirements.txt
python -m uvicorn main:app --app-dir apps/authoring-service --host 0.0.0.0 --port 8001 --reload --reload-dir apps/authoring-service/app
```

### 2. Field Service (Exécution Unity & Vision)

```bash
python -m pip install -r apps/field-service/requirements.txt
python -m uvicorn main:app --app-dir apps/field-service --host 0.0.0.0 --port 8000 --reload --reload-dir apps/field-service/app
```

### 3. HSE Dashboard (Console Web React)

```bash
npm --prefix apps/hse-dashboard ci
npm --prefix apps/hse-dashboard run dev -- --port 5173 --strictPort
```

### 4. Unity App (Client AR Meta Quest)

Ouvrir le projet Unity contenant les sources dans l'éditeur. Le composant
`SmartLOTOClient.cs` utilise `http://127.0.0.1:8000` (`field-service`) sur le PC ;
sur casque, renseigner l'IP LAN du PC. Les contrats hors ligne restent dans
`unity-app/Assets/StreamingAssets/`.

### Maintenance et scénario SL-POC-01

Depuis la racine, dans l'environnement Python activé :

```bash
python scripts/verify_contract.py       # Vérification des deux contrats statiques
# Arrêter les API et sauvegarder la base avant cette commande destructive :
python scripts/reset_db.py             # Vide la base configurée et le stockage standard
```

Après un reset, importer le PDF de `apps/authoring-service/data/reference/` dans le
dashboard, puis relire, approuver et publier la révision. Aucun seed n'est injecté
automatiquement. [LAUNCH.md](LAUNCH.md) détaille aussi l'import HTTP, l'export Unity,
`scripts/patch_sl_poc_01.py` et `scripts/test_field_api.py`.
Les lanceurs Windows sont dans `scripts/start_backend.ps1` et
`scripts/start_backend.bat`. Les originaux graphiques sont dans
`docs/assets/branding/` ; les images servies par le dashboard restent dans son
dossier `public/`. La copie initiale de la base de la racine est conservée dans
`data/backups/smartloto.root-before-cleanup.db`.

---

## API Reference

Interactive documentation is available at `/docs` on each service when running in development mode.

### Authoring Service — Key Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/generation/documents` | Upload a PDF; returns a persistent generation job (`202`) |
| `GET` | `/api/v1/generation/jobs/{job_id}` | Read generation status and resulting draft |
| `GET` | `/api/v1/procedures` | List all procedures with current status |
| `GET` | `/api/v1/procedures/{id}` | Full procedure detail including version history |
| `PATCH` | `/api/v1/procedures/{id}/draft` | Save the reviewed draft as a new revision |
| `POST` | `/api/v1/procedures/{id}/versions/{vid}/approve` | Submit HSE approval for an exact revision |
| `POST` | `/api/v1/procedures/{id}/versions/{vid}/publish` | Publish an approved revision |
| `GET` | `/api/v1/procedures/{id}/export` | Export the Unity JSON contract |
| `DELETE` | `/api/v1/procedures/{id}` | Archive (soft-delete) a procedure |
| `GET` | `/api/v1/audit` | Query the immutable audit trail |

### Field Service — Key Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/procedures` | List procedures visible to the field client |
| `GET` | `/procedures/{machine_id}` | Retrieve the published procedure; optional `version_id` |
| `POST` | `/interventions/start` | Begin a new intervention |
| `POST` | `/interventions/validate-step` | Validate an isolation step (YOLO-World inference) |
| `POST` | `/interventions/override-step` | Manual override with documented justification |
| `POST` | `/interventions/close` | Close intervention and generate PDF audit report |

---

## Key Design Decisions

**Shared local persistence** — both API services resolve the same SQLite database at `data/smartloto.db`. Runtime records and local backups are excluded from Git; reference documents and Unity contracts remain versioned.

**Human-in-the-loop enforcement** — The state machine (`draft_pending_review → approved → published`) is enforced at the service layer for the exact revision being reviewed. The current demo allows self-approval by default. To require separate author and reviewer identities, configure both `APP_ENV=production` and `ALLOW_SELF_APPROVAL=false`.

**Server-selected PDF provider** — `DOCUMENT_GENERATION_PROVIDER` selects Groq or Gemini on the server, using the corresponding API key and model settings. The dashboard submits the PDF and follows the persistent job through its `job_id`; provider credentials stay on the backend.

**Immutable audit trail** — All state transitions emit append-only audit events. Approved and published versions are immutable; edits require creating a new draft version.

**QR codes** — Each published procedure is associated with a QR code encoding the `machine_id`. Field operators scan the code to retrieve the active procedure version from the field service without manual lookup.

---

## Current workflow and verification

The current implementation includes persistent PDF ingestion, revision-based HSE
review with clarifications and evidence, Unity contract exports, and interventions
pinned to the published procedure revision. The dashboard exposes generation jobs,
component and workflow review, audit history, and publication controls. The Unity
client carries the canonical phases and verification methods, with explicit operator
confirmation, signature capture, and maintenance calibration controls.

The workspace cleanup changes file locations and configuration paths. Local databases,
API keys, generated evidence, caches and build outputs are excluded from Git. Reference
PDF/JSON fixtures, branding assets and the two Unity demo contracts are versioned.

| Verification | Result |
|---|---|
| API startup, health checks, SL-POC-01 retrieval and export | Passed |
| Dashboard startup, public images, API proxy and production build | Passed |
| Two static SL-POC-01 contracts and field API scenario through PDF report | Passed |
| Database reset and citation migration on disposable copies | Passed; original demo database unchanged |
| Local authoring tests, excluding the real-provider PDF test | 27 passed |
| Field contract tests | 4 passed, 1 failed |

The failing field test,
`test_canonical_v2_keeps_arbitrary_phases_methods_and_source_payload`, expects an
unchanged workflow while the serializer normalizes its fields. This mismatch remains
visible; the cleanup did not change the serializer or that test. A Unity/Quest build
and a new real-provider PDF generation have not been run. See [LAUNCH.md](LAUNCH.md)
for launch, reset, import, export, and verification commands, and
[Unity integration notes](docs/UNITY_INTEGRATION_READY.md) for the operator contract.

---

## Compliance

SmartLOTO is designed to support compliance with **OSHA 29 CFR 1910.147** (The Control of Hazardous Energy). The audit trail, 4-eyes approval rule, version history, and immutable intervention logs are intended to satisfy documentation requirements for energy-isolation programs. This software does not constitute legal compliance advice; consult your safety officer.

---

## License

Proprietary. All rights reserved.
