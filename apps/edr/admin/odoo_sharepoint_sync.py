"""
Odoo + SharePoint exact-name sync.

Pulls active Odoo project.project records and SharePoint sites, then
compares normalized Odoo project name against normalized SharePoint
displayName.  100% exact match only — no fuzzy matching, no token
scoring, no guessing.

Safety rules (enforced here, not just documented):
- Read-only Odoo (XML-RPC, no writes).
- Read-only Microsoft Graph (no writes to SharePoint or Mail).
- Odoo follower and Odoo email addresses are never read or used.
- Token value is never logged, printed, or returned.
- PRJ-xxx codes are never used as business truth.
"""
from __future__ import annotations

import asyncio
import re
import unicodedata
import xmlrpc.client
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel

from apps.edr.config import settings
from apps.edr.connectors.graph_token import get_graph_token

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class OdooProjectInfo(BaseModel):
    model_config = {"extra": "forbid"}
    odoo_id: int
    name: str
    normalized_name: str


class SharePointSiteInfo(BaseModel):
    model_config = {"extra": "forbid"}
    site_id: str
    display_name: str
    site_name: str
    normalized_display_name: str
    web_url: str


class OdooSitePairResult(BaseModel):
    model_config = {"extra": "forbid"}
    internal_key: str
    odoo_project_id: int
    odoo_project_name: str
    sharepoint_site_id: str
    sharepoint_drive_id: str | None
    sharepoint_site_name: str
    sharepoint_display_name: str
    sharepoint_web_url: str
    match_confidence: int
    mapping_status: str
    mapping_method: str
    project_member_emails: list[str]
    member_read_status: str
    auto_saved: bool
    save_skipped_reason: str | None


class OdooSharePointSyncResult(BaseModel):
    model_config = {"extra": "forbid"}
    scanned_at: str
    odoo_configured: bool
    sharepoint_configured: bool
    odoo_projects_scanned: int
    sharepoint_sites_scanned: int
    token_roles: list[str]
    exact_matches: int
    no_match_count: int
    multiple_match_count: int
    auto_saved_count: int
    matched_pairs: list[OdooSitePairResult]
    unmatched_odoo_names: list[str]
    unmatched_sharepoint_names: list[str]
    odoo_emails_used: bool
    odoo_followers_used: bool
    summary: str


# ---------------------------------------------------------------------------
# Name normalization — safe formatting differences only
# ---------------------------------------------------------------------------

def normalize_name(s: str) -> str:
    """Normalize a project name for exact comparison.

    Handles only safe formatting differences:
    - strip leading/trailing whitespace
    - NFC unicode normalization
    - collapse repeated internal spaces
    - normalize curly/typographic quotes to straight quotes
    - normalize em/en dashes to ASCII hyphen
    No case folding, no punctuation removal, no stemming.
    """
    s = s.strip()
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r" +", " ", s)
    # Curly double quotes
    s = s.replace("“", '"').replace("”", '"')
    # Curly single quotes / apostrophes
    s = s.replace("‘", "'").replace("’", "'")
    s = s.replace("‚", "'").replace("„", '"')
    # En dash, em dash, horizontal bar, figure dash → ASCII hyphen
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace("―", "-").replace("‒", "-")
    return s


