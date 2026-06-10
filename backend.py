"""
SmartLOTO Field Service entry-point.

Start with:  uvicorn backend:app --host 0.0.0.0 --port 8000
"""

from dotenv import load_dotenv

load_dotenv()

from runtime.main import app  # noqa: E402 — must load .env before runtime imports

__all__ = ["app"]
