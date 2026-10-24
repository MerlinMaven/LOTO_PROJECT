"""Deprecated text generation entry point.

Document generation is implemented only by document_generation_service. There is no
sample procedure, hard-coded workflow, or provider fallback in this module.
"""

from fastapi import HTTPException


def generate_procedure(*args, **kwargs):
    raise HTTPException(
        status_code=410,
        detail="La génération texte historique est désactivée. Importez un PDF via /generation/documents.",
    )
