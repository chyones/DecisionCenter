"""Node 12 — Draft JSON Report. Spec: Sections 14 and 16.

Generates the canonical structured report using the heavy tier.
Every claim MUST bind to evidence_ids; financial values MUST come from Odoo.
"""

from __future__ import annotations

import json
import re

from apps.edr.graph import coverage
from apps.edr.graph.financial_evidence import filter_financial_evidence
from apps.edr.graph.intent import (
    classify_report_type,
    detect_language,
    is_management_question,
    is_salary_payroll_evidence,
)
from apps.edr.graph.project_identity import ProjectIdentity, resolve_project_identity
from apps.edr.graph.state import DecisionState
from apps.edr.llm import call_llm, sanitize_evidence

try:
    import json_repair
except Exception:  # pragma: no cover
    json_repair = None


# ---------------------------------------------------------------------------
# Odoo financial pre-extraction (deterministic — no LLM)
# ---------------------------------------------------------------------------


_FILENAME_LIKE = re.compile(
    r"\b[\w\-]+\.(pdf|xlsx?|docx?|pptx?|dwg|dxf|jpe?g|png|csv|zip|rar|txt)\b",
    re.IGNORECASE,
)

# A currency amount asserted inside claim text (figures must stay Odoo-led).
_AMOUNT_IN_TEXT_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:AED|SAR|USD|EUR|درهم|ريال)", re.IGNORECASE
)


