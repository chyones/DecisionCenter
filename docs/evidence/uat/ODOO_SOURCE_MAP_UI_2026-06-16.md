# Odoo Source Map — UI Visibility (2026-06-16)

Adds read-only visibility of the Odoo Source Map to the Projects area so users can
see where DecisionCenter searches inside Odoo for each project. Built entirely from
the existing source registry — no project ids are hardcoded.

Scope honoured: report generation unchanged; AI providers unchanged; SharePoint and
Email unchanged; PRJ-001 / PRJ-002 are validation samples only (no special logic).
**No go-live claim. Production remains NOT_LIVE.**

## What was added

### Backend (built from the registry, never hardcoded)
- `apps/edr/connectors/odoo_sources.py` — display metadata on each `OdooSource`
  (`display_name`, `groups`, `gap_type`, `warning`), the 13 `DISPLAY_GROUPS`, and
  `source_map_entries()` / `denylisted_path_strings()` projections.
- `apps/edr/admin/odoo_source_map.py` — `build_source_map(...)` composes the generic
  registry + this project's **runtime** Odoo project id + analytic account id (read
  from the saved mapping). `scan_source_counts(...)` runs a **read-only** per-source
  record-count scan via the existing n8n Odoo webhook (reuses the proven,
  denylist-safe queries; one source failing never aborts the others).
- `apps/edr/app.py` — two admin-gated endpoints:
  - `GET  /admin/source-mappings/{code}/odoo-source-map` — the map (no counts).
  - `POST /admin/source-mappings/{code}/odoo-source-map/scan` — read-only scan; emits
    an `admin.odoo_source_map_scan` audit event before the scan; returns the map with
    counts merged.

### Frontend
- `frontend/src/screens/OdooSourceMapPanel.tsx` — presentational panel.
- `frontend/src/screens/odooSourceMap.ts` — pure grouping/labelling helpers.
- `frontend/src/screens/AdminSourceMappingScreen.tsx` — adds a **Mapping | Odoo Source
  Map** tab in the project editor column. The three existing header actions remain:
  Enrich Email Groups, Sync Odoo + SharePoint, Rescan Microsoft Sources.
- API types added (`OdooSourceMapEntry`, `OdooSourceMapResponse`).

## What the UI shows (per selected project)

Odoo project id · analytic account id · project source status · enabled Odoo source
categories · and, for each of the 22 registry sources: source name, Odoo model,
project-link path, key fields, confidence, gap type, last scan status, record count
(after scan, capped@100 shown as `N+`), and any warning. Plus: generic-map notice,
"PRJ-001/002 are not fixed logic", missing/disabled sources, connector gaps, and the
9 ambiguous/denylisted paths that are never queried.

Required source groups present (13): Project identity, Contract value, Actual cost,
Accounting / journal lines, Vendor bills, RFQ / LPO / PO, Purchase lines, Material
requests, Stock / deliveries, HR expenses, Payroll, Manpower / staff, Attachments.

## Tests

- Backend: `apps/edr/tests/integration/test_odoo_source_map_api.py` — 20 tests
  (generic builder = 22 sources / 13 groups / 9 denylisted; runtime ids not hardcoded;
  unmappable when analytic id missing / Odoo disabled; scan merge + cap + isolation;
  endpoint admin-gate + 404 + audit-before-scan).
- Frontend: vitest + @testing-library added (`vitest.config.ts`, `src/test/setup.ts`,
  `npm test`). `odooSourceMap.test.ts` (helpers) + `OdooSourceMapPanel.test.tsx`
  (rendering) — 17 tests: renders 13 groups, 9 denylisted paths, runtime ids (no
  14602/21963 leakage), record counts after scan with `100+`, warnings/gaps,
  missing-sources, scan button enable/disable.

All backend (132 in the touched area) and frontend (17) tests pass; ruff, doc-drift,
ai-context, tsc, and `npm run build` clean.

## Operator note

Live counts require the deployed n8n Odoo workflow; counts are capped by its
`search_read` limit until the structured workflow is deployed. The scan is read-only.
