"""Report-type policy registry — the single source of truth that maps a report
type to the sections it renders and the quality-gate checks that apply.

This is the spine for the type-driven report pipeline. It is intentionally
*descriptive of current behaviour* so consumers can adopt it without changing
outputs:

* ``sections`` mirrors what ``exporters/markdown.py`` emits today (salary/data
  reports already omit Root Causes / Delay / Contractual).
* ``qg_checks`` mirrors the effective gating in ``node_13_quality_gate`` today
  (the management/intent/irrelevant checks already self-gate on report type;
  listing them here lets the gate skip the no-ops explicitly instead).

Report-type keys are exactly the values ``intent.classify_report_type`` emits
today. Future types (financial, risk, delay, document_search) will be added here
alongside the resolver change that emits them (slices 4-5); until then
``policy_for`` falls back to the general policy, which is the current default.

Nothing in this module changes runtime behaviour on its own — consumers opt in.
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

# Numbered + special sections in render order, for the two current shapes.
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

#: Project sources a report of each type considers. Today every enabled source
#: is attempted regardless of type, so these are advisory until slice 4 wires a
#: source policy; ``required`` is empty to avoid asserting unenforced behaviour.
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


#: Active report types — exactly the values intent.classify_report_type emits.
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
