"""Report-type policy registry — the single source of truth that maps a report
type to the sections it renders and the quality-gate checks that apply.

This is the spine for the type-driven report pipeline. Consumers:
* the renderers gate sections on ``policy.renders(SEC_*)``;
* node_13 runs only the check families in ``policy.qg_checks``;
* ``sources_required``/``sources_optional`` describe the source policy per type
  (advisory until node-level enforcement lands).

Report-type keys are exactly the values ``intent.classify_report_type`` emits.
``policy_for`` falls back to the general policy for unknown types.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Section identifiers (match canonical report_json keys) -----------------
SEC_EXECUTIVE_SUMMARY = "executive_summary"
SEC_MANAGEMENT_QUESTION_ANSWER = "management_question_answer"
SEC_FINANCIAL_SNAPSHOT = "financial_snapshot"
SEC_KEY_FINDINGS = "key_findings"
SEC_ROOT_CAUSES = "root_causes"
SEC_DELAY_ANALYSIS = "delay_analysis"
SEC_CONTRACTUAL = "contractual_implications"
SEC_RECOMMENDED_ACTIONS = "recommended_actions"
SEC_CONFLICTS = "conflicts"
SEC_MISSING_DATA = "missing_data"
SEC_SOURCES = "sources"
SEC_QUALITY_GATE = "quality_gate"

# --- Quality-gate check families (match the check groups in node_13) --------
CHK_CLAIMS = "claims"
CHK_FINANCIALS = "financials"
CHK_SOURCES = "sources"
CHK_CONFLICTS = "conflicts"
CHK_EXECUTIVE_SUMMARY = "executive_summary"
CHK_SEARCH_SUMMARY = "search_summary"
CHK_PROJECT_IDENTITY = "project_identity"
CHK_CONFIDENCE = "confidence"
CHK_TIMEOUT_SEMANTICS = "timeout_semantics"
CHK_MANAGEMENT_QUESTION_ANSWER = "management_question_answer"
CHK_INTENT_CORRECTNESS = "intent_correctness"
CHK_IRRELEVANT_SECTIONS = "irrelevant_sections"

#: Checks every report runs regardless of type. (Connector-coverage gating is
#: applied unconditionally in node_13.run and is intentionally not listed here.)
BASELINE_CHECKS: tuple[str, ...] = (
    CHK_CLAIMS,
    CHK_FINANCIALS,
    CHK_SOURCES,
    CHK_CONFLICTS,
    CHK_EXECUTIVE_SUMMARY,
    CHK_SEARCH_SUMMARY,
    CHK_PROJECT_IDENTITY,
    CHK_CONFIDENCE,
    CHK_TIMEOUT_SEMANTICS,
)

# Numbered + special sections in render order, for the full executive shape.
_FULL_SECTIONS: tuple[str, ...] = (
    SEC_EXECUTIVE_SUMMARY,
    SEC_MANAGEMENT_QUESTION_ANSWER,
    SEC_FINANCIAL_SNAPSHOT,
    SEC_KEY_FINDINGS,
    SEC_ROOT_CAUSES,
    SEC_DELAY_ANALYSIS,
    SEC_CONTRACTUAL,
    SEC_RECOMMENDED_ACTIONS,
    SEC_CONFLICTS,
    SEC_MISSING_DATA,
    SEC_SOURCES,
    SEC_QUALITY_GATE,
)
# Salary / data reports are focused extracts: they omit Root Causes / Delay /
# Contractual AND the financial snapshot (an all-"Not available" budget table
# is noise on an HR/data extract).
_DATA_SECTIONS: tuple[str, ...] = (
    SEC_EXECUTIVE_SUMMARY,
    SEC_KEY_FINDINGS,
    SEC_RECOMMENDED_ACTIONS,
    SEC_CONFLICTS,
    SEC_MISSING_DATA,
    SEC_SOURCES,
    SEC_QUALITY_GATE,
)
# Financial reports keep the financial snapshot; drop root-cause/delay/
# contractual/MQA (those belong to decision/risk/delay reports).
_FINANCIAL_SECTIONS: tuple[str, ...] = (
    SEC_EXECUTIVE_SUMMARY,
    SEC_FINANCIAL_SNAPSHOT,
    SEC_KEY_FINDINGS,
    SEC_RECOMMENDED_ACTIONS,
    SEC_CONFLICTS,
    SEC_MISSING_DATA,
    SEC_SOURCES,
    SEC_QUALITY_GATE,
)
# Risk reports: findings + root causes + contractual implications (the risk
# register surface); no financial snapshot, no delay analysis, no MQA.
_RISK_SECTIONS: tuple[str, ...] = (
    SEC_EXECUTIVE_SUMMARY,
    SEC_KEY_FINDINGS,
    SEC_ROOT_CAUSES,
    SEC_CONTRACTUAL,
    SEC_RECOMMENDED_ACTIONS,
    SEC_CONFLICTS,
    SEC_MISSING_DATA,
    SEC_SOURCES,
    SEC_QUALITY_GATE,
)
# Delay reports: delay analysis + root causes; no financial, no contractual, no MQA.
_DELAY_SECTIONS: tuple[str, ...] = (
    SEC_EXECUTIVE_SUMMARY,
    SEC_KEY_FINDINGS,
    SEC_DELAY_ANALYSIS,
    SEC_ROOT_CAUSES,
    SEC_RECOMMENDED_ACTIONS,
    SEC_CONFLICTS,
    SEC_MISSING_DATA,
    SEC_SOURCES,
    SEC_QUALITY_GATE,
)
# Document search: a compact list of located documents; no financial, no
# management framing, no root-cause/delay/contractual, no recommendations.
_DOCUMENT_SECTIONS: tuple[str, ...] = (
    SEC_EXECUTIVE_SUMMARY,
    SEC_KEY_FINDINGS,
    SEC_SOURCES,
    SEC_MISSING_DATA,
    SEC_QUALITY_GATE,
)

#: Project sources a report of each type considers.
_PROJECT_SOURCES: tuple[str, ...] = ("odoo", "sharepoint", "email")


@dataclass(frozen=True)
class ReportPolicy:
    report_type: str
    sections: tuple[str, ...]
    qg_checks: tuple[str, ...]
    sources_required: tuple[str, ...] = ()
    sources_optional: tuple[str, ...] = _PROJECT_SOURCES

    def renders(self, section: str) -> bool:
        return section in self.sections

    def runs_check(self, check: str) -> bool:
        return check in self.qg_checks


#: Report types — exactly the values intent.classify_report_type emits.
POLICY: dict[str, ReportPolicy] = {
    "management_question": ReportPolicy(
        report_type="management_question",
        sections=_FULL_SECTIONS,
        qg_checks=BASELINE_CHECKS + (CHK_MANAGEMENT_QUESTION_ANSWER,),
    ),
    "salary_payroll": ReportPolicy(
        report_type="salary_payroll",
        sections=_DATA_SECTIONS,
        qg_checks=BASELINE_CHECKS + (CHK_INTENT_CORRECTNESS, CHK_IRRELEVANT_SECTIONS),
    ),
    "data_report": ReportPolicy(
        report_type="data_report",
        sections=_DATA_SECTIONS,
        qg_checks=BASELINE_CHECKS + (CHK_INTENT_CORRECTNESS, CHK_IRRELEVANT_SECTIONS),
    ),
    "financial": ReportPolicy(
        report_type="financial",
        sections=_FINANCIAL_SECTIONS,
        qg_checks=BASELINE_CHECKS,
        sources_required=("odoo",),
    ),
    "risk": ReportPolicy(
        report_type="risk",
        sections=_RISK_SECTIONS,
        qg_checks=BASELINE_CHECKS,
    ),
    "delay": ReportPolicy(
        report_type="delay",
        sections=_DELAY_SECTIONS,
        qg_checks=BASELINE_CHECKS,
    ),
    "document_search": ReportPolicy(
        report_type="document_search",
        sections=_DOCUMENT_SECTIONS,
        qg_checks=BASELINE_CHECKS,
        sources_required=("sharepoint",),
    ),
    "general_project_status": ReportPolicy(
        report_type="general_project_status",
        sections=_FULL_SECTIONS,
        qg_checks=BASELINE_CHECKS,
    ),
}

#: Default used for unknown / not-yet-emitted report types.
DEFAULT_POLICY: ReportPolicy = POLICY["general_project_status"]


def policy_for(report_type: str | None) -> ReportPolicy:
    """Return the policy for ``report_type`` (general default when unknown)."""
    if not report_type:
        return DEFAULT_POLICY
    return POLICY.get(report_type, DEFAULT_POLICY)


def qg_checks_for(report_type: str | None) -> tuple[str, ...]:
    return policy_for(report_type).qg_checks


def sections_for(report_type: str | None) -> tuple[str, ...]:
    return policy_for(report_type).sections
