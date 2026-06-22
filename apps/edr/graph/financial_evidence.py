"""Financial query expansion and evidence screening.

Financial reports should only use financial project evidence from documents and
email. Odoo remains the financial source of truth for numbers, but BOQs,
payment certificates, invoices, purchase orders, cost reports, variations, and
procurement/payment correspondence are useful context.
"""

from __future__ import annotations

import re

FINANCIAL_SEARCH_TERMS: tuple[str, ...] = (
    "BOQ",
    "bill of quantities",
    "payment certificate",
    "invoice",
    "purchase order",
    "LPO",
    "cost report",
    "variation",
    "budget",
    "procurement",
    "payment",
    "مصاريف",
    "تكاليف",
    "ميزانية",
    "فاتورة",
    "فواتير",
    "مستخلص",
    "دفعة",
    "مدفوعات",
    "مشتريات",
)

_FINANCIAL_RE = re.compile(
    r"\b(boq|bill\s+of\s+quantities|payment\s+certificate|invoice|invoices|"
    r"purchase\s+order|purchase\s+orders|\bpo\b|\blpo\b|cost\s+report|"
    r"cost\s+breakdown|variation|budget|procurement|payment|payments|"
    r"expense|expenses|expenditure|spend|spending|commercial|valuation|"
    r"supplier|subcontractor|account|ledger|interim\s+payment|ipc)\b|"
    r"(مصاريف|مصروف|مصروفات|نفقات|تكلفة|تكاليف|الميزانية|ميزانية|"
    r"فاتورة|فواتير|مستخلص|دفعة|دفعات|مدفوعات|مشتريات|امر\s+شراء|أمر\s+شراء)",
    re.IGNORECASE,
)

_EXCLUDED_NON_FINANCIAL_RE = re.compile(
    r"\b(schedule|programme|program|baseline|lookahead|drawing|drawings|"
    r"shop\s+drawing|qaqc|qa/qc|quality|mir|material\s+inspection\s+request|"
    r"method\s+statement|technical\s+submittal|submittal|submittals|"
    r"test\s+report|inspection\s+request|\bitp\b|\brfi\b)\b|"
    r"(جدول\s+زمني|برنامج\s+زمني|رسومات|مخططات|الجودة|فحص|اختبار|"
    r"اعتماد\s+فني|طريقة\s+تنفيذ)",
    re.IGNORECASE,
)


def financial_search_terms(query: str) -> list[str]:
    """Return ordered financial terms for connector searches."""
    terms: list[str] = []

    def add(term: str) -> None:
        if term and term not in terms:
            terms.append(term)

    if query and _FINANCIAL_RE.search(query):
        add(query.strip())
    for term in FINANCIAL_SEARCH_TERMS:
        add(term)
    return terms


def financial_search_query(query: str) -> str:
    """Compact expansion for connectors that accept only one query string."""
    terms = financial_search_terms(query)
    return " ".join(terms[:10])


def is_financial_evidence(evidence: dict, *, query: str = "") -> bool:
    """Return True when a retrieved document/email item is financial context.

    Odoo evidence is always retained because financial figures are verified
    downstream by deterministic Odoo extraction.
    """
    if evidence.get("source_type") == "odoo":
        return True

    tags = " ".join(str(t) for t in evidence.get("tags", []) or [])
    meta = evidence.get("metadata") or {}
    metadata_text = " ".join(str(v) for v in meta.values())
    text = " ".join(
        str(part)
        for part in (
            evidence.get("title", ""),
            evidence.get("excerpt", ""),
            evidence.get("source_uri", ""),
            tags,
            metadata_text,
        )
    )
    if not _FINANCIAL_RE.search(text):
        return False

    # Keep explicitly requested excluded categories, but suppress them for
    # ordinary financial queries like "project expenses report".
    if _EXCLUDED_NON_FINANCIAL_RE.search(text) and not _EXCLUDED_NON_FINANCIAL_RE.search(query):
        return False
    return True


def filter_financial_evidence(evidence: list[dict], *, query: str = "") -> list[dict]:
    """Filter a mixed evidence pack down to financial evidence only."""
    return [ev for ev in evidence if isinstance(ev, dict) and is_financial_evidence(ev, query=query)]

