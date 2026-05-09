"""Node 14 - Compose and Export Report. Spec: Sections 16 and 29.

Generates all requested output formats from the validated JSON report.
- Export runs only when the quality gate has explicitly passed.
- All formats derive from state.report_json (canonical JSON).
- state.output_formats controls which formats are produced (default: ["md"]).
- Results are stored in state.outputs["exported_reports"] (metadata dict) and
  state.outputs["report_exports_raw"] (format -> bytes, for node_15 to persist).
"""

from apps.edr.exporters import export_report
from apps.edr.graph.state import DecisionState


async def run(state: DecisionState) -> DecisionState:
    quality_gate = state.outputs.get("quality_gate", "needs_review")
    # Spec Section 17: only an explicit "passed" gate allows export.
    # "needs_review", "failed", or any other value blocks the export.
    if quality_gate != "passed":
        state.outputs["markdown_report_status"] = (
            f"skipped_quality_gate_{quality_gate}"
        )
        return state.mark("node_14_compose_md")

    if not state.report_json:
        state.outputs["markdown_report_status"] = "skipped_no_validated_report"
        return state.mark("node_14_compose_md")

    report = dict(state.report_json)
    report.setdefault("request_id", state.request_id)

    formats = state.output_formats or ["md"]
    results = export_report(report, formats)

    state.outputs["exported_reports"] = {
        fmt: {
            "filename": r.filename,
            "mime_type": r.mime_type,
            "size_bytes": len(r.content),
        }
        for fmt, r in results.items()
    }
    state.outputs["report_exports_raw"] = {fmt: r.content for fmt, r in results.items()}
    state.outputs["markdown_report_status"] = (
        "generated" if results else "no_formats_requested"
    )

    return state.mark("node_14_compose_md")
