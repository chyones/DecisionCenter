"""Report exporters — generate all output formats from the canonical JSON report.

Spec rules:
- JSON is the canonical internal format. All exports derive from it.
- Markdown (.md)   — default human-readable format.
- Word (.docx)     — formal executive reports.
- PDF (.pdf)       — locked/shareable final reports.
- Excel (.xlsx)    — evidence tables, financial summaries, source lists, audit data.
- PowerPoint (.pptx) — executive presentation summaries.
"""

from __future__ import annotations

from apps.edr.exporters.base import FILE_EXTENSIONS, MIME_TYPES, ExportResult


def export_report(
    report: dict,
    formats: list[str],
    base_filename: str = "executive-decision-report",
) -> dict[str, ExportResult]:
    """Generate all requested formats from the validated JSON report dict.

    Returns a mapping of format code -> ExportResult.
    Unknown format codes are silently skipped.
    """
    results: dict[str, ExportResult] = {}
    for fmt in formats:
        content = _generate(report, fmt)
        if content is None:
            continue
        raw = content.encode("utf-8") if isinstance(content, str) else content
        results[fmt] = ExportResult(
            format=fmt,
            content=raw,
            filename=f"{base_filename}{FILE_EXTENSIONS.get(fmt, '.bin')}",
            mime_type=MIME_TYPES.get(fmt, "application/octet-stream"),
        )
    return results


def _generate(report: dict, fmt: str) -> bytes | str | None:
    if fmt == "md":
        from apps.edr.exporters.markdown import to_markdown

        return to_markdown(report)
    if fmt == "docx":
        from apps.edr.exporters.word import to_word

        return to_word(report)
    if fmt == "xlsx":
        from apps.edr.exporters.excel import to_excel

        return to_excel(report)
    if fmt == "pdf":
        from apps.edr.exporters.pdf import to_pdf

        return to_pdf(report)
    if fmt == "pptx":
        from apps.edr.exporters.powerpoint import to_powerpoint

        return to_powerpoint(report)
    return None
