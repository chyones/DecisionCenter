"""Phase 1D-fixup regression tests.

Cover the four critical correctness fixes (Session 1):
- C-1 Qdrant collection naming agrees between init script and runtime.
- C-2 Odoo domain JSON is built via json.dumps (no f-string interpolation) and
      queries real project.project columns.
- C-8 Node 14 only exports when quality_gate == "passed".
- L-5 EvidenceObject.metadata accepts list values (e.g. email recipients).
"""

from __future__ import annotations

import asyncio
import json
import re

import pytest

from apps.edr.connectors.odoo import build_project_query
from apps.edr.graph import node_08_odoo, node_14_compose_md
from apps.edr.graph.state import DecisionState
from apps.edr.retrieval.qdrant_store import EvidenceStore
from apps.edr.schemas.evidence import EvidenceObject
from scripts import init_qdrant


# ---------------------------------------------------------------------------
# C-1 — Qdrant collection naming alignment
# ---------------------------------------------------------------------------


def test_init_script_and_runtime_agree_on_collection_name() -> None:
    project_code = "PRJ-001"
    runtime_name = EvidenceStore._collection_name(project_code)
    init_name = init_qdrant.collection_name(project_code)
    assert runtime_name == init_name
    assert runtime_name.startswith("edr_")


def test_init_script_rejects_non_alphanumeric_project_code() -> None:
    with pytest.raises(ValueError):
        init_qdrant.collection_name("---")


# ---------------------------------------------------------------------------
# C-2 — Odoo domain JSON construction (injection-safe + real columns)
# ---------------------------------------------------------------------------


def test_odoo_node_builds_domain_via_json_dumps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hostile project_code values must not break out of the JSON literal."""
    captured: dict = {}

    async def fake_read_odoo(payload: dict) -> list:
        captured.update(payload)
        return []

    class _FakeMapping:
        @staticmethod
        def load() -> "_FakeMapping":
            return _FakeMapping()

        def get(self, project_code: str) -> dict:
            return {"odoo": {"project_model": "project.project"}}

    monkeypatch.setattr(node_08_odoo, "read_odoo", fake_read_odoo)
    monkeypatch.setattr(node_08_odoo, "ProjectMapping", _FakeMapping)

    hostile = 'PRJ"], ["1", "=", "1"]]; --'
    state = DecisionState(
        request_id="r-1",
        user_id="u-1",
        role=None,
        project_code=hostile,
        query="status",
    )

    asyncio.run(node_08_odoo.run(state))

    # With no mapped numeric external id, the node falls back to an exact name
    # match — json.dumps keeps the hostile value safely contained as a single
    # leaf (no breakout into extra clauses).
    parsed = json.loads(captured["domain"])
    assert parsed == [["name", "=", hostile]]
    fields = json.loads(captured["fields"])
    assert "name" in fields
    assert "budget" not in fields and "actual_cost" not in fields


def test_odoo_node_uses_verified_mapped_odoo_project_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified numeric Odoo id must be queried via the real ``id`` column."""
    captured: dict = {}

    async def fake_read_odoo(payload: dict) -> list:
        captured.update(payload)
        return []

    class _FakeMapping:
        @staticmethod
        def load() -> "_FakeMapping":
            return _FakeMapping()

        def get(self, project_code: str) -> dict:
            assert project_code == "PRJ-001"
            return {
                "odoo": {
                    "project_model": "project.project",
                    "project_external_id": "14602",
                    "project_name": "Construction of Civil Defense building in Al Marfa",
                }
            }

    monkeypatch.setattr(node_08_odoo, "read_odoo", fake_read_odoo)
    monkeypatch.setattr(node_08_odoo, "ProjectMapping", _FakeMapping)

    state = DecisionState(
        request_id="r-1",
        user_id="u-1",
        role=None,
        project_code="PRJ-001",
        query="status",
    )

    asyncio.run(node_08_odoo.run(state))

    # 14602 is the project.project record id, queried via the real ``id`` column
    # (not the nonexistent ``project_external_id`` field).
    parsed = json.loads(captured["domain"])
    assert parsed == [["id", "=", 14602]]
    fields = json.loads(captured["fields"])
    assert "budget" not in fields and "actual_cost" not in fields


