# Project Display Names Fixed from SharePoint — Implementation Evidence

**Verdict:** `PROJECT_DISPLAY_NAMES_FIXED_FROM_SHAREPOINT_NOT_LIVE`
**Date:** 2026-06-05
**Timestamp (UTC):** 2026-06-05T06:30:00Z
**HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
**Branch:** `main`
**Production status:** NOT_LIVE

---

## 1. Objective

Replace all user-facing occurrences of fixture project identifiers (`PRJ-001`, `PRJ-002`) with
the verified SharePoint-derived business project names. Internal keys (`project_code`) are
preserved for code routing — only user-visible display is updated.

---

## 2. Files Inspected

| File | Usage found |
|------|------------|
| `docs/config/project_source_mapping.json` | `project_code: PRJ-001 / PRJ-002`; no `display_name` |
| `apps/edr/rbac/project_mapping.py` | Loads JSON; `project_code` used as primary key |
| `apps/edr/persistence/postgres_store.py` | `_seed_source_mappings`; `project_name` column never seeded from JSON |
| `apps/edr/app.py` | `WorkspaceProject` had no `project_name`; `ReportSummary` / `ReportContentResponse` had no `project_name` |
| `frontend/src/api/types.ts` | `WorkspaceProject` had no `project_name` field |
| `frontend/src/screens/QueryComposerScreen.tsx` | `{p.project_code}` in dropdown — user-facing |
| `frontend/src/screens/AdminSourceMappingScreen.tsx` | `{m.project_code}` in sidebar — admin-facing |
| `frontend/src/screens/ReportsListScreen.tsx` | `{report.project_code}` in table — user-facing |
| `frontend/src/screens/ReportViewScreen.tsx` | `{report.project_code}` in header — user-facing |
| `frontend/src/screens/AdminApprovalQueueScreen.tsx` | `{item.project_code}` — admin tool, not changed |
| `frontend/src/screens/AdminDashboardScreen.tsx` | `{ev.project_code}` — admin tool, not changed |
| `frontend/src/screens/AdminAuditLogScreen.tsx` | `{ev.project_code}` — admin tool, not changed |
| `apps/edr/tests/integration/test_*.py` | PRJ-001/PRJ-002 as fixture keys — test-internal, not changed |
| `docs/evidence/uat/` | Historical evidence references — not changed |
| `docs/design/UI_CONTRACT_v1.md` | Design doc reference — not changed |
| `docs/config/project_source_mapping.example.json` | Example file — not changed |

---

## 3. Usage Classification

| Location | Classification | Action |
|---------|---------------|--------|
| `QueryComposerScreen.tsx` dropdown | **User-facing** | Fixed |
| `ReportsListScreen.tsx` project column | **User-facing** | Fixed |
| `ReportViewScreen.tsx` project label | **User-facing** | Fixed |
| `AdminSourceMappingScreen.tsx` sidebar | **Admin-facing** | Fixed (name as primary, code as sub-label) |
| `AdminApprovalQueueScreen.tsx` | Admin tool | Not changed (code appropriate for admin) |
| `AdminDashboardScreen.tsx` | Admin tool | Not changed |
| `AdminAuditLogScreen.tsx` | Admin tool | Not changed |
| `project_code` field in DB rows | Internal routing key | Preserved unchanged |
| `project_code` in API payloads | Internal key in requests | Preserved unchanged |
| Test fixtures (`_REAL_SITE_ROW`, etc.) | Test-internal fixture | Not changed; clearly marked test data |
| Historical evidence files | Historical records | Not changed per hard restrictions |
| `project_source_mapping.example.json` | Example/template | Not changed |
| `docs/design/` | Design docs | Not changed |

---

## 4. Display Names — Before and After

### Al Mirfa Project (PRJ-001)

