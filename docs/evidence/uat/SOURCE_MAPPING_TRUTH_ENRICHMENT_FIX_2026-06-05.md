# Source Mapping Truth Enrichment Fix

**Verdict:** `SOURCE_MAPPING_TRUTH_ENRICHMENT_FIXED_NOT_LIVE`
**Date:** 2026-06-05
**Production status:** `NOT_LIVE`
**Scope:** `PRJ-001` and `PRJ-002` only

This fix converts `PRJ-001` and `PRJ-002` back to internal routing codes only.
Project names now come from verified Odoo `project.project.name` values, not
from SharePoint URL slugs, SharePoint display names, or PRJ codes. No writes
were made to Odoo, SharePoint, Microsoft Graph, or mailboxes.

## Before And After

### PRJ-001

| Field | Before | After |
|---|---|---|
| Project name | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region - Type "D". CD Al Mirfa - D` | `Construction of Civil Defense building in Al Marfa` |
| Enabled sources | `sharepoint`, `owncloud`, `email`, `odoo` | `odoo`, `sharepoint` |
| SharePoint | `example-site-id-001`, `example-drive-id-001`, `/Projects/PRJ-001` | verified site id, verified drive id, `/` |
| ownCloud | `/Projects/PRJ-001` | disabled, empty path |
| Email | `project-prj-001@example.com`, `doc-control@example.com` | disabled, empty mailboxes/domains |
| Odoo external id | `PRJ-001` | `14602` |
| Odoo project name | empty | `Construction of Civil Defense building in Al Marfa` |
| Analytic account id | missing | `21963` |
| Cost model | `account.analytic.line` | `account.analytic.line` |
| Project manager | missing | `Ahmad Ezzat Anwar` |

### PRJ-002

| Field | Before | After |
|---|---|---|
| Project name | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region - Type "D". CD Madinat Zayed - D` | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| Enabled sources | `sharepoint`, `owncloud`, `email`, `odoo` | `odoo`, `sharepoint` |
| SharePoint | `example-site-id-002`, `example-drive-id-002`, `/Projects/PRJ-002` | verified site id, verified drive id, `/` |
| ownCloud | `/Projects/PRJ-002` | disabled, empty path |
| Email | `project-prj-002@example.com`, `doc-control-002@example.com` | disabled, empty mailboxes/domains |
| Odoo external id | `PRJ-002` | `14601` |
| Odoo project name | empty | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| Analytic account id | missing | `21960` |
| Cost model | `account.analytic.line` | `account.analytic.line` |
| Project manager | missing | `Ahmad Ezzat Anwar` |

## Removed Placeholders

Removed from both checked-in config and runtime `source_mappings` rows:

- `example-site-id-*`
- `example-drive-id-*`
- `/Projects/PRJ-*`
- `project-prj-*@example.com`
- `doc-control*@example.com`
- Odoo external ids `PRJ-001` and `PRJ-002`
- unverified `CON-*` contract placeholders

## Disabled Sources

For both PRJ rows:

- `owncloud` is disabled because ownCloud coordinates are not verified.
- `email` is disabled because no real shared mailbox, document-control mailbox,
  or domain mapping has been provided and validated.
- `enabled_sources` is now exactly `["odoo", "sharepoint"]`.

## Validation Blockers

The backend and UI now block `complete` status when a mapping contains:

- `example-*`
- `example.com`
- `/Projects/PRJ-*`
- `PRJ-*` as Odoo external id
- enabled ownCloud while ownCloud is not configured
- enabled Email without a real mailbox/domain
- enabled SharePoint without real `site_id` and `drive_id`
- enabled Odoo without numeric Odoo project id and matching Odoo project name

Known remaining non-enabled missing source fields for both rows:

- Commercial Manager: `MISSING_SOURCE_FIELD`
- Finance Owner: `MISSING_SOURCE_FIELD`
- Document Controller: `MISSING_SOURCE_FIELD`
- Email mailboxes/domains: `MISSING_SOURCE_FIELD`
- ownCloud coordinates: `MISSING_SOURCE_FIELD`

These fields were left empty. No people, mailboxes, or document-control
addresses were invented.

## Implementation Notes

- Existing `PRJ-001` and `PRJ-002` rows are updated in place; no separate
  `odoo-*` rows were created for these mappings.
- `docs/config/project_source_mapping.json` now stores the verified Odoo names,
  numeric Odoo project ids, analytic account ids, SharePoint site ids, and
  SharePoint drive ids.
- `PostgresStore.init_schema()` now idempotently repairs the two verified PRJ
  rows from the config file.
- Admin Source Mapping list/detail responses recompute status from the guard so
  stale `complete` values do not display as complete when blockers exist.
- Node 08 and Node 11 use the mapped Odoo project id when available, while still
  JSON-encoding the domain safely.
- Odoo + SharePoint sync tests assert Odoo uses `search_read` only and Graph
  helper uses GET only.

## Verification

Commands run:

| Command | Result |
|---|---|
| `ruff check .` | passed |
| `python3 -m compileall apps scripts` | passed |
| `pytest apps/edr/tests/integration/test_phase2b_source_mapping.py -q` | `60 passed` |
| `pytest apps/edr/tests/integration/test_odoo_sharepoint_sync.py -q` | `32 passed` |
| `pytest apps/edr/tests/integration -q` | `665 passed, 3 skipped` inside Compose with repo mounted |
| `npm --prefix frontend run lint` | passed |
| `npm --prefix frontend run build` | passed; existing Vite chunk-size warning only |
| `python3 scripts/check_doc_drift.py` | passed |
| `python3 scripts/check_ai_context.py` | passed |
| `python3 scripts/agent_postflight.py --allow-no-evidence` | passed |

Runtime PostgreSQL rows were also updated in place for `PRJ-001` and `PRJ-002`
to match the checked-in truth mapping. The local `app` service was recreated
with the rebuilt image, and `/healthz` returned PostgreSQL, Redis, Qdrant, and
MinIO as `ok`. Production remains `NOT_LIVE`.
