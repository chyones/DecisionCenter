"""Markdown exporter. Spec: Section 29 (report structure, 11 required sections).

Numbered body sections are emitted through a running counter so that when a
report type suppresses sections (e.g. salary/data reports omit Root Causes /
Delay / Contractual), the remaining sections stay contiguously numbered instead
of leaving visible gaps (1, 2, 3, 7, ...). Full reports are unchanged (1..11).
"""

from __future__ import annotations

from datetime import datetime, timezone


def to_markdown(report: dict) -> str:
    """Generate executive-decision-report.md from the canonical JSON report dict."""
    lines: list[str] = []

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

    lines += [
        f"# {report_title} — {project_name} — {project_code}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Request ID | {request_id} |",
        f"| Project Name | {project_name} |",
        f"| Project Code | {project_code} |",
        f"| Report Type | {report_type} |",
        f"| Language | {language} |",
        f"| Quality Gate | {qg_status} |",
        f"| Evidence Completeness | {report.get('evidence_completeness', 'n/a')} |",
        f"| Generated | {generated_at} |",
        "",
        f"**Query:** {query}",
        "",
        "---",
        "",
    ]

    # Running section counter so numbered headings stay contiguous regardless of
    # which sections a given report type includes.
    _counter = {"n": 0}

    def heading(title: str) -> str:
        _counter["n"] += 1
        return f"## {_counter['n']}. {title}"

    # 0. Connector Coverage — every enabled source, attempted/zero made visible
    _coverage_section(lines, report)

    # Executive Summary
    lines.append(heading("Executive Summary"))
    lines.append("")
    summary = report.get("executive_summary", [])
    if isinstance(summary, str):
        lines.append(summary)
    elif summary:
        for item in summary:
            if isinstance(item, dict):
                claim = item.get("claim", "")
                confidence = item.get("confidence", "medium")
                refs = item.get("evidence_ids", [])
                ref_str = " — " + ", ".join(f"[{r}]" for r in refs) if refs else ""
                lines.append(f"- {claim} *(Confidence: {confidence})*{ref_str}")
    else:
        lines.append("_No summary available._")
    lines.append("")

    # Management Question Answer (executive decision memo) — unnumbered insert
    mqa = report.get("management_question_answer") or {}
    if isinstance(mqa, dict) and mqa.get("executive_answer"):
        lines.append("## Management Question Answer")
        lines.append("")
        lines.append(f"**Executive answer:** {mqa.get('executive_answer', '')}")
        lines.append("")
        why = mqa.get("why_biggest_problem") or []
        if why:
            lines.append("**Why this is the biggest problem:**")
            for bullet in why:
                lines.append(f"- {bullet}")
            lines.append("")
        evidence_used = mqa.get("evidence_used") or []
        if evidence_used:
            lines.append("**Evidence used:**")
            for item in evidence_used:
                lines.append(f"- {item}")
            lines.append("")
        impact = mqa.get("business_impact") or {}
        if isinstance(impact, dict) and any(impact.values()):
            lines.append("**Business impact:**")
            for label, key in (
                ("Schedule", "schedule_impact"),
                ("Cost / Commercial", "cost_commercial_impact"),
                ("Operational / Client", "operational_client_impact"),
            ):
                value = impact.get(key, "") or "_Not specified_"
                lines.append(f"- **{label}:** {value}")
            lines.append("")
        if mqa.get("decision_required"):
            lines.append(f"**Decision required:** {mqa['decision_required']}")
            lines.append("")
        action = mqa.get("recommended_action") or {}
        if isinstance(action, dict) and action.get("specific_action"):
            lines.append("**Recommended action:**")
            lines.append(f"- **Action:** {action.get('specific_action', '')}")
            lines.append(f"- **Owner role:** {action.get('owner_role', '')}")
            lines.append(f"- **Timeframe:** {action.get('timeframe', '')}")
            lines.append("")
        if mqa.get("risks_if_no_action"):
            lines.append(f"**Risks if no action:** {mqa['risks_if_no_action']}")
            lines.append("")
        lines.append(
            f"**Confidence:** {mqa.get('confidence', 'medium')} — "
            f"{mqa.get('missing_evidence_or_assumptions', '') or 'No missing evidence noted.'}"
        )
        lines.append("")

    # Financial Snapshot — Odoo
    lines.append(heading("Financial Snapshot — Odoo"))
    lines.append("")
    fs = report.get("financial_snapshot") or {}
    if isinstance(fs, dict):
        budget = fs.get("budget") or {}
        actual = fs.get("actual_cost") or {}
        variance = fs.get("variance") or {}
        currency = (budget.get("currency") if isinstance(budget, dict) else None) or "AED"
        lines += [
            "| Item | Value | Source |",
            "|---|---|---|",
            _fin_row("Budget", budget, currency),
            _fin_row("Actual Cost", actual, currency),
        ]
        if isinstance(variance, dict):
            v = variance.get("value")
            c = variance.get("currency", currency)
            formula = variance.get("formula", "")
            val_str = f"{v:,.2f} {c}" if v is not None else "Not available"
            formula_note = f" *(Formula: {formula})*" if formula else ""
            lines.append(f"| Variance | {val_str}{formula_note} | — |")
    else:
        lines.append("_Financial data not available._")
    if isinstance(fs, dict) and fs.get("note"):
        lines.append("")
        lines.append(f"> {fs['note']}.")
    lines.append("")

    is_data_report = report_type in ("salary_payroll", "data_report")

    # Findings sections
    _findings_section(lines, heading("Key Findings"), report.get("key_findings", []))
    if not is_data_report:
        _findings_section(lines, heading("Root Causes"), report.get("root_causes", []))
        _findings_section(lines, heading("Delay Analysis"), report.get("delay_analysis", []))
        _findings_section(
            lines,
            heading("Contractual / Commercial Implications"),
            report.get("contractual_implications", []),
        )

    lines.append(heading("Recommended Actions — Proposal Only"))
    lines.append("")
    actions = report.get("recommended_actions", [])
    if actions:
        for item in actions:
            if isinstance(item, dict):
                text = item.get("text", str(item))
                confidence = item.get("confidence", "medium")
                refs = item.get("evidence_ids", [])
                ref_str = " — " + ", ".join(f"[{r}]" for r in refs) if refs else ""
                lines.append(f"- **Proposal:** {text} *(Confidence: {confidence})*{ref_str}")
            else:
                lines.append(f"- **Proposal:** {item}")
    else:
        lines.append("_No recommended actions._")
    lines.append("")

    # Conflicting Evidence
    lines.append(heading("Conflicting Evidence"))
    lines.append("")
    conflicts = report.get("conflicts", [])
    if conflicts:
        for c in conflicts:
            if isinstance(c, dict):
                lines += [
                    f"**Type:** `{c.get('conflict_type', 'unknown')}`",
                    "",
                    c.get("description", ""),
                    "",
                    f"- Source A: {c.get('source_a_ref', '—')}",
                    f"- Source B: {c.get('source_b_ref', '—')}",
                    "",
                ]
    else:
        lines.append("_No conflicting evidence detected._")
    lines.append("")

    # Missing Data / Assumptions
    lines.append(heading("Missing Data / Assumptions"))
    lines.append("")
    missing = report.get("missing_data", [])
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("_No missing data._")
    lines.append("")

    # What was checked / required data (salary/payroll availability reports) — unnumbered
    what_checked = report.get("what_was_checked", [])
    if what_checked:
        lines.append("## What Was Checked")
        lines.append("")
        for item in what_checked:
            lines.append(f"- {item}")
        lines.append("")
    required = report.get("required_data", [])
    if required:
        lines.append("## Required Data / Next Steps")
        lines.append("")
        for item in required:
            lines.append(f"- {item}")
        lines.append("")

    # Sources
    lines.append(heading("Sources"))
    lines.append("")
    sources = report.get("sources", [])
    if sources:
        for src in sources:
            if isinstance(src, dict):
                sid = src.get("source_id", "S?")
                used_in = ", ".join(src.get("used_in", [])) or "—"
                lines += [
                    f"**[{sid}]** Source Type: {src.get('source_type', '—')}",
                    f"- Title: {src.get('title', '—')}",
                    f"- Reference: {src.get('reference', '—')}",
                    f"- Date: {src.get('date') or '—'}",
                    f"- Confidence: {src.get('confidence', '—')}",
                    f"- Used in: {used_in}",
                    "",
                ]
    else:
        lines.append("_No sources cited._")
    lines.append("")

    # Quality Gate Status
    lines.append(heading("Quality Gate Status"))
    lines.append("")
    lines.append(f"**Status:** `{qg_status}`")
    lines.append("")
    lines += [
        "---",
        "",
        f"*Generated by Decision Center — {generated_at}*",
    ]

    return "\n".join(lines)


