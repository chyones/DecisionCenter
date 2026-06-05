"""
Microsoft Graph read-only rescan for the admin source-mapping panel.

Discovers SharePoint sites, drives, and mailboxes, then scores each
against existing project mappings to produce AUTO_MAPPED,
NEEDS_CONFIRMATION, MISSING_SHAREPOINT, MISSING_MAILBOX, CONFLICT,
or DISABLED verdicts.

Safety rules (enforced here, not just documented):
- Read-only Microsoft Graph.  No writes to SharePoint or Mail.
- Does not write to the database; caller decides to confirm.
- Token value is never logged, printed, or returned.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from apps.edr.connectors.graph_token import get_graph_token
from apps.edr.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_PLACEHOLDER_SITE_IDS: frozenset[str] = frozenset({
    "",
    "example-site-id",
    "example-site-id-001",
    "example-site-id-002",
})
_PLACEHOLDER_DRIVE_IDS: frozenset[str] = frozenset({
    "",
    "example-drive-id",
    "example-drive-id-001",
    "example-drive-id-002",
})
_PLACEHOLDER_MAILBOX_DOMAINS: frozenset[str] = frozenset({"example.com"})

_STOP_WORDS: frozenset[str] = frozenset({
    "the", "and", "for", "with", "from", "area", "type", "region",
    "center", "centre", "in", "of", "at", "to", "by", "a", "an",
    "this", "that", "will", "its",
})

# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

MappingStatus = Literal[
    "AUTO_MAPPED",
    "NEEDS_CONFIRMATION",
    "MISSING_SHAREPOINT",
    "MISSING_MAILBOX",
    "CONFLICT",
    "DISABLED",
]


class SiteCandidate(BaseModel):
    model_config = {"extra": "forbid"}
    site_id: str
    display_name: str
    web_url: str
    drive_id: str | None = None
    drive_name: str | None = None
    root_item_count: int | None = None
    match_strength: Literal["strong", "medium", "weak", "existing"]
    confidence: float


class MailboxCandidate(BaseModel):
    model_config = {"extra": "forbid"}
    address: str
    accessible: bool
    http_status: int


class ProjectRescanResult(BaseModel):
    model_config = {"extra": "forbid"}
    project_code: str
    project_name: str
    existing_site_id: str
    existing_drive_id: str
    sharepoint_status: MappingStatus
    mailbox_status: MappingStatus
    site_candidates: list[SiteCandidate]
    mailbox_candidates: list[MailboxCandidate]
    reason: str
    recommended_site_id: str | None = None
    recommended_drive_id: str | None = None
    recommended_mailboxes: list[str] = []


class MicrosoftRescanResponse(BaseModel):
    model_config = {"extra": "forbid"}
    scanned_at: str
    token_roles: list[str]
    has_sites_read_all: bool
    has_mail_read: bool
    total_sites_discovered: int
    project_results: list[ProjectRescanResult]
    summary: str


# ---------------------------------------------------------------------------
# Read-only Graph discovery client
# ---------------------------------------------------------------------------

class GraphDiscoveryClient:
    """Thin async read-only wrapper around Microsoft Graph v1.0."""

    def __init__(self, token: str) -> None:
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _get(
        self, path: str, params: dict[str, str] | None = None
    ) -> tuple[int, dict[str, Any]]:
        url = f"{_GRAPH_BASE}{path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=self._headers, params=params or {})
        try:
            body: dict[str, Any] = r.json()
        except Exception:
            body = {}
        return r.status_code, body

    async def enumerate_sites(self, search_term: str) -> list[dict[str, Any]]:
        """Return all named sites (filters out contentstorage entries)."""
        status, data = await self._get(
            "/sites",
            {"search": search_term, "$select": "id,displayName,webUrl,name", "$top": "100"},
        )
        if status != 200:
            return []
        return [
            s for s in data.get("value", [])
            if "contentstorage" not in s.get("webUrl", "")
        ]

    async def get_drives(self, site_id: str) -> list[dict[str, Any]]:
        status, data = await self._get(
            f"/sites/{site_id}/drives",
            {"$select": "id,name,driveType,webUrl"},
        )
        if status != 200:
            return []
        return data.get("value", [])

    async def get_root_children_count(self, drive_id: str) -> tuple[int, int]:
        """Returns (http_status, item_count_at_root)."""
        status, data = await self._get(
            f"/drives/{drive_id}/root/children",
            {"$top": "5", "$select": "id,name"},
        )
        return status, len(data.get("value", [])) if status == 200 else 0

    async def probe_site(self, site_id: str) -> tuple[int, dict[str, Any]]:
        return await self._get(f"/sites/{site_id}", {"$select": "id,displayName,webUrl"})

    async def probe_mailbox(self, address: str) -> tuple[bool, int]:
        status, _ = await self._get(
            f"/users/{address}/mailFolders/inbox", {"$top": "1"}
        )
        return status == 200, status


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _decode_token_roles(token: str) -> list[str]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return []
        pad = parts[1] + "=="
        payload = json.loads(base64.urlsafe_b64decode(pad))
        return sorted(payload.get("roles", []))
    except Exception:
        return []


def _is_placeholder_site(site_id: str) -> bool:
    return not site_id or site_id in _PLACEHOLDER_SITE_IDS or "example" in site_id.lower()


def _is_placeholder_drive(drive_id: str) -> bool:
    return not drive_id or drive_id in _PLACEHOLDER_DRIVE_IDS or "example" in drive_id.lower()


def _is_placeholder_mailbox(address: str) -> bool:
    if not address:
        return True
    domain = address.split("@")[-1].lower() if "@" in address else ""
    return domain in _PLACEHOLDER_MAILBOX_DOMAINS


def _sig_words(text: str) -> list[str]:
    return [w for w in text.lower().split() if len(w) > 3 and w not in _STOP_WORDS]


def _compute_match(
    project_code: str,
    project_name: str,
    site: dict[str, Any],
) -> tuple[Literal["strong", "medium", "weak", "none"], float]:
    """Return (strength, confidence ∈ [0.0, 1.0])."""
    display = site.get("displayName", "").lower()

    # Strong: project code found verbatim in site name
    if project_code.lower() in display:
        return "strong", 1.0

    # Keyword overlap with project name
    if project_name:
        sig = _sig_words(project_name)
        if sig:
            hits = sum(1 for w in sig if w in display)
            ratio = hits / len(sig)
            if ratio >= 0.8:
                return "strong", round(ratio, 2)
            if ratio >= 0.5:
                return "medium", round(ratio, 2)
            if ratio > 0:
                return "weak", round(ratio, 2)

    return "none", 0.0


def _derive_search_term() -> str:
    """Extract company-name component from PUBLIC_HOSTNAME for site search.

    'vantage.elrace.com' → 'elrace'.
    Falls back to 'elrace' if parsing fails.
    """
    hostname = settings.public_hostname or ""
    parts = hostname.rstrip("/").split(".")
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else "elrace"


# ---------------------------------------------------------------------------
# Per-project rescan
# ---------------------------------------------------------------------------

async def _rescan_one_project(
    client: GraphDiscoveryClient,
    project_code: str,
    project_name: str,
    existing_site_id: str,
    existing_drive_id: str,
    existing_mailboxes: list[str],
    mapping_disabled: bool,
    all_sites: list[dict[str, Any]],
) -> ProjectRescanResult:

    if mapping_disabled:
        return ProjectRescanResult(
            project_code=project_code,
            project_name=project_name,
            existing_site_id=existing_site_id,
            existing_drive_id=existing_drive_id,
            sharepoint_status="DISABLED",
            mailbox_status="DISABLED",
            site_candidates=[],
            mailbox_candidates=[],
            reason="Mapping is disabled.",
        )

    # ---- SharePoint --------------------------------------------------------
    site_candidates: list[SiteCandidate] = []
    sp_status: MappingStatus
    sp_reason: str
    recommended_site_id: str | None = None
    recommended_drive_id: str | None = None

    if not _is_placeholder_site(existing_site_id):
        # Probe existing site
        http_st, site_data = await client.probe_site(existing_site_id)
        if http_st == 200:
            # Get drives, prefer existing drive_id
            drives = await client.get_drives(existing_site_id)
            doc_drives = [d for d in drives if d.get("driveType") == "documentLibrary"]
            chosen_drive_id: str | None = None
            chosen_drive_name: str | None = None
            item_count: int | None = None
            if doc_drives:
                matching = [d for d in doc_drives if d["id"] == existing_drive_id]
                chosen = (matching or doc_drives)[0]
                chosen_drive_id = chosen["id"]
                chosen_drive_name = chosen.get("name")
                _, item_count = await client.get_root_children_count(chosen_drive_id)
            site_candidates = [SiteCandidate(
                site_id=existing_site_id,
                display_name=site_data.get("displayName", ""),
                web_url=site_data.get("webUrl", ""),
                drive_id=chosen_drive_id,
                drive_name=chosen_drive_name,
                root_item_count=item_count,
                match_strength="existing",
                confidence=1.0,
            )]
            sp_status = "AUTO_MAPPED"
            sp_reason = "Existing site_id confirmed reachable via Microsoft Graph."
            recommended_site_id = existing_site_id
            recommended_drive_id = chosen_drive_id
        else:
            sp_status = "NEEDS_CONFIRMATION"
            sp_reason = (
                f"Existing site_id returned HTTP {http_st}. "
                "Site may have been deleted or moved. Admin must re-assign."
            )
    else:
        # Discover from all_sites
        _strength_order = {"strong": 0, "medium": 1, "weak": 2}
        scored: list[tuple[dict[str, Any], Literal["strong", "medium", "weak"], float]] = []
        for site in all_sites:
            strength, confidence = _compute_match(project_code, project_name, site)
            if strength != "none":
                scored.append((site, strength, confidence))  # type: ignore[arg-type]
        scored.sort(key=lambda x: (_strength_order[x[1]], -x[2]))

        if not scored:
            sp_status = "MISSING_SHAREPOINT"
            sp_reason = (
                f"No candidate sites found for '{project_code}'. "
                "Supply project_name or enter site_id manually."
            )
        else:
            # Enrich top-5 candidates with drive info
            for site, strength, confidence in scored[:5]:
                drives = await client.get_drives(site["id"])
                doc_drives = [d for d in drives if d.get("driveType") == "documentLibrary"]
                if doc_drives:
                    drv = doc_drives[0]
                    _, cnt = await client.get_root_children_count(drv["id"])
                    site_candidates.append(SiteCandidate(
                        site_id=site["id"],
                        display_name=site.get("displayName", ""),
                        web_url=site.get("webUrl", ""),
                        drive_id=drv["id"],
                        drive_name=drv.get("name"),
                        root_item_count=cnt,
                        match_strength=strength,
                        confidence=confidence,
                    ))
                else:
                    site_candidates.append(SiteCandidate(
                        site_id=site["id"],
                        display_name=site.get("displayName", ""),
                        web_url=site.get("webUrl", ""),
                        match_strength=strength,
                        confidence=confidence,
                    ))

            strong = [c for c in site_candidates if c.match_strength == "strong"]
            if len(strong) == 1:
                sp_status = "AUTO_MAPPED"
                sp_reason = f"Single strong match: '{strong[0].display_name}'."
                recommended_site_id = strong[0].site_id
                recommended_drive_id = strong[0].drive_id
            elif len(strong) > 1:
                sp_status = "CONFLICT"
                sp_reason = f"{len(strong)} strong matches found. Admin must choose."
            else:
                sp_status = "NEEDS_CONFIRMATION"
                sp_reason = (
                    f"{len(scored)} candidate(s) found but none are a deterministic match. "
                    "Admin must confirm."
                )

    # ---- Mailbox -----------------------------------------------------------
    mb_candidates: list[MailboxCandidate] = []
    mb_status: MappingStatus
    mb_reason: str
    recommended_mailboxes: list[str] = []

    real_mailboxes = [m for m in existing_mailboxes if not _is_placeholder_mailbox(m)]
    if not real_mailboxes:
        mb_status = "MISSING_MAILBOX"
        mb_reason = "All mailbox entries are placeholders. Operator must supply real SMTP addresses."
    else:
        for addr in real_mailboxes:
            accessible, http_st = await client.probe_mailbox(addr)
            mb_candidates.append(MailboxCandidate(
                address=addr, accessible=accessible, http_status=http_st
            ))
        accessible_mbs = [m for m in mb_candidates if m.accessible]
        if accessible_mbs:
            mb_status = "AUTO_MAPPED"
            mb_reason = (
                f"{len(accessible_mbs)}/{len(real_mailboxes)} mailbox(es) "
                "confirmed accessible via Mail.Read."
            )
            recommended_mailboxes = [m.address for m in accessible_mbs]
        else:
            mb_status = "NEEDS_CONFIRMATION"
            mb_reason = (
                "Existing mailbox addresses returned non-200 via Mail.Read. "
                "Verify addresses or check Mail.Read permission scope."
            )

    return ProjectRescanResult(
        project_code=project_code,
        project_name=project_name,
        existing_site_id=existing_site_id,
        existing_drive_id=existing_drive_id,
        sharepoint_status=sp_status,
        mailbox_status=mb_status,
        site_candidates=site_candidates,
        mailbox_candidates=mb_candidates,
        reason=f"SharePoint: {sp_reason} | Mailbox: {mb_reason}",
        recommended_site_id=recommended_site_id,
        recommended_drive_id=recommended_drive_id,
        recommended_mailboxes=recommended_mailboxes,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_microsoft_rescan(
    projects: list[dict[str, Any]],
    *,
    search_term: str | None = None,
) -> MicrosoftRescanResponse:
    """
    Read-only Graph discovery pass for the given project list.

    Args:
        projects: each dict must have keys project_code, project_name,
                  sharepoint {site_id, drive_id}, email {shared_mailboxes},
                  mapping_status.
        search_term: override the auto-derived tenant search term.

    Returns:
        MicrosoftRescanResponse — per-project results, no DB writes.
    """
    scanned_at = datetime.now(timezone.utc).isoformat()
    term = search_term or _derive_search_term()

    token = await get_graph_token()
    if not token:
        return MicrosoftRescanResponse(
            scanned_at=scanned_at,
            token_roles=[],
            has_sites_read_all=False,
            has_mail_read=False,
            total_sites_discovered=0,
            project_results=[],
            summary=(
                "BLOCKED: No Graph token available. "
                "Entra credentials (ENTRA_CLIENT_ID, ENTRA_TENANT_ID, ENTRA_CLIENT_SECRET) "
                "are not configured."
            ),
        )

    roles = _decode_token_roles(token)
    has_sp = "Sites.Read.All" in roles
    has_mail = "Mail.Read" in roles

    client = GraphDiscoveryClient(token)

    all_sites: list[dict[str, Any]] = []
    if has_sp:
        all_sites = await client.enumerate_sites(term)

    # Run per-project rescans concurrently
    tasks = [
        _rescan_one_project(
            client=client,
            project_code=p["project_code"],
            project_name=p.get("project_name", ""),
            existing_site_id=(p.get("sharepoint") or {}).get("site_id", ""),
            existing_drive_id=(p.get("sharepoint") or {}).get("drive_id", ""),
            existing_mailboxes=(p.get("email") or {}).get("shared_mailboxes", []),
            mapping_disabled=p.get("mapping_status") == "disabled",
            all_sites=all_sites if has_sp else [],
        )
        for p in projects
    ]
    results: list[ProjectRescanResult] = list(await asyncio.gather(*tasks))

    auto   = sum(1 for r in results if r.sharepoint_status == "AUTO_MAPPED")
    needs  = sum(1 for r in results if r.sharepoint_status in {"NEEDS_CONFIRMATION", "CONFLICT"})
    miss   = sum(1 for r in results if r.sharepoint_status == "MISSING_SHAREPOINT")
    dis    = sum(1 for r in results if r.sharepoint_status == "DISABLED")

    summary = (
        f"{len(results)} project(s) scanned | "
        f"SharePoint: {auto} auto-mapped, {needs} need confirmation, "
        f"{miss} missing, {dis} disabled | "
        f"Sites.Read.All={has_sp} Mail.Read={has_mail} "
        f"sites_discovered={len(all_sites)}"
    )

    return MicrosoftRescanResponse(
        scanned_at=scanned_at,
        token_roles=roles,
        has_sites_read_all=has_sp,
        has_mail_read=has_mail,
        total_sites_discovered=len(all_sites),
        project_results=results,
        summary=summary,
    )
