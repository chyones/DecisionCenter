# Odoo Source Map — automatic batched deep scan (2026-06-17)

## Problem
`Scan Odoo Sources` ran every Odoo source in **one synchronous request**. With
20+ sources, each hitting the n8n → Odoo webhook, that single request could run
past the 120 s reverse-proxy timeout and fail wholesale.

## Fix (read-only; no report-gen / AI / SharePoint / Email / registry changes)
The scan now runs as a **background scan session**:

- `POST …/odoo-source-map/scan` starts a session and **returns immediately** with
  the all-`pending` snapshot + a `scan_session_id`. No request holds the proxy
  open while Odoo is queried → the 120 s timeout is structurally impossible.
- The session processes sources **one at a time, fully isolated** (one slow/failing
  source never blocks or aborts the rest), in small batches:
  - **`search_count`** for the exact total (one cheap call) when the deployed
    workflow supports it;
  - a **bounded sample** read in `≤ page_size` (100) `offset` batches up to
    `sample_target` (300) — a whole large table is never read in one call;
  - legacy fallback (workflow without count): one safe page, marked `capped`.
- **Strict timeouts**: per-batch (`odoo_scan_batch_timeout_s`, default 20 s) and
  per-source (`odoo_scan_source_timeout_s`, default 45 s).
- Per-source result: status ∈ {pending, running, completed, partial, capped,
  empty, failed, timeout, unmapped} + count, total, capped/complete flags, error,
  duration, last-scanned, pages.
- Snapshots persisted to `odoo_scan_sessions` after every source → the UI polls
  `GET …/scan/{session_id}` for live progress, `GET …/odoo-source-map` merges the
  latest scan on reload, and `POST …/scan/{session_id}/retry?mode=failed|incomplete`
  re-runs only the selected sources (completed ones are never re-scanned).
- Scope is taken **only** from the project's saved mapping (Odoo project id +
  analytic account id) via the denylist-safe `build_source_query`; unmapped
  sources are never queried; denylisted paths are never queried; no PRJ-001/002
  ids are hardcoded.

n8n `odoo_read` workflow gains an **additive** `operation:"count"` (search_count)
and honours `offset` (backward compatible — the report-generation path sends
neither and is unchanged). Deploying it unlocks *exact* totals; until then the
scan degrades to a capped single page (still no timeout).

## Live proof — real PRJ-001 scan (this is not a simulation)
Run against the live n8n + Odoo + Postgres with the **deployed** (no-count yet)
workflow, so `search_count` returned None → legacy real single-page reads.
Scope read from the saved mapping: `project_external_id=14602`,
`analytic_account_id=21963`.

Config: `page_size=100, sample_target=300, batch_timeout_s=10, source_timeout_s=20`.

Result: **overall = partial** (NOT failed) in **246 s wall**, progress
`completed=2, capped=14, empty=2, failed=1, timeout=3, total=22` —
**18/22 sources returned real data**:

```
project_identity        completed count=1
analytic_identity       completed count=1
actual_cost             capped    count=100
account_move_lines      capped    count=100
vendor_bills            capped    count=100
purchase_orders         capped    count=100
purchase_order_lines    capped    count=100
material_requests       capped    count=100
material_request_lines  capped    count=100
mr_analysis_links       empty     count=0
stock_pickings          capped    count=100
stock_moves             capped    count=100
hr_expenses             capped    count=100
payroll_headers         capped    count=100
payroll_cost_allocation capped    count=100
payslip_inputs          capped    count=100
worked_days             capped    count=100
staff_employees         empty     count=0
payroll_lines           timeout   (search_count probe > 10s)
staff_list              failed    (Odoo returned HTTP 502 Bad Gateway)
project_attachments     timeout   (search_count probe > 10s)
po_rfq_attachments      timeout   (search_count probe > 10s)
```

`capped=100` reflects the deployed workflow having no `search_count`; once the
enhanced workflow is deployed these become exact `completed` totals.

### Failed / timeout sources are isolated and explained
`payroll_lines`, `staff_list`, `project_attachments`, `po_rfq_attachments`.
They did **not** affect the other 18. Causes: genuinely slow Odoo models whose
*probe* exceeded the tightened 10 s proof timeout (production default is 20 s),
in degraded double-call mode (count-probe + read); `staff_list` returned a real
Odoo **502**. `po_rfq_attachments` is a known audit-discrepancy source. With the
deployed `search_count` workflow (a single cheap call) + the 20 s default, these
are expected to resolve.

### Retry failed works
`select_retry_keys(mode=failed)` → exactly the 4 failed sources. Retry re-ran
**only** those 4; `non-retried sources changed: none (completed sources
untouched)`. They remained timeout because the underlying Odoo endpoints are
still slow/erroring (real infra), proving isolation rather than an engine fault.

### Persistence / reload works
A fresh `PostgresStore` read the latest persisted snapshot; `build_source_map`
merged it (= what `GET …/odoo-source-map` returns after a page reload):
`22 sources carry a scan status; 18 carry a record_count` — persisted counts
survive reload. Throwaway proof rows were deleted afterward.

## Tests
- Engine `test_odoo_scan_session.py` (14): large-source offset batching, very-large
  via count, empty, per-batch timeout, slow-source-doesn't-block-others, partial,
  legacy cap, retry-only-failed, no-broad-unscoped-query, denylist-not-queried,
  unmapped-not-queried, no-PRJ-hardcode, snapshot round-trip, retry modes.
- API `test_odoo_source_map_api.py`: async-start contract, 404 status, admin gate.
- Isolation: `conftest.py` pins `ODOO_EXTENDED_SOURCES_ENABLED=false` (+ llm
  provider) so the suite is deterministic regardless of the host `.env`.
- Full non-live suite: **824 passed, 1 failed** — the single failure
  (`test_evaluation.py::test_runner_threshold_exit_non_zero`) is a pre-existing
  *offline-sandbox* failure (DNS name-resolution to a live service), unrelated to
  this change and to the extended-sources flag.
- Frontend vitest 22 passed; eslint + tsc clean; backend ruff clean.

## Not a go-live statement
Implemented + tested, **not deployed**. Operator must rebuild the frontend `dist`,
rebuild the `app` container, and redeploy the n8n `odoo_read` workflow (the last
unlocks exact totals). Do not rebuild the frontend alone — it would call endpoints
the currently-running `app` lacks.
