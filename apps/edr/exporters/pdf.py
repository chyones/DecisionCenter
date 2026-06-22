"""PDF (.pdf) exporter — locked/shareable final reports.

Uses ReportLab for zero system-dependency PDF generation.
Arabic text requires registering an Arabic TTF font (e.g. Amiri) before calling
to_pdf(); the exporter uses Helvetica by default (Latin/English only).

RTL limitation (Phase 1H):
- Amiri font is registered and used for Arabic glyphs.
- ReportLab does NOT perform bidi shaping or Arabic reshaping.
- Arabic text is rendered left-to-right with isolated glyphs.
- Full RTL support requires python-bidi + arabic-reshaper (future phase).
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from apps.edr.graph.report_policy import (
    SEC_CONTRACTUAL,
    SEC_DELAY_ANALYSIS,
    SEC_FINANCIAL_SNAPSHOT,
    SEC_ROOT_CAUSES,
    policy_for,
)

# ---------------------------------------------------------------------------
# Arabic font registration (OFL-licensed Amiri)
# ---------------------------------------------------------------------------
_AMIRI_PATH = Path(__file__).with_name("Amiri-Regular.ttf")
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def _register_arabic_font() -> str | None:
    if _AMIRI_PATH.exists():
        try:
            pdfmetrics.registerFont(TTFont("Amiri", str(_AMIRI_PATH)))
            return "Amiri"
        except Exception:
            pass
    return None


_ARABIC_FONT = _register_arabic_font()


def _contains_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text))


def _pick_font(text: str) -> str:
    if _ARABIC_FONT and _contains_arabic(text):
        return _ARABIC_FONT
    return "Helvetica"


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


def _styles(body_font: str = "Helvetica") -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DC_Title", parent=base["Title"], fontSize=18, spaceAfter=10, fontName=body_font
        ),
        "h1": ParagraphStyle(
            "DC_H1",
            parent=base["Heading1"],
            fontSize=13,
            textColor=_BRAND_BLUE,
            spaceAfter=6,
            spaceBefore=14,
            fontName=body_font,
        ),
        "body": ParagraphStyle(
            "DC_Body", parent=base["Normal"], fontSize=10, spaceAfter=4, fontName=body_font
        ),
        "bullet": ParagraphStyle(
            "DC_Bullet",
            parent=base["Normal"],
            fontSize=10,
            leftIndent=16,
            spaceAfter=3,
            fontName=body_font,
        ),
        "caption": ParagraphStyle(
            "DC_Caption",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.grey,
            fontName=body_font,
        ),
    }


_TBL_HEADER = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
)

_META_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (0, -1), _BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]
)


def _build_story(report: dict, doc: BaseDocTemplate) -> tuple[list, bool]:
    """Build the Platypus story list and return it with the has_arabic flag."""
    request_id = report.get("request_id", "N/A")
    project_code = report.get("project_code") or "N/A"
    pid = report.get("project_identity") or {}
    project_name = pid.get("project_name") or project_code
    report_type = report.get("report_type", "executive_decision")
    report_title = report_type.replace("_", " ").title()
    query = report.get("query") or report.get("question", "N/A")
    language = report.get("language", "en")
    qg_status = report.get("quality_gate_status", "not_run")
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    policy = policy_for(report_type)

    has_arabic = language == "ar" or _contains_arabic(query) or _contains_arabic(str(report))
    body_font = _ARABIC_FONT if (has_arabic and _ARABIC_FONT) else "Helvetica"
    s = _styles(body_font)
    story: list = []
    section_no = 0

    def _heading(title: str) -> Paragraph:
        nonlocal section_no
        section_no += 1
        return Paragraph(f"{section_no}. {title}", s["h1"])

    story.append(Paragraph(f"{report_title} — {project_name} — {project_code}", s["title"]))
    story.append(Spacer(1, 0.3 * cm))

    meta_table = Table(
        [
            ["Request ID", request_id],
            ["Project Name", project_name],
            ["Project Code", project_code],
            ["Report Type", report_type],
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
    story.append(_heading("Executive Summary"))
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
                story.append(Paragraph(f"• {claim} <i>[{confidence}]{ref_note}</i>", s["bullet"]))
    else:
        story.append(Paragraph("No summary available.", s["body"]))

    # Financial Snapshot — Odoo
    if policy.renders(SEC_FINANCIAL_SNAPSHOT):
        story.append(_heading("Financial Snapshot — Odoo"))
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
                variance_row = [
                    "Variance",
                    f"{val_str}{' (' + formula + ')' if formula else ''}",
                    "—",
                ]

            fin_table = Table(
                [
                    ["Item", "Value", "Source"],
                    _fv(fs.get("contract_value") or {}, "Contract Value"),
                    _fv(fs.get("estimate") or {}, "Estimate"),
                    _fv(budget, "Budget"),
                    _fv(actual, "Actual Cost"),
                    _fv(fs.get("committed_cost") or {}, "Committed Cost"),
                    variance_row,
                ],
                colWidths=[3.5 * cm, 10 * cm, 3 * cm],
            )
            fin_table.setStyle(_TBL_HEADER)
            story.append(fin_table)
        else:
            story.append(Paragraph("Financial data not available.", s["body"]))
        story.append(Spacer(1, 0.3 * cm))

    # 3–7. Findings sections
    section_specs = [
        ("Key Findings", "key_findings"),
        ("Recommended Actions — Proposal Only", "recommended_actions"),
    ]
    if policy.renders(SEC_ROOT_CAUSES):
        section_specs[1:1] = [
            ("Root Causes", "root_causes"),
        ]
    if policy.renders(SEC_DELAY_ANALYSIS):
        insert_at = len(section_specs) - 1
        section_specs[insert_at:insert_at] = [
            ("Delay Analysis", "delay_analysis"),
        ]
    if policy.renders(SEC_CONTRACTUAL):
        insert_at = len(section_specs) - 1
        section_specs[insert_at:insert_at] = [
            ("Contractual / Commercial Implications", "contractual_implications"),
        ]
    for heading, key in section_specs:
        story.append(_heading(heading))
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
    story.append(_heading("Conflicting Evidence"))
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
    story.append(_heading("Missing Data / Assumptions"))
    missing = report.get("missing_data", [])
    if missing:
        for item in missing:
            story.append(Paragraph(f"• {item}", s["bullet"]))
    else:
        story.append(Paragraph("No missing data.", s["body"]))

    what_checked = report.get("what_was_checked", [])
    if what_checked:
        story.append(Paragraph("What Was Checked", s["h1"]))
        for item in what_checked:
            story.append(Paragraph(f"• {item}", s["bullet"]))

    required = report.get("required_data", [])
    if required:
        story.append(Paragraph("Required Data / Next Steps", s["h1"]))
        for item in required:
            story.append(Paragraph(f"• {item}", s["bullet"]))

    # 10. Sources
    story.append(_heading("Sources"))
    sources = report.get("sources", [])
    if sources:
        src_rows = [["ID", "Type", "Title", "Reference", "Date", "Confidence"]]
        for src in sources:
            if isinstance(src, dict):
                src_rows.append(
                    [
                        src.get("source_id", "—"),
                        src.get("source_type", "—"),
                        src.get("title", "—")[:28],
                        src.get("reference", "—")[:32],
                        src.get("date") or "—",
                        src.get("confidence", "—"),
                    ]
                )
        src_table = Table(
            src_rows,
            colWidths=[1.4 * cm, 2.2 * cm, 4.0 * cm, 5.0 * cm, 2.0 * cm, 2.0 * cm],
        )
        src_table.setStyle(_TBL_HEADER)
        story.append(src_table)
    else:
        story.append(Paragraph("No sources cited.", s["body"]))

    # 11. Quality Gate Status
    story.append(_heading("Quality Gate Status"))
    story.append(Paragraph(f"Status: <b>{qg_status}</b>", s["body"]))

    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(f"Generated by Decision Center — {generated_at}", s["caption"]))

    if has_arabic:
        story.append(
            Paragraph(
                "RTL limitation: Arabic glyphs are rendered with Amiri font. "
                "Full bidirectional shaping and Arabic reshaping are not yet implemented.",
                s["caption"],
            )
        )

    return story, has_arabic


def to_pdf(report: dict) -> bytes:
    """Generate a locked PDF from the canonical JSON report dict."""
    buf = io.BytesIO()
    doc = _make_doc(buf)
    story, _has_arabic = _build_story(report, doc)
    doc.build(story)
    return buf.getvalue()
