"""Read-only Microsoft 365 group email enrichment for source mappings.

Scope is intentionally narrow: PRJ-001 and PRJ-002 only, no Microsoft Graph
writes, no mailbox mutation, and no invented people or mailboxes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from apps.edr.admin.microsoft_rescan import _GRAPH_BASE, _decode_token_roles
from apps.edr.connectors.graph_token import get_graph_token

REQUIRED_GRAPH_GROUP_ROLES: tuple[str, ...] = (
    "GroupMember.Read.All",
    "Group.Read.All",
    "Directory.Read.All",
    "User.Read.All",
)

VERDICT_ENRICHED = "SOURCE_MAPPING_EMAIL_GROUP_ENRICHED_NOT_LIVE"
VERDICT_PARTIAL = "SOURCE_MAPPING_EMAIL_GROUP_PARTIAL_NOT_LIVE"
VERDICT_BLOCKED_PERMISSION = (
    "SOURCE_MAPPING_EMAIL_GROUP_BLOCKED_NEEDS_GRAPH_PERMISSION_NOT_LIVE"
)
VERDICT_BLOCKED_NO_GROUP = "SOURCE_MAPPING_EMAIL_GROUP_BLOCKED_NO_GROUP_SOURCE_NOT_LIVE"

GroupMembershipStatus = Literal[
    "BLOCKED_NEEDS_GRAPH_PERMISSION",
    "NO_SHAREPOINT_SITE",
    "NO_GROUP_SOURCE",
    "GROUP_FOUND_NO_MAILBOX",
    "GROUP_FOUND_NO_MEMBERS",
    "GROUP_MEMBERS_READ",
]


class EmailGroup(BaseModel):
    model_config = {"extra": "forbid"}
    id: str = ""
    display_name: str = ""
    mail: str = ""
    mail_enabled: bool = False


class EmailGroupMember(BaseModel):
    model_config = {"extra": "forbid"}
    id: str = ""
    display_name: str = ""
    mail: str = ""
    user_principal_name: str = ""
    job_title: str = ""
    department: str = ""
    email: str = ""


class EmailGroupProjectResult(BaseModel):
    model_config = {"extra": "forbid"}
    project_code: str
    project_name: str
    sharepoint_site_id: str
    group_membership_status: GroupMembershipStatus
    group: EmailGroup = EmailGroup()
    group_members: list[EmailGroupMember] = []
    member_count: int = 0
    related_people: dict[str, Any] = {}
    email_enabled: bool = False
    missing_permissions: list[str] = []
    blockers: list[str] = []


class EmailGroupEnrichmentResponse(BaseModel):
    model_config = {"extra": "forbid"}
    scanned_at: str
    verdict: str
    token_roles: list[str]
    missing_permissions: list[str]
    project_results: list[EmailGroupProjectResult]
    summary: str


class GraphEmailGroupClient:
    """Thin async read-only wrapper around Microsoft Graph v1.0."""

    def __init__(self, token: str) -> None:
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _get(
        self, path_or_url: str, params: dict[str, str] | None = None
    ) -> tuple[int, dict[str, Any]]:
        url = path_or_url if path_or_url.startswith("https://") else f"{_GRAPH_BASE}{path_or_url}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, headers=self._headers, params=params or {})
        try:
            body: dict[str, Any] = response.json()
        except Exception:
            body = {}
        return response.status_code, body

    async def _get_paged(
        self, path: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_url: str | None = path
        next_params = params
        while next_url:
            status, data = await self._get(next_url, next_params)
            if status >= 400:
                return items
            value = data.get("value")
            if isinstance(value, list):
                items.extend(item for item in value if isinstance(item, dict))
            next_url = data.get("@odata.nextLink")
            next_params = None
        return items

    async def enumerate_unified_groups(self) -> list[dict[str, Any]]:
        return await self._get_paged(
            "/groups",
            {
                "$select": "id,displayName,mail,mailEnabled",
                "$filter": "groupTypes/any(c:c eq 'Unified')",
                "$top": "999",
            },
        )

    async def group_root_site(self, group_id: str) -> dict[str, Any] | None:
        status, data = await self._get(
            f"/groups/{group_id}/sites/root",
            {"$select": "id,displayName,webUrl"},
        )
        if status >= 400:
            return None
        return data if isinstance(data, dict) else None

    async def find_connected_group(self, site_id: str) -> EmailGroup | None:
        """Return the Microsoft 365 group whose root site matches site_id."""
        groups = await self.enumerate_unified_groups()
        for raw_group in groups:
            group_id = str(raw_group.get("id") or "")
            if not group_id:
                continue
            root_site = await self.group_root_site(group_id)
            if not root_site:
                continue
            if str(root_site.get("id") or "") == site_id:
                return EmailGroup(
                    id=group_id,
                    display_name=str(raw_group.get("displayName") or ""),
                    mail=str(raw_group.get("mail") or ""),
                    mail_enabled=bool(raw_group.get("mailEnabled")),
                )
        return None

    async def group_members(self, group_id: str) -> list[EmailGroupMember]:
        raw_members = await self._get_paged(
            f"/groups/{group_id}/members/microsoft.graph.user",
            {
                "$select": "id,displayName,mail,userPrincipalName,jobTitle,department",
                "$top": "999",
            },
        )
        return dedupe_group_members(raw_members)


def _usable_email(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped and "@" in stripped and "example.com" not in stripped.lower())


def _member_email(raw: dict[str, Any]) -> str:
    mail = str(raw.get("mail") or "").strip()
    if _usable_email(mail):
        return mail
    upn = str(raw.get("userPrincipalName") or "").strip()
    return upn if _usable_email(upn) else ""


def dedupe_group_members(raw_members: list[dict[str, Any] | EmailGroupMember]) -> list[EmailGroupMember]:
    members: list[EmailGroupMember] = []
    seen: set[str] = set()
    for raw in raw_members:
        data = raw.model_dump() if isinstance(raw, EmailGroupMember) else raw
        if not isinstance(data, dict):
            continue
        odata_type = str(data.get("@odata.type") or "").lower()
        if odata_type and odata_type != "#microsoft.graph.user":
            continue
        email = data.get("email") or _member_email(data)
        email = str(email or "").strip()
        if not _usable_email(email):
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        members.append(
            EmailGroupMember(
                id=str(data.get("id") or ""),
                display_name=str(data.get("displayName") or data.get("display_name") or ""),
                mail=str(data.get("mail") or ""),
                user_principal_name=str(
                    data.get("userPrincipalName") or data.get("user_principal_name") or ""
                ),
                job_title=str(data.get("jobTitle") or data.get("job_title") or ""),
                department=str(data.get("department") or ""),
                email=email,
            )
        )
    return members


def _person_label(member: EmailGroupMember) -> str:
    name = member.display_name.strip() or member.email
    return f"{name} <{member.email}>"


def classify_related_people(
    existing_related_people: dict[str, Any] | None,
    members: list[EmailGroupMember],
) -> dict[str, Any]:
    """Classify only roles proved by member jobTitle or department."""
    existing = existing_related_people or {}
    related = {
        "project_manager": str(existing.get("project_manager") or ""),
        "commercial_manager": "",
        "finance_owner": "",
        "document_controller": "",
        "other": [],
    }
    classified_emails: set[str] = set()

    for member in members:
        proof = f"{member.job_title} {member.department}".lower()
        label = _person_label(member)
        key = member.email.lower()
        if "document controller" in proof or "document control" in proof:
            if not related["document_controller"]:
                related["document_controller"] = label
            classified_emails.add(key)
        elif "commercial" in proof:
            if not related["commercial_manager"]:
                related["commercial_manager"] = label
            classified_emails.add(key)
        elif "finance" in proof:
            if not related["finance_owner"]:
                related["finance_owner"] = label
            classified_emails.add(key)

    other: list[str] = []
    seen_other: set[str] = set()
    for member in members:
        key = member.email.lower()
        if key in classified_emails or key in seen_other:
            continue
        seen_other.add(key)
        other.append(_person_label(member))
    related["other"] = other
    return related


def _project_result_blocked(
    project: dict[str, Any],
    *,
    missing_permissions: list[str],
) -> EmailGroupProjectResult:
    return EmailGroupProjectResult(
        project_code=str(project.get("project_code") or ""),
        project_name=str(project.get("project_name") or ""),
        sharepoint_site_id=str((project.get("sharepoint") or {}).get("site_id") or ""),
        group_membership_status="BLOCKED_NEEDS_GRAPH_PERMISSION",
        missing_permissions=missing_permissions,
        blockers=[VERDICT_BLOCKED_PERMISSION],
        related_people=project.get("related_people") or {},
    )


async def _enrich_project(
    client: GraphEmailGroupClient,
    project: dict[str, Any],
) -> EmailGroupProjectResult:
    code = str(project.get("project_code") or "")
    project_name = str(project.get("project_name") or "")
    sharepoint = project.get("sharepoint") or {}
    site_id = str(sharepoint.get("site_id") or "")
    if not site_id:
        return EmailGroupProjectResult(
            project_code=code,
            project_name=project_name,
            sharepoint_site_id="",
            group_membership_status="NO_SHAREPOINT_SITE",
            blockers=[VERDICT_BLOCKED_NO_GROUP],
            related_people=project.get("related_people") or {},
        )

    group = await client.find_connected_group(site_id)
    if group is None:
        return EmailGroupProjectResult(
            project_code=code,
            project_name=project_name,
            sharepoint_site_id=site_id,
            group_membership_status="NO_GROUP_SOURCE",
            blockers=[VERDICT_BLOCKED_NO_GROUP],
            related_people=project.get("related_people") or {},
        )

    members = await client.group_members(group.id)
    group_mailbox_ok = bool(group.mail_enabled and _usable_email(group.mail))
    if members:
        status: GroupMembershipStatus = "GROUP_MEMBERS_READ"
    elif group_mailbox_ok:
        status = "GROUP_FOUND_NO_MEMBERS"
    else:
        status = "GROUP_FOUND_NO_MAILBOX"

    blockers = [] if group_mailbox_ok else [VERDICT_BLOCKED_NO_GROUP]
    related_people = classify_related_people(project.get("related_people"), members)
    return EmailGroupProjectResult(
        project_code=code,
        project_name=project_name,
        sharepoint_site_id=site_id,
        group_membership_status=status,
        group=group,
        group_members=members,
        member_count=len(members),
        related_people=related_people,
        email_enabled=group_mailbox_ok,
        blockers=blockers,
    )


async def run_email_group_enrichment(
    projects: list[dict[str, Any]],
) -> EmailGroupEnrichmentResponse:
    """Run a read-only Microsoft 365 group enrichment pass."""
    scoped_projects = [
        project
        for project in projects
        if str(project.get("project_code") or "") in {"PRJ-001", "PRJ-002"}
    ]
    scanned_at = datetime.now(timezone.utc).isoformat()
    token = await get_graph_token()
    if not token:
        missing = list(REQUIRED_GRAPH_GROUP_ROLES)
        results = [
            _project_result_blocked(project, missing_permissions=missing)
            for project in scoped_projects
        ]
        return EmailGroupEnrichmentResponse(
            scanned_at=scanned_at,
            verdict=VERDICT_BLOCKED_PERMISSION,
            token_roles=[],
            missing_permissions=missing,
            project_results=results,
            summary="BLOCKED: no Graph token available for Microsoft 365 group discovery.",
        )

    roles = _decode_token_roles(token)
    missing = [role for role in REQUIRED_GRAPH_GROUP_ROLES if role not in roles]
    if missing:
        results = [
            _project_result_blocked(project, missing_permissions=missing)
            for project in scoped_projects
        ]
        return EmailGroupEnrichmentResponse(
            scanned_at=scanned_at,
            verdict=VERDICT_BLOCKED_PERMISSION,
            token_roles=roles,
            missing_permissions=missing,
            project_results=results,
            summary=(
                "BLOCKED: Microsoft Graph token is missing group/member roles: "
                + ", ".join(missing)
            ),
        )

    client = GraphEmailGroupClient(token)
    results = list(
        await asyncio.gather(*[_enrich_project(client, project) for project in scoped_projects])
    )
    if all(result.email_enabled and not result.blockers for result in results):
        verdict = VERDICT_ENRICHED
    elif any(result.email_enabled for result in results):
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_BLOCKED_NO_GROUP

    return EmailGroupEnrichmentResponse(
        scanned_at=scanned_at,
        verdict=verdict,
        token_roles=roles,
        missing_permissions=[],
        project_results=results,
        summary=(
            f"{len(results)} project(s) scanned | "
            f"group mailboxes verified={sum(1 for r in results if r.email_enabled)} | "
            f"members read={sum(r.member_count for r in results)}"
        ),
    )
