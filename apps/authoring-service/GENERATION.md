# PDF procedure generation

The HSE dashboard submits PDF files to `POST /api/v1/generation/documents`. The
authoring service validates the PDF, records its SHA-256 content identity and page
count, extracts text page by page with PDFium, and runs Tesseract OCR on pages with
empty or malformed extraction. The original PDF is passed to the configured Gemini
model for native text and visual analysis. Extraction/OCR failures are reported with
the draft; they are not replaced with sample content.

Gemini selection is server-side (`GEMINI_API_KEY`, `GEMINI_MODEL`). The actual system
instruction and request prompt are maintained in
`app/services/document_generation_service.py` as `SYSTEM_INSTRUCTION` and the prompt
inside `_call_gemini`. PDF text is delimited as untrusted evidence; document content
cannot change the system instruction.

## Canonical draft

New document drafts use `schema_version: "2.0"`, validated by
`app/schemas_workflow.py`. The stored `workflow_definition` is the sole editable
procedure representation. It contains a revision ID, equipment/objective, source
manifest and content fingerprint, components, qualified facts, visual observations,
unknowns, contradictions, phases/stages/steps, evidence references, clarifications,
review state, and deterministic validation diagnostics. Each save creates a new
revision and preserves the previous version.

Validation checks structure, identifier uniqueness, component/fact/source references,
dependency references/order/cycles, verification criteria, measurement instrument
references, unresolved conditions, clarification links, citation matching, expected
final state, and page references. Clarification responses recalculate per-step review
readiness. These
checks establish internal consistency. They do not certify the engineering content,
the quality of a source, or the ability of a camera or sensor to verify a physical
state. Any detector prompt is a candidate label only.

An HSE reviewer can edit components/actions, add clarification answers and justifications,
link clarifications to affected actions, mark those actions reviewed, and save a new
revision. Unresolved clarifications or blocking diagnostics prevent approval. A
successful provider response is never treated as approval.

## Operator compatibility

The field-service and Unity DTOs carry canonical phases, steps, verification methods,
criteria, the procedure-version ID and source workflow JSON. Interventions request
and retain their pinned revision. Human maintenance confirmation uses its dedicated
attestation endpoint; it is not an override and requires no vision capture. Visual
verification uses the stored HSE context. Candidate localization is guidance and
never a separate proof of equipment state.

The source bundle in `unity-app/` is integrated into an external Unity project.
See [Unity setup](../../docs/UNITY_INTEGRATION_READY.md) for dependencies and
[API contracts](../../docs/unity_api_contracts.md) for the implemented routes.
Contract tests do not replace an editor/device build of the receiving project.

## Persistence and lifecycle

The database is initialized additively. It no longer inserts or rewrites a demonstration
procedure. Approval and publication endpoints require an exact version ID. Audit events
record the reviewer/publisher identity, timestamp, and version ID. Publication changes
the active revision pointer; subsequent saves create new versions. Interventions store
the published version ID and continue retrieving that same revision after a later
publication. Existing local SQLite databases add the intervention version column without
dropping existing records.

Tests in `tests/test_workflow_validation.py` use synthetic data to exercise schema and
invariant checks (multiple energy types, missing objectives, contradictions, human and
measurement checks, dependencies, and filename/ID independence). Most are isolated software checks; the normalization test that invokes semantic
grounding requires the configured provider. Neither suite is industrial validation
or a substitute for HSE review.