def _fin_row(label: str, node: dict, currency: str) -> str:
    if not isinstance(node, dict):
        return f"| {label} | Not available | — |"
    v = node.get("value")
    c = node.get("currency", currency)
    src = node.get("evidence_id") or "—"
    val_str = f"{v:,.2f} {c}" if v is not None else "Not available"
    return f"| {label} | {val_str} | {src} |"


def _findings_section(lines: list[str], heading: str, items: list) -> None:
    lines.append(heading)
    lines.append("")
    if items:
        for item in items:
            if isinstance(item, dict):
                text = item.get("text", str(item))
                confidence = item.get("confidence", "medium")
                refs = item.get("evidence_ids", [])
                ref_str = " — " + ", ".join(f"[{r}]" for r in refs) if refs else ""
                lines.append(f"- {text} *(Confidence: {confidence})*{ref_str}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("_Not available._")
    lines.append("")


def _coverage_section(lines: list[str], report: dict) -> None:
    """Render the connector coverage table: every enabled source with its
    attempted/evidence-count/status, so zero-evidence sources are never hidden."""
    lines.append("## Connector Coverage")
    lines.append("")
    coverage_rows = report.get("connector_coverage", [])
    if coverage_rows:
        lines += [
            "| Source | Enabled | Attempted | Evidence | Status | Reason |",
            "|---|---|---|---|---|---|",
        ]
        for row in coverage_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {row.get('source','—')} "
                f"| {'yes' if row.get('enabled') else 'no'} "
                f"| {'yes' if row.get('attempted') else 'no'} "
                f"| {row.get('evidence_count', 0)} "
                f"| {row.get('status','—')} "
                f"| {row.get('reason','') or '—'} |"
            )
        lines.append("")
        lines.append(f"**Evidence completeness:** {report.get('evidence_completeness', 'n/a')}")
    else:
        lines.append("_No connector coverage recorded._")
    lines.append("")
