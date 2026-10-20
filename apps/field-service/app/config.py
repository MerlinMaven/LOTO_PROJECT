"""
SmartLOTO Field Service — Configuration.
Gère les variables d'environnement, les chemins absolus immuables (modèle YOLO, local storage, SQLite)
et offre un fonctionnement 100% autonome et local.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Chemins de base résolus de manière absolue
APP_DIR = Path(__file__).resolve().parent
SERVICE_DIR = APP_DIR.parent

# Détection robuste de la racine LOTO_PROJECT
PROJECT_ROOT = APP_DIR.parent.parent.parent
for candidate in [APP_DIR] + list(APP_DIR.parents):
    if (candidate / "apps").is_dir() and (candidate / "unity-app").is_dir():
        PROJECT_ROOT = candidate
        break

DEFAULT_SQLITE_PATH = (PROJECT_ROOT / "smartloto.db").resolve()

def resolve_sqlite_path() -> Path:
    raw_env = os.getenv("DATABASE_URL", "").strip() or os.getenv("SQLITE_DB_PATH", "").strip()
    if raw_env:
        # Extraire chemin si format URL sqlite:///...
        if ":///" in raw_env:
            path_part = raw_env.split(":///")[-1]
        elif "://" in raw_env:
            path_part = raw_env.split("://")[-1]
        else:
            path_part = raw_env
        p = Path(path_part)
        return p if p.is_absolute() else (PROJECT_ROOT / path_part.lstrip("./\\")).resolve()
    return DEFAULT_SQLITE_PATH

SQLITE_DB_PATH = resolve_sqlite_path()

# Poids du modèle YOLO-World (absolu)
DEFAULT_WEIGHTS_PATH = (SERVICE_DIR / "weights" / "yolov8s-worldv2.pt").resolve()
WEIGHTS_PATH = os.getenv("YOLO_MODEL_PATH", str(DEFAULT_WEIGHTS_PATH))

# Stockage local des artefacts (preuves photos, signatures, rapports PDF)
DEFAULT_STORAGE_DIR = (SERVICE_DIR / "storage").resolve()
STORAGE_DIR = Path(os.getenv("LOCAL_STORAGE_DIR", str(DEFAULT_STORAGE_DIR))).resolve()
STORAGE_PATH_EVIDENCE = "evidence"
STORAGE_PATH_SIGNATURES = "signatures"
STORAGE_PATH_REPORTS = "reports"

# URL de base pour servir les fichiers statiques (PDF, images)
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

# CORS : autorise toutes les origines pour le dev local
CORS_ORIGINS = ["*"]
