# Project Source Mapping Exact Sync — Implementation Evidence

**Verdict:** `PROJECT_SOURCE_MAPPING_EXACT_SYNC_IMPLEMENTED_NOT_LIVE`
**Date:** 2026-06-05
**Timestamp (UTC):** 2026-06-05T12:00:00Z
**HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
**Branch:** `main`
**Production status:** NOT_LIVE

---

## 1. Objective

Implement automatic Project Source Mapping Sync based on exact Odoo main project name
↔ SharePoint site displayName matching. The sync is read-only: it reads Odoo projects
via XML-RPC and SharePoint sites via Microsoft Graph, then auto-saves confirmed 1:1
exact matches to `source_mappings` without writing to Odoo or SharePoint.

---

## 2. Matching Rule

| Rule | Detail |
|------|--------|
| Algorithm | Exact equality after normalization (100% match only) |
| Normalization | NFC unicode compose, trim whitespace, collapse repeated spaces, curly quotes → straight, em/en/figure dashes → hyphen |
| Case | Case-sensitive (no case folding) |
| Fuzzy | Disabled (no token scoring, no partial match, no Levenshtein) |
| Field | `odoo_project.name` (main name only) vs `sharepoint_site.displayName` |

---

## 3. Files Changed / Created

| File | Type | Description |
|------|------|-------------|
| `apps/edr/admin/odoo_sharepoint_sync.py` | NEW | Sync engine: Odoo XML-RPC + Graph enumeration + exact match + member pull |
| `apps/edr/persistence/postgres_store.py` | MOD | Added `list_source_mappings_full()` for sync engine |
| `apps/edr/app.py` | MOD | Added `POST /admin/source-mappings/sync-odoo-sharepoint` endpoint |
| `frontend/src/api/types.ts` | MOD | Added `OdooSitePairResult`, `OdooSharePointSyncResult` types |
| `frontend/src/api/index.ts` | MOD | Re-exported new types from module index |
| `frontend/src/screens/AdminSourceMappingScreen.tsx` | MOD | Added "Sync Odoo + SharePoint" button + `OdooSyncPanel` modal |
| `apps/edr/tests/integration/test_odoo_sharepoint_sync.py` | NEW | 30 integration tests for sync engine, endpoint RBAC, auto-save logic |

---

## 4. Sync Engine Design

### Odoo Data Pull
- Protocol: Python `xmlrpc.client` (built-in), wrapped in `asyncio.to_thread()`
- Endpoint: `/xmlrpc/2/common` (auth) + `/xmlrpc/2/object` (execute_kw)
- Model: `project.project`
- Filter: `[('active', '=', True)]`
- Fields: `['id', 'name']` only — no emails, no followers, no partner_id
- Credentials: `settings.odoo_url`, `settings.odoo_database`, `settings.odoo_user`, `settings.odoo_password`

### SharePoint Data Pull
- Protocol: Microsoft Graph REST API via `get_graph_token()` (existing token helper)
- Site enumeration: `GET /sites?search=*&$top=200` with pagination
- Drive discovery: `GET /sites/{id}/drives` → first drive's id
- Member pull: `GET /sites/{id}/permissions` → `grantedToV2.user.email` or `grantedToV2.siteUser.email`
- Required permission: `Sites.Read.All` (already granted in Gate 2)
- No writes to Microsoft Graph

### Auto-Save Conditions

A matched pair is auto-saved only when ALL of the following are true:
1. Exactly one Odoo project normalizes to the same name as exactly one SharePoint site
2. `site_id` is non-empty
3. `drive_id` is non-None (drive found)
4. The site's `site_id` is NOT already held by a `mapping_status='complete'` row

If any condition fails, `auto_saved=False` and `save_skipped_reason` is populated.

### Storage Fields
| DB column / JSONB key | Value |
|---|---|
| `project_code` | `odoo-<odoo_project_id>` |
| `project_name` | Odoo project main name |
| `sharepoint.site_id` | Graph site id |
| `sharepoint.drive_id` | Graph drive id |
| `sharepoint.root_path` | `/` |
| `sharepoint.web_url` | Site URL |
| `sharepoint.site_name` | Site hostname slug |
| `sharepoint.display_name` | SharePoint `displayName` |
| `email.shared_mailboxes` | SharePoint member emails (from permissions only) |
| `odoo.project_external_id` | str(odoo_project_id) |
| `odoo.mapping_method` | `ODOO_MAIN_NAME_EQUALS_SHAREPOINT_SITE_NAME` |
| `odoo.match_confidence` | `100` |
| `odoo.internal_key` | `odoo-<odoo_project_id>` |
| `mapping_status` | `complete` |
| `enabled_sources` | `["sharepoint", "odoo"]` |

---

## 5. Hard Restrictions — All Confirmed

| Restriction | Status |
|---|---|
| Do not modify Odoo | CONFIRMED — XML-RPC `search_read` only |
| Do not modify SharePoint | CONFIRMED — no Graph writes |
| Do not write to Microsoft Graph | CONFIRMED — read-only Graph calls only |
| Do not use Odoo emails | CONFIRMED — `odoo_emails_used=False` always; only `id` and `name` read |
| Do not use Odoo followers | CONFIRMED — `odoo_followers_used=False` always; not read |
| Do not use fuzzy matching | CONFIRMED — exact normalized equality only |
| Do not expose PRJ as business name | CONFIRMED — new auto-saved mappings use `odoo-<id>` keys; PRJ-00x rows unchanged |
| Do not touch mailbox placeholders | CONFIRMED — `shared_mailboxes` in existing mappings not modified |
| Do not start Gate 4, Gate 5, UAT, Slice 7 | CONFIRMED — not started |
| Do not mark LIVE | CONFIRMED — production status remains NOT_LIVE |
| Do not print secrets/tokens | CONFIRMED — no credentials logged or returned |

