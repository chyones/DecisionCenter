"""Node 14 - Compose and Export Report. Spec: Sections 16 and 29.

Generates all requested output formats from the validated JSON report.
- Export runs only when the quality gate has not hard-failed.
- All formats derive from state.report_json (canonical JSON).
- state.output_formats controls which formats are produced (default: ["md"]).
- Results are stored in state.outputs["exported_reports"] (metadata dict) and
  state.outputs["report_exports_raw"] (format -> bytes, for node_15 to persist).
"""

from apps.edr.exporters import export_report
from apps.edr.graph.state import DecisionState

_STUB_REPORT: dict = {
    "request_id": "stub",
    "project_code": None,
    "query": "Stub — no validated JSON report yet.",
    "language": "en",
    "executive_summary": [],
    "financial_snapshot": {
        "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
        "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
        "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
    },
    "key_findings": [],
    "root_causes": [],
    "delay_analysis": [],
    "contractual_implications": [],
    "recommended_actions": [],
    "missing_data": ["No evidence retrieved — connectors not yet implemented."],
    "conflicts": [],
    "sources": [],
    "quality_gate_status": "needs_review",
}


def run(state: DecisionState) -> DecisionState:
    quality_gate = state.outputs.get("quality_gate", "needs_review")
    if quality_gate == "failed":
        state.outputs["markdown_report_status"] = "skipped_quality_gate_failed"
        return state.mark("node_14_compose_md")

    report = state.report_json or _STUB_REPORT
    if state.report_json:
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
