"""
SmartLOTO Field Service — root compatibility shim.

Allows `uvicorn backend:app --host 0.0.0.0 --port 8000` to keep working
without change while the actual implementation lives in apps/field-service/.

Canonical entry point:
    cd apps/field-service && uvicorn main:app --host 0.0.0.0 --port 8000
"""

import sys
import os

# Add the field-service directory so `runtime` resolves correctly.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "apps", "field-service"))

from dotenv import load_dotenv

load_dotenv()

from runtime.main import app  # noqa: E402

__all__ = ["app"]
