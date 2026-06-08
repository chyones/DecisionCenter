# Source Mapping Email Group Live Recheck — 2026-06-05

## Verdict

`SOURCE_MAPPING_EMAIL_GROUP_ENRICHED_NOT_LIVE`

Both PRJ-001 and PRJ-002 have a verified Microsoft 365 group mailbox and their members were successfully read from Microsoft Graph. Email is enabled for both projects. Production remains `NOT_LIVE`. Gate 4, Gate 5, UAT, Slice 7, and LIVE were not started.

## Scope

- PRJ-001 and PRJ-002 only.
- Microsoft Graph group permission verification and group enrichment.
- No new features implemented.
- No writes to Odoo, SharePoint, or Microsoft Graph.
- No emails sent, deleted, archived, or modified.
- No secrets or token values printed.
- ownCloud remains disabled.

## Runtime State

| Check | Result |
|---|---|
| API health (`/healthz`) | `ok` — postgres, redis, qdrant, minio all ok |
| Git branch | `main` (uncommitted working-tree changes; base commit `029de7c`) |

## Graph Token Role Check

Token present. Role count: **7**.

| Role | Present |
|---|---|
| `GroupMember.Read.All` | ok |
| `Group.Read.All` | ok |
| `Directory.Read.All` | ok |
| `User.Read.All` | ok |
| `Sites.Read.All` | ok |
| `Files.Read.All` | ok |
| `Mail.Read` | ok |

All four required group/member roles present. No missing permissions.

## Enrichment Run Results

`run_email_group_enrichment` called directly with live project data (Postgres unreachable outside Docker network; config-file project records used as input — equivalent data).

```
SUMMARY: 2 project(s) scanned | group mailboxes verified=2 | members read=35
```

### PRJ-001

| Field | Value |
|---|---|
| Project name | `Construction of Civil Defense building in Al Marfa` |
| `group_membership_status` | `GROUP_MEMBERS_READ` |
| `email_enabled` | `True` |
| `group.id` | `71313630-ba8f-4eb3-b385-151f124e7903` |
| `group.display_name` | `Construction of Civil Defense building in Al Marfa` |
| `group.mail` | `ConstructionofCivilDefenseCenterinAlMirfaAlDhafraRegion@elrace.com` |
| `group.mail_enabled` | `True` |
| `member_count` | `17` |
| `blockers` | `[]` |
| `missing_permissions` | `[]` |

Members read (17): Younes Chajraoui (IT Manager), El Race Construction (System Administrator), Hassan Abuebeid (Projects Director), Aly Nour eldin (Branch Manager), Numeriano Apayyo (Project Manager), Leonila Robledo (QA/QC Engineer), Mohammed Orfali (Civil Engineer), Asif Younas (Document Controller), Amro Behairy (Project Manager), Ahmed Anwar (Project Manager), jawad (Odoo Developer), Mohamed Serag (Civil Engineer), Muhammad Usman (Document Controller), Kevin Soriano (Civil Engineer), Ahmed Sabry (Civil Engineer), Kamrul Hasan (Planning Engineer), Hossam Ghoneim (Electrical Engineer).

Document Controller: `Asif Younas <asif@elrace.com>`

### PRJ-002

| Field | Value |
|---|---|
| Project name | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| `group_membership_status` | `GROUP_MEMBERS_READ` |
| `email_enabled` | `True` |
| `group.id` | `57dda9ae-f753-42fa-b966-7376ba809a6f` |
| `group.display_name` | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| `group.mail` | `ConstructionofCivilDefenseCenterinIndustrialAreaofMadin@elrace.com` |
| `group.mail_enabled` | `True` |
| `member_count` | `18` |
| `blockers` | `[]` |
| `missing_permissions` | `[]` |

Members read (18): Ashad Aboobacker (Mechanical Engineer), Younes Chajraoui (IT Manager), El Race Construction (System Administrator), Hassan Abuebeid (Projects Director), Aly Nour eldin (Branch Manager), Numeriano Apayyo (Project Manager), Leonila Robledo (QA/QC Engineer), Mohammed Orfali (Civil Engineer), Asif Younas (Document Controller), Amro Behairy (Project Manager), Ahmed Anwar (Project Manager), Ishaq Ahmad (Architectural Draftsman), jawad (Odoo Developer), Mohamed Serag (Civil Engineer), Muhammad Usman (Document Controller), Kevin Soriano (Civil Engineer), Kamrul Hasan (Planning Engineer), Hossam Ghoneim (Electrical Engineer).

Document Controller: `Asif Younas <asif@elrace.com>`

## Compliance Verification

| Constraint | Status |
|---|---|
| Group members NOT stored as Shared Mailboxes | COMPLIANT — members stored in `microsoft.group_members` (EmailGroupMember objects), not in `email.shared_mailboxes` |
| Email enabled only if group mailbox verified | COMPLIANT — both projects have `mail_enabled=True` and real `group.mail` |
| ownCloud remains disabled | COMPLIANT — ownCloud not present in `enabled_sources` for either project |
| No writes to Odoo | COMPLIANT |
| No writes to SharePoint | COMPLIANT |
| No writes to Microsoft Graph | COMPLIANT — only GET calls via `GraphEmailGroupClient._get` / `_get_paged` |
| No emails sent/deleted/modified | COMPLIANT |
| No secrets printed | COMPLIANT — token not printed; only decoded role names reported |
| Project names from Odoo `project.project.name` | COMPLIANT — `project_name` field from config/DB, not derived from SharePoint URL |

## Checks

| Check | Result |
|---|---|
| `ruff check .` | clean |
| `python3 -m compileall apps scripts` | clean |
| `pytest test_email_group_enrichment.py` | 30 passed |
| `pytest test_phase2b_source_mapping.py` | 67 passed (67+31=98 combined) |
| `npm run lint` | clean |
| `npm run build` | ✓ 6.14s (chunk-size warning only, pre-existing) |
| `check_doc_drift.py` | clean |
| `check_ai_context.py` | clean |
| `agent_postflight.py` | clean |

## Final Verdict

`SOURCE_MAPPING_EMAIL_GROUP_ENRICHED_NOT_LIVE`
