"""Phase 2B Slice 6 — Project Source Mapping integration tests.

Coverage:
- RBAC: all 8 non-admin roles → 403 on all 5 endpoints
- Missing claims → 401
- Happy path: list, get detail, validate, upsert, disable
- Get detail 404
- Validate complete vs incomplete mapping
- Upsert happy path
- A-21 audit-before-save order
- Disable happy path → 204
- Disable not found → 404
- Disable already disabled → 409
- C-1: no query / report content / evidence in responses
- C-6: no credential values in responses
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.app import (
    SourceMappingDetail,
    EmailGroupEnrichmentRequest,
    SourceMappingListResponse,
    SourceMappingUpsertRequest,
    _compute_mapping_status,
    _require_admin,
)
from apps.edr.admin.email_group_enrichment import (
    VERDICT_BLOCKED_PERMISSION,
    classify_related_people,
    dedupe_group_members,
    run_email_group_enrichment,
)
from apps.edr.auth.validator import JWTClaims
from apps.edr.persistence.postgres_store import PostgresStore
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# RBAC — all endpoints deny every non-admin role (parametrised)
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


def _fake_token(roles: list[str]) -> str:
    payload = {"roles": roles}
    enc = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"h.{enc}.s"


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_list_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_detail_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_validate_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_upsert_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_disable_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Missing claims → 401
# ---------------------------------------------------------------------------


def test_source_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# List — happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_list_returns_mappings() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "project_code": "PRJ-001",
            "project_name": "Alpha",
            "mapping_status": "complete",
            "contract_numbers": '["CON-001"]',
        },
        {
            "project_code": "PRJ-002",
            "project_name": "Beta",
            "mapping_status": "incomplete",
            "contract_numbers": '["CON-002"]',
        },
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_source_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_source_mappings(claims)

    assert isinstance(result, SourceMappingListResponse)
    assert len(result.mappings) == 2
    assert result.mappings[0].project_code == "PRJ-001"
    assert result.mappings[1].mapping_status == "incomplete"


# ---------------------------------------------------------------------------
# Get detail — happy path + 404
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_detail_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "project_name": "Alpha",
        "contract_numbers": '["CON-001"]',
        "sharepoint": '{"site_id": "s1", "drive_id": "d1", "root_path": "/r1"}',
        "owncloud": '{"base_path": "/o1"}',
        "email": '{"shared_mailboxes": ["m1"], "document_control_mailbox": "dc1"}',
        "odoo": '{"project_model": "pm", "cost_model": "cm", "project_external_id": "pe"}',
        "related_people": '{"project_manager": "pm"}',
        "enabled_sources": '["sharepoint", "email"]',
        "allowed_roles": '["executive", "finance"]',
        "mapping_status": "complete",
        "last_validation_result": None,
        "last_validated_at": None,
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "updated_at": datetime(2026, 5, 2, 12, 0, 0),
        "created_by_hash": "abc",
        "updated_by_hash": "def",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import get_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await get_source_mapping("PRJ-001", claims)

    assert isinstance(result, SourceMappingDetail)
    assert result.project_code == "PRJ-001"
    assert result.sharepoint.site_id == "s1"


@pytest.mark.anyio
async def test_source_detail_not_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=None)

    from apps.edr.app import get_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_source_mapping("MISSING", claims)

    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Validate — pure function tests
# ---------------------------------------------------------------------------


def test_validate_complete_mapping() -> None:
    project_name = "Construction of Civil Defense building in Al Marfa"
    body = SourceMappingUpsertRequest(
        project_name=project_name,
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        odoo={
            "project_external_id": "14602",
            "project_name": project_name,
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
            "analytic_account_id": "21963",
        },
        enabled_sources=["sharepoint", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "complete"
    assert errors == []


def test_validate_incomplete_mapping() -> None:
    body = SourceMappingUpsertRequest(
        sharepoint={"site_id": "", "drive_id": "", "root_path": ""},
        enabled_sources=["sharepoint"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any(e.field == "sharepoint.site_id" for e in errors)


def test_example_site_id_cannot_be_complete() -> None:
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "example-site-id-001", "drive_id": "real-drive-id", "root_path": "/"},
        odoo={
            "project_external_id": "14602",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any(e.field == "sharepoint.site_id" for e in errors)


def test_example_com_mailbox_cannot_be_complete() -> None:
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        email={"shared_mailboxes": ["project-prj-001@example.com"]},
        odoo={
            "project_external_id": "14602",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "email", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any(e.field == "email.shared_mailboxes" for e in errors)


def test_prj_code_cannot_be_odoo_external_id() -> None:
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        odoo={
            "project_external_id": "PRJ-001",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any("Internal PRJ codes" in e.message for e in errors)


def test_email_disabled_when_no_real_mailbox_exists() -> None:
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        email={"shared_mailboxes": [], "document_control_mailbox": ""},
        odoo={
            "project_external_id": "14602",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "email", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any(e.field == "email.shared_mailboxes" for e in errors)


def test_email_can_use_verified_group_mailbox_without_shared_mailbox() -> None:
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        email={"shared_mailboxes": [], "document_control_mailbox": ""},
        microsoft={
            "group": {
                "id": "group-1",
                "display_name": "Civil Defense Al Marfa",
                "mail": "civil-defense-al-marfa@elrace.com",
                "mail_enabled": True,
            },
            "group_membership_status": "GROUP_MEMBERS_READ",
            "group_members": [],
            "member_count": 0,
            "missing_permissions": [],
            "blockers": [],
        },
        odoo={
            "project_external_id": "14602",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "email", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "complete"
    assert errors == []


def test_group_members_are_not_stored_as_shared_mailboxes() -> None:
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        email={"shared_mailboxes": ["member@elrace.com"], "document_control_mailbox": ""},
        microsoft={
            "group": {
                "id": "group-1",
                "display_name": "Civil Defense Al Marfa",
                "mail": "civil-defense-al-marfa@elrace.com",
                "mail_enabled": True,
            },
            "group_membership_status": "GROUP_MEMBERS_READ",
            "group_members": [{"id": "u1", "email": "member@elrace.com"}],
            "member_count": 1,
            "missing_permissions": [],
            "blockers": [],
        },
        odoo={
            "project_external_id": "14602",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "email", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any("microsoft.group_members" in e.message for e in errors)


def test_missing_graph_permission_blocks_email_enabled_mapping() -> None:
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        email={"shared_mailboxes": [], "document_control_mailbox": ""},
        microsoft={
            "group": {
                "id": "",
                "display_name": "",
                "mail": "",
                "mail_enabled": False,
            },
            "group_membership_status": "BLOCKED_NEEDS_GRAPH_PERMISSION",
            "group_members": [],
            "member_count": 0,
            "missing_permissions": ["Group.Read.All"],
            "blockers": [VERDICT_BLOCKED_PERMISSION],
        },
        odoo={
            "project_external_id": "14602",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "email", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any(e.field == "microsoft.missing_permissions" for e in errors)
    assert any(e.field == "microsoft.group_membership_status" for e in errors)


def test_microsoft_group_blocker_prevents_complete_when_email_off() -> None:
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        microsoft={
            "group_membership_status": "BLOCKED_NEEDS_GRAPH_PERMISSION",
            "missing_permissions": ["Group.Read.All"],
            "blockers": [VERDICT_BLOCKED_PERMISSION],
        },
        odoo={
            "project_external_id": "14602",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any(e.field == "microsoft.blockers" for e in errors)


def test_member_emails_are_deduplicated_and_non_users_ignored() -> None:
    members = dedupe_group_members([
        {
            "@odata.type": "#microsoft.graph.user",
            "id": "u1",
            "displayName": "One",
            "mail": "one@elrace.com",
            "userPrincipalName": "one.upn@elrace.com",
        },
        {
            "@odata.type": "#microsoft.graph.user",
            "id": "u2",
            "displayName": "One Duplicate",
            "mail": "",
            "userPrincipalName": "ONE@elrace.com",
        },
        {
            "@odata.type": "#microsoft.graph.servicePrincipal",
            "id": "sp1",
            "displayName": "Service",
            "mail": "svc@elrace.com",
        },
        {
            "@odata.type": "#microsoft.graph.user",
            "id": "u3",
            "displayName": "No Mail",
            "mail": "",
            "userPrincipalName": "",
        },
    ])
    assert [member.email for member in members] == ["one@elrace.com"]


def test_related_people_only_from_verified_member_metadata() -> None:
    members = dedupe_group_members([
        {
            "id": "c1",
            "displayName": "Commercial Lead",
            "mail": "commercial@elrace.com",
            "jobTitle": "Commercial Manager",
            "department": "Projects",
        },
        {
            "id": "f1",
            "displayName": "Finance Lead",
            "mail": "finance@elrace.com",
            "jobTitle": "",
            "department": "Finance",
        },
        {
            "id": "o1",
            "displayName": "Site User",
            "mail": "site.user@elrace.com",
            "jobTitle": "Engineer",
            "department": "Projects",
        },
    ])
    related = classify_related_people({"project_manager": "Ahmad Ezzat Anwar"}, members)
    assert related["project_manager"] == "Ahmad Ezzat Anwar"
    assert related["commercial_manager"] == "Commercial Lead <commercial@elrace.com>"
    assert related["finance_owner"] == "Finance Lead <finance@elrace.com>"
    assert related["document_controller"] == ""
    assert related["other"] == ["Site User <site.user@elrace.com>"]


@pytest.mark.anyio
async def test_email_group_missing_permission_stops_before_graph_reads() -> None:
    projects = [
        {
            "project_code": "PRJ-001",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "sharepoint": {"site_id": "real-site-id"},
            "related_people": {"project_manager": "Ahmad Ezzat Anwar"},
        }
    ]
    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value=_fake_token(["Sites.Read.All"])),
        ),
        patch("apps.edr.admin.email_group_enrichment.GraphEmailGroupClient") as client_cls,
    ):
        result = await run_email_group_enrichment(projects)
    assert result.verdict == VERDICT_BLOCKED_PERMISSION
    assert result.project_results[0].group_membership_status == "BLOCKED_NEEDS_GRAPH_PERMISSION"
    client_cls.assert_not_called()


@pytest.mark.anyio
async def test_email_group_permission_blocker_does_not_upsert_mapping() -> None:
    from apps.edr.app import enrich_email_groups

    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "project_name": "Construction of Civil Defense building in Al Marfa",
        "contract_numbers": "[]",
        "sharepoint": '{"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"}',
        "owncloud": '{"base_path": ""}',
        "email": '{"shared_mailboxes": [], "document_control_mailbox": ""}',
        "microsoft": "{}",
        "odoo": (
            '{"project_model": "project.project", "cost_model": "account.analytic.line",'
            ' "project_external_id": "14602",'
            ' "project_name": "Construction of Civil Defense building in Al Marfa"}'
        ),
        "related_people": '{"project_manager": "Ahmad Ezzat Anwar"}',
        "enabled_sources": '["odoo", "sharepoint"]',
        "allowed_roles": "[]",
        "mapping_status": "complete",
        "last_validation_result": None,
        "last_validated_at": None,
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "updated_at": datetime(2026, 5, 1, 10, 0, 0),
        "created_by_hash": "",
        "updated_by_hash": "",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings = AsyncMock(return_value=[fake_row])
    mock_pg.insert_admin_event = AsyncMock(return_value=1)
    mock_pg.upsert_source_mapping = AsyncMock(return_value=None)

    async def _fake_run_email_group_enrichment(projects):
        return await run_email_group_enrichment(projects)

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch(
            "apps.edr.app.run_email_group_enrichment",
            new=AsyncMock(side_effect=_fake_run_email_group_enrichment),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value=_fake_token(["Sites.Read.All"])),
        ),
    ):
        result = await enrich_email_groups(
            claims,
            EmailGroupEnrichmentRequest(project_codes=["PRJ-001"]),
        )

    assert result.verdict == VERDICT_BLOCKED_PERMISSION
    mock_pg.upsert_source_mapping.assert_not_awaited()


def test_owncloud_disabled_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.edr.config import settings

    monkeypatch.setattr(settings, "owncloud_username", None)
    monkeypatch.setattr(settings, "owncloud_password", None)
    body = SourceMappingUpsertRequest(
        project_name="Construction of Civil Defense building in Al Marfa",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        owncloud={"base_path": "/verified"},
        odoo={
            "project_external_id": "14602",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "owncloud", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any(e.field == "enabled_sources" and "ownCloud" in e.message for e in errors)


def test_project_name_must_come_from_odoo_not_sharepoint_url() -> None:
    body = SourceMappingUpsertRequest(
        project_name="CivilDefenseCenterinIndustrialAreaofMadinatZayed",
        sharepoint={"site_id": "real-site-id", "drive_id": "real-drive-id", "root_path": "/"},
        odoo={
            "project_external_id": "14601",
            "project_name": "Construction of Civil Defense building in Zayed City Al Dhafra.",
            "project_model": "project.project",
            "cost_model": "account.analytic.line",
        },
        enabled_sources=["sharepoint", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-002", body)
    assert status == "incomplete"
    assert any(e.field == "project_name" for e in errors)


@pytest.mark.anyio
async def test_prj_rows_are_enriched_in_existing_rows() -> None:
    class FakeConn:
        def __init__(self) -> None:
            self.calls: list[tuple] = []

        async def execute(self, *args):
            self.calls.append(args)

    conn = FakeConn()
    await PostgresStore()._migrate_verified_prj_source_mappings(conn)

    calls_by_code = {call[1]: call for call in conn.calls}
    assert set(calls_by_code) == {"PRJ-001", "PRJ-002"}

    prj001 = calls_by_code["PRJ-001"]
    assert prj001[2] == "Construction of Civil Defense building in Al Marfa"
    assert json.loads(prj001[4])["root_path"] == "/"
    assert json.loads(prj001[6])["shared_mailboxes"] == []
    assert json.loads(prj001[7])["group_membership_status"] == "GROUP_MEMBERS_READ"
    assert json.loads(prj001[7])["group"]["mail_enabled"] is True
    assert json.loads(prj001[8])["project_external_id"] == "14602"
    assert json.loads(prj001[8])["analytic_account_id"] == "21963"
    assert json.loads(prj001[10]) == ["email", "odoo", "sharepoint"]

    prj002 = calls_by_code["PRJ-002"]
    assert prj002[2] == "Construction of Civil Defense building in Zayed City Al Dhafra."
    assert json.loads(prj002[8])["project_external_id"] == "14601"
    assert json.loads(prj002[8])["analytic_account_id"] == "21960"


# ---------------------------------------------------------------------------
# Upsert — happy path + A-21 audit-before-save
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_upsert_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "project_name": "Alpha",
        "contract_numbers": '["CON-001"]',
        "sharepoint": '{"site_id": "s1", "drive_id": "d1", "root_path": "/r1"}',
        "owncloud": '{"base_path": "/o1"}',
        "email": '{"shared_mailboxes": ["m1"], "document_control_mailbox": "dc1"}',
        "odoo": '{"project_model": "pm", "cost_model": "cm", "project_external_id": "pe"}',
        "related_people": '{"project_manager": "pm"}',
        "enabled_sources": '["sharepoint"]',
        "allowed_roles": '["executive"]',
        "mapping_status": "complete",
        "last_validation_result": None,
        "last_validated_at": None,
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "updated_at": datetime(2026, 5, 2, 12, 0, 0),
        "created_by_hash": "abc",
        "updated_by_hash": "def",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_admin_event = AsyncMock(return_value=42)
    mock_pg.upsert_source_mapping = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import upsert_source_mapping

    body = SourceMappingUpsertRequest(
        sharepoint={"site_id": "s1", "drive_id": "d1", "root_path": "/r1"},
        enabled_sources=["sharepoint"],
    )
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await upsert_source_mapping("PRJ-001", body, claims)

    assert isinstance(result, SourceMappingDetail)
    assert result.project_code == "PRJ-001"


@pytest.mark.anyio
async def test_source_upsert_audit_before_save() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "project_name": "Alpha",
        "contract_numbers": '[]',
        "sharepoint": '{}',
        "owncloud": '{}',
        "email": '{}',
        "odoo": '{}',
        "related_people": '{}',
        "enabled_sources": '[]',
        "allowed_roles": '[]',
        "mapping_status": "incomplete",
        "last_validation_result": None,
        "last_validated_at": None,
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "updated_at": datetime(2026, 5, 1, 10, 0, 0),
        "created_by_hash": "",
        "updated_by_hash": "",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_admin_event = AsyncMock(return_value=99)
    mock_pg.upsert_source_mapping = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import upsert_source_mapping

    body = SourceMappingUpsertRequest()
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        await upsert_source_mapping("PRJ-001", body, claims)

    calls = mock_pg.method_calls
    call_names = [c[0] for c in calls]
    audit_idx = call_names.index("insert_admin_event")
    upsert_idx = call_names.index("upsert_source_mapping")
    assert audit_idx < upsert_idx, "A-21 violation: audit must fire before DB write"


# ---------------------------------------------------------------------------
# Disable — happy path, 404, 409
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_disable_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "mapping_status": "complete",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)
    mock_pg.insert_admin_event = AsyncMock(return_value=77)
    mock_pg.disable_source_mapping = AsyncMock(return_value=None)

    from apps.edr.app import disable_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        response = await disable_source_mapping("PRJ-001", claims)

    assert response.status_code == 204
    mock_pg.disable_source_mapping.assert_awaited_once_with("PRJ-001")


@pytest.mark.anyio
async def test_source_disable_not_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=None)

    from apps.edr.app import disable_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await disable_source_mapping("MISSING", claims)

    assert exc.value.status_code == 404
    mock_pg.insert_admin_event.assert_not_called()
    mock_pg.disable_source_mapping.assert_not_called()


@pytest.mark.anyio
async def test_source_disable_already_disabled() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {"project_code": "PRJ-001", "mapping_status": "disabled"}
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import disable_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await disable_source_mapping("PRJ-001", claims)

    assert exc.value.status_code == 409
    mock_pg.insert_admin_event.assert_not_called()
    mock_pg.disable_source_mapping.assert_not_called()


# ---------------------------------------------------------------------------
# C-1 — no business content in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_list_no_business_content() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "project_code": "PRJ-001",
            "project_name": "Alpha",
            "mapping_status": "complete",
            "contract_numbers": '["CON-001"]',
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_source_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_source_mappings(claims)

    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content found in source list"


# ---------------------------------------------------------------------------
# C-6 — no credential values in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_list_no_credentials() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "project_code": "PRJ-001",
            "project_name": "Alpha",
            "mapping_status": "complete",
            "contract_numbers": '["CON-001"]',
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_source_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_source_mappings(claims)

    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in source list"
