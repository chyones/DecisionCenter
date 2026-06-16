"""Node 12 — Draft JSON Report. Spec: Sections 14 and 16.

Generates the canonical structured report using the heavy tier.
Every claim MUST bind to evidence_ids; financial values MUST come from Odoo.
"""

from __future__ import annotations

import json

from apps.edr.graph import coverage
from apps.edr.graph.state import DecisionState
from apps.edr.llm import call_llm, sanitize_evidence


# ---------------------------------------------------------------------------
# Odoo financial pre-extraction (deterministic — no LLM)
# ---------------------------------------------------------------------------


def _extract_odoo_context(odoo_evidence: list[dict]) -> dict:
    """Pre-process Odoo evidence into structured context for the LLM prompt.

    Odoo analytic line excerpts encode data as "Category / Amount / Date".
    We extract this deterministically so the LLM doesn't have to parse it
    from raw text, and so the financial snapshot can be corrected post-LLM.
    """
    project_records: list[dict] = []
    cost_lines: list[dict] = []
    for ev in odoo_evidence:
        uri = ev.get("source_uri", "").lower()
        # analytic lines come from the account.analytic.line model
        if "analytic" in uri:
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
        excerpt = line.get("excerpt", "")
        parts = [p.strip() for p in excerpt.split(" / ")]
        cat = parts[0] if parts else ""
        if cat and cat not in categories:
            categories.append(cat)
        if len(parts) >= 2:
            try:
                amt = float(parts[1].replace(",", ""))
                total_amount += amt
                has_amount = True
            except (ValueError, IndexError):
                pass
        date_str = parts[2] if len(parts) >= 3 else ""
        if date_str:
            dates.append(date_str)
            if date_str > best_date:
                best_date = date_str
                best_evidence_id = line.get("evidence_id")

    # Most recent 15 cost lines for prompt (keep token budget reasonable)
    sorted_lines = sorted(
        cost_lines,
        key=lambda e: (
            e.get("excerpt", "").split(" / ")[2].strip()
            if len(e.get("excerpt", "").split(" / ")) >= 3
            else ""
        ),
        reverse=True,
    )

    return {
        "project_records": project_records,
        "cost_count": len(cost_lines),
        "categories": categories[:15],
        "total_amount": round(total_amount, 2) if has_amount else None,
        "has_amount": has_amount,
        "latest_date": max(dates) if dates else None,
        "best_evidence_id": best_evidence_id,
        "sample_lines": sorted_lines[:15],
    }


# ---------------------------------------------------------------------------
# Cohere rerank — source-aware strategy
# ---------------------------------------------------------------------------


