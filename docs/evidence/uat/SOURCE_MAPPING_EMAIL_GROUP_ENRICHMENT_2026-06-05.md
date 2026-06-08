# Source Mapping Email Group Enrichment — 2026-06-05

## Verdict

`SOURCE_MAPPING_EMAIL_GROUP_BLOCKED_NEEDS_GRAPH_PERMISSION_NOT_LIVE`

Production remains `NOT_LIVE`. Gate 4, Gate 5, UAT, Slice 7, and LIVE were not started.

## Scope

- PRJ-001 and PRJ-002 only.
- Email enrichment only.
- ownCloud remains disabled.
- No writes to Odoo, SharePoint, Microsoft Graph, or email were performed.
- No secrets or token values were printed.

## Live Graph Permission Check

Token role names were decoded without printing the token.

Observed roles:

- `Files.Read.All`
- `Mail.Read`
- `Sites.Read.All`

Missing required roles:

- `GroupMember.Read.All`
- `Group.Read.All`
- `Directory.Read.All`
- `User.Read.All`

Because at least one required role is missing, Microsoft 365 group discovery stops before group or member reads.

## PRJ-001 Before / After

Before:

- Project name: `Construction of Civil Defense building in Al Marfa`
- Odoo project ID: `14602`
- SharePoint site ID and drive ID: verified
- Enabled sources: `odoo`, `sharepoint`
- Email: disabled; no shared mailbox; no document-control mailbox
- ownCloud: disabled
- Microsoft group metadata: absent

After:

- Project name remains from Odoo: `Construction of Civil Defense building in Al Marfa`
- Odoo project ID remains `14602`
- SharePoint site ID and drive ID remain verified
- Enabled sources remain `odoo`, `sharepoint`
- Mapping status is not complete while the Microsoft group blocker is unresolved
- Email remains disabled
- ownCloud remains disabled
- `microsoft.group_membership_status = BLOCKED_NEEDS_GRAPH_PERMISSION`
- `microsoft.member_count = 0`
- `microsoft.group_members = []`
- `microsoft.missing_permissions` lists the four missing Graph group/member roles
- Blocker: `SOURCE_MAPPING_EMAIL_GROUP_BLOCKED_NEEDS_GRAPH_PERMISSION_NOT_LIVE`

## PRJ-002 Before / After

Before:

- Project name: `Construction of Civil Defense building in Zayed City Al Dhafra.`
- Odoo project ID: `14601`
- SharePoint site ID and drive ID: verified
- Enabled sources: `odoo`, `sharepoint`
- Email: disabled; no shared mailbox; no document-control mailbox
- ownCloud: disabled
- Microsoft group metadata: absent

After:

- Project name remains from Odoo: `Construction of Civil Defense building in Zayed City Al Dhafra.`
- Odoo project ID remains `14601`
- SharePoint site ID and drive ID remain verified
- Enabled sources remain `odoo`, `sharepoint`
- Mapping status is not complete while the Microsoft group blocker is unresolved
- Email remains disabled
- ownCloud remains disabled
- `microsoft.group_membership_status = BLOCKED_NEEDS_GRAPH_PERMISSION`
- `microsoft.member_count = 0`
- `microsoft.group_members = []`
- `microsoft.missing_permissions` lists the four missing Graph group/member roles
- Blocker: `SOURCE_MAPPING_EMAIL_GROUP_BLOCKED_NEEDS_GRAPH_PERMISSION_NOT_LIVE`

## Storage / Validation Rules Implemented

- Added `microsoft` source-mapping storage for group mailbox and group members.
- Group mailbox is stored separately from shared mailboxes.
- Individual group members are stored under `microsoft.group_members`, not `email.shared_mailboxes`.
- Email can be enabled only with a real shared/document-control mailbox or a verified Microsoft 365 group mailbox.
- Missing Graph group/member permissions block Email completion.
- Group member email deduplication uses `mail`, then `userPrincipalName`.
- Non-user principals and users without usable email are ignored.
- Commercial Manager, Finance Owner, and Document Controller are filled only when member `jobTitle` or `department` proves the role.
- Unclassified verified members go to Related People / Other.

## UI Updates

- Complete badge is suppressed when blockers exist.
- Email status, group membership status, group mailbox status, member count, missing permissions, blockers, and members are visible.
- Missing fields render as `Missing`.
- ownCloud checkbox is disabled in the Source Mapping screen.
- PRJ-001 and PRJ-002 continue to show Odoo project names and numeric Odoo IDs.

## Verification

System `pytest` is currently blocked by a host-level FastAPI/Pydantic mismatch before collection:

- `ImportError: cannot import name 'PYDANTIC_V2' from 'fastapi._compat'`

The project virtualenv has the expected dependency set (`fastapi 0.115.0`, `pydantic 2.8.0`), so pytest was run with `.venv/bin/python -m pytest`.

Passed:

- `ruff check .`
- `python3 -m compileall apps scripts`
- `.venv/bin/python -m pytest apps/edr/tests/integration/test_phase2b_source_mapping.py -q` — 68 passed
- `.venv/bin/python -m pytest apps/edr/tests/integration/test_email_group_enrichment.py -q` — 30 passed
- `.venv/bin/python -m pytest apps/edr/tests/integration/test_odoo_sharepoint_sync.py -q` — 32 passed
- `.venv/bin/python -m pytest apps/edr/tests/integration -q` — 694 passed, 12 skipped
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `python3 scripts/check_doc_drift.py`
- `python3 scripts/check_ai_context.py`
- `python3 scripts/agent_postflight.py --allow-no-evidence`

Notes:

- `npm --prefix frontend run build` emitted only the existing Vite chunk-size warning.
- Full integration emitted warnings only; no failures.
- Host-side direct PostgreSQL refresh could not resolve the compose service name from outside the Docker network; the schema migration remains idempotent and will add `source_mappings.microsoft` on app init.

## Final State

Email group enrichment is implemented but blocked by missing Microsoft Graph group/member permissions.

Final verdict:

`SOURCE_MAPPING_EMAIL_GROUP_BLOCKED_NEEDS_GRAPH_PERMISSION_NOT_LIVE`
