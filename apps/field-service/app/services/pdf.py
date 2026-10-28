"""
SmartLOTO Field Service — Génération de rapport d'audit PDF.
Produit un document d'audit conforme OSHA 29 CFR 1910.147 avec horodatage,
historique des étapes vérifiées par IA / dérogations, et signature numérique.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional
from xml.sax.saxutils import escape


def _format_timestamp(value) -> str:
    if not value:
        return "—"
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp.strftime("%d/%m/%Y à %H:%M:%S")
    except (TypeError, ValueError):
        return str(value)


def generate_audit_report(intervention: dict, machine_name: str, sig_bytes: Optional[bytes]) -> bytes:
    """Génère le rapport PDF complet sous forme d'octets."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import (
            Image,
            KeepTogether,
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
            fontSize=20,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=12,
        )
        h2_style = ParagraphStyle(
            "DocH2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = styles["BodyText"]
        result_styles = {
            label: ParagraphStyle("Result " + label, parent=body_style,
                                  fontName="Helvetica-Bold", fontSize=8, leading=10,
                                  textColor=colors.HexColor(color))
            for label, color in {
                "Succès (IA)": "#15803D", "Confirmé par humain": "#0E7490",
                "Critère non satisfait": "#92400E", "Indéterminé": "#92400E",
                "Dérogation": "#92400E", "Erreur technique": "#B91C1C", "Échec": "#B91C1C",
            }.items()
        }

        elements = []
        elements.append(Paragraph("SmartLOTO — Rapport d'intervention LOTO (HSE)", title_style))
        elements.append(Paragraph(f"Émis le : {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}", body_style))
        elements.append(Spacer(1, 12))

        # Métadonnées
        info_data = [
            [Paragraph("<b>ID Intervention :</b>", body_style), Paragraph(str(intervention.get("id", "")), body_style)],
            [Paragraph("<b>Code Machine :</b>", body_style), Paragraph(str(intervention.get("machine_id", "")), body_style)],
            [Paragraph("<b>Révision de procédure :</b>", body_style), Paragraph(escape(str(intervention.get("procedure_version_id", ""))), body_style)],
            [Paragraph("<b>Nom Machine :</b>", body_style), Paragraph(machine_name, body_style)],
            [Paragraph("<b>Opérateur AR :</b>", body_style), Paragraph(str(intervention.get("operator_name", "")), body_style)],
            [Paragraph("<b>Début :</b>", body_style), Paragraph(escape(_format_timestamp(intervention.get("started_at"))), body_style)],
            [Paragraph("<b>Fin :</b>", body_style), Paragraph(escape(_format_timestamp(intervention.get("completed_at") or datetime.now())), body_style)],
        ]
        t_info = Table(info_data, colWidths=[140, 320])
        t_info.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7FAFC")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ])
        )
        elements.append(t_info)
        elements.append(Spacer(1, 14))

        # Journal d'audit des actions
        elements.append(Paragraph("Journal d'Audit des Étapes", h2_style))
        logs = intervention.get("logs", []) or []
        log_rows = [["Horodatage", "Étape", "Action", "Type", "Résultat"]]
        for log in logs:
            if log.get("type") == "operator_signature":
                continue  # Rendered in the dedicated signature section below.
            ts = log.get("timestamp") or ""
            ts_short = ts[11:19] if len(ts) > 18 else ts
            if log.get("type") == "human_confirmation":
                result = "Confirmé par humain"
            elif log.get("type") in {"vision_detection", "contextual_vision"}:
                outcome=(log.get("observation") or {}).get("outcome")
                result = "Succès (IA)" if log.get("success") else "Erreur technique" if outcome=="technical_error" else "Indéterminé" if outcome=="indeterminate" else "Critère non satisfait"
            elif log.get("type") in {"manual_override_with_evidence", "operator_override"}:
                result = "Dérogation"
            else:
                result = "Échec"
            log_rows.append([
                ts_short,
                f"Étape {log.get('stage_id', '')}",
                Paragraph(escape(str(log.get("action_description", ""))), body_style),
                Paragraph(escape(str(log.get("execution_phase", ""))) + "<br/>" + escape(
                    {"human_confirmation":"Confirmation humaine", "contextual_vision":"Contrôle visuel", "vision_detection":"Contrôle visuel", "operator_override":"Dérogation"}.get(log.get("type"),str(log.get("type", "")))), body_style),
                Paragraph(escape(result), result_styles[result]),
            ])
        t_logs = Table(log_rows, colWidths=[70, 60, 160, 100, 70], repeatRows=1)
        t_logs.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ])
        )
        elements.append(t_logs)

        # Both signatures belong to this exact procedure revision and intervention.
        signature_style = ParagraphStyle("Signature", parent=body_style,
                                         fontName="Times-Italic", fontSize=15, leading=18)
        small_style = ParagraphStyle("Signature details", parent=body_style, fontSize=8, leading=11)

        def signature_box(title, record, fallback_name, image_bytes=None):
            box = [Paragraph(title, small_style), Spacer(1, 8)]
            if not record and not image_bytes:
                box.append(Paragraph("Signature non disponible pour cette r\u00e9vision.", small_style))
                return box
            record = record or {}
            name = str(record.get("name") or fallback_name or "")
            box.append(Paragraph(escape(name), signature_style))
            reviewer = record.get("reviewer_id")
            if reviewer and reviewer != name:
                box.append(Paragraph(escape(str(reviewer)), small_style))
            box.append(Paragraph(escape(str(record.get("role") or "")), small_style))
            box.append(Paragraph(escape(_format_timestamp(record.get("signed_at"))), small_style))
            if record.get("status") == "generated":
                box.append(Paragraph("Signature nominative de cl\u00f4ture g\u00e9n\u00e9r\u00e9e", small_style))
            if image_bytes:
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(io.BytesIO(image_bytes)) as candidate:
                        candidate.verify()
                    picture = Image(io.BytesIO(image_bytes))
                    picture._restrictSize(180, 65)
                    box.append(picture)
                except (OSError, ValueError, SyntaxError):
                    box.append(Paragraph("Image de signature illisible.", small_style))
            digest = str(record.get("sha256") or "")
            if digest:
                box.append(Paragraph("SHA-256 :<br/>" + escape(digest[:32]) + "<br/>" + escape(digest[32:]), small_style))
            return box

        signatures = Table([[
            signature_box("<b>Approbation Proc\u00e9dure</b><br/>Responsable HSE",
                          intervention.get("hse_signature"), ""),
            signature_box("<b>Ex\u00e9cution &amp; Cl\u00f4ture</b><br/>Op\u00e9rateur AR",
                          intervention.get("operator_signature"), intervention.get("operator_name"), sig_bytes),
        ]], colWidths=[230, 230])
        signatures.setStyle(TableStyle([
            ("BOX", (0, 0), (0, 0), 0.8, colors.HexColor("#2B6CB0")),
            ("BOX", (1, 0), (1, 0), 0.8, colors.HexColor("#2B6CB0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 10),
        ]))
        elements.append(KeepTogether([
            Spacer(1, 12),
            Paragraph("Signatures &amp; Validation de Conformit\u00e9", h2_style),
            signatures,
        ]))
        output = io.BytesIO()
        SimpleDocTemplate(output, pagesize=letter).build(elements)
        return output.getvalue()

    except ImportError as exc:
        raise RuntimeError("Le g\u00e9n\u00e9rateur PDF ReportLab doit \u00eatre install\u00e9.") from exc
