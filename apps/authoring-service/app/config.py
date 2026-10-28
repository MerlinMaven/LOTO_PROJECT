"""
SmartLOTO Authoring Service — Configuration.
Gère les variables d'environnement, les clés API des modèles LLM et la connexion DB.
Mode autonome SQLite activé par défaut pointant sur data/smartloto.db.
"""

from __future__ import annotations

import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Chemins de base résolus de manière absolue
APP_DIR = Path(__file__).resolve().parent
SERVICE_DIR = APP_DIR.parent

# Détection robuste de la racine LOTO_PROJECT
PROJECT_ROOT = APP_DIR.parent.parent.parent
for candidate in [APP_DIR] + list(APP_DIR.parents):
    if (candidate / "apps").is_dir() and (candidate / "unity-app").is_dir():
        PROJECT_ROOT = candidate
        break

def _get_default_sqlite_path() -> Path:
    data_dir = (PROJECT_ROOT / "data").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return (data_dir / "smartloto.db").resolve()

DEFAULT_SQLITE_PATH = _get_default_sqlite_path()

def resolve_db_url() -> tuple[str, Path]:
    raw_env = os.getenv("DATABASE_URL", "").strip() or os.getenv("SQLITE_DB_PATH", "").strip()
    if raw_env:
        if "postgresql" in raw_env:
            return raw_env, DEFAULT_SQLITE_PATH
        # Normalisation URL SQLite (relative ou absolue)
        if ":///" in raw_env:
            path_part = raw_env.split(":///")[-1]
        elif "://" in raw_env:
            path_part = raw_env.split("://")[-1]
        else:
            path_part = raw_env
        p = Path(path_part)
        resolved = p if p.is_absolute() else (PROJECT_ROOT / path_part.lstrip("./\\")).resolve()
        return f"sqlite+aiosqlite:///{resolved.as_posix()}", resolved

    return f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH.as_posix()}", DEFAULT_SQLITE_PATH

DATABASE_URL, SQLITE_DB_PATH = resolve_db_url()

# Ports et hôtes
PORT = int(os.getenv("PORT", "8001"))
APP_ENV = os.getenv("APP_ENV", "development")

# Clés API des fournisseurs LLM (pour la génération assistée de procédures)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-7b-instruct")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# The document-generation flow uses one server-selected multimodal model.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()

# Provider selection is explicit; the presence of a key never changes it.
DOCUMENT_GENERATION_PROVIDER = os.getenv(
    "DOCUMENT_GENERATION_PROVIDER", ""
).strip().lower()
GROQ_DOCUMENT_MODEL = os.getenv("GROQ_DOCUMENT_MODEL", "qwen/qwen3.8-27b")
PROVIDER_REQUEST_TIMEOUT_SECONDS = float(os.getenv("PROVIDER_REQUEST_TIMEOUT_SECONDS", "150"))
MAX_GENERATION_JOB_SECONDS = float(os.getenv("MAX_GENERATION_JOB_SECONDS", "480"))

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "")
VLLM_MODEL = os.getenv("VLLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")

# CORS : autorise toutes les origines pour le dev local
CORS_ORIGINS = ["*"]