async def _apply_rerank(
    state: DecisionState, evidence: list[dict]
) -> tuple[list[dict], str]:
    """Source-aware evidence selection for the LLM prompt.

    All Odoo and Email items are always included — they are structured and
    critical for financial/comms analysis.  SharePoint/ownCloud items are
    reranked by Cohere and capped at the top 10 most relevant.
    state.evidence is never modified here; only the prompt list is changed.
    """
    from apps.edr.config import settings

    odoo_ev = [e for e in evidence if e.get("source_type") == "odoo"]
    email_ev = [e for e in evidence if e.get("source_type") == "email"]
    other = [e for e in evidence if e.get("source_type") not in ("odoo", "email")]

    key = getattr(settings, "cohere_api_key", None)
    if not key or not other:
        status = "skipped_no_key" if not key else "no_doc_evidence"
        return odoo_ev + email_ev + other[:15], status

    try:
        from apps.edr.retrieval.hybrid_search import SearchHit
        from apps.edr.retrieval.rerank import Reranker

        hits = [
            SearchHit(evidence_id=e.get("evidence_id", ""), score=0.0, payload=e)
            for e in other
        ]
        ranked_hits = await Reranker(api_key=key).rerank(state.query, hits)
        sp_ranked = [h.payload for h in ranked_hits]
        n_o, n_e, n_s = len(odoo_ev), len(email_ev), len(sp_ranked)
        return odoo_ev + email_ev + sp_ranked, f"ok_odoo={n_o}_email={n_e}_sp={n_s}"
    except Exception as exc:
        return odoo_ev + email_ev + other[:10], f"fallback:{type(exc).__name__}"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt(state: DecisionState, prompt_evidence: list[dict]) -> str:
    odoo_ev = [e for e in prompt_evidence if e.get("source_type") == "odoo"]
    email_ev = [e for e in prompt_evidence if e.get("source_type") == "email"]
    sp_ev = [e for e in prompt_evidence if e.get("source_type") in ("sharepoint", "owncloud", "cad")]

    odoo_ctx = _extract_odoo_context(odoo_ev)

    role = state.role or "unknown"
    can_see_finance = role in (
        "executive", "project_manager", "finance", "commercial", "procurement", "legal"
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
            + (f"  Total tracked expense: {odoo_ctx['total_amount']} AED\n" if odoo_ctx["has_amount"] else "")
            + f"  Cost categories: {', '.join(odoo_ctx['categories'][:10]) or 'none extracted'}\n"
            + (f"  Latest record date: {odoo_ctx['latest_date']}\n" if odoo_ctx["latest_date"] else "")
        )
        sample_excerpts = []
        for line in odoo_ctx["sample_lines"]:
            safe_ex, _ = sanitize_evidence(line.get("excerpt", ""))
            sample_excerpts.append(f"  [{line.get('evidence_id', '')}] {safe_ex}")
        odoo_lines.append("Representative cost lines:\n" + "\n".join(sample_excerpts))
    odoo_section = "\n".join(odoo_lines) if odoo_lines else "No Odoo data available."

    # --- SharePoint / document block ---
    sp_lines: list[str] = []
    for ev in sp_ev[:10]:
        safe_ex, _ = sanitize_evidence(ev.get("excerpt", "") or ev.get("title", ""))
        sp_lines.append(f"[{ev.get('evidence_id', '')}] {ev.get('title', 'Untitled')}:\n{safe_ex[:300]}")
    sp_section = "\n\n".join(sp_lines) if sp_lines else "No document evidence available."

    # --- Email block ---
    email_lines: list[str] = []
    for ev in email_ev:
        safe_ex, _ = sanitize_evidence(ev.get("excerpt", ""))
        email_lines.append(
            f"[{ev.get('evidence_id', '')}] Subject: {ev.get('title', 'No subject')}\n{safe_ex[:300]}"
        )
    email_section = "\n\n".join(email_lines) if email_lines else "No email evidence available."

    # Pre-computed financial hint so the LLM can fill the snapshot correctly
    actual_hint = (
        f"actual_cost: status='available', value={odoo_ctx['total_amount']}, "
        f"evidence_id='{odoo_ctx['best_evidence_id'] or ''}'"
        if odoo_ctx["has_amount"]
        else "actual_cost: status='not_available' (no cost lines in evidence)"
    )

    return (
        "You are an executive decision-support analyst for a construction company.\n"
        "Generate a FULLY POPULATED structured JSON report. Every required section must have real content.\n\n"
        "ABSOLUTE RULES:\n"
        "1. Every claim MUST carry at least one evidence_id from the evidence listed below.\n"
        "2. Every financial number MUST carry an Odoo evidence_id.\n"
        "3. Do NOT invent facts, numbers, or dates not present in the evidence.\n"
        "4. KEY_FINDINGS must be synthesized analytical insights — NEVER raw filenames or document titles.\n"
        "   CORRECT: 'Four successive BOQ revisions indicate ongoing scope changes into Q1 2026.'\n"
        "   WRONG:   'BOQ Revision 4.xlsx', 'Project_Schedule_Rev3.pdf'\n"
        "5. EXECUTIVE_SUMMARY must contain 4–8 complete sentences covering:\n"
        "   project status, financial status, schedule/delay signals, top risk, recommended next step.\n"
        "6. MISSING_DATA must list every item that could not be determined, including budget.\n\n"
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
        '    {"claim": "4-8 sentence synthesized summary", "evidence_ids": ["ev_..."], "confidence": "high|medium|low"}\n'
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
        '  "missing_data": ["Project budget (AED): not available in Odoo analytic line records", ...],\n'
        '  "conflicts": [...],\n'
        '  "sources": [{"source_id": "S1", "source_type": "sharepoint|odoo|email", "title": "...", "reference": "...", "date": "...", "confidence": "...", "used_in": ["section"]}]\n'
        "}\n"
    )


