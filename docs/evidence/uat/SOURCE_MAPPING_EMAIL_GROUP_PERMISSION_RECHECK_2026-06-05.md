# Source Mapping Email Group Permission Recheck — 2026-06-05

## Verdict

`SOURCE_MAPPING_EMAIL_GROUP_BLOCKED_NEEDS_GRAPH_PERMISSION_NOT_LIVE`

Production remains `NOT_LIVE`. Gate 4, Gate 5, UAT, Slice 7, and LIVE were not started.

## Scope

- PRJ-001 and PRJ-002 only.
- Microsoft Graph group permission verification only.
- No new features implemented.
- No writes to Odoo, SharePoint, Microsoft Graph, or email.
- ownCloud remains disabled.

## Runtime State

| Check | Result |
|---|---|
| API health (`/healthz`) | `ok` — postgres, redis, qdrant, minio all ok |
| Git branch | `main` (uncommitted working-tree changes; base commit `029de7c`) |

## Graph Token Role Check

Token is present. Role count decoded from token claims: **3**.

| Role | Present |
|---|---|
| `GroupMember.Read.All` | **MISSING** |
| `Group.Read.All` | **MISSING** |
| `Directory.Read.All` | **MISSING** |
| `User.Read.All` | **MISSING** |
| `Sites.Read.All` | ok |
| `Files.Read.All` | ok |
| `Mail.Read` | ok |

All four required group/member roles are absent from the token.

## Effect on PRJ-001 and PRJ-002

Because at least one required Graph role is missing, `run_email_group_enrichment` returns `VERDICT_BLOCKED_PERMISSION` before any group or member reads occur. No changes are written to either project's source mapping. Both projects remain:

- `microsoft.group_membership_status = BLOCKED_NEEDS_GRAPH_PERMISSION`
- `microsoft.member_count = 0`
- `microsoft.group_members = []`
- `email_enabled = false`
- `ownCloud = disabled`
- `enabled_sources` unchanged (`odoo`, `sharepoint`)

## Required Action to Unblock

Grant the following four Application permissions to the registered Entra service principal and re-run `POST /admin/source-mappings/enrich-email-groups`:

1. `GroupMember.Read.All`
2. `Group.Read.All`
3. `Directory.Read.All`
4. `User.Read.All`

Admin consent is required for all four.

## Final Verdict

`SOURCE_MAPPING_EMAIL_GROUP_BLOCKED_NEEDS_GRAPH_PERMISSION_NOT_LIVE`
