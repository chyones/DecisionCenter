"""Slice 3a tests — the ReportPolicy registry (spine) is accurate and complete.

These pin the policy to the *current* behaviour so it can be adopted by the
renderer / quality gate without changing outputs, and so the policy can't drift
away from the report types the classifier actually emits.
"""

from __future__ import annotations

from apps.edr.graph import report_policy as rp
from apps.edr.graph.intent import classify_report_type

# The complete, authoritative output set of intent.classify_report_type.
_CLASSIFIER_TYPES = {
    "management_question",
    "salary_payroll",
    "data_report",
    "general_project_status",
}


def test_policy_covers_exactly_the_classifier_report_types():
    assert set(rp.POLICY) == _CLASSIFIER_TYPES


def test_every_classified_query_has_a_policy_entry():
    # Each sample must classify to a type the policy knows (reachability).
    samples = (
        "what is the biggest problem for this project",   # management_question
        "give me salary report by staff name and file id",  # salary_payroll
        "list all delay analysis reports by date",         # data_report
        "what is the current status of the project",       # general_project_status
    )
    for q in samples:
        rt = classify_report_type(q)
        assert rt in rp.POLICY, (q, rt)
        assert rp.policy_for(rt).report_type == rt


def test_unknown_and_none_fall_back_to_general_default():
    assert rp.policy_for(None) is rp.DEFAULT_POLICY
    assert rp.policy_for("financial") is rp.DEFAULT_POLICY  # not yet emitted
    assert rp.DEFAULT_POLICY.report_type == "general_project_status"


def test_management_profile_runs_mqa_check_others_do_not():
    assert rp.policy_for("management_question").runs_check(rp.CHK_MANAGEMENT_QUESTION_ANSWER)
    assert not rp.policy_for("general_project_status").runs_check(rp.CHK_MANAGEMENT_QUESTION_ANSWER)
    assert not rp.policy_for("salary_payroll").runs_check(rp.CHK_MANAGEMENT_QUESTION_ANSWER)


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
