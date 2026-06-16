"""Tests for the Odoo Source Map visibility API.

Covers the generic builder and the two admin endpoints:
- GET  /admin/source-mappings/{code}/odoo-source-map
- POST /admin/source-mappings/{code}/odoo-source-map/scan

The map MUST be built from the registry (22 sources, 13 groups, 9 denylisted
paths) and carry the project's RUNTIME ids — never hardcoded PRJ-001/PRJ-002.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.admin.odoo_source_map import build_source_map, scan_source_counts
from apps.edr.auth.validator import JWTClaims
from apps.edr.connectors import odoo_sources as src
from apps.edr.rbac.roles import Role


# Arbitrary, non-validation project + ids — proves there is no PRJ-001/002 logic.
ARB_CODE = "ZED-777"
ARB_PROJECT_ID = "99001"
ARB_ANALYTIC_ID = "88002"


def _fake_row(
    *,
    code: str = ARB_CODE,
    project_id: str = ARB_PROJECT_ID,
    analytic_id: str = ARB_ANALYTIC_ID,
    enabled: list[str] | None = None,
) -> dict:
    odoo = {
        "project_model": "project.project",
        "cost_model": "account.analytic.line",
        "project_external_id": project_id,
        "project_name": "Some Project",
        "analytic_account_id": analytic_id,
    }
    return {
        "project_code": code,
        "project_name": "Some Project",
        "contract_numbers": "[]",
        "sharepoint": '{"site_id": "s", "drive_id": "d", "root_path": "/"}',
        "owncloud": '{"base_path": ""}',
        "email": "{}",
        "microsoft": "{}",
        "odoo": json.dumps(odoo),
        "related_people": "{}",
        "enabled_sources": json.dumps(enabled if enabled is not None else ["odoo", "sharepoint"]),
        "allowed_roles": "[]",
        "mapping_status": "complete",
        "last_validation_result": None,
        "last_validated_at": None,
        "created_at": None,
        "updated_at": None,
        "created_by_hash": None,
        "updated_by_hash": None,
    }


def _mock_pg(row: dict | None) -> MagicMock:
    pg = MagicMock()
    pg.init_schema = AsyncMock(return_value=None)
    pg.get_source_mapping = AsyncMock(return_value=row)
    pg.insert_admin_event = AsyncMock(return_value=None)
    return pg


# ---------------------------------------------------------------------------
# Pure builder
# ---------------------------------------------------------------------------


def _cfg(project_id: str | None = ARB_PROJECT_ID, analytic_id: str | None = ARB_ANALYTIC_ID) -> dict:
    return {
        "project_external_id": project_id or "",
        "analytic_account_id": analytic_id or "",
    }


def test_build_lists_all_22_sources_and_13_groups() -> None:
    resp = build_source_map(
        project_code=ARB_CODE, odoo_config=_cfg(), mapping_status="complete",
        odoo_enabled=True, extended_enabled=False,
    )
    assert resp.generic is True
    assert len(resp.sources) == 22
    assert len(resp.groups) == 13
    assert resp.groups == list(src.DISPLAY_GROUPS)
    assert len(resp.denylisted_paths) == 9


def test_build_uses_runtime_ids_not_hardcoded_samples() -> None:
    resp = build_source_map(
        project_code=ARB_CODE, odoo_config=_cfg(), mapping_status="complete",
        odoo_enabled=True, extended_enabled=True,
    )
    assert resp.odoo_project_id == ARB_PROJECT_ID
    assert resp.analytic_account_id == ARB_ANALYTIC_ID
    # No validation-sample id leaks into any link value.
    serialized = resp.model_dump_json()
    for sample in ("14602", "14601", "21963", "21960"):
        assert sample not in serialized
    # Project-scoped sources resolve to the project id; analytic-scoped to analytic id.
    by_key = {s.key: s for s in resp.sources}
    assert by_key["material_requests"].link_value == ARB_PROJECT_ID  # project scope
    assert by_key["purchase_orders"].link_value == ARB_ANALYTIC_ID   # analytic scope
    assert by_key["material_requests"].mappable is True
    assert by_key["purchase_orders"].mappable is True


def test_build_marks_analytic_sources_unmappable_when_analytic_id_missing() -> None:
    resp = build_source_map(
        project_code=ARB_CODE, odoo_config=_cfg(analytic_id=None),
        mapping_status="incomplete", odoo_enabled=True, extended_enabled=False,
    )
    by_key = {s.key: s for s in resp.sources}
    assert by_key["purchase_orders"].mappable is False  # analytic scope, no id
    assert by_key["material_requests"].mappable is True  # project scope, has id
    assert "purchase_orders" in resp.missing_sources
    assert any("Analytic account id is not set" in n for n in resp.notes)


def test_build_all_unmappable_when_odoo_disabled() -> None:
    resp = build_source_map(
        project_code=ARB_CODE, odoo_config=_cfg(), mapping_status="complete",
        odoo_enabled=False, extended_enabled=False,
    )
    assert all(s.mappable is False for s in resp.sources)
    assert resp.enabled_categories == []
    assert any("not in this project's enabled sources" in n for n in resp.notes)


def test_build_surfaces_known_warnings_generically() -> None:
    resp = build_source_map(
        project_code=ARB_CODE, odoo_config=_cfg(), mapping_status="complete",
        odoo_enabled=True, extended_enabled=True,
    )
    by_key = {s.key: s for s in resp.sources}
    assert by_key["po_rfq_attachments"].warning  # has a discrepancy caveat
    assert by_key["staff_employees"].warning
    # gap_type + confidence are surfaced per source
    assert by_key["project_identity"].gap_type == "CONNECTOR FIELD GAP"
    assert by_key["staff_list"].confidence == "medium"


def test_build_enabled_categories_cover_required_groups() -> None:
    resp = build_source_map(
        project_code=ARB_CODE, odoo_config=_cfg(), mapping_status="complete",
        odoo_enabled=True, extended_enabled=True,
    )
    # With both ids present and odoo enabled, every display group is active.
    assert set(resp.enabled_categories) == set(src.DISPLAY_GROUPS)


# ---------------------------------------------------------------------------
# Scan (read-only) — mocked n8n
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_scan_counts_merge_and_cap() -> None:
    async def fake_read(payload: dict) -> list:
        if payload["model"] == "purchase.order":
            return list(range(100))  # capped
        if payload["model"] == "account.move":
            raise RuntimeError("n8n 500")
        if payload["model"] == "staff.list":
            return []  # empty
        return list(range(3))

    with patch("apps.edr.admin.odoo_source_map.read_odoo", fake_read):
        scan = await scan_source_counts(
            project_code=ARB_CODE, odoo_config=_cfg(), allowed_odoo_ids=[ARB_PROJECT_ID],
        )

    assert scan.reachable is True
    assert scan.capped_at == 100
    assert scan.statuses["purchase_orders"] == "capped"
    assert scan.statuses["vendor_bills"].startswith("error:")
    assert scan.statuses["staff_list"] == "empty"
    assert scan.counts["material_requests"] == 3

    # Merged into the map: capped flag + record_count surfaced per source.
    resp = build_source_map(
        project_code=ARB_CODE, odoo_config=_cfg(), mapping_status="complete",
        odoo_enabled=True, extended_enabled=True, scan=scan,
    )
    by_key = {s.key: s for s in resp.sources}
    assert by_key["purchase_orders"].capped is True
    assert by_key["purchase_orders"].record_count == 100
    assert by_key["material_requests"].record_count == 3
    assert resp.last_scanned_at == scan.scanned_at


@pytest.mark.anyio
async def test_scan_unmapped_sources_not_queried() -> None:
    calls: list[str] = []

    async def fake_read(payload: dict) -> list:
        calls.append(payload["model"])
        return list(range(2))

    with patch("apps.edr.admin.odoo_source_map.read_odoo", fake_read):
        scan = await scan_source_counts(
            project_code=ARB_CODE, odoo_config=_cfg(analytic_id=None),
            allowed_odoo_ids=[ARB_PROJECT_ID],
        )
    # Analytic-scoped sources are unmapped and never hit the network.
    assert "purchase.order" not in calls
    assert scan.statuses["purchase_orders"] == "unmapped"
    assert "material.purchase.requisition" in calls


# ---------------------------------------------------------------------------
# Endpoints (admin gate + wiring)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_endpoint_happy_path() -> None:
    from apps.edr.app import get_odoo_source_map

    claims = JWTClaims(user_id="admin", role="admin")
    pg = _mock_pg(_fake_row())
    with patch("apps.edr.app.get_postgres_store", return_value=pg):
        resp = await get_odoo_source_map(ARB_CODE, claims)

    assert resp.project_code == ARB_CODE
    assert resp.odoo_project_id == ARB_PROJECT_ID
    assert len(resp.sources) == 22


@pytest.mark.anyio
async def test_get_endpoint_404_when_missing() -> None:
    from apps.edr.app import get_odoo_source_map

    claims = JWTClaims(user_id="admin", role="admin")
    pg = _mock_pg(None)
    with patch("apps.edr.app.get_postgres_store", return_value=pg):
        with pytest.raises(HTTPException) as exc:
            await get_odoo_source_map("MISSING", claims)
    assert exc.value.status_code == 404


@pytest.mark.parametrize("role", [r for r in Role if r != Role.ADMIN])
def test_endpoints_require_admin(role: Role) -> None:
    from apps.edr.app import _require_admin

    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_scan_endpoint_runs_scan_and_audits() -> None:
    from apps.edr.app import scan_odoo_source_map

    claims = JWTClaims(user_id="admin", role="admin")
    pg = _mock_pg(_fake_row())

    async def fake_read(payload: dict) -> list:
        return list(range(7))

    with (
        patch("apps.edr.app.get_postgres_store", return_value=pg),
        patch("apps.edr.admin.odoo_source_map.read_odoo", fake_read),
    ):
        resp = await scan_odoo_source_map(ARB_CODE, claims)

    # Audit event emitted before the read-only scan.
    pg.insert_admin_event.assert_awaited()
    assert resp.last_scanned_at is not None
    by_key = {s.key: s for s in resp.sources}
    assert by_key["material_requests"].record_count == 7


@pytest.mark.anyio
async def test_scan_endpoint_skips_scan_when_odoo_disabled() -> None:
    from apps.edr.app import scan_odoo_source_map

    claims = JWTClaims(user_id="admin", role="admin")
    pg = _mock_pg(_fake_row(enabled=["sharepoint"]))  # odoo not enabled

    called = {"read": False}

    async def fake_read(payload: dict) -> list:
        called["read"] = True
        return []

    with (
        patch("apps.edr.app.get_postgres_store", return_value=pg),
        patch("apps.edr.admin.odoo_source_map.read_odoo", fake_read),
    ):
        resp = await scan_odoo_source_map(ARB_CODE, claims)

    assert called["read"] is False  # no live calls when odoo disabled
    assert resp.last_scanned_at is None
    assert all(s.mappable is False for s in resp.sources)
