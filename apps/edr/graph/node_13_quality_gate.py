"""Node 13 — Quality Gate. Spec: Sections 15, 17, and 16.

Deterministic claim checker.  No LLM is used here.
"""

from __future__ import annotations

import re

from apps.edr.graph import coverage
from apps.edr.graph import report_policy as rp
from apps.edr.graph.intent import classify_report_type
from apps.edr.graph.state import DecisionState
from apps.edr.schemas.quality_gate import ClaimCheck, QualityGateResult


_SEARCH_SUMMARY_PATTERNS = re.compile(
    r"\b(evidence\s+retrieval|evidence\s+review|search\s+results?|"
    r"retrieved|catalogued|document\(s\)\s+and|email\(s\)\s+retrieved|"
    r"available\s+evidence)\b",
    re.IGNORECASE,
)


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
            checks.append(
                ClaimCheck(
                    claim_id=section,
                    verdict="unsupported",
                    evidence_ids=[],
                    reason="Claim has no evidence_ids.",
                )
            )
            continue

        invalid = [e for e in item_eids if e not in evidence_ids]
        if invalid:
            checks.append(
                ClaimCheck(
                    claim_id=section,
                    verdict="unsupported",
                    evidence_ids=item_eids,
                    reason=f"Evidence ID(s) not found in pack: {invalid}.",
                )
            )
        else:
            checks.append(
                ClaimCheck(
                    claim_id=section,
                    verdict="supported",
                    evidence_ids=item_eids,
                    reason="All evidence_ids present in evidence pack.",
                )
            )

    return checks


def _check_financials(report: dict, evidence_ids: set[str]) -> list[ClaimCheck]:
    """Verify every financial number has an Odoo evidence_id."""
    checks: list[ClaimCheck] = []
    fs = report.get("financial_snapshot") or {}
    if not isinstance(fs, dict):
        return checks

    for field in ("budget", "contract_value", "estimate", "actual_cost", "committed_cost"):
        node = fs.get(field)
        if not isinstance(node, dict):
            continue
        status = node.get("status", "not_available")
        # Only "available" figures must be evidence-bound; not_available and
        # "inconclusive" (e.g. Odoo timeout) carry no number to validate.
        if status != "available":
            continue
        eid = node.get("evidence_id")
        if not eid:
            checks.append(
                ClaimCheck(
                    claim_id=f"financial_snapshot.{field}",
                    verdict="unsupported",
                    evidence_ids=[],
                    reason=f"Financial field '{field}' is marked available but has no Odoo evidence_id.",
                )
            )
        elif eid not in evidence_ids:
            checks.append(
                ClaimCheck(
                    claim_id=f"financial_snapshot.{field}",
                    verdict="unsupported",
                    evidence_ids=[eid],
                    reason=f"Financial field '{field}' cites evidence_id '{eid}' which is not in the evidence pack.",
                )
            )

    variance = fs.get("variance")
    if isinstance(variance, dict):
        v_eids = variance.get("evidence_ids", [])
        if v_eids:
            invalid = [e for e in v_eids if e not in evidence_ids]
            if invalid:
                checks.append(
                    ClaimCheck(
                        claim_id="financial_snapshot.variance",
                        verdict="unsupported",
                        evidence_ids=v_eids,
                        reason=f"Variance cites missing evidence_id(s): {invalid}.",
                    )
                )

    return checks


def _check_sources(report: dict, evidence_ids: set[str]) -> list[ClaimCheck]:
    checks: list[ClaimCheck] = []
    sources = report.get("sources", [])
    if not isinstance(sources, list):
        checks.append(
            ClaimCheck(
                claim_id="sources",
                verdict="needs_review",
                evidence_ids=[],
                reason="Sources section is missing or not a list.",
            )
        )
    return checks


def _check_conflicts(report: dict) -> list[ClaimCheck]:
    checks: list[ClaimCheck] = []
    conflicts = report.get("conflicts", [])
    if not isinstance(conflicts, list):
        checks.append(
            ClaimCheck(
                claim_id="conflicts",
                verdict="needs_review",
                evidence_ids=[],
                reason="Conflicts section is not a list.",
            )
        )
    return checks


def _check_executive_summary(report: dict, evidence: list[dict]) -> list[ClaimCheck]:
    """Fail if executive_summary is an explicit empty list when evidence was retrieved.

    An absent key (report produced by a test stub) is not checked.
    Only an explicitly empty list [] with non-empty evidence is a violation.
    """
    checks: list[ClaimCheck] = []
    es = report.get("executive_summary")
    if isinstance(es, list) and len(es) == 0 and evidence:
        checks.append(
            ClaimCheck(
                claim_id="executive_summary",
                verdict="unsupported",
                evidence_ids=[],
                reason=(
                    "Executive summary is empty despite retrieved evidence. "
                    "A report with evidence must include a synthesized executive summary."
                ),
            )
        )
    return checks


