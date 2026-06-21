"""Block A tests — expanded report-type resolver.

classify_report_type now emits financial / risk / delay / document_search in
addition to the original four. One resolver, documented precedence:
salary -> management(decision framing) -> financial -> risk -> delay ->
document_search -> data_report -> general.
"""

from __future__ import annotations

import pytest

from apps.edr.graph.intent import classify_report_type as c


@pytest.mark.parametrize(
    "q",
    [
        "what is the actual cost?",
        "show budget vs actual",
        "purchase order status",
        "invoice vs odoo",
        "committed cost to date",
        "supplier cost breakdown",
        "procurement status",
    ],
)
def test_financial_queries(q):
    assert c(q) == "financial", q


@pytest.mark.parametrize(
    "q",
    [
        "show me the risk register",
        "is there a claim against us?",
        "contract risk exposure",
        "liquidated damages risk",
    ],
)
def test_risk_queries(q):
    assert c(q) == "risk", q


@pytest.mark.parametrize(
    "q",
    [
        "what is the delay status?",
        "eot entitlement",
        "is the project behind schedule?",
        "critical path slippage",
    ],
)
def test_delay_queries(q):
    assert c(q) == "delay", q


@pytest.mark.parametrize(
    "q",
    [
        "find the latest drawing",
        "locate the submittal document",
        "where is the transmittal letter",
        "show me the RFI document",
    ],
)
def test_document_search_queries(q):
    assert c(q) == "document_search", q


def test_decision_framing_beats_domain():
    # "biggest risk" is a decision question -> management, not risk.
    assert c("what is the biggest risk for this project") == "management_question"
    assert c("what is the biggest problem for this project") == "management_question"


def test_salary_beats_financial():
    # Payroll/HR sensitivity has top precedence even though it is also cost data.
    assert c("give me the payroll register by staff name") == "salary_payroll"


def test_existing_types_unchanged():
    assert c("give me salary report by staff name and file id") == "salary_payroll"
    assert c("give me a table of all log entries by id") == "data_report"
    assert c("what is the current status of the project") == "general_project_status"
