"""Tests for Odoo + SharePoint exact-name sync.

Covers:
- normalize_name: safe transformations only
- _match_projects_to_sites: exact match / no-match / multi-match
- run_odoo_sharepoint_sync: blocked when not configured
- sync endpoint RBAC: non-admin → 403, missing claims → 401
- sync endpoint admin happy-path (mocked odoo + graph)
- no fuzzy matching (slightly-different names must not match)
- odoo emails/followers not used
- existing MANUALLY_CONFIRMED mapping not overwritten
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.admin.odoo_sharepoint_sync import (
    OdooProjectInfo,
    SharePointSiteInfo,
    _match_projects_to_sites,
    normalize_name,
    run_odoo_sharepoint_sync,
)
from apps.edr.app import _require_admin
from apps.edr.auth.validator import JWTClaims
from apps.edr.rbac.roles import Role

# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


def test_normalize_trim() -> None:
    assert normalize_name("  Alpha  ") == "Alpha"


def test_normalize_collapse_spaces() -> None:
    assert normalize_name("Alpha  Beta") == "Alpha Beta"


def test_normalize_curly_double_quotes() -> None:
    assert normalize_name('“Type D”') == '"Type D"'


def test_normalize_curly_single_quotes() -> None:
    assert normalize_name("it’s done") == "it's done"


def test_normalize_en_dash() -> None:
    assert normalize_name("Al Mirfa – D") == "Al Mirfa - D"


def test_normalize_em_dash() -> None:
    assert normalize_name("Al Mirfa — D") == "Al Mirfa - D"


def test_normalize_nfc() -> None:
    # NFC: combining char should be composed
    composed = "\xe9"       # é as single char
    decomposed = "é"  # é as e + combining accent
    assert normalize_name(decomposed) == composed


def test_normalize_idempotent() -> None:
    s = "Construction of Civil Defense Center - Type D"
    assert normalize_name(normalize_name(s)) == normalize_name(s)


def test_normalize_no_case_fold() -> None:
    assert normalize_name("ALPHA") != normalize_name("alpha")


# ---------------------------------------------------------------------------
# _match_projects_to_sites
# ---------------------------------------------------------------------------


def _make_odoo(name: str, odoo_id: int = 1) -> OdooProjectInfo:
    return OdooProjectInfo(odoo_id=odoo_id, name=name, normalized_name=normalize_name(name))


def _make_site(display_name: str, site_id: str = "s1") -> SharePointSiteInfo:
    return SharePointSiteInfo(
        site_id=site_id,
        display_name=display_name,
        site_name="siteName",
        normalized_display_name=normalize_name(display_name),
        web_url="https://example.sharepoint.com/sites/test",
    )


def test_match_exact_one_to_one() -> None:
    proj = _make_odoo("Construction of Civil Defense Center")
    site = _make_site("Construction of Civil Defense Center")
    exact, no_match, multi = _match_projects_to_sites([proj], [site])
    assert len(exact) == 1
    assert exact[0][0] is proj
    assert exact[0][1] is site
    assert no_match == []
    assert multi == []


def test_match_no_match() -> None:
    proj = _make_odoo("Alpha Project")
    site = _make_site("Beta Project")
    exact, no_match, multi = _match_projects_to_sites([proj], [site])
    assert len(exact) == 0
    assert len(no_match) == 1
    assert multi == []


def test_match_no_fuzzy() -> None:
    proj = _make_odoo("Construction of Civil Defense Center")
    site = _make_site("Civil Defense Center")  # subset, not exact
    exact, no_match, multi = _match_projects_to_sites([proj], [site])
    assert len(exact) == 0
    assert len(no_match) == 1


def test_match_multi_match() -> None:
    proj = _make_odoo("Alpha")
    site1 = _make_site("Alpha", "s1")
    site2 = _make_site("Alpha", "s2")
    exact, no_match, multi = _match_projects_to_sites([proj], [site1, site2])
    assert len(exact) == 0
    assert len(multi) == 1
    assert no_match == []


def test_match_normalization_quotes() -> None:
    odoo_name = "Construction – Type “D”"
    sp_name = "Construction - Type \"D\""
    proj = _make_odoo(odoo_name)
    site = _make_site(sp_name)
    exact, _, _ = _match_projects_to_sites([proj], [site])
    assert len(exact) == 1


def test_match_case_sensitive() -> None:
    proj = _make_odoo("alpha project")
    site = _make_site("Alpha Project")
    exact, no_match, _ = _match_projects_to_sites([proj], [site])
    assert len(exact) == 0
    assert len(no_match) == 1


def test_match_mixed_list() -> None:
    proj1 = _make_odoo("Alpha", 1)
    proj2 = _make_odoo("Beta", 2)
    proj3 = _make_odoo("Gamma", 3)
    site1 = _make_site("Alpha", "s1")
    site2_a = _make_site("Beta", "s2")
    site2_b = _make_site("Beta", "s3")
    # Alpha → exact match; Beta → multi-match; Gamma → no match
    exact, no_match, multi = _match_projects_to_sites(
        [proj1, proj2, proj3], [site1, site2_a, site2_b]
    )
    assert len(exact) == 1 and exact[0][0] is proj1
    assert len(no_match) == 1 and no_match[0] is proj3
    assert len(multi) == 1 and multi[0] is proj2


# ---------------------------------------------------------------------------
# run_odoo_sharepoint_sync — blocked when not configured
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_sync_blocked_when_odoo_not_configured() -> None:
    from apps.edr.config import settings

    with (
        patch.object(settings, "odoo_url", None),
        patch.object(settings, "odoo_database", None),
    ):
        result = await run_odoo_sharepoint_sync([])

    assert result.odoo_configured is False
    assert result.exact_matches == 0
    assert result.auto_saved_count == 0
    assert "BLOCKED" in result.summary


@pytest.mark.anyio
async def test_sync_blocked_when_graph_token_empty() -> None:
    with (
        patch(
            "apps.edr.admin.odoo_sharepoint_sync.get_graph_token",
            new=AsyncMock(return_value=""),
        ),
        patch(
            "apps.edr.admin.odoo_sharepoint_sync._fetch_odoo_projects",
            new=AsyncMock(return_value=(True, [], "")),
        ),
    ):
        result = await run_odoo_sharepoint_sync([])

    assert result.sharepoint_configured is False
    assert "BLOCKED" in result.summary


# ---------------------------------------------------------------------------
# Endpoint RBAC
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_sync_endpoint_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


def test_sync_endpoint_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Endpoint admin happy-path: auto-saves one exact match
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_sync_endpoint_admin_auto_saves() -> None:
    from apps.edr.app import sync_odoo_sharepoint

    claims = JWTClaims(user_id="admin", role="admin")

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings_full = AsyncMock(return_value=[])
    mock_pg.insert_admin_event = AsyncMock(return_value=1)
    mock_pg.upsert_source_mapping = AsyncMock(return_value=None)

    from apps.edr.admin.odoo_sharepoint_sync import (
        OdooSharePointSyncResult,
        OdooSitePairResult,
    )

    fake_pair = OdooSitePairResult(
        internal_key="odoo-42",
        odoo_project_id=42,
        odoo_project_name="Alpha Project",
        sharepoint_site_id="s-abc",
        sharepoint_drive_id="d-abc",
        sharepoint_site_name="alphaproject",
        sharepoint_display_name="Alpha Project",
        sharepoint_web_url="https://example.sharepoint.com/sites/alphaproject",
        match_confidence=100,
        mapping_status="AUTO_MATCHED_EXACT",
        mapping_method="ODOO_MAIN_NAME_EQUALS_SHAREPOINT_SITE_NAME",
        project_member_emails=["user1@example.com"],
        member_read_status="ok",
        auto_saved=True,
        save_skipped_reason=None,
    )
    fake_result = OdooSharePointSyncResult(
        scanned_at="2026-06-05T10:00:00+00:00",
        odoo_configured=True,
        sharepoint_configured=True,
        odoo_projects_scanned=1,
        sharepoint_sites_scanned=5,
        token_roles=["Files.Read.All", "Sites.Read.All"],
        exact_matches=1,
        no_match_count=0,
        multiple_match_count=0,
        auto_saved_count=1,
        matched_pairs=[fake_pair],
        unmatched_odoo_names=[],
        unmatched_sharepoint_names=[],
        odoo_emails_used=False,
        odoo_followers_used=False,
        summary="odoo=1 sp=5 | exact=1 no_match=0 multi=0 | auto_saved=1",
    )

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch(
            "apps.edr.app.run_odoo_sharepoint_sync",
            new=AsyncMock(return_value=fake_result),
        ),
    ):
        result = await sync_odoo_sharepoint(claims)

    assert result.auto_saved_count == 1
    assert result.odoo_emails_used is False
    assert result.odoo_followers_used is False
    # Verify upsert was called once for the auto-saved pair
    mock_pg.upsert_source_mapping.assert_awaited_once()
    call_kwargs = mock_pg.upsert_source_mapping.call_args.kwargs
    assert call_kwargs["project_code"] == "odoo-42"
    assert call_kwargs["project_name"] == "Alpha Project"
    assert call_kwargs["mapping_status"] == "complete"
    assert call_kwargs["sharepoint"]["site_id"] == "s-abc"
    assert call_kwargs["sharepoint"]["drive_id"] == "d-abc"
    assert call_kwargs["email"]["shared_mailboxes"] == ["user1@example.com"]
    assert call_kwargs["odoo"]["project_external_id"] == "42"
    assert call_kwargs["odoo"]["mapping_method"] == "ODOO_MAIN_NAME_EQUALS_SHAREPOINT_SITE_NAME"


@pytest.mark.anyio
async def test_sync_endpoint_skips_when_site_already_confirmed() -> None:
    """Auto-save must be skipped when an existing complete mapping holds the site_id."""
    from apps.edr.app import sync_odoo_sharepoint

    claims = JWTClaims(user_id="admin", role="admin")

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings_full = AsyncMock(return_value=[])
    mock_pg.insert_admin_event = AsyncMock(return_value=1)
    mock_pg.upsert_source_mapping = AsyncMock(return_value=None)

    from apps.edr.admin.odoo_sharepoint_sync import (
        OdooSharePointSyncResult,
        OdooSitePairResult,
    )

    skipped_pair = OdooSitePairResult(
        internal_key="odoo-99",
        odoo_project_id=99,
        odoo_project_name="Existing Project",
        sharepoint_site_id="s-existing",
        sharepoint_drive_id="d-existing",
        sharepoint_site_name="existingproject",
        sharepoint_display_name="Existing Project",
        sharepoint_web_url="https://example.sharepoint.com/sites/existingproject",
        match_confidence=100,
        mapping_status="AUTO_MATCHED_EXACT",
        mapping_method="ODOO_MAIN_NAME_EQUALS_SHAREPOINT_SITE_NAME",
        project_member_emails=[],
        member_read_status="empty",
        auto_saved=False,
        save_skipped_reason="site_id already in MANUALLY_CONFIRMED mapping (project_code=PRJ-001)",
    )
    fake_result = OdooSharePointSyncResult(
        scanned_at="2026-06-05T10:00:00+00:00",
        odoo_configured=True,
        sharepoint_configured=True,
        odoo_projects_scanned=1,
        sharepoint_sites_scanned=3,
        token_roles=["Sites.Read.All"],
        exact_matches=1,
        no_match_count=0,
        multiple_match_count=0,
        auto_saved_count=0,
        matched_pairs=[skipped_pair],
        unmatched_odoo_names=[],
        unmatched_sharepoint_names=[],
        odoo_emails_used=False,
        odoo_followers_used=False,
        summary="odoo=1 sp=3 | exact=1 no_match=0 multi=0 | auto_saved=0",
    )

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch(
            "apps.edr.app.run_odoo_sharepoint_sync",
            new=AsyncMock(return_value=fake_result),
        ),
    ):
        result = await sync_odoo_sharepoint(claims)

    # No upsert should have been called
    mock_pg.upsert_source_mapping.assert_not_awaited()
    assert result.auto_saved_count == 0


# ---------------------------------------------------------------------------
# Odoo emails/followers invariant
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_sync_result_never_uses_odoo_emails() -> None:
    """odoo_emails_used and odoo_followers_used must always be False."""
    with (
        patch(
            "apps.edr.admin.odoo_sharepoint_sync._fetch_odoo_projects",
            new=AsyncMock(return_value=(True, [], "")),
        ),
        patch(
            "apps.edr.admin.odoo_sharepoint_sync.get_graph_token",
            new=AsyncMock(return_value=""),
        ),
    ):
        result = await run_odoo_sharepoint_sync([])

    assert result.odoo_emails_used is False
    assert result.odoo_followers_used is False
