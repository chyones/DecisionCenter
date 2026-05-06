"""PDF (.pdf) exporter — locked/shareable final reports.

Uses ReportLab for zero system-dependency PDF generation.
Arabic text requires registering an Arabic TTF font (e.g. Amiri) before calling
to_pdf(); the exporter uses Helvetica by default (Latin/English only).
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

_PAGE_W, _PAGE_H = A4
_MARGIN = 2.0 * cm
_BRAND_BLUE = colors.HexColor("#1F3864")
_LIGHT_GREY = colors.HexColor("#F2F2F2")


def _make_doc(buf: io.BytesIO) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame)])
    return doc


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("DC_Title", parent=base["Title"], fontSize=18, spaceAfter=10),
        "h1": ParagraphStyle(
            "DC_H1",
            parent=base["Heading1"],
            fontSize=13,
            textColor=_BRAND_BLUE,
            spaceAfter=6,
            spaceBefore=14,
        ),
        "body": ParagraphStyle("DC_Body", parent=base["Normal"], fontSize=10, spaceAfter=4),
        "bullet": ParagraphStyle(
            "DC_Bullet",
            parent=base["Normal"],
            fontSize=10,
            leftIndent=16,
            spaceAfter=3,
        ),
        "caption": ParagraphStyle(
            "DC_Caption",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.grey,
        ),
    }


_TBL_HEADER = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), _BRAND_BLUE),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ("PADDING", (0, 0), (-1, -1), 4),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
])

_META_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (0, -1), _BRAND_BLUE),
    ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ("PADDING", (0, 0), (-1, -1), 4),
])


def to_pdf(report: dict) -> bytes:
    """Generate a locked PDF from the canonical JSON report dict."""
    buf = io.BytesIO()
    doc = _make_doc(buf)
    s = _styles()
    story: list = []

    request_id = report.get("request_id", "N/A")
    project_code = report.get("project_code") or "N/A"
    query = report.get("query") or report.get("question", "N/A")
    language = report.get("language", "en")
    qg_status = report.get("quality_gate_status", "not_run")
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    story.append(Paragraph("Executive Decision Report", s["title"]))
    story.append(Spacer(1, 0.3 * cm))

    meta_table = Table(
        [
            ["Request ID", request_id],
            ["Project", project_code],
            ["Language", language],
            ["Quality Gate", qg_status],
            ["Generated", generated_at],
        ],
        colWidths=[3.5 * cm, doc.width - 3.5 * cm],
    )
    meta_table.setStyle(_META_STYLE)
    story.append(meta_table)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"<b>Query:</b> {query}", s["body"]))
    story.append(Spacer(1, 0.5 * cm))

    # 1. Executive Summary
    story.append(Paragraph("1. Executive Summary", s["h1"]))
    summary = report.get("executive_summary", [])
    if isinstance(summary, str):
        story.append(Paragraph(summary, s["body"]))
    elif summary:
        for item in summary:
            if isinstance(item, dict):
                claim = item.get("claim", "")
                confidence = item.get("confidence", "medium")
                refs = ", ".join(item.get("evidence_ids", []))
                ref_note = f" — {refs}" if refs else ""
                story.append(
                    Paragraph(f"• {claim} <i>[{confidence}]{ref_note}</i>", s["bullet"])
                )
    else:
        story.append(Paragraph("No summary available.", s["body"]))

    # 2. Financial Snapshot — Odoo
    story.append(Paragraph("2. Financial Snapshot — Odoo", s["h1"]))
    fs = report.get("financial_snapshot") or {}
    if isinstance(fs, dict):
        budget = fs.get("budget") or {}
        actual = fs.get("actual_cost") or {}
        variance = fs.get("variance") or {}
        currency = (budget.get("currency") if isinstance(budget, dict) else None) or "AED"

        def _fv(node: dict, label: str) -> list:
            if not isinstance(node, dict):
                return [label, "Not available", "—"]
            v = node.get("value")
            c = node.get("currency", currency)
            src = node.get("evidence_id") or "—"
            val_str = f"{v:,.2f} {c}" if v is not None else "Not available"
            return [label, val_str, src]

        variance_row = ["Variance", "Not available", "—"]
        if isinstance(variance, dict):
            v = variance.get("value")
            c = variance.get("currency", currency)
            formula = variance.get("formula", "")
            val_str = f"{v:,.2f} {c}" if v is not None else "Not available"
            variance_row = ["Variance", f"{val_str}{' (' + formula + ')' if formula else ''}", "—"]

        fin_table = Table(
            [["Item", "Value", "Source"], _fv(budget, "Budget"), _fv(actual, "Actual Cost"), variance_row],
            colWidths=[3.5 * cm, 10 * cm, 3 * cm],
        )
        fin_table.setStyle(_TBL_HEADER)
        story.append(fin_table)
    else:
        story.append(Paragraph("Financial data not available.", s["body"]))
    story.append(Spacer(1, 0.3 * cm))

    # 3–7. Findings sections
    for heading, key in [
        ("3. Key Findings", "key_findings"),
        ("4. Root Causes", "root_causes"),
        ("5. Delay Analysis", "delay_analysis"),
        ("6. Contractual / Commercial Implications", "contractual_implications"),
        ("7. Recommended Actions — Proposal Only", "recommended_actions"),
    ]:
        story.append(Paragraph(heading, s["h1"]))
        items = report.get(key, [])
        if items:
            for item in items:
                if isinstance(item, dict):
                    text = item.get("text", str(item))
                    confidence = item.get("confidence", "medium")
                    refs = ", ".join(item.get("evidence_ids", []))
                    ref_note = f" — {refs}" if refs else ""
                    story.append(
                        Paragraph(f"• {text} <i>[{confidence}]{ref_note}</i>", s["bullet"])
                    )
                else:
                    story.append(Paragraph(f"• {item}", s["bullet"]))
        else:
            story.append(Paragraph("Not available.", s["body"]))

    # 8. Conflicting Evidence
    story.append(Paragraph("8. Conflicting Evidence", s["h1"]))
    conflicts = report.get("conflicts", [])
    if conflicts:
        for c in conflicts:
            if isinstance(c, dict):
                story.append(
                    Paragraph(
                        f"<b>Type:</b> {c.get('conflict_type', '?')} — {c.get('description', '')}",
                        s["body"],
                    )
                )
                story.append(Paragraph(f"• Source A: {c.get('source_a_ref', '—')}", s["bullet"]))
                story.append(Paragraph(f"• Source B: {c.get('source_b_ref', '—')}", s["bullet"]))
    else:
        story.append(Paragraph("No conflicting evidence detected.", s["body"]))

    # 9. Missing Data / Assumptions
    story.append(Paragraph("9. Missing Data / Assumptions", s["h1"]))
    missing = report.get("missing_data", [])
    if missing:
        for item in missing:
            story.append(Paragraph(f"• {item}", s["bullet"]))
    else:
        story.append(Paragraph("No missing data.", s["body"]))

    # 10. Sources
    story.append(Paragraph("10. Sources", s["h1"]))
    sources = report.get("sources", [])
    if sources:
        src_rows = [["ID", "Type", "Title", "Reference", "Date", "Confidence"]]
        for src in sources:
            if isinstance(src, dict):
                src_rows.append([
                    src.get("source_id", "—"),
                    src.get("source_type", "—"),
                    src.get("title", "—")[:28],
                    src.get("reference", "—")[:32],
                    src.get("date") or "—",
                    src.get("confidence", "—"),
                ])
        src_table = Table(
            src_rows,
            colWidths=[1.4 * cm, 2.2 * cm, 4.0 * cm, 5.0 * cm, 2.0 * cm, 2.0 * cm],
        )
        src_table.setStyle(_TBL_HEADER)
        story.append(src_table)
    else:
        story.append(Paragraph("No sources cited.", s["body"]))

    # 11. Quality Gate Status
    story.append(Paragraph("11. Quality Gate Status", s["h1"]))
    story.append(Paragraph(f"Status: <b>{qg_status}</b>", s["body"]))

    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(f"Generated by Decision Center — {generated_at}", s["caption"]))

    doc.build(story)
    return buf.getvalue()
