"""
SmartLOTO Authoring Service — Point d'entrée principal.

Lancement local :
    cd apps/authoring-service
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload
"""

from app.main import app

__all__ = ["app"]
