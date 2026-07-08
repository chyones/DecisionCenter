"""Markdown exporter — executive-first layout. Spec: Section 29.

The body reads as a professional decision document: the executive summary
leads, only sections with real content render, and confidence markers appear
only when a claim is low-confidence. Pipeline metadata (request id, quality
gate, connector coverage) renders in a governance appendix at the end — never
ahead of the analysis. Every heading and label localizes to the report
language (``report["language"]``: en/ar); evidence citation tokens are kept
inline because the UI turns them into clickable citation chips.

Section presence is driven by the per-type ReportPolicy (apps/edr/graph/
report_policy.py). Numbered headings flow through a running counter so
suppressed sections never leave a gap.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from apps.edr.graph.report_policy import (
    SEC_CONTRACTUAL,
    SEC_DELAY_ANALYSIS,
    SEC_FINANCIAL_SNAPSHOT,
    SEC_ROOT_CAUSES,
    SEC_SOURCES,
    policy_for,
)

#: Display names per report type key (title fallback: key.title()).
_TYPE_NAMES: dict[str, dict[str, str]] = {
    "financial": {"en": "Financial Report", "ar": "التقرير المالي"},
    "management_question": {"en": "Executive Decision Report", "ar": "تقرير القرار الإداري"},
    "general_project_status": {"en": "Project Status Report", "ar": "تقرير حالة المشروع"},
    "salary_payroll": {"en": "Salary / Payroll Report", "ar": "تقرير الرواتب"},
    "data_report": {"en": "Data Report", "ar": "تقرير البيانات"},
    "risk": {"en": "Risk Report", "ar": "تقرير المخاطر"},
    "delay": {"en": "Delay Report", "ar": "تقرير التأخير"},
    "document_search": {"en": "Document Search Report", "ar": "تقرير البحث في المستندات"},
    "executive_decision": {"en": "Executive Decision Report", "ar": "تقرير القرار الإداري"},
}

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "date": "Date",
        "query": "Query",
        "sec.executive_summary": "Executive Summary",
        "sec.mqa": "Management Question — Answer",
        "sec.financial_snapshot": "Financial Snapshot — Odoo",
        "sec.key_findings": "Key Findings",
        "sec.root_causes": "Root Causes",
        "sec.delay_analysis": "Delay Analysis",
        "sec.contractual": "Contractual / Commercial Implications",
        "sec.recommended": "Recommended Actions — Proposal Only",
        "sec.conflicts": "Conflicting Evidence",
        "sec.missing": "Missing Data / Assumptions",
        "sec.what_checked": "What Was Checked",
        "sec.required_data": "Required Data / Next Steps",
        "sec.sources": "Appendix — Sources",
        "sec.governance": "Appendix — Report Governance",
        "sec.coverage": "Data Source Coverage",
        "no_summary": "_No summary available._",
        "fin.item": "Item",
        "fin.value": "Value",
        "fin.source": "Source",
        "fin.contract_value": "Contract Value",
        "fin.estimate": "Estimate",
        "fin.budget": "Budget",
        "fin.actual_cost": "Actual Cost (analytic/journal)",
        "fin.payroll_cost": "Payroll / Staff",
        "fin.expense_cost": "HR Expenses (petty cash/car/fuel)",
        "fin.committed_cost": "Committed Cost (LPO/PO)",
        "fin.total_incurred": "Total Incurred",
        "fin.variance": "Variance",
        "fin.formula": "Formula",
        "fin.none_available": "_No verified Odoo financial figures are available for this report._",
        "fin.not_available_list": "Not available in Odoo",
        "fin.not_available": "Not available",
        "low_confidence": "low confidence — analyst review advised",
        "proposal": "Proposal",
        "mqa.answer": "Executive answer",
        "mqa.why": "Why this is the biggest problem",
        "mqa.evidence": "Evidence used",
        "mqa.impact": "Business impact",
        "mqa.schedule": "Schedule",
        "mqa.cost": "Cost / Commercial",
        "mqa.operational": "Operational / Client",
        "mqa.not_specified": "_Not specified_",
        "mqa.decision": "Decision required",
        "mqa.action": "Recommended action",
        "mqa.action.text": "Action",
        "mqa.action.owner": "Owner role",
        "mqa.action.time": "Timeframe",
        "mqa.risks": "Risks if no action",
        "mqa.confidence": "Confidence",
        "mqa.no_missing": "No missing evidence noted.",
        "conflict.type": "Type",
        "conflict.a": "Source A",
        "conflict.b": "Source B",
        "gov.request_id": "Request ID",
        "gov.report_type": "Report Type",
        "gov.language": "Language",
        "gov.quality_gate": "Quality Gate",
        "gov.completeness": "Evidence Completeness",
        "gov.generated": "Generated",
        "cov.source": "Source",
        "cov.enabled": "Enabled",
        "cov.attempted": "Attempted",
        "cov.evidence": "Evidence",
        "cov.status": "Status",
        "cov.reason": "Reason",
        "cov.none": "_No connector coverage recorded._",
        "yes": "yes",
        "no": "no",
        "src.date": "date",
        "src.confidence": "confidence",
        "footer": "Generated by Decision Center",
    },
    "ar": {
        "date": "التاريخ",
        "query": "الاستفسار",
        "sec.executive_summary": "الملخص التنفيذي",
        "sec.mqa": "إجابة سؤال الإدارة",
        "sec.financial_snapshot": "الموقف المالي — Odoo",
        "sec.key_findings": "أبرز النتائج",
        "sec.root_causes": "الأسباب الجذرية",
        "sec.delay_analysis": "تحليل التأخير",
        "sec.contractual": "الآثار التعاقدية والتجارية",
        "sec.recommended": "الإجراءات الموصى بها — مقترح فقط",
        "sec.conflicts": "تعارض الأدلة",
        "sec.missing": "البيانات الناقصة / الافتراضات",
        "sec.what_checked": "ما تم فحصه",
        "sec.required_data": "البيانات المطلوبة / الخطوات التالية",
        "sec.sources": "الملحق — المصادر",
        "sec.governance": "الملحق — حوكمة التقرير",
        "sec.coverage": "تغطية مصادر البيانات",
        "no_summary": "_لا يتوفر ملخص._",
        "fin.item": "البند",
        "fin.value": "القيمة",
        "fin.source": "المصدر",
        "fin.contract_value": "قيمة العقد",
        "fin.estimate": "التكلفة التقديرية",
        "fin.budget": "الميزانية",
        "fin.actual_cost": "التكلفة الفعلية (قيود تحليلية)",
        "fin.payroll_cost": "الرواتب والموظفون",
        "fin.expense_cost": "المصروفات النثرية (عهدة/سيارات/وقود)",
        "fin.committed_cost": "التكاليف الملتزم بها (أوامر الشراء)",
        "fin.total_incurred": "إجمالي التكلفة المتكبدة",
        "fin.variance": "الفرق",
        "fin.formula": "المعادلة",
        "fin.none_available": "_لا تتوفر أرقام مالية موثقة من Odoo لهذا التقرير._",
        "fin.not_available_list": "غير متوفر في Odoo",
        "fin.not_available": "غير متوفر",
        "low_confidence": "ثقة منخفضة — يُنصح بمراجعة محلل",
        "proposal": "مقترح",
        "mqa.answer": "الإجابة التنفيذية",
        "mqa.why": "لماذا تُعد هذه المشكلة الأكبر",
        "mqa.evidence": "الأدلة المستخدمة",
        "mqa.impact": "الأثر على الأعمال",
        "mqa.schedule": "الجدول الزمني",
        "mqa.cost": "التكلفة / التجاري",
        "mqa.operational": "التشغيلي / العميل",
        "mqa.not_specified": "_غير محدد_",
        "mqa.decision": "القرار المطلوب",
        "mqa.action": "الإجراء الموصى به",
        "mqa.action.text": "الإجراء",
        "mqa.action.owner": "الجهة المسؤولة",
        "mqa.action.time": "الإطار الزمني",
        "mqa.risks": "المخاطر في حال عدم اتخاذ إجراء",
        "mqa.confidence": "درجة الثقة",
        "mqa.no_missing": "لا توجد أدلة ناقصة مسجلة.",
        "conflict.type": "النوع",
        "conflict.a": "المصدر أ",
        "conflict.b": "المصدر ب",
        "gov.request_id": "معرّف الطلب",
        "gov.report_type": "نوع التقرير",
        "gov.language": "اللغة",
        "gov.quality_gate": "بوابة الجودة",
        "gov.completeness": "اكتمال الأدلة",
        "gov.generated": "تاريخ الإنشاء",
        "cov.source": "المصدر",
        "cov.enabled": "مفعّل",
        "cov.attempted": "تمت المحاولة",
        "cov.evidence": "الأدلة",
        "cov.status": "الحالة",
        "cov.reason": "السبب",
        "cov.none": "_لا يوجد سجل لتغطية الموصلات._",
        "yes": "نعم",
        "no": "لا",
        "src.date": "التاريخ",
        "src.confidence": "الثقة",
        "footer": "أُنشئ بواسطة مركز القرار",
    },
}

#: Snapshot rows in render order: (fs key, label key).
_FIN_ROWS: tuple[tuple[str, str], ...] = (
    ("contract_value", "fin.contract_value"),
    ("estimate", "fin.estimate"),
    ("budget", "fin.budget"),
    ("actual_cost", "fin.actual_cost"),
    ("payroll_cost", "fin.payroll_cost"),
    ("expense_cost", "fin.expense_cost"),
    ("committed_cost", "fin.committed_cost"),
    ("total_incurred", "fin.total_incurred"),
)

#: Cost rows display as magnitudes — Odoo stores costs as negative amounts,
#: and a minus sign in an executive table reads as a credit.
_FIN_COST_KEYS = frozenset(
    ("actual_cost", "payroll_cost", "expense_cost", "committed_cost", "total_incurred")
)

# Source titles occasionally carry an empty-excerpt artifact ("RCC-PO-33107: .").
_EMPTY_TITLE_TAIL = re.compile(r"[:;,\s]+\.?\s*$")


def to_markdown(report: dict) -> str:
    """Generate executive-decision-report.md from the canonical JSON report dict."""
    lang = "ar" if report.get("language") == "ar" else "en"
    t = _STRINGS[lang]

    request_id = report.get("request_id", "N/A")
    project_code = report.get("project_code") or "N/A"
    pid = report.get("project_identity") or {}
    project_name = pid.get("project_name") or project_code
    report_type = report.get("report_type", "executive_decision")
    type_names = _TYPE_NAMES.get(report_type)
    report_title = (
        type_names[lang] if type_names else report_type.replace("_", " ").title()
    )
    query = report.get("query") or report.get("question", "N/A")
    qg_status = report.get("quality_gate_status", "not_run")
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    policy = policy_for(report_type)

    lines: list[str] = [
        f"# {report_title} — {project_name} — {project_code}",
        "",
        f"**{t['date']}:** {generated_at[:10]}",
        f"**{t['query']}:** {query}",
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

    def confidence_suffix(confidence: str) -> str:
        # Professional register: flag only what needs analyst attention.
        return f" *({t['low_confidence']})*" if confidence == "low" else ""

    # Executive Summary — always first, always present.
    lines.append(heading(t["sec.executive_summary"]))
    lines.append("")
    summary = report.get("executive_summary", [])
    if isinstance(summary, str):
        lines.append(summary)
    elif summary:
        for item in summary:
            if isinstance(item, dict):
                claim = item.get("claim", "")
                refs = item.get("evidence_ids", [])
                ref_str = " — " + ", ".join(f"[{r}]" for r in refs) if refs else ""
                lines.append(
                    f"- {claim}{confidence_suffix(item.get('confidence', 'medium'))}{ref_str}"
                )
    else:
        lines.append(t["no_summary"])
    lines.append("")

    # Management Question Answer (executive decision memo) — unnumbered insert
    mqa = report.get("management_question_answer") or {}
    if isinstance(mqa, dict) and mqa.get("executive_answer"):
        lines.append(f"## {t['sec.mqa']}")
        lines.append("")
        lines.append(f"**{t['mqa.answer']}:** {mqa.get('executive_answer', '')}")
        lines.append("")
        why = mqa.get("why_biggest_problem") or []
        if why:
            lines.append(f"**{t['mqa.why']}:**")
            for bullet in why:
                lines.append(f"- {bullet}")
            lines.append("")
        evidence_used = mqa.get("evidence_used") or []
        if evidence_used:
            lines.append(f"**{t['mqa.evidence']}:**")
            for item in evidence_used:
                lines.append(f"- {item}")
            lines.append("")
        impact = mqa.get("business_impact") or {}
        if isinstance(impact, dict) and any(impact.values()):
            lines.append(f"**{t['mqa.impact']}:**")
            for label_key, key in (
                ("mqa.schedule", "schedule_impact"),
                ("mqa.cost", "cost_commercial_impact"),
                ("mqa.operational", "operational_client_impact"),
            ):
                value = impact.get(key, "") or t["mqa.not_specified"]
                lines.append(f"- **{t[label_key]}:** {value}")
            lines.append("")
        if mqa.get("decision_required"):
            lines.append(f"**{t['mqa.decision']}:** {mqa['decision_required']}")
            lines.append("")
        action = mqa.get("recommended_action") or {}
        if isinstance(action, dict) and action.get("specific_action"):
            lines.append(f"**{t['mqa.action']}:**")
            lines.append(f"- **{t['mqa.action.text']}:** {action.get('specific_action', '')}")
            lines.append(f"- **{t['mqa.action.owner']}:** {action.get('owner_role', '')}")
            lines.append(f"- **{t['mqa.action.time']}:** {action.get('timeframe', '')}")
            lines.append("")
        if mqa.get("risks_if_no_action"):
            lines.append(f"**{t['mqa.risks']}:** {mqa['risks_if_no_action']}")
            lines.append("")
        lines.append(
            f"**{t['mqa.confidence']}:** {mqa.get('confidence', 'medium')} — "
            f"{mqa.get('missing_evidence_or_assumptions', '') or t['mqa.no_missing']}"
        )
        lines.append("")

    # Financial Snapshot — Odoo (only for report types that include it).
    # Only rows with verified values render; unavailable items collapse into a
    # single note so the table never reads as a wall of "Not available".
    if policy.renders(SEC_FINANCIAL_SNAPSHOT):
        lines.append(heading(t["sec.financial_snapshot"]))
        lines.append("")
        fs = report.get("financial_snapshot") or {}
        if isinstance(fs, dict):
            budget = fs.get("budget") or {}
            currency = (budget.get("currency") if isinstance(budget, dict) else None) or "AED"
            rows: list[str] = []
            unavailable: list[str] = []
            for key, label_key in _FIN_ROWS:
                node = fs.get(key)
                if not isinstance(node, dict) or node.get("value") is None:
                    unavailable.append(t[label_key])
                    continue
                value = node.get("value")
                if key in _FIN_COST_KEYS:
                    value = abs(value)
                cur = node.get("currency", currency)
                src = node.get("evidence_id") or "—"
                rows.append(f"| {t[label_key]} | {value:,.2f} {cur} | {src} |")
            variance = fs.get("variance")
            if isinstance(variance, dict) and variance.get("value") is not None:
                formula = variance.get("formula", "")
                formula_note = f" *({t['fin.formula']}: {formula})*" if formula else ""
                rows.append(
                    f"| {t['fin.variance']} | {variance['value']:,.2f} "
                    f"{variance.get('currency', currency)}{formula_note} | — |"
                )
            else:
                unavailable.append(t["fin.variance"])
            if rows:
                lines += [
                    f"| {t['fin.item']} | {t['fin.value']} | {t['fin.source']} |",
                    "|---|---|---|",
                    *rows,
                ]
                if unavailable:
                    lines.append("")
                    lines.append(
                        f"*{t['fin.not_available_list']}: {'، '.join(unavailable) if lang == 'ar' else ', '.join(unavailable)}.*"
                    )
            else:
                lines.append(t["fin.none_available"])
            if fs.get("note"):
                lines.append("")
                lines.append(f"> {fs['note']}.")
        else:
            lines.append(t["fin.none_available"])
        lines.append("")

    def findings_section(title: str, items: list) -> None:
        """Render a findings section; suppressed entirely when empty."""
        if not items:
            return
        lines.append(heading(title))
        lines.append("")
        for item in items:
            if isinstance(item, dict):
                text = item.get("text", str(item))
                refs = item.get("evidence_ids", [])
                ref_str = " — " + ", ".join(f"[{r}]" for r in refs) if refs else ""
                lines.append(
                    f"- {text}{confidence_suffix(item.get('confidence', 'medium'))}{ref_str}"
                )
            else:
                lines.append(f"- {item}")
        lines.append("")

    findings_section(t["sec.key_findings"], report.get("key_findings", []))
    if policy.renders(SEC_ROOT_CAUSES):
        findings_section(t["sec.root_causes"], report.get("root_causes", []))
    if policy.renders(SEC_DELAY_ANALYSIS):
        findings_section(t["sec.delay_analysis"], report.get("delay_analysis", []))
    if policy.renders(SEC_CONTRACTUAL):
        findings_section(t["sec.contractual"], report.get("contractual_implications", []))

    # Recommended Actions — rendered only when there is a real proposal.
    actions = report.get("recommended_actions", [])
    if actions:
        lines.append(heading(t["sec.recommended"]))
        lines.append("")
        for item in actions:
            if isinstance(item, dict):
                text = item.get("text", str(item))
                refs = item.get("evidence_ids", [])
                ref_str = " — " + ", ".join(f"[{r}]" for r in refs) if refs else ""
                lines.append(
                    f"- **{t['proposal']}:** {text}"
                    f"{confidence_suffix(item.get('confidence', 'medium'))}{ref_str}"
                )
            else:
                lines.append(f"- **{t['proposal']}:** {item}")
        lines.append("")

    # Conflicting Evidence — rendered only when conflicts exist.
    conflicts = report.get("conflicts", [])
    if conflicts:
        lines.append(heading(t["sec.conflicts"]))
        lines.append("")
        for c in conflicts:
            if isinstance(c, dict):
                lines += [
                    f"**{t['conflict.type']}:** `{c.get('conflict_type', 'unknown')}`",
                    "",
                    c.get("description", ""),
                    "",
                    f"- {t['conflict.a']}: {c.get('source_a_ref', '—')}",
                    f"- {t['conflict.b']}: {c.get('source_b_ref', '—')}",
                    "",
                ]

    # Missing Data / Assumptions — rendered only when something is missing.
    missing = report.get("missing_data", [])
    if missing:
        lines.append(heading(t["sec.missing"]))
        lines.append("")
        for item in missing:
            lines.append(f"- {item}")
        lines.append("")

    # What was checked / required data (salary/payroll availability reports) — unnumbered
    what_checked = report.get("what_was_checked", [])
    if what_checked:
        lines.append(f"## {t['sec.what_checked']}")
        lines.append("")
        for item in what_checked:
            lines.append(f"- {item}")
        lines.append("")
    required = report.get("required_data", [])
    if required:
        lines.append(f"## {t['sec.required_data']}")
        lines.append("")
        for item in required:
            lines.append(f"- {item}")
        lines.append("")

    # Appendix — Sources (condensed; kept out of the main body)
    appendix_sources = report.get("sources", [])
    if policy.renders(SEC_SOURCES) and appendix_sources:
        lines.append(f"## {t['sec.sources']}")
        lines.append("")
        for src in appendix_sources:
            if not isinstance(src, dict):
                continue
            sid = src.get("source_id", "S?")
            title = _EMPTY_TITLE_TAIL.sub("", str(src.get("title") or "").strip()) or "—"
            lines.append(
                f"- **[{sid}]** `{src.get('source_type', '—')}` — {title} — "
                f"{src.get('reference', '—')} *({t['src.date']}: {src.get('date') or '—'}؛ "
                f"{t['src.confidence']}: {src.get('confidence', '—')})*"
                if lang == "ar"
                else f"- **[{sid}]** `{src.get('source_type', '—')}` — {title} — "
                f"{src.get('reference', '—')} *({t['src.date']}: {src.get('date') or '—'}; "
                f"{t['src.confidence']}: {src.get('confidence', '—')})*"
            )
        lines.append("")

    # Appendix — Report Governance: pipeline metadata for reviewers/auditors.
    # Deliberately last so the document leads with the analysis.
    lines.append(f"## {t['sec.governance']}")
    lines.append("")
    lines += [
        "| | |",
        "|---|---|",
        f"| {t['gov.request_id']} | {request_id} |",
        f"| {t['gov.report_type']} | {report_type} |",
        f"| {t['gov.language']} | {report.get('language', 'en')} |",
        f"| {t['gov.quality_gate']} | {qg_status} |",
        f"| {t['gov.completeness']} | {report.get('evidence_completeness', 'n/a')} |",
        f"| {t['gov.generated']} | {generated_at} |",
        "",
    ]
    coverage_rows = report.get("connector_coverage", [])
    lines.append(f"### {t['sec.coverage']}")
    lines.append("")
    if coverage_rows:
        lines += [
            f"| {t['cov.source']} | {t['cov.enabled']} | {t['cov.attempted']} "
            f"| {t['cov.evidence']} | {t['cov.status']} | {t['cov.reason']} |",
            "|---|---|---|---|---|---|",
        ]
        for row in coverage_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {row.get('source', '—')} "
                f"| {t['yes'] if row.get('enabled') else t['no']} "
                f"| {t['yes'] if row.get('attempted') else t['no']} "
                f"| {row.get('evidence_count', 0)} "
                f"| {row.get('status', '—')} "
                f"| {row.get('reason', '') or '—'} |"
            )
    else:
        lines.append(t["cov.none"])
    lines.append("")

    lines += [
        "---",
        "",
        f"*{t['footer']} — {generated_at}*",
    ]

    return "\n".join(lines)