def _check_project_identity(report: dict) -> list[ClaimCheck]:
    """Validate the verified Project Identity Contract is present and not guessed."""
    checks: list[ClaimCheck] = []
    pid = report.get("project_identity")
    if not isinstance(pid, dict):
        checks.append(
            ClaimCheck(
                claim_id="project_identity",
                verdict="unsupported",
                evidence_ids=[],
                reason="Report is missing the required project_identity object.",
            )
        )
        return checks

    name = str(pid.get("project_name") or "").strip()
    code = str(pid.get("project_code") or "").strip()
    confidence = pid.get("identity_confidence")

    if not name or name.lower() == "not verified":
        checks.append(
            ClaimCheck(
                claim_id="project_identity.project_name",
                verdict="unsupported",
                evidence_ids=[],
                reason="Project name is missing or not verified; reports must use a verified project name.",
            )
        )
    elif confidence not in ("verified", "partial"):
        checks.append(
            ClaimCheck(
                claim_id="project_identity.identity_confidence",
                verdict="needs_review",
                evidence_ids=[],
                reason=f"Project identity confidence is '{confidence}'; expected verified or partial.",
            )
        )

    if not code:
        checks.append(
            ClaimCheck(
                claim_id="project_identity.project_code",
                verdict="needs_review",
                evidence_ids=[],
                reason="Project code is missing from project_identity.",
            )
        )

    return checks


_FILENAME_RE = re.compile(
    r"^[\w\-.()' &]+\.(pdf|xlsx|xls|docx|doc|pptx|ppt|dwg|dxf|jpe?g|png|csv|zip|rar|txt)$",
    re.IGNORECASE,
)
_FILENAME_EMBEDDED_RE = re.compile(
    r"\b[\w\-]+\.(pdf|xlsx|xls|docx|doc|pptx|ppt|dwg|dxf|jpe?g|png|csv|zip|rar|txt)\b",
    re.IGNORECASE,
)


def _check_raw_filename_findings(report: dict) -> list[ClaimCheck]:
    """Block visible report-body claims that leak raw filenames as analysis."""
    checks: list[ClaimCheck] = []
    for section in (
        "executive_summary",
        "key_findings",
        "root_causes",
        "delay_analysis",
        "contractual_implications",
        "recommended_actions",
    ):
        items = report.get(section, [])
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            text = (item.get("text") or item.get("claim") or "").strip()
            if text and (_FILENAME_RE.match(text) or _FILENAME_EMBEDDED_RE.search(text)):
                eids = item.get("evidence_ids", [])
                checks.append(
                    ClaimCheck(
                        claim_id=f"{section}[{idx}].raw_filename",
                        verdict="unsupported",
                        evidence_ids=eids if isinstance(eids, list) else [],
                        reason=(
                            "Visible report body contains a raw filename rather than "
                            "executive-facing synthesized analysis."
                        ),
                    )
                )
    return checks


def _check_intent_correctness(report: dict, query: str) -> list[ClaimCheck]:
    """Ensure report type matches query intent and non-management reports do not use MQA framing."""
    checks: list[ClaimCheck] = []
    report_type = report.get("report_type", classify_report_type(query))
    mqa = report.get("management_question_answer") or {}
    has_mqa_answer = isinstance(mqa, dict) and bool((mqa.get("executive_answer") or "").strip())

    if report_type in ("salary_payroll", "data_report", "document_search") and has_mqa_answer:
        checks.append(
            ClaimCheck(
                claim_id="intent.management_question_answer",
                verdict="needs_review",
                evidence_ids=[],
                reason=f"Report type is '{report_type}' but management_question_answer is populated.",
            )
        )

    if report_type == "salary_payroll":
        es = report.get("executive_summary", [])
        text = " ".join(item.get("claim", "") for item in es if isinstance(item, dict)).lower()
        if "biggest problem" in text or "management should decide" in text:
            checks.append(
                ClaimCheck(
                    claim_id="intent.salary_payroll_framing",
                    verdict="needs_review",
                    evidence_ids=[],
                    reason="Salary/payroll report uses management-decision or 'biggest problem' framing.",
                )
            )

    return checks


