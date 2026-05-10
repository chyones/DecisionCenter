"""Arabic PDF hardening tests.

Limitation (Phase 1H):
- Amiri font is registered and used for Arabic glyph rendering.
- ReportLab does NOT perform bidi shaping or Arabic reshaping.
- Arabic text is rendered left-to-right with isolated glyphs.
- Full RTL support requires python-bidi + arabic-reshaper (future phase).
"""

from __future__ import annotations

from apps.edr.exporters.pdf import (
    _build_story,
    _contains_arabic,
    _make_doc,
    _register_arabic_font,
    to_pdf,
)


def test_contains_arabic_detects_arabic_text() -> None:
    assert _contains_arabic("مشروع") is True
    assert _contains_arabic("Hello world") is False
    assert _contains_arabic("Mixed مشروع English") is True


def test_contains_arabic_empty_string() -> None:
    assert _contains_arabic("") is False


def test_register_arabic_font_returns_name_when_present() -> None:
    font_name = _register_arabic_font()
    assert font_name == "Amiri"


def test_build_story_english_no_rtl_disclaimer() -> None:
    report = {
        "request_id": "r1",
        "project_code": "PRJ-001",
        "query": "What is the budget?",
        "language": "en",
        "quality_gate_status": "passed",
        "executive_summary": [],
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": [],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "missing_data": [],
        "conflicts": [],
        "sources": [],
    }
    buf = _make_doc(__import__("io").BytesIO())
    story, has_arabic = _build_story(report, buf)
    assert has_arabic is False
    texts = [str(item.text) for item in story if hasattr(item, "text")]
    assert not any("RTL limitation" in t for t in texts)


def test_build_story_arabic_has_rtl_disclaimer() -> None:
    report = {
        "request_id": "r2",
        "project_code": "PRJ-001",
        "query": "ما هو حالة المشروع؟",
        "language": "ar",
        "quality_gate_status": "passed",
        "executive_summary": [],
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": [],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "missing_data": [],
        "conflicts": [],
        "sources": [],
    }
    buf = _make_doc(__import__("io").BytesIO())
    story, has_arabic = _build_story(report, buf)
    assert has_arabic is True
    texts = [str(item.text) for item in story if hasattr(item, "text")]
    assert any("RTL limitation" in t for t in texts)


def test_build_story_mixed_arabic_english_has_rtl_disclaimer() -> None:
    report = {
        "request_id": "r3",
        "project_code": "PRJ-001",
        "query": "What is the budget for مشروع؟",
        "language": "en",
        "quality_gate_status": "passed",
        "executive_summary": [{"claim": "Budget is available.", "evidence_ids": [], "confidence": "medium"}],
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": [],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "missing_data": [],
        "conflicts": [],
        "sources": [],
    }
    buf = _make_doc(__import__("io").BytesIO())
    story, has_arabic = _build_story(report, buf)
    assert has_arabic is True
    texts = [str(item.text) for item in story if hasattr(item, "text")]
    assert any("RTL limitation" in t for t in texts)


def test_pdf_arabic_produces_valid_pdf_structure() -> None:
    report = {
        "request_id": "r4",
        "project_code": "PRJ-001",
        "query": "تقرير المشروع",
        "language": "ar",
        "quality_gate_status": "passed",
        "executive_summary": [{"claim": "الميزانية متاحة", "evidence_ids": [], "confidence": "medium"}],
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": [],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "missing_data": [],
        "conflicts": [],
        "sources": [],
    }
    pdf_bytes = to_pdf(report)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