| Context | Before | After |
|---------|--------|-------|
| QueryComposerScreen dropdown | `PRJ-001` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type "D". CD Al Mirfa – D` |
| ReportsListScreen project column | `PRJ-001` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type "D". CD Al Mirfa – D` |
| ReportViewScreen project label | `PRJ-001` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type "D". CD Al Mirfa – D` |
| AdminSourceMappingScreen sidebar | `PRJ-001` (primary) | Name as primary + `PRJ-001` as sub-label |
| DB `project_name` column | `''` (empty) | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type "D". CD Al Mirfa – D` (migrated on next `init_schema`) |
| Internal `project_code` key | `PRJ-001` | `PRJ-001` (unchanged) |

### Madinat Zayed Project (PRJ-002)

| Context | Before | After |
|---------|--------|-------|
| QueryComposerScreen dropdown | `PRJ-002` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type "D". CD Madinat Zayed – D` |
| ReportsListScreen project column | `PRJ-002` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type "D". CD Madinat Zayed – D` |
| ReportViewScreen project label | `PRJ-002` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type "D". CD Madinat Zayed – D` |
| AdminSourceMappingScreen sidebar | `PRJ-002` (primary) | Name as primary + `PRJ-002` as sub-label |
| DB `project_name` column | `''` (empty) | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type "D". CD Madinat Zayed – D` (migrated) |
| Internal `project_code` key | `PRJ-002` | `PRJ-002` (unchanged) |

---

## 5. Files Changed

| File | Change |
|------|--------|
| `docs/config/project_source_mapping.json` | Added `display_name`, `sharepoint_aliases`, `mapping_status_gate`, `mapping_method` to both entries |
| `apps/edr/persistence/postgres_store.py` | `_seed_source_mappings` now reads `display_name` as `project_name`; added `_migrate_project_names` that back-fills empty `project_name` rows on `init_schema` |
| `apps/edr/app.py` | `WorkspaceProject.project_name` added; `get_workspace_context` passes `display_name`; `ReportSummary.project_name` added; `ReportContentResponse.project_name` added; `list_reports` and report content endpoint now look up and include `project_name` |
| `frontend/src/api/types.ts` | `project_name: string` added to `WorkspaceProject`; `project_name?: string \| null` added to `ReportSummary` and `ReportContentResponse` |
| `frontend/src/screens/QueryComposerScreen.tsx` | Dropdown option now shows `p.project_name \|\| p.project_code` |
| `frontend/src/screens/AdminSourceMappingScreen.tsx` | Sidebar now shows project name as primary label + code as sub-label |
| `frontend/src/screens/ReportsListScreen.tsx` | Project column now shows `report.project_name \|\| report.project_code` |
| `frontend/src/screens/ReportViewScreen.tsx` | Project label now shows `report.project_name \|\| report.project_code` |

---

## 6. SharePoint site_id and drive_id Preserved

| Field | PRJ-001 | PRJ-002 |
|-------|---------|---------|
| `sharepoint.site_id` | `elrace.sharepoint.com,a505675a-...` | `elrace.sharepoint.com,52b8cba7-...` | 
| `sharepoint.drive_id` | `b!WmcFpV3Rg...` | `b!p8u4UiNk9...` |

Values are unchanged from Gate 3 confirmation. No SharePoint, Odoo, or Microsoft writes performed.

---

## 7. Internal Key Structure

`project_code` (`PRJ-001`, `PRJ-002`) remains the internal routing key throughout:
- DB primary key: `source_mappings.project_code`
- API request payloads: `project_code` field
- `ProjectMapping.get(code)` lookup
- URL path parameters: `/admin/source-mappings/{code}`
- Internal logs and audit events

`display_name` / `project_name` is the user-visible string only. The two are never conflated.

---

## 8. DB Migration

`_migrate_project_names` (idempotent, runs inside `init_schema`):
```sql
UPDATE source_mappings
SET project_name = $2
WHERE project_code = $1 AND project_name = ''
```
Only updates rows with empty `project_name`. Safe to run multiple times.

---

## 9. Recommended Mapping Structure — Applied