def _check_irrelevant_sections(report: dict, query: str) -> list[ClaimCheck]:
    """Reports must not carry sections that do not belong to their type.

    - salary/data: no root_causes/delay_analysis/contractual_implications.
    - document_search: also no financial snapshot (a retrieval/listing answer).
    """
    checks: list[ClaimCheck] = []
    report_type = report.get("report_type", classify_report_type(query))
    if report_type not in ("salary_payroll", "data_report", "document_search"):
        return checks

    irrelevant: list[str] = []
    for section in ("root_causes", "delay_analysis", "contractual_implications"):
        data = report.get(section, [])
        if isinstance(data, list) and data:
            irrelevant.append(section)
    if report_type == "document_search":
        fs = report.get("financial_snapshot") or {}
        if isinstance(fs, dict) and any(
            isinstance(fs.get(k), dict) and fs[k].get("status") == "available"
            for k in ("budget", "contract_value", "estimate", "actual_cost", "committed_cost")
        ):
            irrelevant.append("financial_snapshot")

    if irrelevant:
        checks.append(
            ClaimCheck(
                claim_id="intent.irrelevant_sections",
                verdict="needs_review",
                evidence_ids=[],
                reason=f"{report_type} report contains irrelevant sections: {irrelevant}.",
            )
        )

    return checks


def _check_confidence_against_evidence(
    report: dict, evidence: list[dict], state: DecisionState
) -> list[ClaimCheck]:
    """Cap confidence when evidence is partial or sources timed out / errored."""
    checks: list[ClaimCheck] = []
    cov = coverage.summary(state)
    has_timeouts = any(
        entry.get("status") == "timeout"
        for entry in cov["sources"].values()
        if entry.get("enabled")
    )
    has_errors = bool(cov.get("connector_errors"))

    high_claim_sections: list[str] = []
    for section, item in _collect_claims(report):
        if item.get("confidence") == "high":
            high_claim_sections.append(section)

    if high_claim_sections and (has_timeouts or has_errors):
        checks.append(
            ClaimCheck(
                claim_id="confidence.cap_high_confidence",
                verdict="needs_review",
                evidence_ids=[],
                reason=(
                    f"High-confidence claims found in {high_claim_sections} despite "
                    f"source failures (timeouts={has_timeouts}, errors={has_errors})."
                ),
            )
        )

    return checks


def _check_timeout_semantics(report: dict, state: DecisionState) -> list[ClaimCheck]:
    """A timed-out source must be described as inconclusive, never as 'no data'."""
    checks: list[ClaimCheck] = []
    cov = coverage.summary(state)
    has_timeouts = any(
        entry.get("status") == "timeout"
        for entry in cov["sources"].values()
        if entry.get("enabled")
    )
    if not has_timeouts:
        return checks

    missing = report.get("missing_data", [])
    text = " ".join(str(m) for m in missing).lower()
    if "no data" in text or "returned empty" in text or "empty result" in text:
        checks.append(
            ClaimCheck(
                claim_id="semantics.timeout_as_no_data",
                verdict="needs_review",
                evidence_ids=[],
                reason="A source timed out but missing_data describes it as 'no data' or 'empty' instead of inconclusive.",
            )
        )

    return checks


def _check_search_summary_patterns(report: dict) -> list[ClaimCheck]:
    """Flag reports whose executive summary reads like an evidence catalog."""
    checks: list[ClaimCheck] = []
    es = report.get("executive_summary", [])
    if not isinstance(es, list):
        return checks

    for idx, item in enumerate(es):
        if not isinstance(item, dict):
            continue
        claim = item.get("claim", "")
        if _SEARCH_SUMMARY_PATTERNS.search(claim):
            checks.append(
                ClaimCheck(
                    claim_id=f"executive_summary[{idx}]",
                    verdict="needs_review",
                    evidence_ids=item.get("evidence_ids", []),
                    reason=(
                        "Executive summary appears to be a search/evidence summary "
                        "rather than an analytical answer to the query."
                    ),
                )
            )
    return checks