def _coerce_number(value) -> float | None:
    """Coerce a scalar to float, rejecting bools and non-numeric strings."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", ""))
        except ValueError:
            return None
    return None


def _amount_from_excerpt(excerpt: str) -> float | None:
    """Parse a cost amount from an evidence excerpt.

    Supports the live n8n format ("name: X; amount: -100.0; date: ...") and the
    legacy "Category / Amount / Date" layout. Returns None when no amount found.
    """
    if not excerpt:
        return None
    m = re.search(r"amount\s*[:=]\s*(-?[\d,]+(?:\.\d+)?)", excerpt, re.IGNORECASE)
    if m:
        val = _coerce_number(m.group(1))
        if val is not None:
            return val
    parts = [p.strip() for p in excerpt.split(" / ")]
    if len(parts) >= 2:
        return _coerce_number(parts[1])
    return None


def _date_from_excerpt(excerpt: str) -> str:
    if not excerpt:
        return ""
    m = re.search(r"date\s*[:=]\s*(\d{4}-\d{2}-\d{2}[^;]*)", excerpt, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    parts = [p.strip() for p in excerpt.split(" / ")]
    return parts[2] if len(parts) >= 3 else ""


def _is_cost_line(ev: dict) -> bool:
    """True only for analytic *line* / move *line* cost rows.

    The analytic *account* identity row carries a balance but is not a cost line
    and must never be summed as one.
    """
    uri = str(ev.get("source_uri", "")).lower()
    model = str((ev.get("metadata") or {}).get("model", "")).lower()
    hay = uri + " " + model
    return "analytic.line" in hay or "account.move.line" in hay


def _cost_line_amount(line: dict) -> float | None:
    """Cost amount: prefer structured f_amount metadata, fall back to excerpt."""
    meta = line.get("metadata") or {}
    val = _coerce_number(meta.get("f_amount"))
    if val is not None:
        return val
    return _amount_from_excerpt(line.get("excerpt", ""))


def _cost_line_date(line: dict) -> str:
    meta = line.get("metadata") or {}
    d = meta.get("f_date")
    if isinstance(d, str) and d.strip():
        return d.strip()
    ts = line.get("timestamp")
    if isinstance(ts, str) and ts.strip():
        return ts.strip()
    return _date_from_excerpt(line.get("excerpt", ""))


def _cost_line_category(line: dict) -> str:
    meta = line.get("metadata") or {}
    ga = meta.get("f_general_account_id")
    if isinstance(ga, list) and len(ga) >= 2 and isinstance(ga[1], str) and ga[1].strip():
        return ga[1].strip()
    name = meta.get("f_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    title = (line.get("title") or "").strip()
    if title and title.lower() not in ("odoo record", "odoo project record"):
        return title
    excerpt = line.get("excerpt", "")
    if " / " in excerpt:
        first = excerpt.split(" / ")[0].strip()
        if first:
            return first
    return ""


def _project_amount(
    project_records: list[dict], *meta_keys: str
) -> tuple[float | None, str | None]:
    """Read a contract/estimate figure from the project record metadata."""
    for rec in project_records:
        meta = rec.get("metadata") or {}
        for key in meta_keys:
            val = _coerce_number(meta.get(key))
            if val is not None:
                return val, rec.get("evidence_id")
    return None, None


def _extract_odoo_context(odoo_evidence: list[dict]) -> dict:
    """Pre-process Odoo evidence into structured context for the LLM prompt.

    Reads the structured ``f_*`` fields the n8n Odoo workflow emits in evidence
    metadata (``f_amount``, ``f_date``, ``f_general_account_id``, ``f_wo_amount``,
    ``f_estimation_amount``) and falls back to parsing the excerpt for older
    payloads. Financial figures are extracted deterministically so the snapshot
    can be corrected post-LLM. Only analytic *line* rows count as cost; the
    analytic *account* identity row never does.
    """
    project_records: list[dict] = []
    cost_lines: list[dict] = []
    for ev in odoo_evidence:
        if _is_cost_line(ev):
            cost_lines.append(ev)
        else:
            project_records.append(ev)

    categories: list[str] = []
    dates: list[str] = []
    total_amount = 0.0
    has_amount = False
    best_evidence_id: str | None = None
    best_date = ""

    for line in cost_lines:
        cat = _cost_line_category(line)
        if cat and cat not in categories:
            categories.append(cat)
        amt = _cost_line_amount(line)
        if amt is not None:
            total_amount += amt
            has_amount = True
        date_str = _cost_line_date(line)
        if date_str:
            dates.append(date_str)
            if date_str > best_date:
                best_date = date_str
                best_evidence_id = line.get("evidence_id")

    if best_evidence_id is None and has_amount:
        # Amounts present but no usable dates — cite the first valued cost line.
        for line in cost_lines:
            if _cost_line_amount(line) is not None and line.get("evidence_id"):
                best_evidence_id = line.get("evidence_id")
                break

    sorted_lines = sorted(cost_lines, key=_cost_line_date, reverse=True)

    contract_value, contract_eid = _project_amount(project_records, "f_wo_amount")
    estimate, estimate_eid = _project_amount(project_records, "f_estimation_amount")

    # Incurred-cost categories carried in separate Odoo models (read loosely
    # here for the executive summary; the snapshot re-binds them strictly).
    payroll_amt, payroll_eid = _sum_odoo_category(
        odoo_evidence, _PAYROLL_CATEGORIES, _PAYROLL_AMOUNT_FIELDS
    )
    expense_amt, expense_eid = _sum_odoo_category(
        odoo_evidence, _EXPENSE_CATEGORIES, _EXPENSE_AMOUNT_FIELDS
    )
    payroll_cost = abs(payroll_amt) if payroll_amt is not None else None
    expense_cost = abs(expense_amt) if expense_amt is not None else None
    incurred: list[tuple[float, str | None]] = []
    if has_amount and total_amount is not None:
        incurred.append((abs(round(total_amount, 2)), best_evidence_id))
    if payroll_cost is not None:
        incurred.append((payroll_cost, payroll_eid))
    if expense_cost is not None:
        incurred.append((expense_cost, expense_eid))
    total_incurred = round(sum(v for v, _ in incurred), 2) if incurred else None
    total_incurred_eid = incurred[0][1] if incurred else None

    return {
        "project_records": project_records,
        "cost_count": len(cost_lines),
        "categories": categories[:15],
        "total_amount": round(total_amount, 2) if has_amount else None,
        "has_amount": has_amount,
        "latest_date": max(dates) if dates else None,
        "best_evidence_id": best_evidence_id,
        "sample_lines": sorted_lines[:15],
        # Contract/estimate figures (populated once PROJECT_FIELDS includes them;
        # consumed by the dedicated financial report type — Slice 4).
        "contract_value": contract_value,
        "contract_value_evidence_id": contract_eid,
        "estimate": estimate,
        "estimate_evidence_id": estimate_eid,
        # Incurred-cost breakdown (analytic/journal is total_amount above).
        "payroll_cost": payroll_cost,
        "payroll_evidence_id": payroll_eid,
        "expense_cost": expense_cost,
        "expense_evidence_id": expense_eid,
        "total_incurred": total_incurred,
        "total_incurred_evidence_id": total_incurred_eid,
        "incurred_component_count": len(incurred),
    }


# ---------------------------------------------------------------------------
# Cohere rerank — source-aware strategy
# ---------------------------------------------------------------------------


async def _apply_rerank(state: DecisionState, evidence: list[dict]) -> tuple[list[dict], str]:
    """Source-aware evidence selection for the LLM prompt.

    Odoo and Email items are structured and critical, but large Odoo packs
    can exceed token budgets and truncate the report.  We cap Odoo at the
    most recent/relevant 20 and keep all email.  SharePoint/ownCloud items
    are reranked by Cohere and capped at the top 10 most relevant.
    state.evidence is never modified here; only the prompt list is changed.
    """
    from apps.edr.config import settings

    report_type = state.outputs.get("report_type", classify_report_type(state.query))
    if report_type == "financial":
        evidence = filter_financial_evidence(evidence, query=state.query)

    odoo_ev = [e for e in evidence if e.get("source_type") == "odoo"][:20]
    email_ev = [e for e in evidence if e.get("source_type") == "email"]
    other = [e for e in evidence if e.get("source_type") not in ("odoo", "email")]

    key = getattr(settings, "cohere_api_key", None)
    if not key or not other:
        status = "skipped_no_key" if not key else "no_doc_evidence"
        selected = odoo_ev + email_ev + other[:15]
        return selected[:50], status

    try:
        from apps.edr.retrieval.hybrid_search import SearchHit
        from apps.edr.retrieval.rerank import Reranker

        hits = [
            SearchHit(evidence_id=e.get("evidence_id", ""), score=0.0, payload=e) for e in other
        ]
        ranked_hits = await Reranker(api_key=key).rerank(state.query, hits)
        sp_ranked = [h.payload for h in ranked_hits][:10]
        selected = odoo_ev + email_ev + sp_ranked
        n_o, n_e, n_s = len(odoo_ev), len(email_ev), len(sp_ranked)
        return selected[:50], f"ok_odoo={n_o}_email={n_e}_sp={n_s}"
    except Exception as exc:
        selected = odoo_ev + email_ev + other[:10]
        return selected[:50], f"fallback:{type(exc).__name__}"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt(
    state: DecisionState,
    prompt_evidence: list[dict],
    *,
    report_type: str,
    project_identity: ProjectIdentity,
    language: str = "en",
) -> str:
    odoo_ev = [e for e in prompt_evidence if e.get("source_type") == "odoo"]
    email_ev = [e for e in prompt_evidence if e.get("source_type") == "email"]
    sp_ev = [
        e for e in prompt_evidence if e.get("source_type") in ("sharepoint", "owncloud", "cad")
    ]

    odoo_ctx = _extract_odoo_context(odoo_ev)

    role = state.role or "unknown"
    can_see_finance = role in (
        "executive",
        "project_manager",
        "finance",
        "commercial",
        "procurement",
        "legal",
    )

    # --- Odoo block ---
    odoo_lines: list[str] = []
    if odoo_ctx["project_records"]:
        rec = odoo_ctx["project_records"][0]
        safe_ex, _ = sanitize_evidence(rec.get("excerpt", ""))
        odoo_lines.append(f"PROJECT RECORD [{rec.get('evidence_id', '')}]:\n{safe_ex}")
    if odoo_ctx["cost_count"] > 0:
        odoo_lines.append(
            f"\nCOST EVIDENCE SUMMARY ({odoo_ctx['cost_count']} analytic lines):\n"
            f"  Budget: NOT PRESENT in these records (analytic lines encode expenses, not budget)\n"
            + (
                f"  Total tracked expense: {odoo_ctx['total_amount']} AED\n"
                if odoo_ctx["has_amount"]
                else ""
            )
            + f"  Cost categories: {', '.join(odoo_ctx['categories'][:10]) or 'none extracted'}\n"
            + (
                f"  Latest record date: {odoo_ctx['latest_date']}\n"
                if odoo_ctx["latest_date"]
                else ""
            )
        )
        sample_excerpts = []
        for line in odoo_ctx["sample_lines"]:
            safe_ex, _ = sanitize_evidence(line.get("excerpt", ""))
            sample_excerpts.append(f"  [{line.get('evidence_id', '')}] {safe_ex}")
        odoo_lines.append("Representative cost lines:\n" + "\n".join(sample_excerpts))
    odoo_section = "\n".join(odoo_lines) if odoo_lines else "No Odoo data available."

    # --- SharePoint / document block ---
    sp_lines: list[str] = []
    for ev in sp_ev[:8]:
        safe_ex, _ = sanitize_evidence(ev.get("excerpt", "") or ev.get("title", ""))
        sp_lines.append(
            f"[{ev.get('evidence_id', '')}] {ev.get('title', 'Untitled')}:\n{safe_ex[:200]}"
        )
    sp_section = "\n\n".join(sp_lines) if sp_lines else "No document evidence available."

    # --- Email block ---
    email_lines: list[str] = []
    for ev in email_ev:
        safe_ex, _ = sanitize_evidence(ev.get("excerpt", ""))
        email_lines.append(
            f"[{ev.get('evidence_id', '')}] Subject: {ev.get('title', 'No subject')}\n{safe_ex[:200]}"
        )
    email_section = "\n\n".join(email_lines) if email_lines else "No email evidence available."

    # Pre-computed financial hint so the LLM can fill the snapshot correctly
    actual_hint = (
        f"actual_cost: status='available', value={odoo_ctx['total_amount']}, "
        f"evidence_id='{odoo_ctx['best_evidence_id'] or ''}'"
        if odoo_ctx["has_amount"]
        else "actual_cost: status='not_available' (no cost lines in evidence)"
    )

    compactness_instruction = (
        "BREVITY RULE — The full JSON response must fit within the 12,000-token output limit.\n"
        "Keep every field concise. Strict limits:\n"
        "- executive_summary: exactly 1 object (4-6 sentences).\n"
        "- key_findings: at most 5 objects, each 1 sentence.\n"
        "- recommended_actions: at most 3 objects.\n"
        "- sources: only for evidence actually cited in the report.\n"
        "- management_question_answer: executive_answer = 1 sentence; why_biggest_problem = 3 short bullets;\n"
        "  business_impact fields = 1 sentence each; decision_required = 1 sentence;\n"
        "  recommended_action fields = short; risks_if_no_action = 1 sentence; missing_evidence_or_assumptions = 1 sentence.\n"
    )

    if report_type == "salary_payroll":
        intent_instruction = (
            "SALARY / PAYROLL DATA REPORT MODE — The user asked for HR/payroll data.\n"
            "Treat salary/payroll as sensitive HR/Finance data.\n"
            "- If verified salary/payroll evidence exists, produce a compact table with columns: "
            "Staff Name, File ID, Role/Trade, Salary/Cost, Period, Source, Confidence.\n"
            "- If salary/payroll evidence is NOT present, return a professional AVAILABILITY report, NOT a fake table.\n"
            "- DO NOT generate management_question_answer, root_causes, delay_analysis, or contractual_implications.\n"
            "- DO NOT use 'biggest problem' framing.\n"
            "- DO NOT infer salary information from construction documents, MIRs, schedules, or general correspondence.\n"
            "- For timed-out sources say 'not confirmed' or 'inconclusive', NEVER 'empty' or 'no data'.\n"
            "- For successfully searched sources without salary matches, say 'no salary records found'.\n"
            "- Confidence must be low or medium when evidence is partial or a relevant source timed out.\n"
            "- Include a 'what_was_checked' summary and a 'required_data' list.\n"
        )
    elif report_type == "management_question":
        intent_instruction = (
            "MANAGEMENT QUESTION MODE — The user asked a focused decision question.\n"
            "Your report must read like an executive decision memo, NOT a search summary.\n"
            "- In MANAGEMENT_QUESTION_ANSWER, name exactly ONE biggest problem in executive_answer.\n"
            "- why_biggest_problem: 3-5 bullets, each tied to a specific evidence_id.\n"
            "- business_impact: separate schedule, cost/commercial, and operational/client impact.\n"
            "- decision_required: state what management must decide now.\n"
            "- recommended_action: specific_action, owner_role, timeframe.\n"
            "- risks_if_no_action: concise.\n"
            "- confidence: high/medium/low, with missing_evidence_or_assumptions.\n"
            "- If evidence is insufficient, say so; do not invent.\n"
            "- The executive_summary and key_findings must support the decision memo, not catalogue evidence.\n"
        )
    elif report_type == "data_report":
        intent_instruction = (
            "DATA REPORT MODE — The user asked for a specific data extraction or list.\n"
            "- Answer the query directly with a compact table or list when possible.\n"
            "- DO NOT generate management_question_answer or 'biggest problem' framing.\n"
            "- Only include sections relevant to the query; omit root_causes/delay_analysis/contractual_implications unless requested.\n"
            "- Cite evidence_ids for every row/fact.\n"
            "- If data is unavailable, explain which sources were checked and what is required.\n"
        )
    elif report_type == "financial":
        intent_instruction = (
            "FINANCIAL REPORT MODE — The user asked for project financials.\n"
            "- Separate and LABEL distinct figures: contract value/estimate, actual cost, "
            "committed cost, purchase orders, invoices, supplier/subcontractor cost, and "
            "labor/salary (only if available). NEVER merge them into one number.\n"
            "- Every financial number MUST carry an Odoo evidence_id; if a figure has no "
            "Odoo evidence, mark it not_available. Do NOT fabricate budget, cost, or salary.\n"
            "- If an Odoo source timed out say 'inconclusive'; if a model/source is not "
            "mapped say 'source not accessible' — NEVER 'no data' or 'empty'.\n"
            "- DO NOT generate management_question_answer or 'biggest problem' framing.\n"
            "- Omit root_causes/delay_analysis/contractual_implications.\n"
            "- executive_summary states what financial data IS and IS NOT available, with "
            "every figure bound to its Odoo evidence_id.\n"
        )
    elif report_type == "risk":
        intent_instruction = (
            "RISK REPORT MODE — The user asked about project risks/claims/exposure.\n"
            "- Surface the risk view via key_findings (one per risk), root_causes, and "
            "contractual_implications; tie each to a specific evidence_id.\n"
            "- DO NOT use the financial snapshot or management decision-memo framing.\n"
            "- DO NOT fabricate risks; if no risk evidence is found, say so and list what "
            "was checked in missing_data.\n"
            "- Confidence must reflect evidence quality; cap it when sources are partial or "
            "timed out.\n"
        )
    elif report_type == "delay":
        intent_instruction = (
            "DELAY REPORT MODE — The user asked about schedule delay / EOT / time impact.\n"
            "- Populate delay_analysis with specific delay events (revisions, EOT, "
            "extensions, slippage) tied to evidence_ids, and root_causes where supported.\n"
            "- DO NOT use the financial snapshot, contractual_implications, or management "
            "decision-memo framing unless the evidence is specifically contractual.\n"
            "- If no delay events are found, say so explicitly and add to missing_data; do "
            "NOT invent delays.\n"
            "- Timed-out sources are 'inconclusive', never 'no data'.\n"
        )
    elif report_type == "document_search":
        intent_instruction = (
            "DOCUMENT SEARCH MODE — The user asked to find or list documents.\n"
            "- Return a compact list of the located documents in key_findings (title + "
            "reference), each with an evidence_id; put full references in sources.\n"
            "- DO NOT generate financial_snapshot, management_question_answer, root_causes, "
            "delay_analysis, or contractual_implications.\n"
            "- This is a retrieval/listing answer: do NOT analyse or infer conclusions.\n"
            "- If nothing matched, say which sources were searched and that no matching "
            "documents were found.\n"
        )
    else:
        intent_instruction = (
            "GENERAL PROJECT STATUS MODE — Provide a concise project status summary.\n"
            "- DO NOT generate management_question_answer unless the query is a decision question.\n"
            "- Focus on verified facts and cite evidence_ids.\n"
        )

    identity_block = (
        f"Project Identity:\n"
        f"- Project Code: {project_identity.project_code}\n"
        f"- Project Name: {project_identity.project_name}\n"
        f"- Identity Source: {project_identity.identity_source}\n"
        f"- Identity Confidence: {project_identity.identity_confidence}\n"
    )
    if project_identity.missing_identity_evidence:
        identity_block += (
            "- Missing Identity Evidence: "
            + "; ".join(project_identity.missing_identity_evidence)
            + "\n"
        )

    return (
        "You are an executive decision-support analyst for a construction company.\n"
        "Generate a FULLY POPULATED structured JSON report. Every required section must have real content.\n\n"
        f"Report type: {report_type}\n"
        f"Report title/header format: <Report Type> — {project_identity.project_name} — {project_identity.project_code}\n\n"
        f"{identity_block}\n"
        "ABSOLUTE RULES:\n"
        "1. Every claim MUST carry at least one evidence_id from the evidence listed below.\n"
        "2. Every financial number MUST carry an Odoo evidence_id.\n"
        "3. Do NOT invent facts, numbers, or dates not present in the evidence.\n"
        '4. VALID JSON ONLY: every string value must be on a single line; escape double quotes with \\" and newlines with \\n.\n'
        "5. KEY_FINDINGS must be synthesized analytical insights — NEVER raw filenames or document titles.\n"
        "   CORRECT: 'Four successive BOQ revisions indicate ongoing scope changes into Q1 2026.'\n"
        "   WRONG:   'BOQ Revision 4.xlsx', 'Project_Schedule_Rev3.pdf'\n"
        "6. EXECUTIVE_SUMMARY must directly answer the user's query in 4–8 sentences.\n"
        "7. MISSING_DATA must list every item that could not be determined, including budget.\n"
        "8. If a source timed out, say 'not confirmed' or 'inconclusive'; NEVER say it returned no data.\n\n"
        "LANGUAGE RULE — The user asked in "
        + ("Arabic" if language == "ar" else "English")
        + f' (code: "{language}").\n'
        "Write ALL narrative text — executive_summary claims, key_findings, root_causes, "
        "delay_analysis, contractual_implications, recommended_actions, missing_data, conflicts, "
        "and management_question_answer — in that language, in a formal executive register.\n"
        "Keep evidence_ids, JSON keys, currency codes, and record references unchanged. "
        f'Set "language" to "{language}".\n\n'
        f"{compactness_instruction}\n"
        f"{intent_instruction}\n"
        f"User role: {role} | Can view financials: {can_see_finance}\n"
        f"Query: {state.query}\n"
        f"Project code: {state.project_code}\n"
        f"Request ID: {state.request_id}\n\n"
        "=== ODOO ERP DATA ===\n"
        f"{odoo_section}\n\n"
        "=== SHAREPOINT DOCUMENTS (top by relevance) ===\n"
        f"{sp_section}\n\n"
        "=== EMAIL CONVERSATIONS ===\n"
        f"{email_section}\n\n"
        "=== EXTRACTION GUIDE ===\n\n"
        "FINANCIAL_SNAPSHOT:\n"
        "  budget → always: value=null, evidence_id=null, status='not_available'\n"
        f"  {actual_hint}\n"
        "  variance → always: value=null, formula=null, status effectively 'not_available'\n\n"
        "DELAY_ANALYSIS:\n"
        "  Look for: revision numbers (Rev N), 'update', 'extension', 'EOT', delay keywords in titles/excerpts.\n"
        "  If delay signals found: produce specific findings with evidence_ids.\n"
        "  If none found: leave delay_analysis empty and add to missing_data.\n\n"
        "CROSS-PROJECT CONTAMINATION:\n"
        "  If any document references a project other than the current one, add a conflict entry.\n\n"
        "MISSING_DATA must always include at minimum:\n"
        "  - 'Project budget (AED): not available in Odoo analytic line records'\n"
        "  - Any other section that could not be substantiated from the evidence.\n\n"
        "Return JSON matching this exact schema:\n"
        "{\n"
        '  "request_id": "string",\n'
        '  "project_code": "string or null",\n'
        '  "query": "string",\n'
        f'  "language": "{language}",\n'
        '  "executive_summary": [\n'
        '    {"claim": "direct answer to the user query in 4-8 sentences", "evidence_ids": ["ev_..."], "confidence": "high|medium|low"}\n'
        "  ],\n"
        '  "financial_snapshot": {\n'
        '    "budget": {"value": null, "currency": "AED", "evidence_id": null, "status": "not_available"},\n'
        '    "actual_cost": {"value": null_or_number, "currency": "AED", "evidence_id": null_or_id, "status": "available|not_available"},\n'
        '    "variance": {"value": null, "currency": "AED", "formula": null, "evidence_ids": []}\n'
        "  },\n"
        '  "key_findings": [{"text": "synthesized insight from evidence", "evidence_ids": ["ev_..."], "confidence": "high|medium|low"}],\n'
        '  "root_causes": [...],\n'
        '  "delay_analysis": [...],\n'
        '  "contractual_implications": [...],\n'
        '  "recommended_actions": [{"text": "...", "evidence_ids": ["ev_..."], "confidence": "high|medium|low"}],\n'
        '  "management_question_answer": {\n'
        '    "executive_answer": "One clear sentence naming the biggest problem or decision.",\n'
        '    "why_biggest_problem": ["bullet 1 tied to evidence", "bullet 2", "bullet 3"],\n'
        '    "evidence_used": ["source type: short summary", "..."],\n'
        '    "business_impact": {\n'
        '      "schedule_impact": "...",\n'
        '      "cost_commercial_impact": "...",\n'
        '      "operational_client_impact": "..."\n'
        "    },\n"
        '    "decision_required": "what management must decide now",\n'
        '    "recommended_action": {\n'
        '      "specific_action": "...",\n'
        '      "owner_role": "...",\n'
        '      "timeframe": "..."\n'
        "    },\n"
        '    "risks_if_no_action": "concise",\n'
        '    "confidence": "high|medium|low",\n'
        '    "missing_evidence_or_assumptions": "..."\n'
        "  },\n"
        '  "missing_data": ["Project budget (AED): not available in Odoo analytic line records", ...],\n'
        '  "conflicts": [...],\n'
        '  "sources": [{"source_id": "S1", "source_type": "sharepoint|odoo|email", "title": "...", "reference": "...", "date": "...", "confidence": "...", "used_in": ["section"]}]\n'
        "}\n"
    )


# ---------------------------------------------------------------------------
# Post-LLM deterministic corrections
# ---------------------------------------------------------------------------


def _enforce_financial_from_odoo(report: dict, odoo_ctx: dict, evidence_ids: set[str]) -> None:
    """Enforce accurate financial snapshot from deterministic Odoo extraction.

    If the LLM left actual_cost as not_available but we have analytic lines
    with a computable total, correct it here so the report is factually right.
    """
    fs = report.get("financial_snapshot")
    if not isinstance(fs, dict):
        return

    # Budget is always not_available from analytic lines
    budget = fs.get("budget")
    if isinstance(budget, dict):
        budget["status"] = "not_available"
        budget["value"] = None
        budget.setdefault("currency", "AED")
        budget["evidence_id"] = None

    # Actual cost from analytic sum — deterministic truth; always override LLM guess.
    actual = fs.get("actual_cost")
    if isinstance(actual, dict):
        # Some LLM outputs stuff multiple ids into a comma-separated evidence_id
        # string or a leftover evidence_ids list. Normalize to one valid id first.
        raw_eid = actual.get("evidence_id")
        if isinstance(raw_eid, str) and "," in raw_eid:
            for cand in (c.strip() for c in raw_eid.split(",")):
                if cand in evidence_ids:
                    actual["evidence_id"] = cand
                    actual.pop("evidence_ids", None)
                    break
        eids_list = actual.get("evidence_ids")
        if isinstance(eids_list, list) and eids_list and not actual.get("evidence_id"):
            for cand in eids_list:
                if cand in evidence_ids:
                    actual["evidence_id"] = cand
                    break

        if odoo_ctx.get("has_amount"):
            # Prefer the most recent analytic line; fall back to any sample line.
            eid = odoo_ctx.get("best_evidence_id") or ""
            if eid not in evidence_ids:
                for line in odoo_ctx.get("sample_lines", []):
                    cand = line.get("evidence_id", "")
                    if cand in evidence_ids:
                        eid = cand
                        break
            if eid in evidence_ids:
                actual["status"] = "available"
                actual["value"] = odoo_ctx["total_amount"]
                actual["currency"] = "AED"
                actual["evidence_id"] = eid
                actual.pop("evidence_ids", None)

        # Final safety: if the field is still marked available with an invalid id,
        # demote it to not_available so the QG does not flag an unsupported citation.
        if actual.get("status") == "available" and actual.get("evidence_id") not in evidence_ids:
            actual["status"] = "not_available"
            actual["value"] = None
            actual["evidence_id"] = None


# Extended-source financial categories: category -> ordered candidate f_* amount fields.
_COMMITTED_CATEGORIES = ("purchase_orders", "purchase_order_lines")
_COMMITTED_AMOUNT_FIELDS = ("f_amount_total", "f_price_subtotal", "f_price_total", "f_amount_untaxed")
_PAYROLL_CATEGORIES = ("payroll_cost_allocation",)
_PAYROLL_AMOUNT_FIELDS = ("f_amount", "f_total")
_EXPENSE_CATEGORIES = ("hr_expenses",)
_EXPENSE_AMOUNT_FIELDS = ("f_total_amount", "f_unit_amount")


def _fin_node(fs: dict, key: str) -> dict:
    node = fs.get(key)
    if not isinstance(node, dict):
        node = {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"}
        fs[key] = node
    return node


def _set_fin_available(fs: dict, key: str, value: float, evidence_id: str) -> None:
    node = _fin_node(fs, key)
    node["value"] = value
    node["currency"] = "AED"
    node["evidence_id"] = evidence_id
    node["status"] = "available"


def _sum_odoo_category(
    odoo_evidence: list[dict],
    categories: tuple[str, ...],
    amount_fields: tuple[str, ...],
    evidence_ids: set[str] | None = None,
) -> tuple[float | None, str | None]:
    """Sum one financial category from tagged extended Odoo evidence.

    Read-only; never fabricates. Sums only explicit f_* amount metadata on
    evidence the pack actually contains. Returns (total, evidence_id) or
    (None, None) when no backed amount exists.
    """
    total = 0.0
    found = False
    eid: str | None = None
    for ev in odoo_evidence:
        meta = ev.get("metadata") or {}
        if meta.get("odoo_category") not in categories:
            continue
        amt = None
        for field in amount_fields:
            amt = _coerce_number(meta.get(field))
            if amt is not None:
                break
        if amt is None:
            continue
        total += amt
        found = True
        cand = ev.get("evidence_id")
        if eid is None and cand and (evidence_ids is None or cand in evidence_ids):
            eid = cand
    if found and eid:
        return round(total, 2), eid
    return None, None


def _enforce_financial_categories(
    report: dict,
    odoo_ctx: dict,
    odoo_evidence: list[dict],
    evidence_ids: set[str],
) -> None:
    """Populate distinct financial figures from Odoo without mixing or fabricating.

    Each figure is set only when a real Odoo evidence_id backs it; otherwise it
    stays not_available. contract_value/estimate come from the project.project
    record; committed_cost from purchase orders / PO lines (extended sources).
    """
    fs = report.get("financial_snapshot")
    if not isinstance(fs, dict):
        return
    cv, cv_eid = odoo_ctx.get("contract_value"), odoo_ctx.get("contract_value_evidence_id")
    if cv not in (None, 0) and cv_eid in evidence_ids:
        _set_fin_available(fs, "contract_value", cv, cv_eid)
    else:
        _fin_node(fs, "contract_value")
    est, est_eid = odoo_ctx.get("estimate"), odoo_ctx.get("estimate_evidence_id")
    if est not in (None, 0) and est_eid in evidence_ids:
        _set_fin_available(fs, "estimate", est, est_eid)
    else:
        _fin_node(fs, "estimate")
    committed, c_eid = _sum_odoo_category(
        odoo_evidence, _COMMITTED_CATEGORIES, _COMMITTED_AMOUNT_FIELDS, evidence_ids
    )
    if committed is not None and c_eid:
        _set_fin_available(fs, "committed_cost", committed, c_eid)
    else:
        _fin_node(fs, "committed_cost")

    # Incurred-cost categories beyond analytic/journal lines: staff payroll and
    # HR expenses (petty cash, vehicle, fuel). Each evidence-bound or left unset.
    payroll = odoo_ctx.get("payroll_cost")
    p_eid = odoo_ctx.get("payroll_evidence_id")
    if payroll is not None and p_eid in evidence_ids:
        _set_fin_available(fs, "payroll_cost", payroll, p_eid)
    else:
        _fin_node(fs, "payroll_cost")
    expense = odoo_ctx.get("expense_cost")
    e_eid = odoo_ctx.get("expense_evidence_id")
    if expense is not None and e_eid in evidence_ids:
        _set_fin_available(fs, "expense_cost", expense, e_eid)
    else:
        _fin_node(fs, "expense_cost")

    # Total incurred = sum of the evidence-backed incurred-cost categories present
    # in THIS evidence pack. Recomputed from the snapshot fields just set, so it
    # never includes a figure that is not itself evidence-bound. Committed (LPO/PO)
    # is a commitment, not spend, and is deliberately excluded.
    incurred_parts = []
    for _k in ("actual_cost", "payroll_cost", "expense_cost"):
        _n = fs.get(_k)
        if isinstance(_n, dict) and _n.get("status") == "available" and _n.get("value") is not None:
            incurred_parts.append((_k, abs(_n["value"]), _n.get("evidence_id")))
    if incurred_parts:
        _total = round(sum(v for _, v, _ in incurred_parts), 2)
        _set_fin_available(fs, "total_incurred", _total, incurred_parts[0][2])
        if len(incurred_parts) > 1:
            fs["note"] = (
                "Total Incurred sums the evidence-backed cost categories retrieved this run "
                "(" + ", ".join(k for k, _, _ in incurred_parts) + "). In Odoo, payroll and "
                "HR expenses can also post journal/analytic lines, so this total may double-count "
                "until reconciled against the analytic ledger. Committed (LPO/PO) cost is shown "
                "separately and is not part of this total."
            )
    else:
        _fin_node(fs, "total_incurred")

    # Derived variance: estimate (cost baseline) vs incurred cost. Uses the
    # broader Total Incurred only when the breakdown adds categories beyond the
    # analytic/journal Actual Cost; otherwise the two are identical and the
    # simpler formula is kept. Evidence-bound; only when BOTH inputs are
    # available. Contract value (revenue/WO) and committed cost are never folded
    # into this comparison.
    est_node = fs.get("estimate") if isinstance(fs.get("estimate"), dict) else {}
    _n_incurred = sum(
        1
        for _k in ("actual_cost", "payroll_cost", "expense_cost")
        if isinstance(fs.get(_k), dict)
        and fs[_k].get("status") == "available"
        and fs[_k].get("value") is not None
    )
    _total_node = fs.get("total_incurred") if isinstance(fs.get("total_incurred"), dict) else {}
    if _n_incurred > 1 and _total_node.get("status") == "available":
        spent_node = _total_node
        spent_formula = "estimate - total_incurred"
    else:
        spent_node = fs.get("actual_cost") if isinstance(fs.get("actual_cost"), dict) else {}
        spent_formula = "estimate - actual_cost"
    var_node = fs.get("variance")
    if not isinstance(var_node, dict):
        var_node = {"value": None, "currency": "AED", "formula": None, "evidence_ids": []}
        fs["variance"] = var_node
    if (
        est_node.get("status") == "available"
        and spent_node.get("status") == "available"
        and est_node.get("value")  # non-zero estimate baseline only
        and spent_node.get("value") is not None
    ):
        spent = abs(spent_node["value"])
        var_node["value"] = round(est_node["value"] - spent, 2)
        var_node["currency"] = "AED"
        var_node["formula"] = spent_formula
        var_node["evidence_ids"] = [
            e for e in (est_node.get("evidence_id"), spent_node.get("evidence_id")) if e
        ]


def _normalize_financial_snapshot(report: dict) -> None:
    """Move any top-level financial keys into the canonical financial_snapshot block.

    Some LLM/repair outputs place actual_cost, budget, planned_cost, etc. at the
    top level. Map them back into financial_snapshot and normalize actual_cost
    so it always uses a singular evidence_id string.
    """
    if not isinstance(report, dict):
        return

    fs = report.get("financial_snapshot")
    if not isinstance(fs, dict):
        fs = {
            "budget": {
                "value": None,
                "currency": "AED",
                "evidence_id": None,
                "status": "not_available",
            },
            "actual_cost": {
                "value": None,
                "currency": "AED",
                "evidence_id": None,
                "status": "not_available",
            },
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        }
        report["financial_snapshot"] = fs

    # Map loose top-level keys into the snapshot.
    top_level_aliases = {
        "actual_total": "actual_cost",
        "estimated_total": "actual_cost",
        "committed_total": "actual_cost",
        "planned_cost": "budget",
    }
    for alias, target in top_level_aliases.items():
        node = report.pop(alias, None)
        if isinstance(node, dict):
            fs.setdefault(target, {})
            for k, v in node.items():
                if k == "evidence_ids" and target == "actual_cost":
                    # Coerce list to singular evidence_id on the canonical field.
                    eids = v if isinstance(v, list) else [v]
                    if eids:
                        fs[target]["evidence_id"] = eids[0]
                else:
                    fs[target][k] = v

    # Ensure actual_cost uses evidence_id, not evidence_ids.
    actual = fs.get("actual_cost")
    if isinstance(actual, dict):
        eids = actual.get("evidence_ids")
        if isinstance(eids, list) and eids and not actual.get("evidence_id"):
            actual["evidence_id"] = eids[0]
        actual.pop("evidence_ids", None)

    # Ensure variance has evidence_ids list.
    variance = fs.get("variance")
    if isinstance(variance, dict):
        variance.setdefault("evidence_ids", [])
        variance.pop("evidence_id", None)


def _is_placeholder_text(text: str) -> bool:
    """Detect strings that are clearly schema examples or ellipses."""
    if not text:
        return True
    lowered = text.lower().strip()
    placeholders = {
        "...",
        "synthesized insight from evidence",
        "one clear sentence naming the biggest problem or decision",
        "what management must decide now",
        "concise",
        "bullet 1 tied to evidence",
        "bullet 2",
        "bullet 3",
    }
    if lowered in placeholders:
        return True
    if lowered.startswith("source type:"):
        return True
    return False


def _is_filename_or_title_only(ev: dict) -> bool:
    """True when the visible text is only a filename/title surrogate."""
    excerpt = str(ev.get("excerpt") or "").strip()
    title = str(ev.get("title") or "").strip()
    if not excerpt:
        return True
    if _FILENAME_LIKE.search(excerpt):
        return True
    if title and excerpt.lower() == title.lower():
        return True
    title_stem = re.sub(r"\.(pdf|xlsx?|docx?|pptx?|dwg|dxf|csv)$", "", title, flags=re.I)
    title_tokens = set(re.findall(r"[a-z0-9]+", title_stem.lower()))
    excerpt_tokens = set(re.findall(r"[a-z0-9]+", excerpt.lower()))
    if title_tokens and excerpt_tokens and excerpt_tokens.issubset(title_tokens):
        return True
    return False


#: Snapshot field -> per-language display label for deterministic findings.
_FIN_FIELD_LABELS: dict[str, dict[str, str]] = {
    "contract_value": {"en": "contract value", "ar": "قيمة العقد"},
    "estimate": {"en": "cost estimate", "ar": "التكلفة التقديرية"},
    "actual_cost": {
        "en": "actual cost (analytic/journal) to date",
        "ar": "التكلفة الفعلية حتى تاريخه (قيود تحليلية)",
    },
    "payroll_cost": {"en": "payroll / staff cost", "ar": "تكلفة الرواتب والموظفين"},
    "expense_cost": {
        "en": "expenses (petty cash, vehicle, fuel)",
        "ar": "المصروفات النثرية (عهدة/سيارات/وقود)",
    },
    "committed_cost": {"en": "committed cost (LPO/PO)", "ar": "التكاليف الملتزم بها (أوامر الشراء)"},
    "total_incurred": {
        "en": "total incurred cost to date",
        "ar": "إجمالي التكلفة المتكبدة حتى تاريخه",
    },
}


def _financial_snapshot_findings(
    report: dict, odoo_ctx: dict, language: str = "en"
) -> list[dict]:
    """Build executive-facing financial findings from Odoo-backed snapshot fields."""
    fs = report.get("financial_snapshot") or {}
    if not isinstance(fs, dict):
        return []
    lang = "ar" if language == "ar" else "en"

    findings: list[dict] = []
    for key in (
        "contract_value",
        "estimate",
        "actual_cost",
        "payroll_cost",
        "expense_cost",
        "committed_cost",
        "total_incurred",
    ):
        node = fs.get(key)
        if not isinstance(node, dict) or node.get("status") != "available":
            continue
        value = node.get("value")
        eid = node.get("evidence_id")
        if value is None or not eid:
            continue
        display_value = (
            abs(value)
            if key
            in ("actual_cost", "payroll_cost", "expense_cost", "total_incurred", "committed_cost")
            else value
        )
        label = _FIN_FIELD_LABELS[key][lang]
        text = (
            f"يُظهر نظام Odoo أن {label} تبلغ {display_value:,.2f} درهم."
            if lang == "ar"
            else f"Odoo shows {label} of {display_value:,.2f} AED."
        )
        findings.append(
            {
                "text": text,
                "evidence_ids": [eid],
                "confidence": "medium",
            }
        )

    variance = fs.get("variance")
    if isinstance(variance, dict) and variance.get("value") is not None:
        eids = _flatten_eids(variance.get("evidence_ids", []))
        if eids:
            if lang == "ar":
                text = (
                    f"الفرق مقارنةً بالتكلفة التقديرية في Odoo هو {variance['value']:,.2f} درهم "
                    f"وفق {variance.get('formula') or 'مدخلات موثقة'}."
                )
            else:
                text = (
                    f"Variance against the Odoo cost estimate is "
                    f"{variance['value']:,.2f} AED using {variance.get('formula') or 'verified inputs'}."
                )
            findings.append(
                {
                    "text": text,
                    "evidence_ids": eids,
                    "confidence": "medium",
                }
            )
    elif findings:
        eids = [f["evidence_ids"][0] for f in findings if f.get("evidence_ids")]
        findings.append(
            {
                "text": (
                    "لا يُحتسب فرق الميزانية لعدم توفر خط أساس (ميزانية/تقدير) غير صفري في Odoo."
                    if lang == "ar"
                    else (
                        "Budget or variance is not reported because no non-zero Odoo "
                        "budget/estimate baseline was available for that calculation."
                    )
                ),
                "evidence_ids": list(dict.fromkeys(eids))[:2],
                "confidence": "low",
            }
        )

    if not findings:
        project_ids = [
            e.get("evidence_id")
            for e in odoo_ctx.get("project_records", [])
            if isinstance(e, dict) and e.get("evidence_id")
        ]
        if project_ids:
            findings.append(
                {
                    "text": (
                        "تم العثور على سجل المشروع في Odoo، لكن لا تتوفر مبالغ تكلفة أو ميزانية "
                        "أو أوامر شراء أو فواتير قابلة للاستخدام."
                        if lang == "ar"
                        else (
                            "Odoo project evidence was found, but no usable Odoo cost, "
                            "budget, purchase order, invoice, or payment amount was available."
                        )
                    ),
                    "evidence_ids": list(dict.fromkeys(project_ids))[:2],
                    "confidence": "low",
                }
            )
    return findings[:8]


def _empty_management_question_answer() -> dict:
    return {
        "executive_answer": "",
        "why_biggest_problem": [],
        "evidence_used": [],
        "business_impact": {
            "schedule_impact": "",
            "cost_commercial_impact": "",
            "operational_client_impact": "",
        },
        "decision_required": "",
        "recommended_action": {"specific_action": "", "owner_role": "", "timeframe": ""},
        "risks_if_no_action": "",
        "confidence": "low",
        "missing_evidence_or_assumptions": "",
    }


def _force_financial_odoo_synthesis(
    report: dict,
    state: DecisionState,
    odoo_ctx: dict,
    project_identity: ProjectIdentity,
    language: str = "en",
) -> None:
    """Keep financial figures Odoo-led without discarding the LLM narrative.

    Deterministic snapshot findings lead key_findings (every number bound to
    its Odoo record). LLM findings that do not assert their own currency
    amounts are kept after them; the LLM executive summary is kept when it has
    real content, otherwise the evidence-bound fallback summary is used.
    """
    figure_findings = _financial_snapshot_findings(report, odoo_ctx, language=language)
    narrative_findings = [
        f
        for f in report.get("key_findings", [])
        if isinstance(f, dict)
        and not _AMOUNT_IN_TEXT_RE.search(str(f.get("text", "")))
        and not _is_placeholder_text(str(f.get("text", "")))
    ]
    report["key_findings"] = (figure_findings + narrative_findings)[:8]

    es = report.get("executive_summary")
    has_llm_summary = isinstance(es, list) and any(
        isinstance(item, dict)
        and (item.get("claim") or "").strip()
        and not _is_placeholder_text(item.get("claim", ""))
        for item in es
    )
    if not has_llm_summary and (odoo_ctx.get("project_records") or odoo_ctx.get("has_amount")):
        report["executive_summary"] = _basic_executive_summary(
            state, [], [], odoo_ctx, project_identity, language=language
        )
    report["root_causes"] = []
    report["delay_analysis"] = []
    report["contractual_implications"] = []
    report["management_question_answer"] = _empty_management_question_answer()


def _report_has_valid_claims(report: dict, evidence_ids: set[str]) -> bool:
    """Return True when the report has at least one real claim with valid evidence IDs."""
    if not isinstance(report, dict):
        return False
    list_sections = (
        "executive_summary",
        "key_findings",
        "root_causes",
        "delay_analysis",
        "contractual_implications",
        "recommended_actions",
    )
    has_real_claim = False
    for section in list_sections:
        items = report.get(section)
        if not isinstance(items, list):
            return False
        for item in items:
            if not isinstance(item, dict):
                continue
            eids = _flatten_eids(item.get("evidence_ids", []))
            if not eids:
                return False
            if any(e not in evidence_ids or not e or e == "ev_..." for e in eids):
                return False
            text = item.get("text") or item.get("claim") or ""
            if not _is_placeholder_text(text):
                has_real_claim = True
    return has_real_claim


_CLAIM_SECTIONS = (
    "executive_summary",
    "key_findings",
    "root_causes",
    "delay_analysis",
    "contractual_implications",
    "recommended_actions",
)


def _salvage_llm_claims(report: dict, evidence_ids: set[str]) -> dict[str, int]:
    """Drop only the invalid claims from an LLM draft, keeping the rest.

    Previously a single claim with an unknown evidence_id discarded the whole
    LLM report in favour of the skeletal deterministic fallback. Instead, a
    claim survives when every cited evidence_id exists in the retrieved
    evidence pack and its text is not schema placeholder text; the caller
    falls back only when nothing survives. Returns dropped counts per section.
    """
    dropped: dict[str, int] = {}
    for section in _CLAIM_SECTIONS:
        items = report.get(section)
        if not isinstance(items, list):
            report[section] = []
            dropped[section] = 0 if not items else 1
            continue
        kept: list = []
        removed = 0
        for item in items:
            if not isinstance(item, dict):
                removed += 1
                continue
            eids = _flatten_eids(item.get("evidence_ids", []))
            text = item.get("text") or item.get("claim") or ""
            if (
                eids
                and all(e and e != "ev_..." and e in evidence_ids for e in eids)
                and not _is_placeholder_text(text)
            ):
                item["evidence_ids"] = eids
                kept.append(item)
            else:
                removed += 1
        report[section] = kept
        dropped[section] = removed
    return dropped


def _enrich_management_question_answer(report: dict, state: DecisionState) -> None:
    """Populate a minimal management_question_answer when the LLM left it empty or as a placeholder."""
    if not is_management_question(state.query):
        return
    mqa = report.setdefault(
        "management_question_answer",
        {
            "executive_answer": "",
            "why_biggest_problem": [],
            "evidence_used": [],
            "business_impact": {
                "schedule_impact": "",
                "cost_commercial_impact": "",
                "operational_client_impact": "",
            },
            "decision_required": "",
            "recommended_action": {"specific_action": "", "owner_role": "", "timeframe": ""},
            "risks_if_no_action": "",
            "confidence": "low",
            "missing_evidence_or_assumptions": "",
        },
    )
    if not isinstance(mqa, dict):
        mqa = report["management_question_answer"] = {
            "executive_answer": "",
            "why_biggest_problem": [],
            "evidence_used": [],
            "business_impact": {
                "schedule_impact": "",
                "cost_commercial_impact": "",
                "operational_client_impact": "",
            },
            "decision_required": "",
            "recommended_action": {"specific_action": "", "owner_role": "", "timeframe": ""},
            "risks_if_no_action": "",
            "confidence": "low",
            "missing_evidence_or_assumptions": "",
        }

    findings = [f for f in (report.get("key_findings") or []) if isinstance(f, dict)]
    first_eids = _flatten_eids(findings[0].get("evidence_ids", [])) if findings else []

    # Deterministic fallback must not present raw evidence as a synthesized
    # decision; state honestly that automated synthesis did not complete.
    if not (mqa.get("executive_answer") or "").strip() or _is_placeholder_text(
        mqa.get("executive_answer", "")
    ):
        mqa["executive_answer"] = (
            "Automated decision analysis could not be completed for this request. "
            "A reviewer must validate the retrieved evidence before a recommendation is issued."
        )

    why = mqa.get("why_biggest_problem")
    if not isinstance(why, list) or len(why) < 3 or all(_is_placeholder_text(b) for b in why):
        mqa["why_biggest_problem"] = [
            "Automated synthesis did not complete for this request.",
            "The retrieved evidence is catalogued in the Sources section for analyst review.",
            "A reviewer must confirm the facts before a management decision is taken.",
        ]

    bi = mqa.setdefault("business_impact", {})
    if not isinstance(bi, dict):
        bi = mqa["business_impact"] = {}
    if not (bi.get("schedule_impact") or "").strip():
        bi["schedule_impact"] = (
            "Potential schedule exposure cannot be quantified without further evidence."
        )
    if not (bi.get("cost_commercial_impact") or "").strip():
        bi["cost_commercial_impact"] = (
            "Commercial impact is unclear pending budget and cost baseline verification."
        )
    if not (bi.get("operational_client_impact") or "").strip():
        bi["operational_client_impact"] = (
            "Client and operational workflows may be affected; confirm with project team."
        )

    if not (mqa.get("decision_required") or "").strip() or _is_placeholder_text(
        mqa.get("decision_required", "")
    ):
        mqa["decision_required"] = (
            "Management should review the findings and decide on immediate mitigation steps."
        )

    rec = mqa.setdefault("recommended_action", {})
    if not isinstance(rec, dict):
        rec = mqa["recommended_action"] = {}
    if not (rec.get("specific_action") or "").strip():
        rec["specific_action"] = "Review the key findings with the project team and confirm facts."
    if not (rec.get("owner_role") or "").strip():
        rec["owner_role"] = "Project Manager"
    if not (rec.get("timeframe") or "").strip():
        rec["timeframe"] = "Within 5 working days"

    if not (mqa.get("risks_if_no_action") or "").strip() or _is_placeholder_text(
        mqa.get("risks_if_no_action", "")
    ):
        mqa["risks_if_no_action"] = (
            "Without action, the issue may escalate into schedule or commercial exposure."
        )

    if not (mqa.get("missing_evidence_or_assumptions") or "").strip():
        mqa["missing_evidence_or_assumptions"] = (
            "Automated synthesis was incomplete; reviewer validation required."
        )

    mqa["confidence"] = "low"
    mqa["evidence_used"] = first_eids or ["evidence catalogued in key_findings"]


def _enforce_missing_data(report: dict, odoo_ctx: dict, language: str = "en") -> None:
    """Deterministically populate missing_data with items that could not be extracted."""
    lang = "ar" if language == "ar" else "en"
    missing = report.setdefault("missing_data", [])
    if not isinstance(missing, list):
        report["missing_data"] = []
        missing = report["missing_data"]

    existing = " ".join(str(m) for m in missing).lower()

    def add(item: str, *keywords: str) -> None:
        nonlocal existing
        if not any(kw.lower() in existing for kw in keywords):
            missing.append(item)
            existing += " " + item.lower()

    report_type = report.get("report_type")

    # Budget is always missing from analytic line records
    add(
        (
            "ميزانية المشروع (درهم): غير متوفرة في سجلات القيود التحليلية في Odoo"
            if lang == "ar"
            else "Project budget (AED): not available in Odoo analytic line records"
        ),
        "budget",
        "ميزانية",
    )
    # Variance is always missing without budget
    add(
        (
            "فرق التكلفة (الميزانية مقابل الفعلي): لا يمكن احتسابه دون خط أساس للميزانية"
            if lang == "ar"
            else "Cost variance (budget vs actual): not calculable without a budget baseline"
        ),
        "variance",
        "فرق التكلفة",
    )
    # Actual cost if no cost lines
    if not odoo_ctx.get("has_amount"):
        add(
            (
                "إجمالي التكلفة الفعلية: غير متوفر — لا توجد قيود تكلفة تحليلية في الأدلة"
                if lang == "ar"
                else "Actual cost total: not available — no cost analytic lines in evidence"
            ),
            "actual cost",
            "actual_cost",
            "التكلفة الفعلية",
        )
    # Delay if delay sections empty in report types that actually render delay/root cause sections.
    if report_type not in ("financial", "salary_payroll", "data_report", "document_search") and not report.get("delay_analysis") and not report.get("root_causes"):
        add(
            (
                "تحليل التأخير: لم تُستخرج أحداث تأخير محددة من المستندات المتاحة"
                if lang == "ar"
                else "Delay analysis: no specific delay events extracted from available documents"
            ),
            "delay",
            "تأخير",
        )
    # Recommended actions if empty
    if not report.get("recommended_actions"):
        add(
            (
                "الإجراءات الموصى بها: لا يوجد أساس كافٍ من الأدلة في المجموعة الحالية"
                if lang == "ar"
                else "Recommended actions: insufficient specific evidence basis in current evidence set"
            ),
            "recommended",
            "الموصى بها",
        )


# ---------------------------------------------------------------------------
# Fallback deterministic builder (no LLM)
# ---------------------------------------------------------------------------


def _basic_executive_summary(
    state: "DecisionState",
    doc_ev: list[dict],
    email_ev: list[dict],
    odoo_ctx: dict,
    project_identity: ProjectIdentity | None = None,
    language: str = "en",
) -> list[dict]:
    """Build a minimal executive_summary so the QG check does not reject deterministic fallback reports.

    This summary is intentionally low-confidence and tells the reviewer that
    automated synthesis failed — it does NOT invent analytical conclusions.
    """
    lang = "ar" if language == "ar" else "en"
    project_name = (
        project_identity.project_name
        if project_identity and project_identity.project_name not in ("", "Not verified")
        else None
    )
    if project_name and state.project_code:
        project_label = f"{project_name} ({state.project_code})"
    elif state.project_code:
        project_label = (
            f"مشروع {state.project_code}" if lang == "ar" else f"Project {state.project_code}"
        )
    else:
        project_label = "المشروع المطلوب" if lang == "ar" else "the requested project"

    def _generic(n: int) -> str:
        if lang == "ar":
            return (
                f"تعذّر إكمال التحليل الآلي لـ{project_label} لهذا الطلب. "
                f"تم فهرسة {n} من عناصر الأدلة المسترجعة في قسم المصادر لمراجعتها؛ "
                "ولا يُقدَّم أي استنتاج آلي. الأثر الكمي على الجدول الزمني أو التكلفة غير متوفر من السجلات."
            )
        return (
            f"Automated analysis for {project_label} could not be completed for this request. "
            f"{n} retrieved evidence item(s) are catalogued in the Sources section for reviewer "
            "validation; no automated conclusion is asserted. Quantified schedule or cost impact "
            "is not available from the records."
        )

    # 1) Lead with the verified Odoo financial position when figures exist —
    #    regardless of whether documents/email were also retrieved. Uses the
    #    real numbers (not "synthesis unavailable"), each bound to its record.
    fin_eids: list[str] = []
    parts: list[str] = []

    def _part(en_label: str, ar_label: str, amount: float) -> str:
        if lang == "ar":
            return f"{ar_label} {amount:,.0f} درهم"
        return f"{en_label} {amount:,.0f} AED"

    cv, cv_eid = odoo_ctx.get("contract_value"), odoo_ctx.get("contract_value_evidence_id")
    if cv not in (None, 0) and cv_eid:
        parts.append(_part("contract value", "قيمة العقد", cv))
        fin_eids.append(cv_eid)
    est, est_eid = odoo_ctx.get("estimate"), odoo_ctx.get("estimate_evidence_id")
    if est not in (None, 0) and est_eid:
        parts.append(_part("cost estimate", "التكلفة التقديرية", est))
        fin_eids.append(est_eid)
    if (
        odoo_ctx.get("has_amount")
        and odoo_ctx.get("total_amount") is not None
        and odoo_ctx.get("best_evidence_id")
    ):
        parts.append(
            _part(
                "actual cost (analytic/journal)",
                "التكلفة الفعلية (قيود تحليلية)",
                abs(odoo_ctx["total_amount"]),
            )
        )
        fin_eids.append(odoo_ctx["best_evidence_id"])
    if odoo_ctx.get("payroll_cost") is not None and odoo_ctx.get("payroll_evidence_id"):
        parts.append(
            _part("payroll/staff cost", "تكلفة الرواتب والموظفين", odoo_ctx["payroll_cost"])
        )
        fin_eids.append(odoo_ctx["payroll_evidence_id"])
    if odoo_ctx.get("expense_cost") is not None and odoo_ctx.get("expense_evidence_id"):
        parts.append(
            _part(
                "expenses (petty cash/vehicle/fuel)",
                "المصروفات النثرية (عهدة/سيارات/وقود)",
                odoo_ctx["expense_cost"],
            )
        )
        fin_eids.append(odoo_ctx["expense_evidence_id"])
    if (
        odoo_ctx.get("incurred_component_count", 0) > 1
        and odoo_ctx.get("total_incurred") is not None
        and odoo_ctx.get("total_incurred_evidence_id")
    ):
        parts.append(
            _part("total incurred", "إجمالي التكلفة المتكبدة", odoo_ctx["total_incurred"])
        )
        fin_eids.append(odoo_ctx["total_incurred_evidence_id"])
    if parts:
        fin_eids = list(dict.fromkeys(fin_eids))[:5]
        if lang == "ar":
            claim = (
                f"بالنسبة إلى {project_label}، الموقف المالي الموثق من Odoo هو: {'؛ '.join(parts)} "
                "(انظر جدول الموقف المالي؛ كل رقم مرتبط بسجله في Odoo). "
                "يتطلب السرد التحليلي الكامل مراجعة محلل."
            )
        else:
            claim = (
                f"For {project_label}, the verified Odoo financial position is: {'; '.join(parts)} "
                "(see the Financial Snapshot, each figure bound to its Odoo record). A full analytical "
                "narrative requires analyst review."
            )
        return [{"claim": claim, "evidence_ids": fin_eids, "confidence": "low"}]

    # 2) No financial figures: document/email-backed -> synthesis pending.
    doc_email_eids = [e.get("evidence_id") for e in (doc_ev + email_ev)[:3] if e.get("evidence_id")]
    if doc_email_eids:
        return [{"claim": _generic(len(doc_email_eids)), "evidence_ids": doc_email_eids, "confidence": "low"}]

    # 3) Odoo-only with no usable figures: cite the project record(s).
    odoo_ids: list[str] = []
    for rec in odoo_ctx.get("project_records", []):
        rid = rec.get("evidence_id") if isinstance(rec, dict) else None
        if rid:
            odoo_ids.append(rid)
    odoo_ids = list(dict.fromkeys(odoo_ids))[:3]
    if not odoo_ids:
        return []
    return [{"claim": _generic(len(odoo_ids)), "evidence_ids": odoo_ids, "confidence": "low"}]


def _source_coverage_note(source: str, source_info: dict) -> str:
    status = source_info.get("status", "unknown")
    attempted = source_info.get("attempted", False)
    count = source_info.get("evidence_count", 0)
    if status == "timeout":
        return f"{source}: attempted; timed out; inconclusive"
    if not attempted:
        return f"{source}: not attempted"
    if count == 0:
        return f"{source}: checked; no salary/payroll records found in retrieved evidence"
    return f"{source}: checked; {count} evidence item(s) retrieved but none contain verified salary/payroll data"


def _first_evidence_id_for_source(evidence: list[dict], source_type: str) -> str | None:
    for ev in evidence:
        if isinstance(ev, dict) and ev.get("source_type") == source_type:
            return ev.get("evidence_id")
    return None


def _build_salary_availability_report(
    state: DecisionState,
    project_identity: ProjectIdentity,
) -> dict:
    """Deterministic availability report when salary/payroll evidence is missing."""
    evidence = state.evidence
    cov_sources = coverage.summary(state)["sources"]

    checked_findings: list[dict] = []
    for src in ("sharepoint", "email", "odoo"):
        info = cov_sources.get(src) or {}
        note = _source_coverage_note(src.capitalize(), info)
        eid = _first_evidence_id_for_source(evidence, src)
        if eid:
            checked_findings.append(
                {
                    "text": note,
                    "evidence_ids": [eid],
                    "confidence": "low",
                }
            )

    if not checked_findings and evidence:
        # Fall back to citing the first available evidence item for the status claim.
        first_eid = evidence[0].get("evidence_id")
        if first_eid:
            checked_findings.append(
                {
                    "text": "Retrieved evidence does not contain verified salary/payroll records.",
                    "evidence_ids": [first_eid],
                    "confidence": "low",
                }
            )

    odoo_timed_out = (cov_sources.get("odoo") or {}).get("status") == "timeout"
    reason = (
        "No verified salary/payroll records were available in the retrieved evidence. "
        + ("Odoo timed out, so ERP payroll/cost data was not confirmed. " if odoo_timed_out else "")
        + "SharePoint/email evidence reviewed does not contain salary/payroll records."
    )

    what_was_checked: list[str] = []
    missing_data: list[str] = []
    for src in ("sharepoint", "email", "odoo"):
        info = cov_sources.get(src) or {}
        if not info.get("enabled"):
            continue
        note = _source_coverage_note(src.capitalize(), info)
        what_was_checked.append(note)
        status = info.get("status", "unknown")
        if status == "timeout":
            missing_data.append(
                f"{src}: salary/payroll retrieval timed out — result is inconclusive"
            )
        elif status == "error":
            missing_data.append(f"{src}: connector error prevented salary/payroll check")
        elif info.get("evidence_count", 0) == 0:
            missing_data.append(f"{src}: no salary/payroll records found")

    required_data = [
        "Verified HR/payroll source with staff name, file ID, salary/cost, and period fields.",
        "Role-based access approval for salary/payroll data (HR/Finance/Executive).",
        "If Odoo is the source: confirmed analytic/accounting line query for labor cost by employee.",
    ]

    sources = []
    for idx, ev in enumerate(evidence, start=1):
        if not isinstance(ev, dict):
            continue
        sources.append(
            {
                "source_id": ev.get("evidence_id", f"S{idx}"),
                "source_type": ev.get("source_type", "sharepoint"),
                "title": ev.get("title", "Untitled"),
                "reference": ev.get("source_uri", "—"),
                "date": ev.get("timestamp") or "—",
                "confidence": ev.get("confidence", "low"),
                "used_in": ["What Was Checked"],
            }
        )

    executive = []
    if checked_findings:
        executive.append(
            {
                "claim": (
                    f"Cannot generate salary report for {project_identity.project_name} "
                    f"({project_identity.project_code}) from verified evidence. "
                    f"{reason}"
                ),
                "evidence_ids": checked_findings[0].get("evidence_ids", []),
                "confidence": "low",
            }
        )

    return {
        "request_id": state.request_id,
        "project_code": state.project_code,
        "project_identity": project_identity.to_dict(),
        "query": state.query,
        "language": "en",
        "report_type": "salary_payroll",
        "executive_summary": executive,
        "financial_snapshot": {
            "budget": {
                "value": None,
                "currency": "AED",
                "evidence_id": None,
                "status": "not_available",
            },
            "actual_cost": {
                "value": None,
                "currency": "AED",
                "evidence_id": None,
                "status": "not_available",
            },
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": checked_findings,
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [
            {
                "text": "Connect a verified HR/payroll source or re-run with an explicit salary/payroll export.",
                "evidence_ids": checked_findings[0].get("evidence_ids", [])
                if checked_findings
                else [],
                "confidence": "low",
            },
        ],
        "management_question_answer": {
            "executive_answer": "",
            "why_biggest_problem": [],
            "evidence_used": [],
            "business_impact": {
                "schedule_impact": "",
                "cost_commercial_impact": "",
                "operational_client_impact": "",
            },
            "decision_required": "",
            "recommended_action": {"specific_action": "", "owner_role": "", "timeframe": ""},
            "risks_if_no_action": "",
            "confidence": "low",
            "missing_evidence_or_assumptions": (
                "Salary/payroll evidence not found; request requires HR/Finance data source and authorization."
            ),
        },
        "missing_data": missing_data or ["No salary/payroll evidence available."],
        "conflicts": [],
        "sources": sources,
        "what_was_checked": what_was_checked,
        "required_data": required_data,
        "connector_coverage": coverage.report_section(state),
        "quality_gate_status": "not_run",
    }


def _build_report_from_evidence(
    state: DecisionState,
    project_identity: ProjectIdentity | None = None,
) -> dict:
    """Deterministic report builder used when no LLM key is available."""
    if project_identity is None:
        project_identity = resolve_project_identity(state)
    language = detect_language(state.query)
    report_type = state.outputs.get("report_type", classify_report_type(state.query))
    if report_type == "financial":
        evidence = filter_financial_evidence(state.evidence, query=state.query)
    else:
        evidence = state.evidence
    role = state.role or "unknown"
    can_see_finance = role in (
        "executive",
        "project_manager",
        "finance",
        "commercial",
        "procurement",
        "legal",
    )
    odoo_ev = [e for e in evidence if e.get("source_type") == "odoo"]
    doc_ev = [e for e in evidence if e.get("source_type") in ("sharepoint", "owncloud")]
    email_ev = [e for e in evidence if e.get("source_type") == "email"]
    odoo_ctx = _extract_odoo_context(odoo_ev)

    budget = {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"}
    actual_cost = {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"}
    if can_see_finance and odoo_ctx["has_amount"] and odoo_ctx["best_evidence_id"]:
        actual_cost = {
            "value": odoo_ctx["total_amount"],
            "currency": "AED",
            "evidence_id": odoo_ctx["best_evidence_id"],
            "status": "available",
        }

    key_findings: list[dict] = []
    delay_analysis: list[dict] = []
    contractual_implications: list[dict] = []
    sources_list: list[dict] = []

    for idx, ev in enumerate(doc_ev + email_ev, start=1):
        eid = ev.get("evidence_id", f"ev_{idx:06d}")
        stype = ev.get("source_type", "sharepoint")
        # Surface the document CONTENT excerpt as a finding — never its filename/
        # title. Skip when the excerpt is empty or is itself a filename (those
        # documents are listed in the Sources appendix only).
        excerpt = (ev.get("excerpt") or "").strip()
        if (
            report_type != "financial"
            and excerpt
            and not _is_filename_or_title_only(ev)
        ):
            finding = {
                "text": excerpt[:200] + ("..." if len(excerpt) > 200 else ""),
                "evidence_ids": [eid],
                "confidence": "low",
            }
            tags = [tg.lower() for tg in ev.get("tags", [])]
            if any(tg in tags for tg in ("delay", "eot", "schedule")):
                delay_analysis.append(finding)
            elif any(tg in tags for tg in ("contract", "claim", "risk")):
                contractual_implications.append(finding)
            else:
                key_findings.append(finding)
        sources_list.append(
            {
                "source_id": f"S{idx}",
                "source_type": stype,
                "title": ev.get("title", "Untitled"),
                "reference": ev.get("source_uri", "—"),
                "date": ev.get("timestamp") or "—",
                "confidence": ev.get("confidence", "medium"),
                "used_in": ["Sources"],
            }
        )

    for idx, ev in enumerate(odoo_ev, start=len(sources_list) + 1):
        sources_list.append(
            {
                "source_id": f"S{idx}",
                "source_type": "odoo",
                "title": ev.get("title", "Odoo Record"),
                "reference": ev.get("source_uri", "—"),
                "date": ev.get("timestamp") or "—",
                "confidence": ev.get("confidence", "high"),
                "used_in": ["Financial Snapshot"],
            }
        )

    missing_data: list[str] = []
    if not evidence:
        missing_data.append(
            "لم يتم استرجاع أي أدلة لهذا الاستفسار."
            if language == "ar"
            else "No evidence was retrieved for this query."
        )

    management_question_answer: dict = {
        "executive_answer": "",
        "why_biggest_problem": [],
        "evidence_used": [],
        "business_impact": {
            "schedule_impact": "",
            "cost_commercial_impact": "",
            "operational_client_impact": "",
        },
        "decision_required": "",
        "recommended_action": {
            "specific_action": "",
            "owner_role": "",
            "timeframe": "",
        },
        "risks_if_no_action": "",
        "confidence": "low",
        "missing_evidence_or_assumptions": (
            "Automated executive synthesis unavailable; evidence catalogued for manual review."
        ),
    }

    report = {
        "request_id": state.request_id,
        "project_code": state.project_code,
        "query": state.query,
        "language": language,
        "project_identity": project_identity.to_dict(),
        "report_type": report_type,
        "executive_summary": _basic_executive_summary(
            state, doc_ev, email_ev, odoo_ctx, project_identity, language=language
        ),
        "financial_snapshot": {
            "budget": budget,
            "actual_cost": actual_cost,
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": key_findings,
        "root_causes": [],
        "delay_analysis": delay_analysis,
        "contractual_implications": contractual_implications,
        "recommended_actions": [],
        "management_question_answer": management_question_answer,
        "missing_data": missing_data,
        "conflicts": [],
        "sources": sources_list,
        "quality_gate_status": "not_run",
    }
    evidence_ids = {e.get("evidence_id", "") for e in evidence if isinstance(e, dict)}
    _enforce_financial_categories(report, odoo_ctx, odoo_ev, evidence_ids)
    if report_type == "financial":
        _force_financial_odoo_synthesis(
            report, state, odoo_ctx, project_identity, language=language
        )
    return report


def _remap_evidence_ids(report: dict, evidence: list[dict]) -> None:
    """Replace synthetic source_ids in claims with real evidence_ids.

    The LLM sometimes invents short source_ids (S1, S3, sp-1) in the sources
    section and then cites them in claims. This breaks the Quality Gate check
    which validates claim evidence_ids against the retrieved evidence pack.
    We map those synthetic ids back to real evidence_ids by matching title or
    source_uri, then rebuild the sources section from the real ids.
    """
    if not isinstance(report, dict):
        return

    # Build lookup tables from the real evidence pack.
    by_title: dict[str, str] = {}
    by_uri: dict[str, str] = {}
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        eid = ev.get("evidence_id", "")
        if not eid:
            continue
        title = str(ev.get("title") or "").strip().lower()
        uri = str(ev.get("source_uri") or "").strip().lower()
        if title:
            by_title[title] = eid
        if uri:
            by_uri[uri] = eid

    # Map synthetic source_ids to real evidence_ids.
    synth_to_real: dict[str, str] = {}
    sources = report.get("sources", [])
    if isinstance(sources, list):
        for src in sources:
            if not isinstance(src, dict):
                continue
            sid = src.get("source_id", "")
            title = str(src.get("title") or "").strip().lower()
            uri = str(src.get("reference") or src.get("source_uri") or "").strip().lower()
            real: str | None = None
            if title and title in by_title:
                real = by_title[title]
            elif uri and uri in by_uri:
                real = by_uri[uri]
            if real and sid and sid != real:
                synth_to_real[sid] = real

    if not synth_to_real:
        return

    def _remap(items: list) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            eids = _flatten_eids(item.get("evidence_ids"))
            if eids:
                item["evidence_ids"] = [synth_to_real.get(e, e) for e in eids]

    # Remap claim evidence_ids across all claim-bearing sections.
    for section in (
        "executive_summary",
        "key_findings",
        "root_causes",
        "delay_analysis",
        "contractual_implications",
        "recommended_actions",
    ):
        _remap(report.get(section, []))

    # Remap management_question_answer evidence_used list if it contains ids.
    mqa = report.get("management_question_answer")
    if isinstance(mqa, dict):
        _remap([mqa])

    # Rebuild sources from real evidence ids actually cited in the report.
    cited: set[str] = set()
    for section in (
        "executive_summary",
        "key_findings",
        "root_causes",
        "delay_analysis",
        "contractual_implications",
        "recommended_actions",
    ):
        for item in report.get(section, []):
            if isinstance(item, dict):
                cited.update(_flatten_eids(item.get("evidence_ids", [])))
    # Also keep sources for financial_snapshot actual_cost evidence_id.
    fs = report.get("financial_snapshot") or {}
    if isinstance(fs, dict):
        ac = fs.get("actual_cost")
        if isinstance(ac, dict):
            cited.add(ac.get("evidence_id") or "")

    evidence_by_id = {e.get("evidence_id"): e for e in evidence if isinstance(e, dict)}
    new_sources: list[dict] = []
    for eid in sorted(cited):
        ev = evidence_by_id.get(eid)
        if not ev:
            continue
        new_sources.append(
            {
                "source_id": eid,
                "source_type": ev.get("source_type", "sharepoint"),
                "title": ev.get("title", "Untitled"),
                "reference": ev.get("source_uri", "—"),
                "date": ev.get("timestamp") or "—",
                "confidence": ev.get("confidence", "medium"),
                "used_in": ["Key Findings"],
            }
        )
    report["sources"] = new_sources


def _rebuild_sources_from_citations(report: dict, evidence: list[dict]) -> None:
    """Rebuild Sources from evidence IDs cited in the visible report body."""
    cited: set[str] = set()
    for section in (
        "executive_summary",
        "key_findings",
        "root_causes",
        "delay_analysis",
        "contractual_implications",
        "recommended_actions",
    ):
        for item in report.get(section, []):
            if isinstance(item, dict):
                cited.update(_flatten_eids(item.get("evidence_ids", [])))

    fs = report.get("financial_snapshot") or {}
    if isinstance(fs, dict):
        for field in ("contract_value", "estimate", "actual_cost", "committed_cost"):
            node = fs.get(field)
            if isinstance(node, dict) and node.get("evidence_id"):
                cited.add(str(node["evidence_id"]))
        variance = fs.get("variance")
        if isinstance(variance, dict):
            cited.update(_flatten_eids(variance.get("evidence_ids", [])))

    evidence_by_id = {e.get("evidence_id"): e for e in evidence if isinstance(e, dict)}
    sources: list[dict] = []
    for eid in sorted(cited):
        ev = evidence_by_id.get(eid)
        if not ev:
            continue
        sources.append(
            {
                "source_id": eid,
                "source_type": ev.get("source_type", "sharepoint"),
                "title": ev.get("title", "Untitled"),
                "reference": ev.get("source_uri", "—"),
                "date": ev.get("timestamp") or "—",
                "confidence": ev.get("confidence", "medium"),
                "used_in": ["Financial Snapshot" if ev.get("source_type") == "odoo" else "Key Findings"],
            }
        )
    report["sources"] = sources


def _flatten_eids(eids) -> list[str]:
    """Flatten a possibly-nested evidence_ids value into a list of strings."""
    if not eids:
        return []
    if isinstance(eids, str):
        return [eids]
    flat: list[str] = []
    for e in eids:
        if isinstance(e, list):
            flat.extend(str(x) for x in e if x is not None)
        elif e is not None:
            flat.append(str(e))
    return flat


def _enforce_executive_summary(
    report: dict, state: DecisionState, language: str = "en"
) -> None:
    """When the LLM returns an empty executive_summary but evidence exists,
    synthesize a minimal fallback from key_findings so the QG check passes.

    The synthesized entry is marked confidence=low to signal partial automation.
    """
    lang = "ar" if language == "ar" else "en"
    es = report.get("executive_summary")
    if not (isinstance(es, list) and len(es) == 0 and state.evidence):
        return

    findings = report.get("key_findings", [])
    if not findings:
        return

    ref_eids: list[str] = []
    for f in findings[:3]:
        ref_eids.extend(e for e in f.get("evidence_ids", []) if e)
    ref_eids = list(dict.fromkeys(ref_eids))[:5]

    if not ref_eids:
        return

    pid = state.outputs.get("project_identity") or {}
    project_name = pid.get("project_name") if isinstance(pid, dict) else None
    if project_name and project_name not in ("", "Not verified") and state.project_code:
        project_label = f"{project_name} ({state.project_code})"
    elif state.project_code:
        project_label = (
            f"مشروع {state.project_code}" if lang == "ar" else f"Project {state.project_code}"
        )
    else:
        project_label = "المشروع المطلوب" if lang == "ar" else "the requested project"
    if lang == "ar":
        claim = (
            f"تعذّر إكمال التحليل الآلي لـ{project_label} لهذا الطلب. "
            f"تم فهرسة {len(ref_eids)} من عناصر الأدلة المسترجعة في قسم المصادر لمراجعتها؛ "
            "ولا يُقدَّم أي استنتاج آلي. الأثر الكمي على الجدول الزمني أو التكلفة غير متوفر من السجلات."
        )
    else:
        claim = (
            f"Automated analysis for {project_label} could not be completed for this request. "
            f"{len(ref_eids)} retrieved evidence item(s) are catalogued in the Sources section for "
            "reviewer validation; no automated conclusion is asserted. Quantified schedule or cost "
            "impact is not available from the records."
        )
    report["executive_summary"] = [{"claim": claim, "evidence_ids": ref_eids, "confidence": "low"}]


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------


async def run(state: DecisionState) -> DecisionState:
    report_type = state.outputs.get("report_type", classify_report_type(state.query))
    language = detect_language(state.query)
    state.outputs["detected_language"] = language
    project_identity = ProjectIdentity.from_dict(
        state.outputs.get("project_identity") or resolve_project_identity(state).to_dict()
    )
    state.outputs["report_type"] = report_type

    # Salary/payroll without verified salary evidence -> deterministic availability report.
    # This prevents the LLM from hallucinating a management decision memo.
    if report_type == "salary_payroll" and not is_salary_payroll_evidence(state.evidence):
        report = _build_salary_availability_report(state, project_identity)
        state.report_json = report
        state.outputs["draft_report_status"] = "salary_availability"
        state.outputs["cohere_rerank_status"] = "skipped_salary_availability"
        return state.mark("node_12_draft_json")

    # Source-aware rerank: keep all Odoo+Email; rerank SharePoint to top 10.
    # state.evidence is preserved intact for coverage/sufficiency reporting.
    prompt_evidence, rerank_status = await _apply_rerank(state, state.evidence)
    state.outputs["cohere_rerank_status"] = rerank_status

    prompt = _build_prompt(
        state,
        prompt_evidence,
        report_type=report_type,
        project_identity=project_identity,
        language=language,
    )
    import sys

    print(
        f"[NODE12] prompt request_id={state.request_id} prompt_chars={len(prompt)} "
        f"prompt_words={len(prompt.split())} rerank={rerank_status}",
        file=sys.stderr,
        flush=True,
    )

    result = await call_llm(
        prompt=prompt,
        tier="heavy",
        request_id=state.request_id,
        node_name="node_12_draft_json",
        expect_json=True,
        max_tokens=12000,
    )

    state.cost_accumulated_usd += result.cost_usd
    state.outputs["node_12_cost_usd"] = result.cost_usd
    print(
        f"[NODE12] llm response request_id={state.request_id} "
        f"model={getattr(result, 'model', 'unknown')} "
        f"input_tokens={getattr(result, 'input_tokens', 0)} "
        f"output_tokens={getattr(result, 'output_tokens', 0)} "
        f"content_chars={len(result.content)}",
        file=sys.stderr,
        flush=True,
    )

    evidence_ids = {e.get("evidence_id", "") for e in state.evidence if isinstance(e, dict)}
    odoo_ctx = _extract_odoo_context([e for e in state.evidence if e.get("source_type") == "odoo"])

    def _normalize(report_candidate: dict | None) -> dict:
        """Coerce a parsed/repaired report into a valid shape or fall back to deterministic builder."""
        if not isinstance(report_candidate, dict):
            state.outputs["draft_report_source"] = "deterministic_fallback"
            return _build_report_from_evidence(state, project_identity)
        _normalize_financial_snapshot(report_candidate)
        _enforce_financial_from_odoo(report_candidate, odoo_ctx, evidence_ids)
        _remap_evidence_ids(report_candidate, state.evidence)
        dropped = _salvage_llm_claims(report_candidate, evidence_ids)
        if any(dropped.values()):
            state.outputs["draft_salvage_dropped"] = {
                k: v for k, v in dropped.items() if v
            }
        if not _report_has_valid_claims(report_candidate, evidence_ids):
            state.outputs["draft_report_source"] = "deterministic_fallback"
            return _build_report_from_evidence(state, project_identity)
        state.outputs["draft_report_source"] = "llm"
        return report_candidate

    report: dict | None = None
    parse_error: Exception | None = None

    # 1. Strict JSON parse
    try:
        parsed = json.loads(result.content)
        if isinstance(parsed, dict):
            report = parsed
        else:
            print(
                f"[NODE12] json parse returned non-dict request_id={state.request_id} type={type(parsed)}",
                file=sys.stderr,
                flush=True,
            )
    except Exception as exc:
        parse_error = exc
        print(
            f"[NODE12] json parse failed request_id={state.request_id} exc={exc} "
            f"content_len={len(result.content)} content_prefix={result.content[:200]} "
            f"content_suffix={result.content[-400:]}",
            file=sys.stderr,
            flush=True,
        )

    # 2. Structural repair without an extra LLM call.
    if not report and json_repair:
        try:
            repaired, ok = json_repair.repair_json(result.content, return_objects=True)
            if ok and isinstance(repaired, dict):
                report = repaired
                print(
                    f"[NODE12] json_repair success request_id={state.request_id}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(
                    f"[NODE12] json_repair failed request_id={state.request_id} ok={ok}",
                    file=sys.stderr,
                    flush=True,
                )
        except Exception as repair_exc:
            print(
                f"[NODE12] json_repair exception request_id={state.request_id} exc={repair_exc}",
                file=sys.stderr,
                flush=True,
            )

    # 3. Last-resort LLM repair only if structural repair failed.
    if not report and parse_error:
        repair_prompt = (
            "The previous output was invalid JSON. Return ONLY a valid JSON object "
            "matching the exact schema in the original prompt. Do not include markdown fences, explanations, "
            "or any text outside the JSON object. Ensure every string value is on a single line "
            'and escapes double quotes with \\" and newlines with \\n.\n\n'
            "Required top-level keys: request_id, project_code, query, language, executive_summary, "
            "financial_snapshot, key_findings, root_causes, delay_analysis, contractual_implications, "
            "recommended_actions, management_question_answer, missing_data, conflicts, sources.\n\n"
            "DO NOT echo the example placeholder text (e.g. 'synthesized insight from evidence', "
            "'One clear sentence...', 'bullet 1 tied to evidence'). Use real evidence IDs only.\n\n"
            f"Original prompt:\n{prompt}"
        )
        try:
            repair_result = await call_llm(
                prompt=repair_prompt,
                tier="heavy",
                request_id=f"{state.request_id}-repair",
                node_name="node_12_draft_json",
                expect_json=True,
                max_tokens=12000,
            )
            state.cost_accumulated_usd += repair_result.cost_usd
            parsed_repair = json.loads(repair_result.content)
            if isinstance(parsed_repair, dict):
                report = parsed_repair
                print(
                    f"[NODE12] llm repair parse request_id={state.request_id} success=True",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(
                    f"[NODE12] llm repair parse request_id={state.request_id} success=False non-dict",
                    file=sys.stderr,
                    flush=True,
                )
        except Exception as repair_exc:
            print(
                f"[NODE12] llm repair parse failed request_id={state.request_id} exc={repair_exc}",
                file=sys.stderr,
                flush=True,
            )

    report = _normalize(report)

    mqa_preview = report.get("management_question_answer")
    print(
        f"[NODE12] parsed report request_id={state.request_id} keys={sorted(report.keys())} "
        f"has_mqa={isinstance(mqa_preview, dict)} mqa_exec_answer_len={len(mqa_preview.get('executive_answer', '')) if isinstance(mqa_preview, dict) else 0}",
        file=sys.stderr,
        flush=True,
    )

    # Ensure required fields exist
    report.setdefault("request_id", state.request_id)
    report.setdefault("project_code", state.project_code)
    report.setdefault("query", state.query)
    # Deterministic: the report language follows the query language.
    report["language"] = language
    report.setdefault("executive_summary", [])
    report.setdefault(
        "financial_snapshot",
        {
            "budget": {
                "value": None,
                "currency": "AED",
                "evidence_id": None,
                "status": "not_available",
            },
            "actual_cost": {
                "value": None,
                "currency": "AED",
                "evidence_id": None,
                "status": "not_available",
            },
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
    )
    report.setdefault("key_findings", [])
    report.setdefault("root_causes", [])
    report.setdefault("delay_analysis", [])
    report.setdefault("contractual_implications", [])
    report.setdefault("recommended_actions", [])
    report.setdefault(
        "management_question_answer",
        {
            "executive_answer": "",
            "why_biggest_problem": [],
            "evidence_used": [],
            "business_impact": {
                "schedule_impact": "",
                "cost_commercial_impact": "",
                "operational_client_impact": "",
            },
            "decision_required": "",
            "recommended_action": {
                "specific_action": "",
                "owner_role": "",
                "timeframe": "",
            },
            "risks_if_no_action": "",
            "confidence": "low",
            "missing_evidence_or_assumptions": "",
        },
    )
    report.setdefault("missing_data", [])
    report.setdefault("conflicts", [])
    report.setdefault("sources", [])
    report.setdefault("quality_gate_status", "not_run")

    # Post-LLM deterministic corrections
    evidence_ids = {e.get("evidence_id", "") for e in state.evidence if isinstance(e, dict)}
    _odoo_evidence = [e for e in state.evidence if e.get("source_type") == "odoo"]
    odoo_ctx = _extract_odoo_context(_odoo_evidence)
    _enforce_financial_from_odoo(report, odoo_ctx, evidence_ids)
    _enforce_financial_categories(report, odoo_ctx, _odoo_evidence, evidence_ids)
    if report_type == "financial":
        _force_financial_odoo_synthesis(
            report, state, odoo_ctx, project_identity, language=language
        )
    _remap_evidence_ids(report, state.evidence)
    if report_type == "financial":
        _rebuild_sources_from_citations(report, state.evidence)
    _enforce_missing_data(report, odoo_ctx, language=language)
    _enforce_executive_summary(report, state, language=language)
    _enrich_management_question_answer(report, state)

    # Enforce the verified Project Identity Contract on every report.
    report["project_identity"] = project_identity.to_dict()
    report["report_type"] = report_type

    # Deterministic connector coverage (factual; never LLM-authored)
    report["connector_coverage"] = coverage.report_section(state)

    # Financial transparency: never invent figures
    if not state.outputs.get("odoo_financial_available"):
        fs = report.get("financial_snapshot")
        if isinstance(fs, dict):
            fs.setdefault("note", "financial data not available in verified Odoo evidence")

    state.report_json = report
    state.outputs["draft_report_status"] = "generated"
    return state.mark("node_12_draft_json")
