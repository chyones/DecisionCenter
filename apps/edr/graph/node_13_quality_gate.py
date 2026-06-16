"""Node 13 — Quality Gate. Spec: Sections 15, 17, and 16.

Deterministic claim checker.  No LLM is used here.
"""

from __future__ import annotations

from apps.edr.graph import coverage
from apps.edr.graph.state import DecisionState
from apps.edr.schemas.quality_gate import ClaimCheck, QualityGateResult


def _collect_claims(report: dict) -> list[tuple[str, dict]]:
    """Flatten all claim-bearing sections into (section_name, item) pairs."""
    claims: list[tuple[str, dict]] = []
    for section in (
        "executive_summary",
        "key_findings",
        "root_causes",
        "delay_analysis",
        "contractual_implications",
        "recommended_actions",
    ):
        for idx, item in enumerate(report.get(section, [])):
            if isinstance(item, dict):
                claims.append((f"{section}[{idx}]", item))
    return claims


def _check_claims(report: dict, evidence_ids: set[str]) -> list[ClaimCheck]:
    """Verify every claim carries at least one valid evidence_id."""
    checks: list[ClaimCheck] = []
    claims = _collect_claims(report)

    for section, item in claims:
        item_eids = item.get("evidence_ids", [])
        if not item_eids:
            checks.append(ClaimCheck(
                claim_id=section,
                verdict="unsupported",
                evidence_ids=[],
                reason="Claim has no evidence_ids.",
            ))
            continue

        invalid = [e for e in item_eids if e not in evidence_ids]
        if invalid:
            checks.append(ClaimCheck(
                claim_id=section,
                verdict="unsupported",
                evidence_ids=item_eids,
                reason=f"Evidence ID(s) not found in pack: {invalid}.",
            ))
        else:
            checks.append(ClaimCheck(
                claim_id=section,
                verdict="supported",
                evidence_ids=item_eids,
                reason="All evidence_ids present in evidence pack.",
            ))

    return checks


def _check_financials(report: dict, evidence_ids: set[str]) -> list[ClaimCheck]:
    """Verify every financial number has an Odoo evidence_id."""
    checks: list[ClaimCheck] = []
    fs = report.get("financial_snapshot") or {}
    if not isinstance(fs, dict):
        return checks

    for field in ("budget", "actual_cost"):
        node = fs.get(field)
        if not isinstance(node, dict):
            continue
        status = node.get("status", "not_available")
        if status == "not_available":
            continue
        eid = node.get("evidence_id")
        if not eid:
            checks.append(ClaimCheck(
                claim_id=f"financial_snapshot.{field}",
                verdict="unsupported",
                evidence_ids=[],
                reason=f"Financial field '{field}' is marked available but has no Odoo evidence_id.",
            ))
        elif eid not in evidence_ids:
            checks.append(ClaimCheck(
                claim_id=f"financial_snapshot.{field}",
                verdict="unsupported",
                evidence_ids=[eid],
                reason=f"Financial field '{field}' cites evidence_id '{eid}' which is not in the evidence pack.",
            ))

    variance = fs.get("variance")
    if isinstance(variance, dict):
        v_eids = variance.get("evidence_ids", [])
        if v_eids:
            invalid = [e for e in v_eids if e not in evidence_ids]
            if invalid:
                checks.append(ClaimCheck(
                    claim_id="financial_snapshot.variance",
                    verdict="unsupported",
                    evidence_ids=v_eids,
                    reason=f"Variance cites missing evidence_id(s): {invalid}.",
                ))

    return checks


def _check_sources(report: dict, evidence_ids: set[str]) -> list[ClaimCheck]:
    checks: list[ClaimCheck] = []
    sources = report.get("sources", [])
    if not isinstance(sources, list):
        checks.append(ClaimCheck(
            claim_id="sources",
            verdict="needs_review",
            evidence_ids=[],
            reason="Sources section is missing or not a list.",
        ))
    return checks


def _check_conflicts(report: dict) -> list[ClaimCheck]:
    checks: list[ClaimCheck] = []
    conflicts = report.get("conflicts", [])
    if not isinstance(conflicts, list):
        checks.append(ClaimCheck(
            claim_id="conflicts",
            verdict="needs_review",
            evidence_ids=[],
            reason="Conflicts section is not a list.",
        ))
    return checks


def _check_executive_summary(report: dict, evidence: list[dict]) -> list[ClaimCheck]:
    """Fail if executive_summary is an explicit empty list when evidence was retrieved.

    An absent key (report produced by a test stub) is not checked.
    Only an explicitly empty list [] with non-empty evidence is a violation.
    """
    checks: list[ClaimCheck] = []
    es = report.get("executive_summary")
    if isinstance(es, list) and len(es) == 0 and evidence:
        checks.append(ClaimCheck(
            claim_id="executive_summary",
            verdict="unsupported",
            evidence_ids=[],
            reason=(
                "Executive summary is empty despite retrieved evidence. "
                "A report with evidence must include a synthesized executive summary."
            ),
        ))
    return checks


