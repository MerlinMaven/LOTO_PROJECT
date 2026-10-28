# Architecture

SmartLOTO is a monorepo with two Python/FastAPI services, one React/Vite console and
a Unity C# source bundle. Paths under `apps/`, `unity-app/` and `data/` are preserved.

| Module | Entry point | Responsibility |
| --- | --- | --- |
| Authoring API | `apps/authoring-service/main.py` | PDF ingestion, extraction jobs, HSE decisions, exact-revision approval/publication and audit events. |
| Field API | `apps/field-service/main.py` | Published procedure access, pinned interventions, contextual vision, human confirmation, evidence and PDF reports. |
| HSE console | `apps/hse-dashboard/src/main.tsx` | Generation, component/workflow/Vision review, source verification, signature and publication. |
| Unity source bundle | `unity-app/SmartLOTOClient.cs` and companion scripts | Operator UI, QR identification, image capture, guidance, confirmation and closure. |

## Data flow

1. Authoring stores an uploaded PDF and its content fingerprint, extracts text/OCR,
   invokes the configured model and validates the canonical draft (`schema_version: 2.0`).
2. The console edits that draft, records clarification decisions and source review,
   then saves before approval. A reviewer signature is attached to the approval audit
   event; it is not injected into the Unity workflow contract.
3. Publication points to an exact approved revision. A later draft does not replace
   the revision already pinned by an intervention.
4. Field verification resolves the step from that pinned revision. Visual checks,
   human confirmations and overrides are distinct records. Candidate localization
   is guidance, not independent proof that a safety criterion is satisfied.
5. Closure stores the operator signature and builds the PDF with the HSE approval
   belonging to the executed revision. Historical records without a signature remain
   distinguishable from newly signed records.

## Persistence and files

- Both APIs use `data/smartloto.db` in the supported local setup.
- Original uploads live in `apps/authoring-service/data/documents/`.
- Field evidence, signatures and reports live in `apps/field-service/storage/` and
  are served through `/storage/...`. `BASE_URL` controls the generated public URLs.
- All runtime state is ignored by Git. Official fixtures remain under
  `apps/authoring-service/data/reference/` and `docs/contracts/`.
- Source contracts: [authoring schemas](../apps/authoring-service/app/schemas_workflow.py),
  [Field DTOs](../apps/field-service/app/models.py), [Unity DTOs](../unity-app/SmartLOTOClient.cs).

## Verification boundaries

Software checks validate schema consistency, revision identity and recorded
workflow behavior. HSE review establishes the engineering decision. Synthetic
images and object detections do not establish physical isolation on equipment.
See [generation details](../apps/authoring-service/GENERATION.md),
[Unity API reference](unity_api_contracts.md) and [release scope](RELEASE.md).
