"""
SmartLOTO Runtime (Field Service).

This package implements the LOTO execution API consumed by:
  - Meta Quest Unity client (SmartLOTOClient.cs)
  - Streamlit HSE dashboard (app.py)

Entry point: uvicorn backend:app --host 0.0.0.0 --port 8000

Architecture note
-----------------
This is the FIELD SERVICE — it handles live LOTO operations by operators
wearing AR headsets.  It is distinct from the AUTHORING SERVICE (backend/app/)
which HSE engineers use to create and review procedures.

                ┌─────────────────────────────────────────────┐
                │  Meta Quest (Unity)  /  Streamlit Dashboard │
                └───────────────┬─────────────────────────────┘
                                │  HTTP / REST JSON
                ┌───────────────▼─────────────────────────────┐
                │  runtime/  (Field Service — this package)   │
                │  • GET  /procedures                         │
                │  • GET  /procedures/{machine_id}            │
                │  • POST /interventions/start                │
                │  • POST /interventions/validate-step        │
                │  • POST /interventions/override-step        │
                │  • POST /interventions/close                │
                │  • POST /procedures/{id}/anchors            │
                └───────────────┬─────────────────────────────┘
                                │  Supabase SDK
                ┌───────────────▼─────────────────────────────┐
                │  Supabase: procedures + interventions tables │
                │  + smartloto-assets storage bucket          │
                └─────────────────────────────────────────────┘
"""
