# Running SmartLOTO

Commands below assume PowerShell and the repository root. Use Python 3.12+ to match
`apps/authoring-service/pyproject.toml`, Node.js 20+, and Git. Scanned PDFs require
Tesseract OCR on `PATH`. On macOS/Linux, replace the virtualenv executable with
`.venv/bin/python`, `npm.cmd` with `npm`, and use equivalent file-copy commands.

## Install and configure

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r apps/authoring-service/requirements.txt -r apps/field-service/requirements.txt
npm.cmd --prefix apps/hse-dashboard ci
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path apps/hse-dashboard/.env)) { Copy-Item apps/hse-dashboard/.env.example apps/hse-dashboard/.env }
```

Fill `GEMINI_API_KEY` and `GEMINI_MODEL` in `.env`. PDF extraction, semantic citation
checks and contextual field vision use explicit provider/model selection. The
presence of another provider's key does not select it automatically. No key belongs
in a `VITE_*` variable: those values are delivered to the browser.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Use `sqlite+aiosqlite:///data/smartloto.db` for both APIs. Relative SQLite paths resolve from the repository root. |
| `DOCUMENT_GENERATION_PROVIDER` | `gemini` for the PDF/semantic-review flow. |
| `FIELD_VISION_PROVIDER` | `gemini` for contextual step verification and guidance. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Private credential and an enabled model ID; required for provider calls. |
| `BASE_URL` | Field server URL embedded in report/image links. Use the LAN address for headset access. |
| `LOCAL_STORAGE_DIR` | Optional absolute field-storage override; omit for the existing service `storage/` directory. |
| `YOLO_MODEL_PATH`, `YOLO_CONFIDENCE` | Optional legacy detector settings; not a fallback for contextual Gemini verification. |
| `APP_ENV`, `ALLOW_SELF_APPROVAL` | Existing approval-policy switches. Development mode allows self-review; setting `ALLOW_SELF_APPROVAL=false` alone does not change that. |

Use the root `.env` for the shared setup. Service-local `.env.example` files are
provided as deployment references; copying them to `.env` can shadow the root file.
Keep both services on the same database. Terminal environment variables take precedence.

## Run

Open three terminals at the repository root:

```powershell
# Authoring: PDF generation jobs, HSE review, approval and publication
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir apps/authoring-service --host 127.0.0.1 --port 8001
```

```powershell
# Field: Unity execution and static evidence/signature/report files
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir apps/field-service --host 0.0.0.0 --port 8000
```

```powershell
# Browser console; /api is proxied to authoring-service by Vite
npm.cmd --prefix apps/hse-dashboard run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Health: `http://127.0.0.1:8001/health` and `http://127.0.0.1:8000/health`.
Console: `http://localhost:5173`. Stop foreground servers with `Ctrl+C`.
The existing `scripts/start_backend.ps1` / `.bat` launch both APIs using `python`
from `PATH`; activate the intended environment first when using these helpers.

## Author and execute a procedure

1. Upload the [v0.3 sample dossier](apps/authoring-service/data/reference/SmartLOTO_SL-POC-01_Dossier_Technique_Descriptif_v0.3.pdf) or your technical PDF in the HSE console.
2. Review the extracted components, facts, workflow and Vision rules; verify citations and resolve HSE questions with their justification.
3. Sign and publish the reviewed revision. Pending edits are saved before approval.
4. In a configured [Unity host project](docs/UNITY_INTEGRATION_READY.md), select the published equipment or scan its QR code.
5. Execute the supplied verification methods. Maintenance confirmations remain human attestations; inconclusive vision results remain inconclusive.
6. Close with the operator signature and open the PDF URL returned by the field service.

The intervention stays pinned to the revision on which it started. Runtime PDFs
and evidence are local artifacts, not source-controlled demo fixtures.

## Checks without modifying operational data

Install test tools in the same environment:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio pdfminer.six
npm.cmd --prefix apps/hse-dashboard run typecheck
npm.cmd --prefix apps/hse-dashboard test
npm.cmd --prefix apps/hse-dashboard run build
```

Run the API suites in separate processes because both services use the package name `app`:

```powershell
Push-Location apps/authoring-service
..\..\.venv\Scripts\python.exe -m pytest tests/test_review_publication.py tests/test_clarification_resolution.py tests/test_procedure_lifecycle.py tests/test_generic_unity_export.py tests/test_phase_policy.py tests/test_workflow_validation.py -q -k 'not synthetic_model_response_is_normalized_without_legacy_duplicate_actions'
Pop-Location

Push-Location apps/field-service
..\..\.venv\Scripts\python.exe -m pytest tests/test_report_signatures.py tests/test_unity_contract.py tests/test_step_vision.py -q
Pop-Location
```

The excluded normalization case calls the configured semantic provider. The older
`test_real_pdf_generation.py` is an opt-in integration test tied to a retired PDF
filename and Groq configuration; do not use it as a clean-clone smoke test or run
it against operational data. No test source or runtime logic was changed for this
repository cleanup. [Release notes](docs/RELEASE.md) record the verification scope.

## Optional local demo reset

`scripts/reset_db.py` deletes application records and standard runtime artifacts.
Run it only on a disposable demo database after stopping both APIs and taking a
backup. It is not part of setup, testing, or release preparation.

## Production hosting scope

A static frontend build needs a reverse proxy for `/api` to authoring-service.
Headsets also need direct access to field-service and its `/storage` URLs.
The current identity headers, permissive CORS settings and development approval
policy require a separate deployment/security review; this release preparation
preserves their existing implementation. The historical Compose configuration is
described in [infra/README.md](infra/README.md) and is not the supported quick start.
