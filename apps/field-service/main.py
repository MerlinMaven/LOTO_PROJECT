"""
SmartLOTO Field Service — Point d'entrée principal.

Lancement local :
    cd apps/field-service
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from app.main import app

__all__ = ["app"]
