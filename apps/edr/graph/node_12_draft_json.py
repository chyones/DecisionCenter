"""Node 12 — Draft JSON Report. Spec: Sections 14 and 16.

Generates the canonical structured report using the heavy tier.
Every claim MUST bind to evidence_ids; financial values MUST come from Odoo.
"""

from __future__ import annotations

import json

from apps.edr.graph import coverage
from apps.edr.graph.state import DecisionState
from apps.edr.llm import call_llm, sanitize_evidence


def _build_prompt(state: DecisionState) -> str:
    # Sanitize every evidence excerpt before it reaches the LLM
    safe_evidence: list[dict] = []
    for ev in state.evidence:
        excerpt = ev.get("excerpt", "")
        safe_excerpt, _ = sanitize_evidence(excerpt)
        safe_ev = dict(ev)
        safe_ev["excerpt"] = safe_excerpt
        safe_evidence.append(safe_ev)

    role = state.role or "unknown"
    can_see_finance = role in ("executive", "project_manager", "finance", "commercial", "procurement", "legal")

    return (
        "You are an executive report writer for a construction-company decision center.\n"
        "Generate a structured JSON report from the verified evidence ONLY.\n\n"
        "ABSOLUTE RULES:\n"
        "1. Every claim MUST have at least one evidence_id.\n"
        "2. Every financial number MUST have an Odoo evidence_id.\n"
        "3. If a required financial value is missing, use status 'not_available' and value null.\n"
        "4. Do NOT invent facts, numbers, or dates.\n"
        "5. Do NOT include execution instructions in Phase 1.\n"
        "6. Recommendations MUST be marked as proposals only.\n"
        "7. Conflicts MUST be disclosed, not hidden.\n\n"
        f"User role: {role}\n"
        f"Can view financials: {can_see_finance}\n"
        f"Query: {state.query}\n"
        f"Project code: {state.project_code}\n"
        f"Request ID: {state.request_id}\n\n"
        "Evidence pack (sanitized):\n"
        f"{json.dumps(safe_evidence, indent=2, ensure_ascii=False)}\n\n"
        "Return JSON matching this exact schema:\n"
        "{\n"
        '  "request_id": "string",\n'
        '  "project_code": "string or null",\n'
        '  "query": "string",\n'
        '  "language": "en or ar",\n'
        '  "executive_summary": [{"claim": "...", "evidence_ids": ["ev_001"], "confidence": "high|medium|low"}],\n'
        '  "financial_snapshot": {\n'
        '    "budget": {"value": null, "currency": "AED", "evidence_id": null, "status": "available|not_available"},\n'
        '    "actual_cost": {"value": null, "currency": "AED", "evidence_id": null, "status": "available|not_available"},\n'
        '    "variance": {"value": null, "currency": "AED", "formula": null, "evidence_ids": []}\n'
        '  },\n'
        '  "key_findings": [{"text": "...", "evidence_ids": ["ev_001"], "confidence": "high|medium|low"}],\n'
        '  "root_causes": [...],\n'
        '  "delay_analysis": [...],\n'
        '  "contractual_implications": [...],\n'
        '  "recommended_actions": [{"text": "...", "evidence_ids": ["ev_001"], "confidence": "high|medium|low"}],\n'
        '  "missing_data": ["string"],\n'
        '  "conflicts": [{"conflict_type": "...", "description": "...", "source_a_ref": "...", "source_b_ref": "...", "confidence_a": "...", "confidence_b": "..."}],\n'
        '  "sources": [{"source_id": "S1", "source_type": "sharepoint|owncloud|email|odoo|cad", "title": "...", "reference": "...", "date": "...", "confidence": "...", "used_in": ["section"]}]\n'
        "}\n"
    )


def _build_report_from_evidence(state: DecisionState) -> dict:
    """Deterministic report builder used in fallback mode (no API key)."""
    evidence = state.evidence
    request_id = state.request_id
    project_code = state.project_code
    query = state.query

    role = state.role or "unknown"
    can_see_finance = role in (
        "executive", "project_manager", "finance", "commercial", "procurement", "legal"
    )

    # Categorize evidence
    odoo_evidence = [e for e in evidence if e.get("source_type") == "odoo"]
    doc_evidence = [e for e in evidence if e.get("source_type") in ("sharepoint", "owncloud")]
    email_evidence = [e for e in evidence if e.get("source_type") == "email"]

    # Financial snapshot from Odoo only
    budget = {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"}
    actual_cost = {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"}
    variance = {"value": None, "currency": "AED", "formula": None, "evidence_ids": []}

    if can_see_finance and odoo_evidence:
        for ev in odoo_evidence:
            excerpt = str(ev.get("excerpt", "")).lower()
            eid = ev.get("evidence_id")
            # Very naive extraction for fallback mode
            if "budget" in excerpt:
                budget["status"] = "available"
                budget["evidence_id"] = eid
            if "actual" in excerpt or "cost" in excerpt:
                actual_cost["status"] = "available"
                actual_cost["evidence_id"] = eid

    # Build findings from document evidence
    key_findings: list[dict] = []
    delay_analysis: list[dict] = []
    contractual_implications: list[dict] = []
    sources_list: list[dict] = []
    used_evidence_ids: set[str] = set()

    for idx, ev in enumerate(doc_evidence + email_evidence, start=1):
        eid = ev.get("evidence_id", f"ev_{idx:06d}")
        used_evidence_ids.add(eid)
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

    # Add Odoo sources
    for idx, ev in enumerate(odoo_evidence, start=len(sources_list) + 1):
        eid = ev.get("evidence_id", f"ev_{idx:06d}")
        used_evidence_ids.add(eid)
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
    if is_financial_query(query) and not odoo_evidence:
        missing_data.append("Odoo financial data not available.")

    report = {
        "request_id": request_id,
        "project_code": project_code,
        "query": query,
        "language": "en",
        "executive_summary": [],
        "financial_snapshot": {
            "budget": budget,
            "actual_cost": actual_cost,
            "variance": variance,
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

    return report


def is_financial_query(query: str) -> bool:
    lower = query.lower()
    return any(kw in lower for kw in ("budget", "cost", "payment", "invoice", "financial", "actual"))


async def run(state: DecisionState) -> DecisionState:
    prompt = _build_prompt(state)
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
        if isinstance(parsed, dict):
            report = parsed
        else:
            report = _build_report_from_evidence(state)
    except Exception:
        report = _build_report_from_evidence(state)

    # If the LLM fallback produced an empty shell but we have evidence,
    # use the deterministic builder to ensure findings are populated.
    has_findings = any(
        report.get(section)
        for section in (
            "executive_summary",
            "key_findings",
            "root_causes",
            "delay_analysis",
            "contractual_implications",
            "recommended_actions",
        )
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

    # Deterministic connector coverage (factual; never LLM-authored). Every
    # enabled source is surfaced with attempted/count/status/reason so a source
    # that returned zero evidence is visible, not hidden.
    report["connector_coverage"] = coverage.report_section(state)

    # Financial transparency: never invent figures. State explicitly when no
    # verified Odoo cost evidence exists.
    if not state.outputs.get("odoo_financial_available"):
        fs = report.get("financial_snapshot")
        if isinstance(fs, dict):
            fs.setdefault("note", "financial data not available in verified Odoo evidence")

    state.report_json = report
    state.outputs["draft_report_status"] = "generated"
    return state.mark("node_12_draft_json")