---

## 6. Member Emails

- Source: SharePoint `GET /sites/{id}/permissions` only
- Format: `grantedToV2.user.email` or `grantedToV2.siteUser.email`
- Odoo emails: NOT used (hard restriction)
- Odoo followers: NOT used (hard restriction)
- If permissions read fails (403): `member_read_status="PERMISSIONS_INSUFFICIENT"`, empty list stored; sync continues
- Per matched project: list stored in `email.shared_mailboxes` JSONB column

---

## 7. Existing MANUALLY_CONFIRMED Mappings — Protected

The sync engine reads all existing `source_mappings` rows via `list_source_mappings_full()`
before scanning. Any row with `mapping_status='complete'` contributes its `sharepoint.site_id`
to a `confirmed_site_ids` set. If an exact-matched site's `site_id` appears in this set,
`auto_saved=False` and `save_skipped_reason` explains which existing project_code owns it.

PRJ-001 and PRJ-002 (existing manually confirmed mappings) are therefore protected.

---

## 8. Frontend Changes

- **Button:** "Sync Odoo + SharePoint" added to AdminSourceMappingScreen header (alongside existing "Rescan Microsoft Sources")
- **Panel:** `OdooSyncPanel` modal shows:
  - Stats grid: Odoo projects scanned, SharePoint sites scanned, exact matches, no-match, multi-match, auto-saved
  - Matched pairs: Odoo name, internal key, SharePoint site, match confidence, member emails, auto-save result
  - Unmatched Odoo project names
  - Compliance badges: "Odoo emails: not used" (green), "Odoo followers: not used" (green)

---

## 9. Test Coverage

| Test | Result |
|---|---|
| `test_normalize_trim` | PASS |
| `test_normalize_collapse_spaces` | PASS |
| `test_normalize_curly_double_quotes` | PASS |
| `test_normalize_curly_single_quotes` | PASS |
| `test_normalize_en_dash` | PASS |
| `test_normalize_em_dash` | PASS |
| `test_normalize_nfc` | PASS |
| `test_normalize_idempotent` | PASS |
| `test_normalize_no_case_fold` | PASS |
| `test_match_exact_one_to_one` | PASS |
| `test_match_no_match` | PASS |
| `test_match_no_fuzzy` | PASS |
| `test_match_multi_match` | PASS |
| `test_match_normalization_quotes` | PASS |
| `test_match_case_sensitive` | PASS |
| `test_match_mixed_list` | PASS |
| `test_sync_blocked_when_odoo_not_configured` | PASS |
| `test_sync_blocked_when_graph_token_empty` | PASS |
| `test_sync_endpoint_admin_auto_saves` | PASS |
| `test_sync_endpoint_skips_when_site_already_confirmed` | PASS |
| `test_sync_result_never_uses_odoo_emails` | PASS |
| `test_sync_endpoint_rbac_denial[executive]` | PASS |
| `test_sync_endpoint_rbac_denial[project_manager]` | PASS |
| `test_sync_endpoint_rbac_denial[finance]` | PASS |
| `test_sync_endpoint_rbac_denial[commercial]` | PASS |
| `test_sync_endpoint_rbac_denial[document_control]` | PASS |
| `test_sync_endpoint_rbac_denial[procurement]` | PASS |
| `test_sync_endpoint_rbac_denial[legal]` | PASS |
| `test_sync_endpoint_rbac_denial[auditor]` | PASS |
| `test_sync_endpoint_missing_claims_401` | PASS |
| **Total** | **30/30 PASS** |

`test_phase2b_source_mapping.py` — 53/53 PASS (no regressions)

---

## 10. Static Analysis

```
ruff check .                      → All checks passed
python3 -m compileall apps scripts → Clean (no syntax errors)
check_doc_drift.py                 → Documentation drift check: clean
check_ai_context.py                → AI context check: clean
agent_postflight.py                → Post-flight: clean
npm --prefix frontend run lint     → No errors
npm --prefix frontend run build    → ✓ built in 9.30s (TypeScript clean)
```

---

## 11. Production Readiness

| Item | Status |
|---|---|
| Backend endpoint `POST /admin/source-mappings/sync-odoo-sharepoint` | NOT_LIVE (pending app rebuild) |
| `list_source_mappings_full()` in postgres_store | NOT_LIVE (pending app rebuild) |
| Frontend "Sync Odoo + SharePoint" button + panel | NOT_LIVE (pending npm build + deploy) |
| Test suite | All passing |
| Odoo credential availability | Pending (NOT_LIVE — see pending external access memory) |
| Graph token `Sites.Read.All` | Already granted (Gate 2 confirmed) |

Production remains NOT_LIVE.

---

## 12. Final Verdict

```
PROJECT_SOURCE_MAPPING_EXACT_SYNC_IMPLEMENTED_NOT_LIVE
```

The exact-name Odoo ↔ SharePoint sync engine is fully implemented:
- Read-only pull of Odoo active projects (id + name only)
- Read-only pull of SharePoint sites + drives + member permissions
- 100% exact normalized-name matching (no fuzzy)
- Auto-save of 1:1 exact matches with `internal_key=odoo-<id>`
- Protection of existing MANUALLY_CONFIRMED mappings
- RBAC guard (admin-only, 401/403 for all others)
- Frontend button + results panel with compliance badges
- 30 new integration tests + 53 existing source-mapping tests all passing
- Odoo emails: NOT used. Odoo followers: NOT used.
- No writes to Odoo, SharePoint, or Microsoft Graph.

---

*Evidence generated by Claude Code — 2026-06-05*
