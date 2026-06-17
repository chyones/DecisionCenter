# Phase close — Odoo Source Map automatic batched deep scan

| Field | Value |
|---|---|
| Branch | `feat/odoo-source-map-batched-scan` |
| Implementation commit | `b01e23b` |
| Phase-close commit | this document (added on the same branch) |
| Base | `main` @ `30748e8` (untouched) |
| Production status | **NOT_LIVE** (not deployed) |
| Merge performed | **No** |
| Deploy performed | **No** |

This document formally closes the batched-scan implementation phase. It records
what was built, how it was verified, what remains, and the operator steps that
are still required. No merge and no deployment were performed in this phase.

> **Post-merge update (2026-06-17, later):** the table above reflects the state at
> phase close (pre-PR). Since then this branch was **merged to `main` via PR #3**
> (merge commit `6f3d310`) and the repo was **consolidated to only `main`** (HEAD
> `a6a8226`; all feature branches deleted, docs(ai) continuity refreshed). The
> code is therefore in `main` but **production remains NOT_LIVE — the operator
> deploy is still pending** (rebuild `app` + frontend `dist` together, then
> redeploy the n8n `odoo_read` workflow for exact `search_count` totals). No
> deployment has been performed.

## What was implemented
Replaced the single synchronous Odoo Source Map scan (which ran ~22 sources in
one request and could exceed the 120 s reverse-proxy timeout) with a background,
resumable, batched scan session.

- **Engine** `apps/edr/admin/odoo_scan_session.py` — per-source isolated scan;
  `search_count` for exact totals; bounded sample paged in `≤100`-row `offset`
  batches (never a full-table read); strict per-batch + per-source timeouts;
  statuses `pending/running/completed/partial/capped/empty/failed/timeout/
  unmapped`; in-process session registry; retry/resume selection.
- **Endpoints** (`apps/edr/app.py`):
  - `POST /admin/source-mappings/{code}/odoo-source-map/scan` — starts a session
    and returns immediately (cannot hold the proxy request open).
  - `GET …/scan/{session_id}` — poll live progress + partial results.
  - `POST …/scan/{session_id}/retry?mode=failed|incomplete` — re-run only the
    selected sources; completed sources are never re-scanned.
  - `GET …/odoo-source-map` — merges the latest live/persisted scan so counts
    survive a page reload.
- **Connector** `apps/edr/connectors/odoo.py` — added `count_odoo()`
  (`operation:"count"`) + `offset` passthrough; `build_*_query` unchanged.
- **Persistence** — new `odoo_scan_sessions` table + save/get/get-latest on
  `PostgresStore` (idempotent `CREATE TABLE IF NOT EXISTS` in `init_schema`).
- **Config** `apps/edr/config.py` — scan tuning knobs (page size, sample target,
  per-batch/per-source timeouts, poll hint).
- **n8n** `n8n/odoo_read.json` — additive `operation:"count"` (search_count) +
  honour `offset`; backward compatible (report-generation path unchanged).
- **Frontend** — live progress bar + per-source status/duration/error and a
  "Retry failed (N)" action; `AdminSourceMappingScreen` polls until terminal.

Scope is taken **only** from each project's saved mapping (Odoo project id +
analytic account id); unmapped sources are never queried; denylisted paths are
never queried; no PRJ-001/PRJ-002 hardcoding. Read-only with respect to Odoo.

### Explicitly not changed
Report generation, AI providers, SharePoint, Email, and the generic Odoo source
registry were **not** changed.

## Review blockers fixed (pre-merge review)
1. **Background scan task could be garbage-collected mid-run.** `asyncio.create_task`
   was called without retaining the returned task; asyncio keeps only *weak*
   references to tasks, so a long scan could be cancelled by GC. Fixed in
   `apps/edr/app.py`: tasks are held in a module-level `_SCAN_TASKS` set and
   removed via `add_done_callback`. Locked by
   `test_launch_scan_task_holds_strong_reference_until_done`.
2. **UI poll could give up before a realistic slow scan finished.** The poll
   deadline in `AdminSourceMappingScreen.tsx` was 5 min; a full 22-source scan at
   production timeouts can run longer in degraded (no-`search_count`) mode. Raised
   to 15 min (server-side scan + persistence are unaffected; reload still merges
   the latest snapshot regardless).

Reviewed and found acceptable (no change needed): the n8n read response now
carries a `meta` field, but `validate_evidence_payload` ignores unknown keys, so
the shared read path used by report generation is unaffected; all Odoo queries
remain project/analytic-scoped and denylist-checked; the `odoo_scan_sessions`
table is created idempotently.

## Tests run (this phase close)
- Backend engine `test_odoo_scan_session.py` — **14 passed**.
- Source-map API `test_odoo_source_map_api.py` — **passed** (async-start contract,
  404 status, admin gate).
- Frontend `vitest` — **22 passed**.
- `ruff` (apps/edr) — clean. Frontend `tsc --noEmit` + `eslint` — clean.
- Earlier full non-live suite: **824 passed, 1 failed**. The single failure
  `test_evaluation.py::test_runner_threshold_exit_non_zero` is a pre-existing
  **offline-sandbox** failure (DNS name-resolution to a live service), unrelated
  to this branch and to the extended-sources flag.

### Test isolation
`apps/edr/tests/conftest.py` pins `odoo_extended_sources_enabled=False` per test
(same autouse pattern as `llm_provider`) so the suite is deterministic regardless
of the host `.env` (which sets the flag true). Opt-in tests set it explicitly.

## Realistic live scan proof (PRJ-001)
Real scan against live n8n + Odoo + Postgres, scope from the saved mapping
(`project 14602 / analytic 21963`), realistic timeouts (batch 10 s / source 20 s),
deployed workflow without `search_count` (→ legacy real single-page reads):
**overall = partial (not failed)** in 246 s, `completed=2, capped=14, empty=2,
failed=1, timeout=3` — **18/22 sources returned real data**. Retry re-ran only
the 4 failed sources (completed sources untouched). A fresh `PostgresStore`
re-read the latest snapshot and the rebuilt map carried 18 record counts
(persisted counts survive reload). Throwaway `proof-*` rows were deleted.

## Known remaining items
- `payroll_lines`, `staff_list` (returned a real Odoo HTTP 502),
  `project_attachments`, `po_rfq_attachments` were slow/erroring against live
  Odoo and timed out under the tightened 10 s proof timeout. They are isolated
  (did not affect the other 18). Expected to resolve under the production 20 s
  default once the `search_count` workflow is deployed (single cheap call instead
  of the degraded count-probe + read). `po_rfq_attachments` is a known
  audit-discrepancy source.
- Until the enhanced n8n workflow is deployed, totals are reported as `capped`
  (floor counts), not exact.

## Operator steps still required (NOT performed here)
1. Rebuild the frontend `dist`.
2. Rebuild the `app` container.
3. Redeploy the n8n `odoo_read` workflow (unlocks exact `search_count` totals).

⚠️ Do not rebuild the frontend alone — it would call endpoints the currently
running `app` lacks. Do not deploy from this branch until the PR is reviewed and
approved.

## Phase status
Implementation complete and verified on `feat/odoo-source-map-batched-scan`.
`main` untouched. Production **NOT_LIVE**. No merge, no deploy. Ready for PR review.