def test_build_project_query_falls_back_to_name_when_no_numeric_id() -> None:
    """Non-numeric external id falls back to an exact project-name match."""
    domain, fields = build_project_query(
        {"project_external_id": "not-a-number", "project_name": "Al Marfa CD"},
        "PRJ-001",
    )
    assert json.loads(domain) == [["name", "=", "Al Marfa CD"]]
    assert json.loads(fields) == [
        "name", "date_start", "date", "user_id", "partner_id", "wo_amount", "estimation_amount",
    ]


# ---------------------------------------------------------------------------
# C-8 — Quality gate semantics in Node 14
# ---------------------------------------------------------------------------


def _state_with_gate(gate_value: str) -> DecisionState:
    state = DecisionState(
        request_id="r-1",
        user_id="u-1",
        role=None,
        project_code="PRJ-001",
        query="status",
    )
    state.outputs["quality_gate"] = gate_value
    state.report_json = {
        "request_id": "r-1",
        "project_code": "PRJ-001",
        "query": "status",
        "language": "en",
        "executive_summary": [],
        "financial_snapshot": {},
        "key_findings": [],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "missing_data": [],
        "conflicts": [],
        "sources": [],
        "quality_gate_status": gate_value,
    }
    return state


def test_node_14_skips_export_when_quality_gate_is_needs_review() -> None:
    state = _state_with_gate("needs_review")
    result = asyncio.run(node_14_compose_md.run(state))
    assert result.outputs["markdown_report_status"] == "skipped_quality_gate_needs_review"
    assert "exported_reports" not in result.outputs


def test_node_14_skips_export_when_quality_gate_is_failed() -> None:
    state = _state_with_gate("failed")
    result = asyncio.run(node_14_compose_md.run(state))
    assert result.outputs["markdown_report_status"] == "skipped_quality_gate_failed"
    assert "exported_reports" not in result.outputs


def test_node_14_exports_when_quality_gate_is_passed() -> None:
    state = _state_with_gate("passed")
    result = asyncio.run(node_14_compose_md.run(state))
    assert result.outputs["markdown_report_status"] == "generated"
    assert "md" in result.outputs["exported_reports"]


def test_node_14_skips_export_when_no_validated_report() -> None:
    state = DecisionState(
        request_id="r-1",
        user_id="u-1",
        role=None,
        project_code="PRJ-001",
        query="status",
    )
    state.outputs["quality_gate"] = "passed"
    result = asyncio.run(node_14_compose_md.run(state))
    assert result.outputs["markdown_report_status"] == "skipped_no_validated_report"


# ---------------------------------------------------------------------------
# L-5 — EvidenceObject.metadata accepts list values
# ---------------------------------------------------------------------------


def test_evidence_object_accepts_list_metadata() -> None:
    evidence = EvidenceObject(
        evidence_id="eml-1",
        source_type="email",
        source_uri="https://graph.microsoft.com/v1.0/users/x/messages/1",
        title="Re: contract",
        excerpt="hello",
        hash_sha256="a" * 64,
        confidence="medium",
        metadata={
            "sender": "alice@example.com",
            "recipients": ["bob@example.com", "carol@example.com"],
            "has_attachments": False,
        },
    )
    assert evidence.metadata["recipients"] == ["bob@example.com", "carol@example.com"]


def test_evidence_object_rejects_nested_dict_metadata() -> None:
    """Metadata must remain flat scalars/lists; nested dicts are still rejected."""
    with pytest.raises(Exception):
        EvidenceObject(
            evidence_id="eml-1",
            source_type="email",
            source_uri="https://example.com",
            title="t",
            excerpt="x",
            hash_sha256="a" * 64,
            confidence="medium",
            metadata={"nested": {"forbidden": True}},
        )


# ---------------------------------------------------------------------------
# Sanity: collection name shape
# ---------------------------------------------------------------------------


def test_collection_name_only_lowercase_alnum_and_underscore() -> None:
    name = EvidenceStore._collection_name("PRJ-001")
    assert re.fullmatch(r"[a-z0-9_]+", name)