def _compute_analytical_completeness(report: dict) -> dict:
    """Compute per-section analytical completeness as metadata.

    This does not affect the QG verdict; it is surfaced as
    report['analytical_completeness'] and state.outputs['analytical_completeness']
    so the UI and operators can see exactly which sections were populated.
    """
    section_specs: list[tuple[str, str, str]] = [
        # (key, priority, type)
        ("executive_summary", "critical", "list"),
        ("key_findings", "important", "list"),
        ("delay_analysis", "contextual", "list"),
        ("root_causes", "contextual", "list"),
        ("contractual_implications", "contextual", "list"),
        ("recommended_actions", "important", "list"),
    ]
    fs = report.get("financial_snapshot") or {}
    financial_specs: list[tuple[str, str]] = [
        ("budget", "critical"),
        ("actual_cost", "important"),
    ]

    sections: dict[str, dict] = {}
    for key, priority, _ in section_specs:
        data = report.get(key, [])
        status = "populated" if isinstance(data, list) and data else "empty"
        sections[key] = {"status": status, "priority": priority}

    for field, priority in financial_specs:
        node = fs.get(field) if isinstance(fs, dict) else None
        status = (
            "available"
            if isinstance(node, dict) and node.get("status") == "available"
            else "not_available"
        )
        sections[f"financial_{field}"] = {"status": status, "priority": priority}

    critical_empty = [
        s for s, v in sections.items()
        if v["priority"] == "critical" and v["status"] in ("empty", "not_available")
    ]
    important_empty = [
        s for s, v in sections.items()
        if v["priority"] == "important" and v["status"] in ("empty", "not_available")
    ]

    if critical_empty:
        overall = "incomplete"
    elif important_empty:
        overall = "partial"
    else:
        overall = "complete"

    return {
        "overall": overall,
        "sections": sections,
        "critical_empty": critical_empty,
        "important_empty": important_empty,
    }


async def run(state: DecisionState) -> DecisionState:
    report = state.report_json or {}
    evidence = state.evidence
    evidence_ids = {e.get("evidence_id", "") for e in evidence if isinstance(e, dict)}

    claim_checks = _check_claims(report, evidence_ids)
    financial_checks = _check_financials(report, evidence_ids)
    source_checks = _check_sources(report, evidence_ids)
    conflict_checks = _check_conflicts(report)
    summary_checks = _check_executive_summary(report, evidence)

    all_checks = claim_checks + financial_checks + source_checks + conflict_checks + summary_checks

    unsupported = [c for c in all_checks if c.verdict == "unsupported"]
    needs_review = [c for c in all_checks if c.verdict == "needs_review"]

    if unsupported:
        verdict = "failed"
    elif needs_review:
        verdict = "needs_review"
    else:
        verdict = "passed"

    # No claims at all and no evidence → empty report
    claims = _collect_claims(report)
    if not claims and not evidence:
        verdict = "failed"
        all_checks.append(ClaimCheck(
            claim_id="global",
            verdict="unsupported",
            evidence_ids=[],
            reason="No evidence retrieved and no claims generated.",
        ))

    # Connector coverage: enabled sources must be attempted; errors are not silent passes.
    cov = coverage.summary(state)
    completeness = cov["completeness"]
    coverage_blocking = list(cov["connector_errors"]) + list(cov["not_attempted_sources"])
    if coverage_blocking:
        if verdict == "passed":
            verdict = "needs_review"
        all_checks.append(ClaimCheck(
            claim_id="connector_coverage",
            verdict="needs_review",
            evidence_ids=[],
            reason=(
                "Enabled source(s) not satisfied (errored or not attempted): "
                f"{coverage_blocking}."
            ),
        ))

    # Analytical completeness metadata (does not change verdict)
    analytical = _compute_analytical_completeness(report)

    # Embed both completeness measures in the report
    if isinstance(report, dict):
        report["quality_gate_status"] = verdict
        report["evidence_completeness"] = completeness
        report["analytical_completeness"] = analytical["overall"]

    qg_result = QualityGateResult(
        request_id=state.request_id,
        verdict=verdict,
        checks=all_checks,
    )

    state.outputs["quality_gate"] = verdict
    state.outputs["quality_gate_result"] = qg_result.model_dump()
    state.outputs["evidence_completeness"] = completeness
    state.outputs["analytical_completeness"] = analytical
    state.outputs["connector_coverage"] = cov["sources"]
    state.outputs["quality_gate unsupported_count"] = len(unsupported)
    state.outputs["quality_gate needs_review_count"] = len(needs_review)

    return state.mark("node_13_quality_gate")
