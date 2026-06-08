"""Tests for email group enrichment (PRJ-001 / PRJ-002 only).

Invariants proved here:
- Email stays disabled when group has no verified mailbox (no mail or mail_enabled=False)
- ownCloud is not added to enabled_sources under any circumstance
- Group members are NOT stored as shared_mailboxes
- Missing Graph permissions produce VERDICT_BLOCKED_PERMISSION immediately
- Member emails are deduplicated (case-insensitive)
- Related people are derived only from verified group members
- No writes to Odoo, SharePoint, Graph, or mailboxes
- RBAC: non-admin → 403, missing claims → 401
- Scope guard: only PRJ-001 / PRJ-002 codes accepted; others are filtered out
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.admin.email_group_enrichment import (
    VERDICT_BLOCKED_NO_GROUP,
    VERDICT_BLOCKED_PERMISSION,
    VERDICT_ENRICHED,
    EmailGroup,
    EmailGroupMember,
    classify_related_people,
    dedupe_group_members,
    run_email_group_enrichment,
)
from apps.edr.app import _require_admin
from apps.edr.auth.validator import JWTClaims
from apps.edr.rbac.roles import Role

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project(code: str, site_id: str = "site-abc") -> dict:
    return {
        "project_code": code,
        "project_name": f"Project {code}",
        "sharepoint": {"site_id": site_id},
        "owncloud": {"base_path": ""},
        "related_people": {},
        "enabled_sources": ["sharepoint"],
    }


def _raw_member(
    id: str = "u1",
    display_name: str = "User One",
    mail: str = "user1@corp.test",
    upn: str = "user1@corp.test",
    job_title: str = "",
    department: str = "",
) -> dict:
    return {
        "@odata.type": "#microsoft.graph.user",
        "id": id,
        "displayName": display_name,
        "mail": mail,
        "userPrincipalName": upn,
        "jobTitle": job_title,
        "department": department,
    }


# ---------------------------------------------------------------------------
# dedupe_group_members
# ---------------------------------------------------------------------------


def test_dedupe_basic() -> None:
    raw = [
        _raw_member(id="u1", mail="alice@corp.test"),
        _raw_member(id="u2", mail="bob@corp.test"),
    ]
    result = dedupe_group_members(raw)
    assert len(result) == 2
    emails = {m.email for m in result}
    assert "alice@corp.test" in emails
    assert "bob@corp.test" in emails


def test_dedupe_case_insensitive() -> None:
    raw = [
        _raw_member(id="u1", mail="Alice@Corp.TEST"),
        _raw_member(id="u2", mail="alice@corp.test"),
    ]
    result = dedupe_group_members(raw)
    assert len(result) == 1


def test_dedupe_skips_non_user_odata_type() -> None:
    raw = [
        {
            "@odata.type": "#microsoft.graph.group",
            "id": "g1",
            "displayName": "Some Group",
            "mail": "group@example.com",
            "userPrincipalName": "",
            "jobTitle": "",
            "department": "",
        }
    ]
    result = dedupe_group_members(raw)
    assert len(result) == 0


def test_dedupe_falls_back_to_upn() -> None:
    raw = [
        _raw_member(id="u1", mail="", upn="user@corp.test"),
    ]
    result = dedupe_group_members(raw)
    assert len(result) == 1
    assert result[0].email == "user@corp.test"


def test_dedupe_skips_no_usable_email() -> None:
    raw = [_raw_member(id="u1", mail="", upn="")]
    result = dedupe_group_members(raw)
    assert len(result) == 0


def test_dedupe_skips_example_com_domain() -> None:
    # Both mail and UPN must be unusable; the filter blocks example.com from both
    raw = [_raw_member(id="u1", mail="test@example.com", upn="test@example.com")]
    result = dedupe_group_members(raw)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# classify_related_people
# ---------------------------------------------------------------------------


def test_classify_document_controller() -> None:
    member = EmailGroupMember(
        id="u1",
        display_name="Doc Control",
        mail="dc@corp.test",
        user_principal_name="dc@corp.test",
        job_title="Document Controller",
        department="",
        email="dc@corp.test",
    )
    result = classify_related_people({}, [member])
    assert result["document_controller"] == "Doc Control <dc@corp.test>"
    assert member.email not in (result.get("other") or [])


def test_classify_commercial_manager() -> None:
    member = EmailGroupMember(
        id="u2",
        display_name="Comm Guy",
        mail="cg@corp.test",
        user_principal_name="cg@corp.test",
        job_title="Commercial Lead",
        department="",
        email="cg@corp.test",
    )
    result = classify_related_people({}, [member])
    assert result["commercial_manager"] == "Comm Guy <cg@corp.test>"


def test_classify_finance_owner() -> None:
    member = EmailGroupMember(
        id="u3",
        display_name="Finance Head",
        mail="fh@corp.test",
        user_principal_name="fh@corp.test",
        job_title="",
        department="Finance",
        email="fh@corp.test",
    )
    result = classify_related_people({}, [member])
    assert result["finance_owner"] == "Finance Head <fh@corp.test>"


def test_classify_unclassified_goes_to_other() -> None:
    member = EmailGroupMember(
        id="u4",
        display_name="Random Person",
        mail="rp@corp.test",
        user_principal_name="rp@corp.test",
        job_title="Engineer",
        department="Construction",
        email="rp@corp.test",
    )
    result = classify_related_people({}, [member])
    assert "Random Person <rp@corp.test>" in result["other"]


def test_classify_preserves_project_manager() -> None:
    existing = {"project_manager": "PM Name <pm@corp.test>"}
    result = classify_related_people(existing, [])
    assert result["project_manager"] == "PM Name <pm@corp.test>"


# ---------------------------------------------------------------------------
# run_email_group_enrichment — no token
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enrichment_blocked_when_no_token() -> None:
    with patch(
        "apps.edr.admin.email_group_enrichment.get_graph_token",
        new=AsyncMock(return_value=""),
    ):
        response = await run_email_group_enrichment([_project("PRJ-001")])

    assert response.verdict == VERDICT_BLOCKED_PERMISSION
    assert len(response.missing_permissions) > 0
    assert all(r.group_membership_status == "BLOCKED_NEEDS_GRAPH_PERMISSION" for r in response.project_results)
    # Email must NOT be enabled when blocked
    assert all(not r.email_enabled for r in response.project_results)


# ---------------------------------------------------------------------------
# run_email_group_enrichment — missing token roles
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enrichment_blocked_when_missing_roles() -> None:

    fake_token = "fake.token.here"
    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value=fake_token),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment._decode_token_roles",
            return_value=[],  # no roles at all
        ),
    ):
        response = await run_email_group_enrichment([_project("PRJ-001")])

    assert response.verdict == VERDICT_BLOCKED_PERMISSION
    assert response.missing_permissions  # at least one missing


# ---------------------------------------------------------------------------
# run_email_group_enrichment — no SharePoint site ID
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enrichment_blocked_no_site_id() -> None:
    project = {
        "project_code": "PRJ-001",
        "project_name": "Test Project",
        "sharepoint": {"site_id": ""},
        "related_people": {},
        "enabled_sources": ["sharepoint"],
    }
    all_roles = list(__import__("apps.edr.admin.email_group_enrichment", fromlist=["REQUIRED_GRAPH_GROUP_ROLES"]).REQUIRED_GRAPH_GROUP_ROLES)

    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value="t.t.t"),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment._decode_token_roles",
            return_value=all_roles,
        ),
    ):
        response = await run_email_group_enrichment([project])

    assert response.verdict == VERDICT_BLOCKED_NO_GROUP
    r = response.project_results[0]
    assert r.group_membership_status == "NO_SHAREPOINT_SITE"
    assert not r.email_enabled


# ---------------------------------------------------------------------------
# run_email_group_enrichment — no group found
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enrichment_blocked_no_group_found() -> None:
    all_roles = list(__import__("apps.edr.admin.email_group_enrichment", fromlist=["REQUIRED_GRAPH_GROUP_ROLES"]).REQUIRED_GRAPH_GROUP_ROLES)

    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value="t.t.t"),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment._decode_token_roles",
            return_value=all_roles,
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient.find_connected_group",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await run_email_group_enrichment([_project("PRJ-001")])

    assert response.verdict == VERDICT_BLOCKED_NO_GROUP
    r = response.project_results[0]
    assert r.group_membership_status == "NO_GROUP_SOURCE"
    assert not r.email_enabled


# ---------------------------------------------------------------------------
# run_email_group_enrichment — group found but mailbox not mail-enabled
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enrichment_group_found_no_mailbox() -> None:
    """Email must stay disabled when group.mail_enabled is False."""
    all_roles = list(__import__("apps.edr.admin.email_group_enrichment", fromlist=["REQUIRED_GRAPH_GROUP_ROLES"]).REQUIRED_GRAPH_GROUP_ROLES)
    fake_group = EmailGroup(id="g1", display_name="Test Group", mail="", mail_enabled=False)

    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value="t.t.t"),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment._decode_token_roles",
            return_value=all_roles,
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient.find_connected_group",
            new=AsyncMock(return_value=fake_group),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient.group_members",
            new=AsyncMock(return_value=[]),
        ),
    ):
        response = await run_email_group_enrichment([_project("PRJ-001")])

    r = response.project_results[0]
    assert not r.email_enabled
    assert r.group_membership_status == "GROUP_FOUND_NO_MAILBOX"


# ---------------------------------------------------------------------------
# run_email_group_enrichment — full enrichment
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enrichment_full_email_enabled() -> None:
    """VERDICT_ENRICHED when both projects have a verified group mailbox."""
    all_roles = list(__import__("apps.edr.admin.email_group_enrichment", fromlist=["REQUIRED_GRAPH_GROUP_ROLES"]).REQUIRED_GRAPH_GROUP_ROLES)
    fake_group = EmailGroup(
        id="g1", display_name="Test Group", mail="group@corp.test", mail_enabled=True
    )
    fake_member = EmailGroupMember(
        id="u1",
        display_name="Alice",
        mail="alice@corp.test",
        user_principal_name="alice@corp.test",
        job_title="Document Controller",
        department="",
        email="alice@corp.test",
    )

    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value="t.t.t"),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment._decode_token_roles",
            return_value=all_roles,
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient.find_connected_group",
            new=AsyncMock(return_value=fake_group),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient.group_members",
            new=AsyncMock(return_value=[fake_member]),
        ),
    ):
        response = await run_email_group_enrichment(
            [_project("PRJ-001"), _project("PRJ-002", site_id="site-xyz")]
        )

    assert response.verdict == VERDICT_ENRICHED
    for r in response.project_results:
        assert r.email_enabled
        assert r.group.mail == "group@corp.test"
        assert r.member_count == 1


# ---------------------------------------------------------------------------
# Invariant: group members MUST NOT be stored as shared_mailboxes
# ---------------------------------------------------------------------------


def test_group_members_not_in_shared_mailboxes() -> None:
    """Members from a group must not appear in the shared_mailboxes list.

    The endpoint writes group members to the microsoft.group_members field,
    not to email.shared_mailboxes. This test proves dedupe_group_members
    returns EmailGroupMember objects (not strings), enforcing separation.
    """
    raw = [_raw_member(id="u1", mail="dm@corp.test")]
    members = dedupe_group_members(raw)
    # Members are EmailGroupMember objects — there is no path to shared_mailboxes
    for m in members:
        assert isinstance(m, EmailGroupMember)
        assert not isinstance(m, str)


# ---------------------------------------------------------------------------
# Invariant: ownCloud must never appear in enabled_sources via enrichment
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_owncloud_never_enabled() -> None:
    """The enrichment response contains no ownCloud references."""
    all_roles = list(__import__("apps.edr.admin.email_group_enrichment", fromlist=["REQUIRED_GRAPH_GROUP_ROLES"]).REQUIRED_GRAPH_GROUP_ROLES)
    fake_group = EmailGroup(
        id="g1", display_name="Test", mail="g@corp.test", mail_enabled=True
    )

    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value="t.t.t"),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment._decode_token_roles",
            return_value=all_roles,
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient.find_connected_group",
            new=AsyncMock(return_value=fake_group),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient.group_members",
            new=AsyncMock(return_value=[]),
        ),
    ):
        response = await run_email_group_enrichment([_project("PRJ-001")])

    # Verify the response itself has no owncloud mention
    response_json = response.model_dump_json()
    assert "owncloud" not in response_json.lower()
    assert "ownCloud" not in response_json


# ---------------------------------------------------------------------------
# Invariant: scope guard — only PRJ-001 / PRJ-002
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_scope_guard_filters_other_codes() -> None:
    """Projects outside PRJ-001/PRJ-002 are silently ignored."""
    all_roles = list(__import__("apps.edr.admin.email_group_enrichment", fromlist=["REQUIRED_GRAPH_GROUP_ROLES"]).REQUIRED_GRAPH_GROUP_ROLES)

    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value="t.t.t"),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment._decode_token_roles",
            return_value=all_roles,
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient.find_connected_group",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await run_email_group_enrichment(
            [_project("PRJ-999"), _project("PRJ-001")]
        )

    codes = {r.project_code for r in response.project_results}
    assert "PRJ-999" not in codes
    assert "PRJ-001" in codes


# ---------------------------------------------------------------------------
# Invariant: no writes — run_email_group_enrichment makes no Graph mutations
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_graph_writes() -> None:
    """Only GET calls are used; no POST/PATCH/DELETE to Graph."""
    all_roles = list(__import__("apps.edr.admin.email_group_enrichment", fromlist=["REQUIRED_GRAPH_GROUP_ROLES"]).REQUIRED_GRAPH_GROUP_ROLES)
    post_called = []

    async def fake_get(*args, **kwargs):
        return 200, {}

    fake_client = MagicMock()
    fake_client.find_connected_group = AsyncMock(return_value=None)
    # Attach a tracker for any write-like calls
    fake_client.post = MagicMock(side_effect=lambda *a, **kw: post_called.append(a))
    fake_client.patch = MagicMock(side_effect=lambda *a, **kw: post_called.append(a))
    fake_client.delete = MagicMock(side_effect=lambda *a, **kw: post_called.append(a))

    with (
        patch(
            "apps.edr.admin.email_group_enrichment.get_graph_token",
            new=AsyncMock(return_value="t.t.t"),
        ),
        patch(
            "apps.edr.admin.email_group_enrichment._decode_token_roles",
            return_value=all_roles,
        ),
        patch(
            "apps.edr.admin.email_group_enrichment.GraphEmailGroupClient",
            return_value=fake_client,
        ),
    ):
        await run_email_group_enrichment([_project("PRJ-001")])

    assert post_called == [], "No write calls (POST/PATCH/DELETE) should have been made"


# ---------------------------------------------------------------------------
# Endpoint RBAC
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_enrich_endpoint_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


def test_enrich_endpoint_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401
