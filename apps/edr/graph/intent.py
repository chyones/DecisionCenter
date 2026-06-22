"""Intent / report-type classification helpers.

Single deterministic resolver (``classify_report_type``) used by node_02, node_12
(prompt mode), node_13 (quality-gate profile) and the renderer (sections). The
Quality Gate must NOT re-detect intent separately — it reads ``report_type``.

Precedence (most specific / most sensitive first):
    1. salary_payroll      — HR/payroll data (most sensitive)
    2. management_question — decision framing ("biggest problem", "should we decide")
    3. financial           — budget/cost/PO/invoice/payment/procurement
    4. risk                — risk register / claims / exposure / LD
    5. delay               — delay / EOT / slippage / behind schedule
    6. document_search     — retrieve a document/drawing/submittal/letter/RFI
    7. data_report         — generic list/table/export extraction
    8. general_project_status (fallback)

A decision question wins over its domain (e.g. "what is the biggest financial
problem" -> management_question, not financial), because it must read as a
decision memo regardless of subject.
"""

from __future__ import annotations

import re

# Management-decision question patterns.
_MANAGEMENT_QUESTION_RE = re.compile(
    r"\b(big|biggest|main|major|top|one|single)\s+(problem|issue|concern|risk)|"
    r"\b(problem|issue|concern|risk)\s+(for|with|on|in)\s+(this\s+)?project|"
    r"\bwhat\s+should\s+(management|we)\s+(decide|do)\b|"
    r"\bwhat\s+decision\s+should\s+(management|we)\s+make\b|"
    r"\bdecide\s+this\s+(week|month)|\bmanagement\s+decide\b|"
    r"\brecommend\w*\s+(action|intervention)|"
    r"\bwhat\s+is\s+the\s+(biggest|single\s+biggest)\s+(problem|risk|issue)",
    re.IGNORECASE,
)

# Salary / payroll / HR-sensitive data patterns.
_SALARY_PAYROLL_RE = re.compile(
    r"\b(salary|salaries|payroll|wage|wages|remuneration|compensation|employee\s+cost|"
    r"labor\s+cost|labour\s+cost|manpower\s+cost|staff\s+cost|hr\s+report|human\s+resources|"
    r"pay\s+slip|payslip|payroll\s+register|staff\s+name|employee\s+name|file\s+id|"
    r"staff\s+file|employee\s+file|personnel\s+file|finance\s+payroll)\b",
    re.IGNORECASE,
)

# Stricter evidence-level match: avoids flagging a document that merely mentions
# the word "salary" in passing. Requires payroll/HR context or concrete data clues.
_SALARY_PAYROLL_DATA_RE = re.compile(
    r"\b(payroll\s+register|payroll\s+report|pay\s+slip|payslip|salary\s+sheet|"
    r"salary\s+register|salary\s+certificate|employee\s+salary|staff\s+salary|"
    r"salary\s+by\s+staff|hr\s+report|human\s+resources\s+report|manpower\s+report|"
    r"labor\s+cost\s+by\s+person|personnel\s+file|staff\s+file|employee\s+file|"
    r"file\s+id|wage\s+register|payroll\s+summary)\b",
    re.IGNORECASE,
)

# Financial reporting patterns (budget/actual/committed/PO/invoice/payment/...).
_FINANCIAL_RE = re.compile(
    r"\b(budget|estimate|estimation|contract\s+value|wo\s+amount|work\s+order\s+value|"
    r"cost|costs|actual\s+cost|committed\s+cost|cost\s+report|cost\s+breakdown|"
    r"cost\s+overrun|financial|finance|invoice|invoices|vendor\s+bill|"
    r"purchase\s+order|purchase\s+orders|\blpo\b|\brfq\b|procurement|"
    r"payment|payments|variance|expenditure|spend|spending|"
    r"supplier\s+cost|subcontractor|account\s+move)\b",
    re.IGNORECASE,
)

# Risk register / claims / exposure patterns.
_RISK_RE = re.compile(
    r"\b(risk|risks|risk\s+register|exposure|liability|liabilities|"
    r"claim|claims|dispute|disputes|contractual\s+risk|contract\s+risk|"
    r"penalty|penalties|liquidated\s+damages|\blds?\b|mitigation)\b",
    re.IGNORECASE,
)

# Delay / time-impact patterns.
_DELAY_RE = re.compile(
    r"\b(delay|delays|delayed|eot|extension\s+of\s+time|"
    r"behind\s+schedule|slippage|overdue|programme\s+slippage|"
    r"schedule\s+delay|time\s+impact|late\s+completion|critical\s+path)\b",
    re.IGNORECASE,
)

# Document-retrieval patterns: a retrieval verb adjacent to a document noun.
_DOCUMENT_SEARCH_RE = re.compile(
    r"\b(find|locate|search|where\s+is|show\s+me|retrieve|latest|copy\s+of|attach)\b"
    r"[^.?!]*\b(document|documents|drawing|drawings|submittal|submittals|"
    r"letter|letters|transmittal|transmittals|\brfi\b|minutes|specification|"
    r"datasheet|certificate)\b|"
    r"\b(document\s+search|drawing\s+register|submittal\s+log|transmittal\s+log)\b",
    re.IGNORECASE,
)

# Generic data extraction / tabular report patterns.
_DATA_REPORT_RE = re.compile(
    r"\b(give\s+me|list|table|export|generate|produce|download|create)\s+.*\b(report|"
    r"table|list|export|summary|breakdown|register|log|ledger)\b|"
    r"\bby\s+(staff|employee|person|name|file|id|date|month|trade|role|department)\b",
    re.IGNORECASE,
)


def classify_report_type(query: str) -> str:
    """Return the authoritative report type for a user query.

    Values: salary_payroll, management_question, financial, risk, delay,
    document_search, data_report, general_project_status.
    """
    q = (query or "").lower()
    if _SALARY_PAYROLL_RE.search(q):
        return "salary_payroll"
    if _MANAGEMENT_QUESTION_RE.search(q):
        return "management_question"
    if _FINANCIAL_RE.search(q):
        return "financial"
    if _RISK_RE.search(q):
        return "risk"
    if _DELAY_RE.search(q):
        return "delay"
    if _DOCUMENT_SEARCH_RE.search(q):
        return "document_search"
    if _DATA_REPORT_RE.search(q):
        return "data_report"
    return "general_project_status"


def is_salary_payroll_query(query: str) -> bool:
    return classify_report_type(query) == "salary_payroll"


def is_salary_payroll_evidence(evidence: list[dict]) -> bool:
    """Return True if the evidence pack actually contains salary/payroll data.

    A generic mention of the word "salary" is not enough; we look for payroll/HR
    source tags or explicit salary/payroll data patterns (register, slips, etc.).
    """
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        tags = [t.lower() for t in ev.get("tags", [])]
        if any(t in tags for t in ("payroll", "hr", "manpower", "salary", "wage", "compensation")):
            return True
        text = " ".join(
            [
                str(ev.get("title", "")),
                str(ev.get("excerpt", "")),
                str(ev.get("source_type", "")),
                str(ev.get("source_uri", "")),
            ]
        ).lower()
        if _SALARY_PAYROLL_DATA_RE.search(text):
            return True
    return False


def is_management_question(query: str) -> bool:
    return classify_report_type(query) == "management_question"
