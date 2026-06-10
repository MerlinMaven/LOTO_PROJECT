"""
External dependency initialisation — Supabase client and YOLO model.

Both objects are initialised at module-import time (same behaviour as the
original backend.py).  Services import this module and access `db` / `model`
as module-level attributes so they always see the live reference.

Usage
-----
    import runtime.database as database

    if database.db is None:
        raise HTTPException(500, "Database unavailable")
    database.db.table("procedures").select("*").execute()

    if database.model is None:
        raise HTTPException(500, "Vision model unavailable")
    database.model.predict(image)
"""

from __future__ import annotations

from typing import Optional

from runtime.config import SUPABASE_KEY, SUPABASE_URL, YOLO_MODEL_PATH

# ── Supabase ──────────────────────────────────────────────────────────────────

db: Optional[object] = None   # supabase.Client at runtime

if not SUPABASE_URL or not SUPABASE_KEY:
    print(
        "WARNING: Supabase not configured. "
        "Set SUPABASE_URL and SUPABASE_KEY in .env to enable database access."
    )
else:
    try:
        from supabase import create_client
        db = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client connected successfully.")
    except Exception as exc:
        print(f"ERROR: Supabase connection failed: {exc}")
        db = None

# ── YOLO-World vision model ───────────────────────────────────────────────────

model: Optional[object] = None   # ultralytics.YOLO at runtime

print("Loading YOLO-World model …")
try:
    from ultralytics import YOLO
    model = YOLO(YOLO_MODEL_PATH)
    print("YOLO-World model loaded successfully.")
except Exception as exc:
    print(f"ERROR: YOLO-World model could not be loaded: {exc}")
    model = None
