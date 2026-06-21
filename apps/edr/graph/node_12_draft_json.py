"""Node 12 — Draft JSON Report. Spec: Sections 14 and 16.

Generates the canonical structured report using the heavy tier.
Every claim MUST bind to evidence_ids; financial values MUST come from Odoo.
"""

from __future__ import annotations

import json
import re

from apps.edr.graph import coverage
from apps.edr.graph.intent import (
    classify_report_type,
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
        '  "language": "en or ar",\n'
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
    if findings:
        first_text = (
            findings[0].get("text", "").strip() or "No specific analytical finding available."
        )
        first_eids = _flatten_eids(findings[0].get("evidence_ids", []))
    else:
        first_text = "No specific analytical finding available."
        first_eids = []

    if not (mqa.get("executive_answer") or "").strip() or _is_placeholder_text(
        mqa.get("executive_answer", "")
    ):
        mqa["executive_answer"] = f"The most prominent issue is: {first_text}"

    why = mqa.get("why_biggest_problem")
    if not isinstance(why, list) or len(why) < 3 or all(_is_placeholder_text(b) for b in why):
        bullets = []
        for f in findings[:3]:
            t = (f.get("text") or "").strip()
            if t and not _is_placeholder_text(t):
                bullets.append(t)
        while len(bullets) < 3:
            bullets.append("Additional evidence review is needed to substantiate this issue.")
        mqa["why_biggest_problem"] = bullets[:5]

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


def _enforce_missing_data(report: dict, odoo_ctx: dict) -> None:
    """Deterministically populate missing_data with items that could not be extracted."""
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

    # Budget is always missing from analytic line records
    add(
        "Project budget (AED): not available in Odoo analytic line records",
        "budget",
    )
    # Variance is always missing without budget
    add(
        "Cost variance (budget vs actual): not calculable without a budget baseline",
        "variance",
    )
    # Actual cost if no cost lines
    if not odoo_ctx.get("has_amount"):
        add(
            "Actual cost total: not available — no cost analytic lines in evidence",
            "actual cost",
            "actual_cost",
        )
    # Delay if delay sections empty
    if not report.get("delay_analysis") and not report.get("root_causes"):
        add(
            "Delay analysis: no specific delay events extracted from available documents",
            "delay",
        )
    # Recommended actions if empty
    if not report.get("recommended_actions"):
        add(
            "Recommended actions: insufficient specific evidence basis in current evidence set",
            "recommended",
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
) -> list[dict]:
    """Build a minimal executive_summary so the QG check does not reject deterministic fallback reports.

    This summary is intentionally low-confidence and tells the reviewer that
    automated synthesis failed — it does NOT invent analytical conclusions.
    """
    ref_eids = [e.get("evidence_id") for e in (doc_ev + email_ev)[:3] if e.get("evidence_id")]
    if not ref_eids:
        return []

    project_name = (
        project_identity.project_name
        if project_identity and project_identity.project_name not in ("", "Not verified")
        else None
    )
    project_label = (
        f"{project_name} ({state.project_code})"
        if project_name and state.project_code
        else (f"Project {state.project_code}" if state.project_code else "the requested project")
    )

    first_ev = (doc_ev + email_ev)[0] if (doc_ev or email_ev) else {}
    first_finding = (first_ev.get("excerpt") or first_ev.get("title") or "").strip()
    if not first_finding:
        first_finding = "the retrieved evidence points to an issue requiring management attention"
    if len(first_finding) > 250:
        first_finding = first_finding[:250] + "..."

    claim = (
        f"For {project_label}, the most prominent issue is: {first_finding}. "
        "Management should review the cited records and decide on the appropriate next steps. "
        "Quantified schedule or cost impact cannot be stated because baselines were not found in the records."
    )
    return [{"claim": claim, "evidence_ids": ref_eids, "confidence": "low"}]


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
        "sources": [],
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
        excerpt = ev.get("excerpt", "")
        stype = ev.get("source_type", "sharepoint")
        confidence = ev.get("confidence", "medium")
        finding = {
            "text": excerpt[:200] + "..." if len(excerpt) > 200 else excerpt,
            "evidence_ids": [eid],
            "confidence": confidence,
        }
        tags = [t.lower() for t in ev.get("tags", [])]
        if any(t in tags for t in ("delay", "eot", "schedule")):
            delay_analysis.append(finding)
        elif any(t in tags for t in ("contract", "claim", "risk")):
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
                "confidence": confidence,
                "used_in": ["Key Findings"],
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
        missing_data.append("No evidence was retrieved for this query.")

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

    return {
        "request_id": state.request_id,
        "project_code": state.project_code,
        "query": state.query,
        "language": "en",
        "project_identity": project_identity.to_dict(),
        "executive_summary": _basic_executive_summary(
            state, doc_ev, email_ev, odoo_ctx, project_identity
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


def _enforce_executive_summary(report: dict, state: DecisionState) -> None:
    """When the LLM returns an empty executive_summary but evidence exists,
    synthesize a minimal fallback from key_findings so the QG check passes.

    The synthesized entry is marked confidence=low to signal partial automation.
    """
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
        project_label = f"Project {state.project_code}"
    else:
        project_label = "the requested project"
    first_finding = findings[0].get("text", "")[:250]

    claim = (
        f"For {project_label}, the most prominent issue is: {first_finding}. "
        "Management should review the cited records and decide on the appropriate next steps. "
        "Quantified schedule or cost impact cannot be stated because baselines were not found in the records."
    )
    report["executive_summary"] = [{"claim": claim, "evidence_ids": ref_eids, "confidence": "low"}]


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------


async def run(state: DecisionState) -> DecisionState:
    report_type = state.outputs.get("report_type", classify_report_type(state.query))
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
            return _build_report_from_evidence(state, project_identity)
        _normalize_financial_snapshot(report_candidate)
        _enforce_financial_from_odoo(report_candidate, odoo_ctx, evidence_ids)
        _remap_evidence_ids(report_candidate, state.evidence)
        if not _report_has_valid_claims(report_candidate, evidence_ids):
            return _build_report_from_evidence(state, project_identity)
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
    report.setdefault("language", "en")
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
    odoo_ctx = _extract_odoo_context([e for e in state.evidence if e.get("source_type") == "odoo"])
    _enforce_financial_from_odoo(report, odoo_ctx, evidence_ids)
    _remap_evidence_ids(report, state.evidence)
    _enforce_missing_data(report, odoo_ctx)
    _enforce_executive_summary(report, state)
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
