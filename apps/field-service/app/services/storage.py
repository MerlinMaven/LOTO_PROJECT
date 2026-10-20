"""
SmartLOTO Field Service — Gestion locale des fichiers statiques.
100% autonome : enregistre physiquement sur disque dans apps/field-service/storage/
(sous-dossiers evidence/, signatures/, reports/) et renvoie l'URL locale absolue.
"""

from __future__ import annotations

import os
from pathlib import Path
from app.config import BASE_URL, STORAGE_DIR


def upload_file(
    file_bytes: bytes,
    file_path: str,
    content_type: str = "image/jpeg",
) -> str:
    """
    Enregistre un fichier binaire (photo de preuve, signature, PDF) sur le disque local
    et retourne son URL d'accès HTTP absolue pour Unity et le Dashboard.
    """
    destination = STORAGE_DIR / file_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(file_bytes)

    # Construction de l'URL absolue servie par StaticFiles
    url_path = file_path.replace("\\", "/").lstrip("/")
    return f"{BASE_URL.rstrip('/')}/storage/{url_path}"
