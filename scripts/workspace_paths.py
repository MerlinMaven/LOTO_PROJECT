"""Paths for maintenance scripts, resolved exactly as in the authoring service."""

from pathlib import Path
import runpy

ROOT_DIR = Path(__file__).resolve().parents[1]
_config = runpy.run_path(str(ROOT_DIR / "apps/authoring-service/app/config.py"))
if not _config["DATABASE_URL"].startswith("sqlite"):
    raise ValueError("Ces scripts locaux nécessitent une base SQLite (DATABASE_URL).")
DB_PATH = _config["SQLITE_DB_PATH"]
