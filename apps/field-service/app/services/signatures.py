"""Internal signature records. No changes to the Unity request/response models."""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from PIL import Image, ImageDraw


def operator_signature(intervention: dict, completed_at: str, image_bytes: bytes | None):
    """Preserve a drawn signature or generate a labelled nominal closure signature."""
    captured = False
    if image_bytes:
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.verify()
            captured = True
        except (OSError, ValueError, SyntaxError):
            pass
    name = str(intervention.get("operator_name") or "Opérateur")
    if not captured:
        image = Image.new("RGB", (640, 160), "white")
        draw = ImageDraw.Draw(image)
        # Pillow's bundled font may be Latin-1 only on older installations.
        text = f"{name}\nSignature nominative de cloture\n{completed_at}".encode("latin-1", "replace").decode("latin-1")
        draw.multiline_text((18, 28), text, fill="#1A365D", spacing=12)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
    record = {"name": name, "role": "Opérateur AR", "signed_at": completed_at,
              "status": "captured" if captured else "generated",
              "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
              "intervention_id": intervention["id"],
              "procedure_version_id": intervention.get("procedure_version_id")}
    record["sha256"] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return record, image_bytes


def hse_signature_for_intervention(db, intervention: dict):
    """Only the approval for the intervention's immutable revision is relevant."""
    version_id = intervention.get("procedure_version_id")
    if not version_id:
        return None
    query = db.table("audit_events").select("*").eq("machine_id", intervention["machine_id"]).eq(
        "event_type", "PROCEDURE_APPROVED")
    try:
        rows = query.execute().data
    except sqlite3.OperationalError as exc:
        # Standalone field installations and historical databases may predate authoring.
        if "no such table: audit_events" not in str(exc):
            raise
        return None
    finally:
        if hasattr(query, "conn"):
            query.conn.close()
    candidates = []
    for row in rows or []:
        payload = row.get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        signature = payload.get("signature")
        if payload.get("version_id") == version_id and isinstance(signature, dict):
            candidates.append(signature)
    return max(candidates, key=lambda sig: sig.get("signed_at", ""), default=None)