# ---------------------------------------------------------------------------
# Post-LLM deterministic corrections
# ---------------------------------------------------------------------------


def _enforce_financial_from_odoo(
    report: dict, odoo_ctx: dict, evidence_ids: set[str]
) -> None:
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

    # Actual cost from analytic sum
    if odoo_ctx.get("has_amount"):
        eid = odoo_ctx.get("best_evidence_id") or ""
        if eid in evidence_ids:
            actual = fs.get("actual_cost")
            if isinstance(actual, dict) and actual.get("status") != "available":
                actual["status"] = "available"
                actual["value"] = odoo_ctx["total_amount"]
                actual["currency"] = "AED"
                actual["evidence_id"] = eid


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
            "actual cost", "actual_cost",
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
) -> list[dict]:
    """Build a minimal executive_summary so the QG check does not reject deterministic fallback reports.

    This summary is intentionally low-confidence and tells the reviewer that
    automated synthesis failed — it does NOT invent analytical conclusions.
    """
    ref_eids = [
        e.get("evidence_id")
        for e in (doc_ev + email_ev)[:3]
        if e.get("evidence_id")
    ]
    if not ref_eids:
        return []

    sp_count = len(doc_ev)
    email_count = len(email_ev)
    odoo_count = len(odoo_ctx.get("project_records", [])) + odoo_ctx.get("cost_count", 0)
    project_label = f"Project {state.project_code}" if state.project_code else "the requested project"

    parts: list[str] = []
    if sp_count:
        parts.append(f"{sp_count} SharePoint document(s)")
    if email_count:
        parts.append(f"{email_count} email communication(s)")
    if odoo_count:
        parts.append(f"{odoo_count} Odoo record(s)")
    evidence_desc = ", ".join(parts) if parts else "available evidence"

    claim = (
        f"Evidence retrieval for {project_label} completed with {evidence_desc}. "
        "Automated analytical synthesis did not produce a complete summary — "
        "this report requires reviewer inspection of the catalogued evidence. "
        "Financial data is not available from Odoo records. "
        "Reviewer should assess key findings and determine project status "
        "before approving or requesting revision."
    )
    return [{"claim": claim, "evidence_ids": ref_eids, "confidence": "low"}]


