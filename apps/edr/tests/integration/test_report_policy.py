"""Tests — the ReportPolicy registry (spine) is accurate and complete.

Pins the policy to the report types the classifier actually emits, and to the
per-type section/QG shape, so renderer + quality gate can rely on it.
"""

from __future__ import annotations

from apps.edr.graph import report_policy as rp
from apps.edr.graph.intent import classify_report_type

# The complete, authoritative output set of intent.classify_report_type.
_CLASSIFIER_TYPES = {
    "management_question",
    "salary_payroll",
    "financial",
    "risk",
    "delay",
    "document_search",
    "data_report",
    "general_project_status",
}


def test_policy_covers_exactly_the_classifier_report_types():
    assert set(rp.POLICY) == _CLASSIFIER_TYPES


def test_every_classified_query_has_a_policy_entry():
    samples = {
        "what is the biggest problem for this project": "management_question",
        "give me salary report by staff name and file id": "salary_payroll",
        "what is the actual cost and budget variance": "financial",
        "show me the risk register and claims": "risk",
        "what is the delay status and EOT": "delay",
        "find the latest drawing document": "document_search",
        "give me a table of all log entries by id": "data_report",
        "what is the current status of the project": "general_project_status",
    }
    for q, expected in samples.items():
        rt = classify_report_type(q)
        assert rt == expected, (q, rt)
        assert rt in rp.POLICY
        assert rp.policy_for(rt).report_type == rt


def test_unknown_and_none_fall_back_to_general_default():
    assert rp.policy_for(None) is rp.DEFAULT_POLICY
    assert rp.policy_for("totally_unknown_type") is rp.DEFAULT_POLICY
    assert rp.DEFAULT_POLICY.report_type == "general_project_status"


def test_management_profile_runs_mqa_check_others_do_not():
    assert rp.policy_for("management_question").runs_check(rp.CHK_MANAGEMENT_QUESTION_ANSWER)
    for rt in ("general_project_status", "salary_payroll", "financial", "risk", "delay",
               "document_search", "data_report"):
        assert not rp.policy_for(rt).runs_check(rp.CHK_MANAGEMENT_QUESTION_ANSWER), rt


def test_salary_and_data_profiles_run_intent_and_irrelevant_checks():
    for rt in ("salary_payroll", "data_report"):
        pol = rp.policy_for(rt)
        assert pol.runs_check(rp.CHK_INTENT_CORRECTNESS)
        assert pol.runs_check(rp.CHK_IRRELEVANT_SECTIONS)
    assert not rp.policy_for("general_project_status").runs_check(rp.CHK_INTENT_CORRECTNESS)


def test_baseline_checks_apply_to_every_type():
    for rt in rp.POLICY:
        assert set(rp.BASELINE_CHECKS) <= set(rp.qg_checks_for(rt)), rt


def test_sections_match_current_renderer_shape():
    # Salary/data are focused extracts: omit Root Causes / Delay / Contractual
    # AND the financial snapshot. Full reports keep all of them.
    for rt in ("salary_payroll", "data_report"):
        secs = rp.sections_for(rt)
        assert rp.SEC_ROOT_CAUSES not in secs
        assert rp.SEC_DELAY_ANALYSIS not in secs
        assert rp.SEC_CONTRACTUAL not in secs
        assert rp.SEC_FINANCIAL_SNAPSHOT not in secs

    full = rp.sections_for("general_project_status")
    for sec in (
        rp.SEC_ROOT_CAUSES,
        rp.SEC_DELAY_ANALYSIS,
        rp.SEC_CONTRACTUAL,
        rp.SEC_FINANCIAL_SNAPSHOT,
    ):
        assert sec in full


def test_new_type_section_shapes():
    # Financial keeps the financial snapshot; drops MQA/root/delay/contractual.
    fin = rp.sections_for("financial")
    assert rp.SEC_FINANCIAL_SNAPSHOT in fin
    assert rp.SEC_MANAGEMENT_QUESTION_ANSWER not in fin
    assert rp.SEC_ROOT_CAUSES not in fin and rp.SEC_DELAY_ANALYSIS not in fin

    # Risk surfaces findings/root-causes/contractual; no financial snapshot, no delay.
    risk = rp.sections_for("risk")
    assert rp.SEC_FINANCIAL_SNAPSHOT not in risk
    assert rp.SEC_DELAY_ANALYSIS not in risk
    assert rp.SEC_CONTRACTUAL in risk and rp.SEC_ROOT_CAUSES in risk

    # Delay surfaces delay analysis + root causes; no financial, no contractual.
    delay = rp.sections_for("delay")
    assert rp.SEC_DELAY_ANALYSIS in delay
    assert rp.SEC_FINANCIAL_SNAPSHOT not in delay
    assert rp.SEC_CONTRACTUAL not in delay

    # Document search is compact: no financial/MQA/root/delay/contractual.
    doc = rp.sections_for("document_search")
    for sec in (
        rp.SEC_FINANCIAL_SNAPSHOT,
        rp.SEC_MANAGEMENT_QUESTION_ANSWER,
        rp.SEC_ROOT_CAUSES,
        rp.SEC_DELAY_ANALYSIS,
        rp.SEC_CONTRACTUAL,
    ):
        assert sec not in doc
    assert rp.SEC_KEY_FINDINGS in doc and rp.SEC_SOURCES in doc


def test_source_policy_hints():
    assert rp.policy_for("financial").sources_required == ("odoo",)
    assert rp.policy_for("document_search").sources_required == ("sharepoint",)
