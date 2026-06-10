"""
Storage service — Supabase Object Storage operations.

All evidence photos, operator signatures, and generated PDF audit reports are
stored in the ``smartloto-assets`` bucket.  This module is the single point of
contact with Supabase Storage so that the bucket name, upload options, and URL
retrieval strategy are all defined in one place.
"""

from __future__ import annotations

from fastapi import HTTPException

import runtime.database as database
from runtime.config import STORAGE_BUCKET


def upload_file(
    file_bytes: bytes,
    file_path: str,
    content_type: str = "image/jpeg",
) -> str:
    """
    Upload raw bytes to the Supabase storage bucket and return the public URL.

    Parameters
    ----------
    file_bytes:
        The raw binary content to upload.
    file_path:
        Destination path inside the bucket (e.g. ``evidence/abc_stage_1.jpg``).
    content_type:
        MIME type of the file.  Defaults to ``image/jpeg``.

    Returns
    -------
    str
        The public URL of the uploaded file, or an empty string if the upload
        fails non-fatally.  Fatal failures (Supabase unavailable) raise HTTP 500.

    Notes
    -----
    The ``x-upsert: true`` option allows re-uploading to the same path without
    a 409 conflict, which is useful during development and re-runs.
    """
    if database.db is None:
        raise HTTPException(status_code=500, detail="Supabase storage unavailable.")

    try:
        database.db.storage.from_(STORAGE_BUCKET).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": content_type, "x-upsert": "true"},
        )
        return database.db.storage.from_(STORAGE_BUCKET).get_public_url(file_path)
    except Exception as exc:
        # Storage failures are logged but do not abort the request — the
        # intervention record is still updated even if evidence upload fails.
        print(f"Storage upload error for '{file_path}': {exc}")
        return ""