# ---------------------------------------------------------------------------
# Odoo XML-RPC client (sync, called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _odoo_read_projects_sync(
    url: str,
    database: str,
    username: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Authenticate and read active project.project records from Odoo.

    Returns list of {id, name} dicts.  Read-only — no writes.
    Odoo follower data and email addresses are NOT requested.
    """
    common = xmlrpc.client.ServerProxy(
        f"{url.rstrip('/')}/xmlrpc/2/common", allow_none=True
    )
    uid = common.authenticate(database, username, api_key, {})
    if not uid:
        raise ValueError("Odoo authentication failed — check ODOO_USERNAME and ODOO_API_KEY")

    obj = xmlrpc.client.ServerProxy(
        f"{url.rstrip('/')}/xmlrpc/2/object", allow_none=True
    )
    records = obj.execute_kw(
        database,
        uid,
        api_key,
        "project.project",
        "search_read",
        [[["active", "=", True]]],
        {"fields": ["id", "name"], "limit": 500},
    )
    return records if isinstance(records, list) else []


async def _fetch_odoo_projects() -> tuple[bool, list[OdooProjectInfo], str]:
    """Async wrapper around the Odoo XML-RPC call.

    Returns (configured, projects, error_reason).
    """
    if not (
        settings.odoo_url
        and settings.odoo_database
        and settings.odoo_username
        and settings.odoo_api_key
    ):
        return False, [], "Odoo not configured (ODOO_URL / ODOO_DATABASE / ODOO_USERNAME / ODOO_API_KEY missing)"

    try:
        raw = await asyncio.to_thread(
            _odoo_read_projects_sync,
            settings.odoo_url,
            settings.odoo_database,
            settings.odoo_username,
            settings.odoo_api_key,
        )
    except Exception as exc:
        return True, [], f"Odoo read failed: {type(exc).__name__}: {exc}"

    projects = [
        OdooProjectInfo(
            odoo_id=int(r["id"]),
            name=str(r["name"]),
            normalized_name=normalize_name(str(r["name"])),
        )
        for r in raw
        if r.get("id") and r.get("name")
    ]
    return True, projects, ""


# ---------------------------------------------------------------------------
# SharePoint Graph client helpers
# ---------------------------------------------------------------------------

def _decode_token_roles(token: str) -> list[str]:
    import base64
    import json
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return []
        pad = parts[1] + "=="
        payload = json.loads(base64.urlsafe_b64decode(pad))
        return sorted(payload.get("roles", []))
    except Exception:
        return []


async def _graph_get(
    token: str,
    path: str,
    params: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    url = f"{_GRAPH_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, headers=headers, params=params or {})
    try:
        body: dict[str, Any] = r.json()
    except Exception:
        body = {}
    return r.status_code, body


def _derive_search_term() -> str:
    hostname = settings.public_hostname or ""
    parts = hostname.rstrip("/").split(".")
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else ""


async def _enumerate_all_sites(token: str, search_term: str) -> list[dict[str, Any]]:
    status, data = await _graph_get(
        token,
        "/sites",
        {"search": search_term, "$select": "id,displayName,webUrl,name", "$top": "200"},
    )
    if status != 200:
        return []
    return [
        s for s in data.get("value", [])
        if "contentstorage" not in s.get("webUrl", "")
    ]


async def _get_document_library_drive(token: str, site_id: str) -> str | None:
    status, data = await _graph_get(
        token,
        f"/sites/{site_id}/drives",
        {"$select": "id,name,driveType"},
    )
    if status != 200:
        return None
    doc_drives = [d for d in data.get("value", []) if d.get("driveType") == "documentLibrary"]
    return doc_drives[0]["id"] if doc_drives else None


async def _get_site_member_emails(token: str, site_id: str) -> tuple[list[str], str]:
    """Attempt to read site permissions and extract user emails.

    Returns (email_list, status) where status is 'ok', 'failed', or 'empty'.
    Uses Sites.Read.All permission (available in current Entra app).
    Does NOT use User.Read.All or Directory.Read.All.
    """
    status, data = await _graph_get(
        token,
        f"/sites/{site_id}/permissions",
        {"$select": "id,roles,grantedToV2"},
    )
    if status == 403:
        return [], "PERMISSIONS_INSUFFICIENT"
    if status != 200:
        return [], f"HTTP_{status}"

    emails: list[str] = []
    for perm in data.get("value", []):
        granted = perm.get("grantedToV2") or {}
        user = granted.get("user") or {}
        email = user.get("email") or user.get("userPrincipalName") or ""
        if email and "@" in email:
            emails.append(email)
        # Also check siteUser
        site_user = granted.get("siteUser") or {}
        su_email = site_user.get("email") or ""
        if su_email and "@" in su_email and su_email not in emails:
            emails.append(su_email)

    return emails, "ok" if emails else "empty"


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def _match_projects_to_sites(
    odoo_projects: list[OdooProjectInfo],
    sp_sites: list[SharePointSiteInfo],
) -> tuple[
    list[tuple[OdooProjectInfo, SharePointSiteInfo]],  # exact matches (1:1)
    list[OdooProjectInfo],   # no match
    list[OdooProjectInfo],   # multiple matches
]:
    """Pure function: compare normalized names, return classified results.

    Match rule: normalized_odoo_name == normalized_sharepoint_displayName
    100% exact — no fuzzy, no token score.
    """
    sp_by_norm: dict[str, list[SharePointSiteInfo]] = {}
    for site in sp_sites:
        sp_by_norm.setdefault(site.normalized_display_name, []).append(site)

    exact: list[tuple[OdooProjectInfo, SharePointSiteInfo]] = []
    no_match: list[OdooProjectInfo] = []
    multi: list[OdooProjectInfo] = []

    for proj in odoo_projects:
        norm = proj.normalized_name
        candidates = sp_by_norm.get(norm, [])
        if len(candidates) == 1:
            exact.append((proj, candidates[0]))
        elif len(candidates) == 0:
            no_match.append(proj)
        else:
            multi.append(proj)

    return exact, no_match, multi


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_odoo_sharepoint_sync(
    existing_mappings: list[dict[str, Any]],
) -> OdooSharePointSyncResult:
    """
    Read Odoo projects + SharePoint sites, exact-match by name, auto-save.

    Args:
        existing_mappings: rows from source_mappings DB table; used to detect
            MANUALLY_CONFIRMED mappings that must not be overwritten.

    Returns:
        OdooSharePointSyncResult — never writes Odoo, never writes SharePoint.
        Auto-save decisions are returned to the caller; actual DB writes are
        the caller's responsibility.
    """
    scanned_at = datetime.now(timezone.utc).isoformat()

    # ---- Odoo ---------------------------------------------------------------
    odoo_configured, odoo_projects, odoo_error = await _fetch_odoo_projects()

    # ---- SharePoint (Graph) -------------------------------------------------
    token = await get_graph_token()
    sp_configured = bool(token)
    token_roles: list[str] = []
    sp_sites: list[SharePointSiteInfo] = []
    sp_error = ""

    if token:
        token_roles = _decode_token_roles(token)
        if "Sites.Read.All" in token_roles:
            term = _derive_search_term()
            raw_sites = await _enumerate_all_sites(token, term)
            sp_sites = [
                SharePointSiteInfo(
                    site_id=s["id"],
                    display_name=s.get("displayName", ""),
                    site_name=s.get("name", ""),
                    normalized_display_name=normalize_name(s.get("displayName", "")),
                    web_url=s.get("webUrl", ""),
                )
                for s in raw_sites
            ]
        else:
            sp_error = "Sites.Read.All not in token roles — cannot enumerate sites"
    else:
        sp_error = "No Graph token — Entra not configured"

    # ---- Early-exit if either source is unavailable --------------------------
    if not odoo_configured or not sp_configured or odoo_error or sp_error:
        reasons: list[str] = []
        if not odoo_configured:
            reasons.append(odoo_error)
        elif odoo_error:
            reasons.append(f"Odoo error: {odoo_error}")
        if not sp_configured:
            reasons.append(sp_error)
        elif sp_error:
            reasons.append(f"SharePoint error: {sp_error}")
        summary = "BLOCKED: " + " | ".join(reasons)
        return OdooSharePointSyncResult(
            scanned_at=scanned_at,
            odoo_configured=odoo_configured,
            sharepoint_configured=sp_configured,
            odoo_projects_scanned=len(odoo_projects),
            sharepoint_sites_scanned=len(sp_sites),
            token_roles=token_roles,
            exact_matches=0,
            no_match_count=len(odoo_projects),
            multiple_match_count=0,
            auto_saved_count=0,
            matched_pairs=[],
            unmatched_odoo_names=[p.name for p in odoo_projects],
            unmatched_sharepoint_names=[s.display_name for s in sp_sites],
            odoo_emails_used=False,
            odoo_followers_used=False,
            summary=summary,
        )

    # ---- Matching -----------------------------------------------------------
    exact_pairs, no_match, multi_match = _match_projects_to_sites(odoo_projects, sp_sites)

    # Build index of existing confirmed mappings by site_id to prevent overwrite
    confirmed_site_ids: set[str] = set()
    existing_keys: dict[str, dict[str, Any]] = {}
    for row in existing_mappings:
        import json as _json

        code = str(row.get("project_code", ""))
        status_val = str(row.get("mapping_status", ""))
        existing_keys[code] = row
        sp_col = row.get("sharepoint")
        if isinstance(sp_col, str):
            try:
                sp_col = _json.loads(sp_col)
            except Exception:
                sp_col = {}
        site_id_val = (sp_col or {}).get("site_id", "") if isinstance(sp_col, dict) else ""
        # "complete" status = manually confirmed or previously auto-confirmed
        if site_id_val and status_val == "complete":
            confirmed_site_ids.add(site_id_val)

    # ---- Per-match: get drive + members, check auto-save eligibility ---------
    pair_tasks = [
        _process_one_pair(token, proj, site, confirmed_site_ids, existing_keys)
        for proj, site in exact_pairs
    ]
    matched_pairs: list[OdooSitePairResult] = list(await asyncio.gather(*pair_tasks))

    auto_saved_count = sum(1 for p in matched_pairs if p.auto_saved)

    # Unmatched SharePoint sites: those whose normalized_display_name is NOT
    # in any exact match
    matched_site_ids = {site.site_id for _, site in exact_pairs}
    unmatched_sp = [s.display_name for s in sp_sites if s.site_id not in matched_site_ids]

    summary_parts = [
        f"odoo={len(odoo_projects)} sp={len(sp_sites)}",
        f"exact={len(exact_pairs)} no_match={len(no_match)} multi={len(multi_match)}",
        f"auto_saved={auto_saved_count}",
    ]
    if not exact_pairs:
        summary_parts.append("No exact Odoo↔SharePoint name matches found")
    summary = " | ".join(summary_parts)

    return OdooSharePointSyncResult(
        scanned_at=scanned_at,
        odoo_configured=odoo_configured,
        sharepoint_configured=sp_configured,
        odoo_projects_scanned=len(odoo_projects),
        sharepoint_sites_scanned=len(sp_sites),
        token_roles=token_roles,
        exact_matches=len(exact_pairs),
        no_match_count=len(no_match),
        multiple_match_count=len(multi_match),
        auto_saved_count=auto_saved_count,
        matched_pairs=matched_pairs,
        unmatched_odoo_names=[p.name for p in no_match],
        unmatched_sharepoint_names=unmatched_sp,
        odoo_emails_used=False,
        odoo_followers_used=False,
        summary=summary,
    )


async def _process_one_pair(
    token: str,
    proj: OdooProjectInfo,
    site: SharePointSiteInfo,
    confirmed_site_ids: set[str],
    existing_keys: dict[str, dict[str, Any]],
) -> OdooSitePairResult:
    """Build the OdooSitePairResult for one matched pair.

    Does NOT write to DB; returns auto_saved=True when the pair is
    eligible for saving (caller decides to write).  The actual save is
    done in the endpoint handler in app.py.
    """
    internal_key = f"odoo-{proj.odoo_id}"

    # Get drive_id
    drive_id = await _get_document_library_drive(token, site.site_id)

    # Get site members
    member_emails, member_status = await _get_site_member_emails(token, site.site_id)

    # Check auto-save eligibility
    save_skipped_reason: str | None = None

    if not site.site_id:
        save_skipped_reason = "site_id is empty"
    elif not drive_id:
        save_skipped_reason = "drive_id could not be determined"
    elif site.site_id in confirmed_site_ids:
        existing_code = next(
            (code for code, row in existing_keys.items()
             if _row_site_id(row) == site.site_id
             and str(row.get("mapping_status", "")) == "complete"),
            None,
        )
        save_skipped_reason = (
            f"site_id already in MANUALLY_CONFIRMED mapping "
            f"(project_code={existing_code})"
        )

    auto_saved = save_skipped_reason is None

    return OdooSitePairResult(
        internal_key=internal_key,
        odoo_project_id=proj.odoo_id,
        odoo_project_name=proj.name,
        sharepoint_site_id=site.site_id,
        sharepoint_drive_id=drive_id,
        sharepoint_site_name=site.site_name,
        sharepoint_display_name=site.display_name,
        sharepoint_web_url=site.web_url,
        match_confidence=100,
        mapping_status="AUTO_MATCHED_EXACT",
        mapping_method="ODOO_MAIN_NAME_EQUALS_SHAREPOINT_SITE_NAME",
        project_member_emails=member_emails,
        member_read_status=member_status,
        auto_saved=auto_saved,
        save_skipped_reason=save_skipped_reason,
    )


def _row_site_id(row: dict[str, Any]) -> str:
    import json as _json

    sp = row.get("sharepoint")
    if isinstance(sp, str):
        try:
            sp = _json.loads(sp)
        except Exception:
            return ""
    return (sp or {}).get("site_id", "") if isinstance(sp, dict) else ""
