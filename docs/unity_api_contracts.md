# Unity / Field API reference

The Field API runs on port **8000**. Authoring and publication run on port **8001**.
The authoritative request models are [app/models.py](../apps/field-service/app/models.py);
Unity serialization is defined in [SmartLOTOClient.cs](../unity-app/SmartLOTOClient.cs).
This repository cleanup changes neither endpoint contracts nor C# sources.

| Method | Field route | Purpose |
| --- | --- | --- |
| GET | `/procedures` | List available published procedures. |
| GET | `/procedures/{machine_id}` | Read the published procedure, or a permitted pinned revision using `version_id`. |
| POST | `/interventions/start` | Start on the published revision using `machine_id` and `operator_name`. |
| POST | `/interventions/validate-step` | Evaluate the submitted capture against the stored step context; client hints do not replace HSE criteria. |
| POST | `/interventions/confirm-step` | Record an explicit human confirmation for a step using that verification method. |
| POST | `/interventions/override-step` | Record an operator override with its reason and image evidence. |
| POST | `/procedures/{machine_id}/anchors` | Store calibrated spatial anchors supplied by Unity. |
| POST | `/interventions/close` | Accept `intervention_id` and `signature_base64`, persist closure and return the PDF report URL. |
| POST | `/guidance/locate-step` | Candidate localization for guidance; it does not validate or advance an intervention. |
| POST | `/tests/verify-step` | Draft/revision image evaluation in the existing test flow. |
| POST | `/tests/confirm-step` | Human confirmation in the existing test flow. |

Authoring exports a selected procedure through
`GET /v1/procedures/{procedure_id}/export` on port 8001. API Explorer pages are
available at `/docs` on each service.

## Revision and evidence identity

An intervention records `procedure_version_id` when it starts. Subsequent execution
uses that revision even after another is published. Step requests include the
intervention/action context; request IDs let the client associate observations with
the submitted capture. A human maintenance confirmation is not an image detection
or an override. Provider failures and indeterminate observations remain distinct
from satisfied or unsatisfied criteria.

Closure returns the existing `status`, `message` and `pdf_report_url` keys.
The report includes the HSE signature associated with the pinned revision and the
operator closure signature. Local artifact URLs retain `/storage/reports/`,
`/storage/evidence/` and `/storage/signatures/`.

## Fixtures and contract tests

- [C01–C07 demonstration matrix](contracts/SL-POC-01_unity_contract.json)
- [Unity StreamingAssets copy](../unity-app/Assets/StreamingAssets/SL-POC-01_unity_contract.json)
- [Unity contract tests](../apps/field-service/tests/test_unity_contract.py)
- [Contextual step verification tests](../apps/field-service/tests/test_step_vision.py)
- [Generic authoring export tests](../apps/authoring-service/tests/test_generic_unity_export.py)
- [Signed report tests](../apps/field-service/tests/test_report_signatures.py)

Treat the fixtures as examples, not as evidence of approval for a real installation.
Run commands and host-project requirements are in [LAUNCH.md](../LAUNCH.md) and
[Unity integration](UNITY_INTEGRATION_READY.md).
