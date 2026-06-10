"""
SmartLOTO Field Service — entry point.

Start with:
    cd apps/field-service
    uvicorn main:app --host 0.0.0.0 --port 8000

The root-level backend.py is a compatibility shim that delegates here so that
the original `uvicorn backend:app` command continues to work without change.
"""

from dotenv import load_dotenv

load_dotenv()

from runtime.main import app  # noqa: E402

__all__ = ["app"]
