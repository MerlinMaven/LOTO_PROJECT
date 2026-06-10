"""
Runtime configuration.

All constants and environment-variable reads are centralised here so that
changing a value never requires touching business-logic code.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ── Supabase ──────────────────────────────────────────────────────────────────

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# ── Object storage ────────────────────────────────────────────────────────────

STORAGE_BUCKET: str = "smartloto-assets"

# Sub-paths inside the bucket
STORAGE_PATH_EVIDENCE: str = "evidence"
STORAGE_PATH_SIGNATURES: str = "signatures"
STORAGE_PATH_REPORTS: str = "reports"

# ── YOLO vision model ─────────────────────────────────────────────────────────

YOLO_MODEL_PATH: str = "yolov8s-worldv2.pt"

# Detection confidence threshold — 0.45 provides a good balance between
# false positives and false negatives for industrial LOTO objects.
YOLO_CONFIDENCE: float = 0.45

# ── API / CORS ────────────────────────────────────────────────────────────────

# Allow all origins so that the Quest headset on the same LAN can reach the
# server regardless of IP address, and so that ngrok tunnels work without
# pre-registering hostnames.
CORS_ORIGINS: list[str] = ["*"]