def _build_report_from_evidence(state: DecisionState) -> dict:
    """Deterministic report builder used when no LLM key is available."""
    evidence = state.evidence
    role = state.role or "unknown"
    can_see_finance = role in (
        "executive", "project_manager", "finance", "commercial", "procurement", "legal"
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
        sources_list.append({
            "source_id": f"S{idx}",
            "source_type": stype,
            "title": ev.get("title", "Untitled"),
            "reference": ev.get("source_uri", "—"),
            "date": ev.get("timestamp") or "—",
            "confidence": confidence,
            "used_in": ["Key Findings"],
        })

    for idx, ev in enumerate(odoo_ev, start=len(sources_list) + 1):
        sources_list.append({
            "source_id": f"S{idx}",
            "source_type": "odoo",
            "title": ev.get("title", "Odoo Record"),
            "reference": ev.get("source_uri", "—"),
            "date": ev.get("timestamp") or "—",
            "confidence": ev.get("confidence", "high"),
            "used_in": ["Financial Snapshot"],
        })

    missing_data: list[str] = []
    if not evidence:
        missing_data.append("No evidence was retrieved for this query.")

    return {
        "request_id": state.request_id,
        "project_code": state.project_code,
        "query": state.query,
        "language": "en",
        "executive_summary": _basic_executive_summary(state, doc_ev, email_ev, odoo_ctx),
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
        "missing_data": missing_data,
        "conflicts": [],
        "sources": sources_list,
        "quality_gate_status": "not_run",
    }


def is_financial_query(query: str) -> bool:
    lower = query.lower()
    return any(kw in lower for kw in ("budget", "cost", "payment", "invoice", "financial", "actual"))


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

    sp_count = len([e for e in state.evidence if e.get("source_type") == "sharepoint"])
    email_count = len([e for e in state.evidence if e.get("source_type") == "email"])
    project_label = f"Project {state.project_code}" if state.project_code else "the requested project"
    first_finding = findings[0].get("text", "")[:200]

    claim = (
        f"{project_label} evidence review: {sp_count} document(s) and {email_count} "
        f"email(s) retrieved. Key finding: {first_finding}. "
        "Financial data is not available from Odoo records. "
        "Automated executive synthesis was incomplete — reviewer assessment required."
    )
    report["executive_summary"] = [{"claim": claim, "evidence_ids": ref_eids, "confidence": "low"}]


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------


async def run(state: DecisionState) -> DecisionState:
    # Source-aware rerank: keep all Odoo+Email; rerank SharePoint to top 10.
    # state.evidence is preserved intact for coverage/sufficiency reporting.
    prompt_evidence, rerank_status = await _apply_rerank(state, state.evidence)
    state.outputs["cohere_rerank_status"] = rerank_status

    prompt = _build_prompt(state, prompt_evidence)
    result = await call_llm(
        prompt=prompt,
        tier="heavy",
        request_id=state.request_id,
        node_name="node_12_draft_json",
        expect_json=True,
        max_tokens=4_000,
    )

    state.cost_accumulated_usd += result.cost_usd
    state.outputs["node_12_cost_usd"] = result.cost_usd

    report: dict
    try:
        parsed = json.loads(result.content)
        report = parsed if isinstance(parsed, dict) else _build_report_from_evidence(state)
    except Exception:
        report = _build_report_from_evidence(state)

    # If LLM produced an empty shell but evidence exists, fall back to deterministic builder.
    has_findings = any(
        report.get(s)
        for s in ("executive_summary", "key_findings", "root_causes",
                  "delay_analysis", "contractual_implications", "recommended_actions")
    )
    if not has_findings and state.evidence:
        report = _build_report_from_evidence(state)

    # Ensure required fields exist
    report.setdefault("request_id", state.request_id)
    report.setdefault("project_code", state.project_code)
    report.setdefault("query", state.query)
    report.setdefault("language", "en")
    report.setdefault("executive_summary", [])
    report.setdefault("financial_snapshot", {
        "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
        "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
        "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
    })
    report.setdefault("key_findings", [])
    report.setdefault("root_causes", [])
    report.setdefault("delay_analysis", [])
    report.setdefault("contractual_implications", [])
    report.setdefault("recommended_actions", [])
    report.setdefault("missing_data", [])
    report.setdefault("conflicts", [])
    report.setdefault("sources", [])
    report.setdefault("quality_gate_status", "not_run")

    # Post-LLM deterministic corrections
    evidence_ids = {e.get("evidence_id", "") for e in state.evidence if isinstance(e, dict)}
    odoo_ctx = _extract_odoo_context(
        [e for e in state.evidence if e.get("source_type") == "odoo"]
    )
    _enforce_financial_from_odoo(report, odoo_ctx, evidence_ids)
    _enforce_missing_data(report, odoo_ctx)
    _enforce_executive_summary(report, state)

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
