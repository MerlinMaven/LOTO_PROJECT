"""
PDF audit report generation.

Produces an OSHA-style PDF that documents every validated step of a LOTO
intervention, including:
  - Intervention metadata (ID, machine, operator, timestamps)
  - Step-by-step audit log with type and result per action
  - Embedded operator signature image

The generated PDF is returned as raw bytes so that the caller can upload it
to Supabase Storage and return the public URL to Unity.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime


def generate_audit_report(intervention: dict, machine_name: str, sig_bytes: bytes | None) -> bytes:
    """
    Generate a PDF audit report for a completed intervention.

    Parameters
    ----------
    intervention:
        The raw intervention row from Supabase (dict with keys: id, machine_id,
        operator_name, started_at, logs).
    machine_name:
        Human-readable machine name retrieved from the procedures table.
    sig_bytes:
        Raw PNG bytes of the operator's digital signature, or None if no
        signature was provided.

    Returns
    -------
    bytes
        The complete PDF file as raw bytes, ready to be uploaded to storage.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=15,
    )
    h2_style = ParagraphStyle(
        "DocH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = styles["BodyText"]

    elements = []

    # Title
    elements.append(Paragraph("SmartLOTO - Rapport d'Audit HSE", title_style))
    elements.append(
        Paragraph(
            f"Generated on: {datetime.now().strftime('%d/%m/%Y at %H:%M')}",
            body_style,
        )
    )
    elements.append(Spacer(1, 15))

    # Metadata table
    info_data = [
        [Paragraph("<b>Intervention ID:</b>", body_style), Paragraph(str(intervention.get("id", "")), body_style)],
        [Paragraph("<b>Machine code:</b>", body_style), Paragraph(str(intervention.get("machine_id", "")), body_style)],
        [Paragraph("<b>Machine name:</b>", body_style), Paragraph(machine_name, body_style)],
        [Paragraph("<b>Operator:</b>", body_style), Paragraph(str(intervention.get("operator_name", "")), body_style)],
        [Paragraph("<b>Start:</b>", body_style), Paragraph(str(intervention.get("started_at", "")), body_style)],
        [Paragraph("<b>End:</b>", body_style), Paragraph(datetime.now().isoformat(), body_style)],
    ]
    t_info = Table(info_data, colWidths=[150, 300])
    t_info.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7FAFC")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    elements.append(t_info)
    elements.append(Spacer(1, 15))

    # Step audit log
    elements.append(Paragraph("Step Audit Log", h2_style))
    logs = intervention.get("logs", []) or []
    log_rows = [["Timestamp", "Stage", "Action", "Type", "Result"]]
    for log in logs:
        ts = (log.get("timestamp") or "")
        ts_short = ts[11:19] if len(ts) > 18 else ts
        if log.get("type") == "vision_detection":
            result = "Success (AI)" if log.get("success") else "Not detected"
        elif log.get("type") == "manual_override_with_evidence":
            result = "Override"
        else:
            result = "Failure"
        log_rows.append([
            ts_short,
            f"Stage {log.get('stage_id', '')}",
            str(log.get("action_description", "")),
            str(log.get("type", "")),
            result,
        ])
    t_logs = Table(log_rows, colWidths=[70, 60, 150, 100, 70])
    t_logs.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ])
    )
    elements.append(t_logs)
    elements.append(Spacer(1, 20))

    # Signature
    elements.append(Paragraph("Operator Signature", h2_style))
    sig_img_path: str | None = None
    if sig_bytes:
        elements.append(Paragraph("Digital signature captured at intervention close:", body_style))
        elements.append(Spacer(1, 5))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(sig_bytes)
            sig_img_path = tmp.name
        try:
            elements.append(Image(sig_img_path, width=150, height=75))
        except Exception as exc:
            elements.append(Paragraph(f"[Signature render error: {exc}]", body_style))
    else:
        elements.append(Paragraph("No signature provided.", body_style))

    # Build PDF to a temp file, read bytes, then clean up
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        tmp_pdf_path = tmp_pdf.name

    try:
        doc = SimpleDocTemplate(tmp_pdf_path, pagesize=letter)
        doc.build(elements)
        with open(tmp_pdf_path, "rb") as f:
            pdf_bytes = f.read()
    finally:
        if os.path.exists(tmp_pdf_path):
            os.remove(tmp_pdf_path)
        if sig_img_path and os.path.exists(sig_img_path):
            os.remove(sig_img_path)

    return pdf_bytes