| Field added to JSON | PRJ-001 value | PRJ-002 value |
|--------------------|---------------|---------------|
| `display_name` | `Construction of Civil Defense Center in Al Mirfa…` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed…` |
| `sharepoint_aliases[0]` | `CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `CivilDefenseCenterinIndustrialAreaofMadinatZayed` |
| `sharepoint_aliases[1]` | `CD Al Mirfa – D` | `CD Madinat Zayed – D` |
| `sharepoint_aliases[2]` | full display name | full display name |
| `mapping_status_gate` | `SHAREPOINT_VERIFIED` | `SHAREPOINT_VERIFIED` |
| `mapping_method` | `VERIFIED_MICROSOFT_GRAPH_GATE_3` | `VERIFIED_MICROSOFT_GRAPH_GATE_3` |

---

## 10. Test Coverage

| Suite | Tests | Result |
|-------|-------|--------|
| `test_phase2b_source_mapping.py` | 53 | All passed |
| `test_phase2b_approvals.py` | ~40 | All passed |
| `test_phase2b_audit.py` | ~40 | All passed |
| `test_phase2b_dashboard.py` | ~40 | All passed |
| `test_rbac.py` | ~40 | All passed |
| `test_microsoft_rescan.py` | 37 | All passed |
| `test_connectors.py` | 25 | All passed |
| `test_phase1*.py` | 82 | All passed |

Tests that reference `PRJ-001` / `PRJ-002` remain unchanged — they use these as fixture keys
(internal routing codes), not as user-facing display strings.

---

## 11. Static Analysis

```
ruff check .               → All checks passed
python3 -m compileall apps scripts → Clean
check_doc_drift.py         → Documentation drift check: clean
check_ai_context.py        → AI context check: clean
agent_postflight.py        → Post-flight: clean
npm run lint               → No errors
npm run build              → ✓ built in 8.62s (TypeScript clean)
```

---

## 12. Confirmation

| Item | Status |
|------|--------|
| SharePoint site_id preserved | **CONFIRMED** — values unchanged |
| SharePoint drive_id preserved | **CONFIRMED** — values unchanged |
| No SharePoint writes | **CONFIRMED** — no Graph API calls made |
| No Odoo writes | **CONFIRMED** |
| No Microsoft user/mail writes | **CONFIRMED** |
| Gate 4 still separate | **CONFIRMED** — mailbox placeholders untouched |
| Production NOT_LIVE | **CONFIRMED** |

---

## 13. Where PRJ-001 / PRJ-002 Still Remain

| Location | Reason | Exposure |
|---------|--------|---------|
| `project_code` field in DB and API | Internal routing key | Hidden from UI |
| URL path: `/admin/source-mappings/PRJ-001` | REST resource identifier | Admin only |
| Audit events: `project_code=PRJ-001` | Audit trail key | Admin/auditor only |
| Test fixtures | Test-internal data | Not in production |
| Historical evidence files | Historical records | Not active UI |
| `project_source_mapping.example.json` | Example template | Not in production |
| `owncloud.base_path`, `sharepoint.root_path` | Path metadata | Not displayed in UI |
| `odoo.project_external_id` | Odoo integration key | Not changed per restrictions |

---

## 14. Production Readiness

| Item | Status |
|------|--------|
| Backend endpoints | NOT_LIVE (pending app rebuild) |
| DB migration (`_migrate_project_names`) | NOT_LIVE (runs on next `init_schema`) |
| Frontend build | NOT_LIVE (pending npm build + deploy) |

Production remains NOT_LIVE.

---

## 15. Final Verdict

```
PROJECT_DISPLAY_NAMES_FIXED_FROM_SHAREPOINT_NOT_LIVE
```

All user-facing screens now display the verified SharePoint business project names instead of
fixture identifiers `PRJ-001` / `PRJ-002`. Internal routing keys are preserved unchanged.
SharePoint IDs from Gate 3 are unmodified. Gate 4 (mail) is unaffected. No writes were made
to SharePoint, Odoo, or any Microsoft service.

---

*Evidence generated by Claude Code — 2026-06-05*
