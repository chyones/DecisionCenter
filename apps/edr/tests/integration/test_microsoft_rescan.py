"""
Tests for Microsoft Mapping Rescan endpoints and discovery engine.

POST /admin/microsoft-mapping/rescan  → rescan_microsoft_mapping
POST /admin/microsoft-mapping/{code}/confirm  → confirm_microsoft_mapping

Patterns follow test_phase2b_source_mapping.py:
  - RBAC denial via direct _require_admin calls (not TestClient)
  - Endpoint handlers imported and called directly with JWTClaims
  - Mock PostgresStore via patch("apps.edr.app.get_postgres_store")
  - Pure-function unit tests for discovery engine helpers
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.app import (
    MicrosoftMappingConfirmRequest,
    MicrosoftRescanRequest,
    _require_admin,
    confirm_microsoft_mapping,
    rescan_microsoft_mapping,
)
from apps.edr.admin.microsoft_rescan import (
    MicrosoftRescanResponse,
    ProjectRescanResult,
    _compute_match,
    _decode_token_roles,
    _derive_search_term,
    _is_placeholder_mailbox,
    _is_placeholder_site,
    run_microsoft_rescan,
)
from apps.edr.auth.validator import JWTClaims
from apps.edr.rbac.roles import Role

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]

_FAKE_SITE_ID = "elrace.sharepoint.com,a505675a-test,26e3f61b-test"
_FAKE_DRIVE_ID = "b!WmcFpV3RgUmm-test-drive-id"

_REAL_SITE_ROW = {
    "project_code": "PRJ-001",
    "project_name": "Civil Defense Al Mirfa",
    "contract_numbers": '["CON-001"]',
    "sharepoint": f'{{"site_id": "{_FAKE_SITE_ID}", "drive_id": "{_FAKE_DRIVE_ID}", "root_path": "/Projects/PRJ-001"}}',
    "owncloud": '{"base_path": "/Projects/PRJ-001"}',
    "email": (
        '{"shared_mailboxes": ["project-prj-001@example.com"],'
        ' "document_control_mailbox": "doc-control@example.com",'
        ' "client_domains": [], "consultant_domains": [], "contractor_domains": []}'
    ),
    "odoo": (
        '{"project_model": "project.project", "cost_model": "account.analytic.line",'
        ' "project_external_id": "PRJ-001", "project_name": ""}'
    ),
    "related_people": (
        '{"project_manager": "", "commercial_manager": "", "finance_owner": "",'
        ' "document_controller": "", "other": []}'
    ),
    "enabled_sources": '["sharepoint"]',
    "allowed_roles": '["executive"]',
    "mapping_status": "complete",
    "last_validation_result": None,
    "last_validated_at": None,
    "created_at": None,
    "updated_at": None,
    "created_by_hash": None,
    "updated_by_hash": None,
}

_PLACEHOLDER_ROW = {
    **_REAL_SITE_ROW,
    "project_code": "PRJ-003",
    "project_name": "New Project",
    "sharepoint": (
        '{"site_id": "example-site-id-003", "drive_id": "example-drive-id-003",'
        ' "root_path": "/Projects/PRJ-003"}'
    ),
    "mapping_status": "incomplete",
}


def _make_store(rows: list[dict]) -> MagicMock:
    store = MagicMock()
    store.init_schema = AsyncMock()
    store.list_source_mappings = AsyncMock(return_value=rows)
    store.get_source_mapping = AsyncMock(return_value=rows[0] if rows else None)
    store.insert_admin_event = AsyncMock()
    store.upsert_source_mapping = AsyncMock()
    return store


def _fake_token(roles: list[str]) -> str:
    payload = {"roles": roles}
    enc = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"h.{enc}.s"


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------


def test_is_placeholder_site_detects_examples():
    assert _is_placeholder_site("example-site-id-001")
    assert _is_placeholder_site("example-site-id")
    assert _is_placeholder_site("")
    assert not _is_placeholder_site(_FAKE_SITE_ID)


def test_is_placeholder_mailbox_detects_example_domain():
    assert _is_placeholder_mailbox("prj@example.com")
    assert _is_placeholder_mailbox("")
    assert not _is_placeholder_mailbox("prj@elrace.com")


def test_decode_token_roles_empty_when_no_token():
    assert _decode_token_roles("") == []
    assert _decode_token_roles("not.a.jwt") == []


def test_decode_token_roles_parses_valid_payload():
    roles = _decode_token_roles(_fake_token(["Sites.Read.All", "Files.Read.All"]))
    assert "Sites.Read.All" in roles
    assert "Files.Read.All" in roles


def test_compute_match_strong_on_project_code():
    site = {"displayName": "PRJ-001 Civil Defense Al Mirfa", "webUrl": "https://x"}
    strength, confidence = _compute_match("PRJ-001", "", site)
    assert strength == "strong"
    assert confidence == 1.0


def test_compute_match_strong_on_project_name_overlap():
    site = {"displayName": "Construction Civil Defense Center Al Mirfa Region", "webUrl": "https://x"}
    strength, confidence = _compute_match("PRJ-001", "Civil Defense Center Al Mirfa", site)
    assert strength in {"strong", "medium"}
    assert confidence > 0


def test_compute_match_none_when_no_overlap():
    site = {"displayName": "HR Team", "webUrl": "https://x"}
    strength, confidence = _compute_match("PRJ-001", "Civil Defense Center Al Mirfa", site)
    assert strength == "none"
    assert confidence == 0.0


def test_derive_search_term_from_hostname():
    with patch("apps.edr.admin.microsoft_rescan.settings") as mock_settings:
        mock_settings.public_hostname = "vantage.elrace.com"
        term = _derive_search_term()
    assert term == "elrace"


# ---------------------------------------------------------------------------
# run_microsoft_rescan unit tests (mock Graph calls)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rescan_no_token_returns_blocked():
    with patch("apps.edr.admin.microsoft_rescan.get_graph_token", return_value=""):
        result = await run_microsoft_rescan([{
            "project_code": "PRJ-001",
            "project_name": "",
            "sharepoint": {},
            "email": {},
            "mapping_status": "incomplete",
        }])
    assert isinstance(result, MicrosoftRescanResponse)
    assert result.has_sites_read_all is False
    assert "BLOCKED" in result.summary
    assert result.project_results == []


@pytest.mark.asyncio
async def test_rescan_existing_valid_site_is_auto_mapped():
    fake_token = _fake_token(["Sites.Read.All", "Files.Read.All", "Mail.Read"])
    site_data = {"id": _FAKE_SITE_ID, "displayName": "PRJ-001 Civil Defense", "webUrl": "https://x"}
    drive = {"id": _FAKE_DRIVE_ID, "name": "Documents", "driveType": "documentLibrary"}

    client_mock = MagicMock()
    client_mock.enumerate_sites = AsyncMock(return_value=[])
    client_mock.probe_site = AsyncMock(return_value=(200, site_data))
    client_mock.get_drives = AsyncMock(return_value=[drive])
    client_mock.get_root_children_count = AsyncMock(return_value=(200, 10))
    client_mock.probe_mailbox = AsyncMock(return_value=(False, 404))

    with (
        patch("apps.edr.admin.microsoft_rescan.get_graph_token", return_value=fake_token),
        patch("apps.edr.admin.microsoft_rescan.GraphDiscoveryClient", return_value=client_mock),
    ):
        result = await run_microsoft_rescan([{
            "project_code": "PRJ-001",
            "project_name": "Civil Defense Al Mirfa",
            "sharepoint": {"site_id": _FAKE_SITE_ID, "drive_id": _FAKE_DRIVE_ID},
            "email": {"shared_mailboxes": ["prj@example.com"]},
            "mapping_status": "complete",
        }])

    assert len(result.project_results) == 1
    prj = result.project_results[0]
    assert prj.sharepoint_status == "AUTO_MAPPED"
    assert prj.recommended_site_id == _FAKE_SITE_ID
    assert prj.recommended_drive_id == _FAKE_DRIVE_ID
    assert len(prj.site_candidates) == 1
    assert prj.site_candidates[0].match_strength == "existing"
    assert prj.site_candidates[0].root_item_count == 10


@pytest.mark.asyncio
async def test_rescan_placeholder_single_strong_match_is_auto_mapped():
    fake_token = _fake_token(["Sites.Read.All", "Files.Read.All", "Mail.Read"])
    matching_site = {
        "id": "site-prj-003",
        "displayName": "PRJ-003 Test Site",
        "webUrl": "https://x/sites/PRJ003",
    }
    drive = {"id": "drive-prj-003", "name": "Documents", "driveType": "documentLibrary"}

    client_mock = MagicMock()
    client_mock.enumerate_sites = AsyncMock(return_value=[matching_site])
    client_mock.get_drives = AsyncMock(return_value=[drive])
    client_mock.get_root_children_count = AsyncMock(return_value=(200, 5))
    client_mock.probe_mailbox = AsyncMock(return_value=(False, 404))

    with (
        patch("apps.edr.admin.microsoft_rescan.get_graph_token", return_value=fake_token),
        patch("apps.edr.admin.microsoft_rescan.GraphDiscoveryClient", return_value=client_mock),
    ):
        result = await run_microsoft_rescan([{
            "project_code": "PRJ-003",
            "project_name": "",
            "sharepoint": {"site_id": "example-site-id-003", "drive_id": "example-drive-id-003"},
            "email": {"shared_mailboxes": []},
            "mapping_status": "incomplete",
        }])

    prj = result.project_results[0]
    assert prj.sharepoint_status == "AUTO_MAPPED"
    assert prj.recommended_site_id == "site-prj-003"
    assert prj.recommended_drive_id == "drive-prj-003"


@pytest.mark.asyncio
async def test_rescan_placeholder_no_match_is_missing():
    fake_token = _fake_token(["Sites.Read.All"])

    client_mock = MagicMock()
    client_mock.enumerate_sites = AsyncMock(return_value=[
        {"id": "site-hr", "displayName": "HR Team", "webUrl": "https://x/sites/HRTeam"},
    ])
    client_mock.probe_mailbox = AsyncMock(return_value=(False, 404))

    with (
        patch("apps.edr.admin.microsoft_rescan.get_graph_token", return_value=fake_token),
        patch("apps.edr.admin.microsoft_rescan.GraphDiscoveryClient", return_value=client_mock),
    ):
        result = await run_microsoft_rescan([{
            "project_code": "PRJ-099",
            "project_name": "Unknown Project",
            "sharepoint": {"site_id": "example-site-id-099", "drive_id": ""},
            "email": {"shared_mailboxes": []},
            "mapping_status": "incomplete",
        }])

    prj = result.project_results[0]
    assert prj.sharepoint_status == "MISSING_SHAREPOINT"
    assert prj.recommended_site_id is None


@pytest.mark.asyncio
async def test_rescan_disabled_project():
    fake_token = _fake_token(["Sites.Read.All"])

    client_mock = MagicMock()
    client_mock.enumerate_sites = AsyncMock(return_value=[])

    with (
        patch("apps.edr.admin.microsoft_rescan.get_graph_token", return_value=fake_token),
        patch("apps.edr.admin.microsoft_rescan.GraphDiscoveryClient", return_value=client_mock),
    ):
        result = await run_microsoft_rescan([{
            "project_code": "PRJ-DIS",
            "project_name": "Disabled Project",
            "sharepoint": {"site_id": "", "drive_id": ""},
            "email": {"shared_mailboxes": []},
            "mapping_status": "disabled",
        }])

    prj = result.project_results[0]
    assert prj.sharepoint_status == "DISABLED"
    assert prj.mailbox_status == "DISABLED"


# ---------------------------------------------------------------------------
# RBAC — _require_admin denies every non-admin role (both endpoints)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_rescan_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_confirm_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


def test_rescan_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# rescan_microsoft_mapping — admin happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rescan_endpoint_admin_happy_path():
    store = _make_store([_REAL_SITE_ROW])
    claims = JWTClaims(user_id="admin@test", role="admin")

    mock_result = MicrosoftRescanResponse(
        scanned_at="2026-06-05T00:00:00Z",
        token_roles=["Sites.Read.All"],
        has_sites_read_all=True,
        has_mail_read=False,
        total_sites_discovered=1,
        project_results=[
            ProjectRescanResult(
                project_code="PRJ-001",
                project_name="Civil Defense Al Mirfa",
                existing_site_id=_FAKE_SITE_ID,
                existing_drive_id=_FAKE_DRIVE_ID,
                sharepoint_status="AUTO_MAPPED",
                mailbox_status="MISSING_MAILBOX",
                site_candidates=[],
                mailbox_candidates=[],
                reason="Existing mapping confirmed.",
            )
        ],
        summary="1 project(s) scanned.",
    )

    body = MicrosoftRescanRequest(project_codes=[])
    with (
        patch("apps.edr.app.get_postgres_store", return_value=store),
        patch("apps.edr.app.run_microsoft_rescan", new=AsyncMock(return_value=mock_result)),
    ):
        result = await rescan_microsoft_mapping(body, claims)

    assert isinstance(result, MicrosoftRescanResponse)
    assert result.has_sites_read_all is True
    assert len(result.project_results) == 1
    assert result.project_results[0].sharepoint_status == "AUTO_MAPPED"
    store.insert_admin_event.assert_called_once()


@pytest.mark.asyncio
async def test_rescan_endpoint_filters_by_project_codes():
    rows = [_REAL_SITE_ROW, {**_PLACEHOLDER_ROW}]
    store = _make_store(rows)
    claims = JWTClaims(user_id="admin@test", role="admin")

    captured: list = []

    async def capture_rescan(projects):
        captured.extend(projects)
        return MicrosoftRescanResponse(
            scanned_at="2026-06-05T00:00:00Z",
            token_roles=[],
            has_sites_read_all=False,
            has_mail_read=False,
            total_sites_discovered=0,
            project_results=[],
            summary="filtered",
        )

    body = MicrosoftRescanRequest(project_codes=["PRJ-001"])
    with (
        patch("apps.edr.app.get_postgres_store", return_value=store),
        patch("apps.edr.app.run_microsoft_rescan", new=capture_rescan),
    ):
        await rescan_microsoft_mapping(body, claims)

    assert len(captured) == 1
    assert captured[0]["project_code"] == "PRJ-001"


# ---------------------------------------------------------------------------
# confirm_microsoft_mapping — 404, 409, success cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_endpoint_404_when_project_missing():
    store = _make_store([])
    store.get_source_mapping = AsyncMock(return_value=None)
    claims = JWTClaims(user_id="admin@test", role="admin")

    body = MicrosoftMappingConfirmRequest(site_id="s", drive_id="d")
    with patch("apps.edr.app.get_postgres_store", return_value=store):
        with pytest.raises(HTTPException) as exc:
            await confirm_microsoft_mapping("PRJ-999", body, claims)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_confirm_endpoint_409_on_confirmed_mapping_overwrite():
    store = _make_store([_REAL_SITE_ROW])
    claims = JWTClaims(user_id="admin@test", role="admin")

    body = MicrosoftMappingConfirmRequest(site_id="completely-different-site", drive_id="d")
    with patch("apps.edr.app.get_postgres_store", return_value=store):
        with pytest.raises(HTTPException) as exc:
            await confirm_microsoft_mapping("PRJ-001", body, claims)
    assert exc.value.status_code == 409
    assert "confirmed site_id" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_confirm_endpoint_allows_same_site_id_reconfirm():
    store = _make_store([_REAL_SITE_ROW])
    claims = JWTClaims(user_id="admin@test", role="admin")

    body = MicrosoftMappingConfirmRequest(site_id=_FAKE_SITE_ID, drive_id=_FAKE_DRIVE_ID)
    with patch("apps.edr.app.get_postgres_store", return_value=store):
        result = await confirm_microsoft_mapping("PRJ-001", body, claims)

    assert result.project_code == "PRJ-001"
    store.insert_admin_event.assert_called_once()
    store.upsert_source_mapping.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_endpoint_placeholder_happy_path():
    store = _make_store([_PLACEHOLDER_ROW])
    store.get_source_mapping = AsyncMock(return_value=_PLACEHOLDER_ROW)
    claims = JWTClaims(user_id="admin@test", role="admin")

    body = MicrosoftMappingConfirmRequest(site_id=_FAKE_SITE_ID, drive_id=_FAKE_DRIVE_ID)
    with patch("apps.edr.app.get_postgres_store", return_value=store):
        result = await confirm_microsoft_mapping("PRJ-003", body, claims)

    assert result.project_code == "PRJ-003"
    store.insert_admin_event.assert_called_once()
    store.upsert_source_mapping.assert_called_once()
    call_kwargs = store.upsert_source_mapping.call_args.kwargs
    assert call_kwargs["sharepoint"]["site_id"] == _FAKE_SITE_ID
    assert call_kwargs["sharepoint"]["drive_id"] == _FAKE_DRIVE_ID


@pytest.mark.asyncio
async def test_confirm_endpoint_a21_audit_before_save():
    store = _make_store([_PLACEHOLDER_ROW])
    store.get_source_mapping = AsyncMock(return_value=_PLACEHOLDER_ROW)
    claims = JWTClaims(user_id="admin@test", role="admin")

    call_order: list[str] = []
    store.insert_admin_event = AsyncMock(side_effect=lambda **kw: call_order.append("audit"))
    store.upsert_source_mapping = AsyncMock(side_effect=lambda **kw: call_order.append("upsert"))

    body = MicrosoftMappingConfirmRequest(site_id=_FAKE_SITE_ID, drive_id=_FAKE_DRIVE_ID)
    with patch("apps.edr.app.get_postgres_store", return_value=store):
        await confirm_microsoft_mapping("PRJ-003", body, claims)

    assert call_order.index("audit") < call_order.index("upsert")
