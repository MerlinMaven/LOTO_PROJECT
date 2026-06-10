"""
SmartLOTO Authoring Service — entry point.

Start with:
    cd apps/authoring-service
    uvicorn main:app --host 0.0.0.0 --port 8001
"""

from app.main import app

__all__ = ["app"]