def _check_management_question_answer(report: dict, query: str) -> list[ClaimCheck]:
    """Validate that focused management questions receive a decision-memo answer."""
    checks: list[ClaimCheck] = []
    report_type = report.get("report_type") or classify_report_type(query)
    if report_type != "management_question":
        return checks

    mqa = report.get("management_question_answer")
    if not isinstance(mqa, dict):
        checks.append(
            ClaimCheck(
                claim_id="management_question_answer",
                verdict="unsupported",
                evidence_ids=[],
                reason="Management question requires a management_question_answer object.",
            )
        )
        return checks

    executive_answer = (mqa.get("executive_answer") or "").strip()
    if not executive_answer:
        checks.append(
            ClaimCheck(
                claim_id="management_question_answer.executive_answer",
                verdict="unsupported",
                evidence_ids=[],
                reason="Management question requires a non-empty executive_answer.",
            )
        )

    why = mqa.get("why_biggest_problem")
    if not isinstance(why, list) or len(why) < 3:
        checks.append(
            ClaimCheck(
                claim_id="management_question_answer.why_biggest_problem",
                verdict="needs_review",
                evidence_ids=[],
                reason="Management question answer should provide 3-5 bullets explaining why this is the biggest problem.",
            )
        )

    impact = mqa.get("business_impact") or {}
    if not isinstance(impact, dict) or not all(
        (impact.get(k) or "").strip()
        for k in ("schedule_impact", "cost_commercial_impact", "operational_client_impact")
    ):
        checks.append(
            ClaimCheck(
                claim_id="management_question_answer.business_impact",
                verdict="needs_review",
                evidence_ids=[],
                reason="Business impact should cover schedule, cost/commercial, and operational/client dimensions.",
            )
        )

    decision = (mqa.get("decision_required") or "").strip()
    if not decision:
        checks.append(
            ClaimCheck(
                claim_id="management_question_answer.decision_required",
                verdict="needs_review",
                evidence_ids=[],
                reason="Management question answer should state what management must decide now.",
            )
        )

    action = mqa.get("recommended_action") or {}
    if not isinstance(action, dict) or not (
        (action.get("specific_action") or "").strip() and (action.get("owner_role") or "").strip()
    ):
        checks.append(
            ClaimCheck(
                claim_id="management_question_answer.recommended_action",
                verdict="needs_review",
                evidence_ids=[],
                reason="Recommended action should include specific_action and owner_role.",
            )
        )

    risks = (mqa.get("risks_if_no_action") or "").strip()
    if not risks:
        checks.append(
            ClaimCheck(
                claim_id="management_question_answer.risks_if_no_action",
                verdict="needs_review",
                evidence_ids=[],
                reason="Management question answer should include risks_if_no_action.",
            )
        )

    confidence = mqa.get("confidence")
    if confidence not in ("high", "medium", "low"):
        checks.append(
            ClaimCheck(
                claim_id="management_question_answer.confidence",
                verdict="needs_review",
                evidence_ids=[],
                reason="Confidence must be high, medium, or low.",
            )
        )

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
        s
        for s, v in sections.items()
        if v["priority"] == "critical" and v["status"] in ("empty", "not_available")
    ]
    important_empty = [
        s
        for s, v in sections.items()
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

    # Per-type quality-gate profile: the ReportPolicy decides which check
    # families apply. Order is preserved so the emitted check list is identical
    # to the previous unconditional sequence for every report type (the
    # type-specific checks already self-gated and returned [] otherwise).
    report_type = report.get("report_type") or classify_report_type(state.query)
    policy = rp.policy_for(report_type)
    check_runners = (
        (rp.CHK_CLAIMS, lambda: _check_claims(report, evidence_ids)),
        (rp.CHK_FINANCIALS, lambda: _check_financials(report, evidence_ids)),
        (rp.CHK_SOURCES, lambda: _check_sources(report, evidence_ids)),
        (rp.CHK_CONFLICTS, lambda: _check_conflicts(report)),
        (rp.CHK_EXECUTIVE_SUMMARY, lambda: _check_executive_summary(report, evidence)),
        (rp.CHK_SEARCH_SUMMARY, lambda: _check_search_summary_patterns(report)),
        (rp.CHK_RAW_FILENAME, lambda: _check_raw_filename_findings(report)),
        (
            rp.CHK_MANAGEMENT_QUESTION_ANSWER,
            lambda: _check_management_question_answer(report, state.query),
        ),
        (rp.CHK_PROJECT_IDENTITY, lambda: _check_project_identity(report)),
        (rp.CHK_INTENT_CORRECTNESS, lambda: _check_intent_correctness(report, state.query)),
        (rp.CHK_IRRELEVANT_SECTIONS, lambda: _check_irrelevant_sections(report, state.query)),
        (
            rp.CHK_CONFIDENCE,
            lambda: _check_confidence_against_evidence(report, evidence, state),
        ),
        (rp.CHK_TIMEOUT_SEMANTICS, lambda: _check_timeout_semantics(report, state)),
    )
    all_checks: list[ClaimCheck] = []
    for _check_name, _run_check in check_runners:
        if policy.runs_check(_check_name):
            all_checks += _run_check()

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
        all_checks.append(
            ClaimCheck(
                claim_id="global",
                verdict="unsupported",
                evidence_ids=[],
                reason="No evidence retrieved and no claims generated.",
            )
        )

    # Connector coverage: enabled sources must be attempted; errors are not silent passes.
    cov = coverage.summary(state)
    completeness = cov["completeness"]
    coverage_blocking = list(cov["connector_errors"]) + list(cov["not_attempted_sources"])
    if coverage_blocking:
        if verdict == "passed":
            verdict = "needs_review"
        all_checks.append(
            ClaimCheck(
                claim_id="connector_coverage",
                verdict="needs_review",
                evidence_ids=[],
                reason=(
                    "Enabled source(s) not satisfied (errored or not attempted): "
                    f"{coverage_blocking}."
                ),
            )
        )

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
