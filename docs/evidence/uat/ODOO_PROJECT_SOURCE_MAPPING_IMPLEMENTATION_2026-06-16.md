# Odoo Project Source Mapping — Implementation Evidence (2026-06-16)

Implements the high-confidence mappings proven in
[`ODOO_PROJECT_SOURCE_MAPPING_DISCOVERY_2026-06-16.md`](ODOO_PROJECT_SOURCE_MAPPING_DISCOVERY_2026-06-16.md).
Read-only. No AI providers, SharePoint, or Email changed. Quality Gate untouched.
No production go-live claim.

## Guardrails honoured

- Read-only Odoo access only (search_read via the existing n8n `odoo_read` webhook).
- Only **high-confidence** proven mappings from the audit are queried (plus the two
  required medium staff sources, tagged `confidence=medium`).
- All audit **denylisted/ambiguous paths are actively rejected** at import and at
  query-build time — they can never be issued.
- Scope is enforced in the **backend connector** using the audit's proven project /
  analytic link paths (the audit allows enforcement "in the n8n workflow or backend
  connector").
- Extended retrieval is **opt-in** (`odoo_extended_sources_enabled`, default off), so
  the existing narrow project+cost flow and the Quality Gate are unchanged until an
  operator enables it.

## Files changed

| File | Change |
|---|---|
| `apps/edr/connectors/odoo_sources.py` | **New.** Frozen registry of 22 proven sources + 9-path denylist + `assert_path_allowed` guard (validated at import). |
| `apps/edr/connectors/odoo.py` | Added `build_source_query`, `build_all_source_queries`, `_resolve_link_value` (project vs analytic scope; injection-safe; `None` when unmappable). |
| `apps/edr/graph/node_08_odoo.py` | Added opt-in `_retrieve_extended_sources`; per-source counts/status in `state.outputs`; graceful per-source failure; financial gating unchanged. |
| `apps/edr/config.py` | Added `odoo_extended_sources_enabled` (default `False`) and `odoo_extended_include_medium` (default `True`). |
| `n8n/odoo_read.json` | Evidence mapping now also emits structured **flat** fields (`f_*`) so aggregation no longer relies on truncated excerpts. Backward-compatible. Env creds + bounded limit preserved. **Requires operator deploy** (not imported/deployed from the sandbox). |
| `apps/edr/tests/integration/test_odoo_extended_sources.py` | **New.** 30 tests: registry integrity, denylist enforcement, scope/injection-safety, node_08 behaviour. |
| `docs/ai/agent-state.json` | Governance anchor refreshed to keep drift within tolerance. |

## Odoo sources added (22; all 19 required categories)

`project` scope = `project.project` id (PRJ-001 14602 / PRJ-002 14601);
`analytic` scope = `account.analytic.account` id (PRJ-001 21963 / PRJ-002 21960).

| Key | Model | Proven link path | Scope | Conf |
|---|---|---|---|---|
| project_identity | project.project | `id` | project | high |
| analytic_identity | account.analytic.account | `id` | analytic | high |
| actual_cost | account.analytic.line | `account_id` | analytic | high |
| account_move_lines | account.move.line | `analytic_account_id` | analytic | high |
| vendor_bills | account.move | `line_ids.analytic_account_id` | analytic | high |
| purchase_orders | purchase.order | `project_id` (= analytic id) | analytic | high |
| purchase_order_lines | purchase.order.line | `account_analytic_id` | analytic | high |
| material_requests | material.purchase.requisition | `project_id` | project | high |
| material_request_lines | material.purchase.requisition.line | `requisition_id.project_id` | project | high |
| mr_analysis_links | material.purchase.requisition.analysis | `mr_id.project_id` | project | high |
| stock_pickings | stock.picking | `purchase_id.project_id` (= analytic id) | analytic | high |
| stock_moves | stock.move | `purchase_line_id.account_analytic_id` | analytic | high |
| hr_expenses | hr.expense | `project_id` | project | high |
| payroll_headers | hr.payslip | `project_id` | project | high |
| payroll_lines | hr.payslip.line | `slip_id.project_id` | project | high |
| payroll_cost_allocation | hr.payslip.cost.allocation | `project_id` (never `cost_center_id`) | project | high |
| payslip_inputs | hr.payslip.input | `payslip_id.project_id` | project | high |
| worked_days | hr.payslip.worked_days | `payslip_id.project_id` | project | high |
| staff_employees | hr.employee | `project_id` | project | medium |
| staff_list | staff.list | `project_id` | project | medium |
| project_attachments | project.attachment | `project_id` | project | high |
| po_rfq_attachments | ir.attachment | `lead_id_po.project_id` (= analytic id) | analytic | high |

## Denylisted / ambiguous paths (rejected by `assert_path_allowed`)

`purchase.order.project_id_mr` · `purchase.order.line.order_id.project_id_mr` ·
`stock.picking.purchase_id.project_id_mr` · `account.move.project` ·
`account.payment.project` · `sale.order.project_ids` · `fleet.vehicle.project_id` ·
`ir.attachment.mpr_id.project_id` · `hr.payslip.cost.allocation.cost_center_id`.

Every registry entry is checked against this set at import — a regression is a hard
import error, not a silent bad query.

## Exact fields retrieved per source

The field allowlist per source is defined in `apps/edr/connectors/odoo_sources.py`
(the `fields=(...)` tuple of each `OdooSource`). Highlights:

- **project.project**: name, project_code, wo_ref_no, **wo_amount** (contract value),
  estimation_amount, date_start, date, partner_id, analytic_account_id, project_status,
  department_id, user_id.
- **account.analytic.account**: name, code, project_ids, **balance, debit, credit**,
  partner_id, currency_id.
- **account.analytic.line**: name, **amount**, date, account_id, project_id, move_id,
  general_account_id, partner_id, employee_id, product_id, unit_amount, currency_id, ref.
- **account.move.line**: …, analytic_account_id, product_id, quantity, **price_subtotal,
  price_total, balance, debit, credit**, currency_id.
- **account.move**: name, ref, move_type, invoice_date, date, state, payment_state,
  partner_id, **amount_total, amount_residual**, currency_id.
- **purchase.order**: name, rfq_name, po_name, date_order, date_approve, state,
  partner_id, **amount_untaxed, amount_total**, invoice_count, picking_count, project_id.
- **purchase.order.line**: order_id, product_id, product_qty, **price_subtotal,
  price_total**, state, qty_received, qty_invoiced, account_analytic_id.
- **hr.expense**: name, date, employee_id, product_id, unit_amount, quantity,
  **total_amount**, state, payment_mode, project_id, analytic_account_id, x_expense_type.
- **hr.payslip / .line / .cost.allocation / .input / .worked_days**: period/employee/
  code/category + **amount / total / number_of_days / number_of_hours**.
- **project.attachment / ir.attachment**: attachment type, file/display, mimetype,
  create/write dates, PO link.

(Full tuples in source; the n8n workflow now returns these as flat `f_*` metadata.)

## Live verification (read-only, through the running n8n → Odoo)

Executed read-only against the live n8n `odoo_read` webhook (reached by container IP;
the `n8n` DNS name is not resolvable from the code sandbox). **The deployed workflow
is the pre-update version**: it runs `search_read` only and caps results at **100**, so
counts ≥100 are shown as `capped@100` and are a floor, not the true total. True totals
are in the audit. The structured `f_*` fields require deploying the updated workflow.

PRJ-001 contract header retrieved live: **wo_amount = 20,580,000**, project_code
`209-2025` — matches the audit exactly.

### Evidence counts by source (live, best of two read passes)

`capped@100` = ≥100 rows exist (deployed workflow ceiling). `✓` = matches audit exactly.

| Source | PRJ-001 | PRJ-002 | Audit (true, direct JSON-RPC) |
|---|---|---|---|
| project_identity | 1 ✓ | (transient fail) | 1 / 1 |
| analytic_identity | 1 ✓ | 1 ✓ | 1 / 1 |
| actual_cost | capped@100 | capped@100 | 4,906 / 6,566 |
| account_move_lines | capped@100 | capped@100 | 1,803 / 1,618 |
| vendor_bills | capped@100 | capped@100 | 302 / 326 |
| purchase_orders | capped@100 | capped@100 | 142 / 154 |
| purchase_order_lines | (transient fail) | capped@100 | 269 / 318 |
| material_requests | (transient fail) | capped@100 | 158 / 178 |
| material_request_lines | (transient fail) | capped@100 | 481 / 489 |
| mr_analysis_links | (transient fail) | **0 — discrepancy** | 158 / 178 |
| stock_pickings | (transient fail) | capped@100 | 152 / 158 |
| stock_moves | (transient fail) | capped@100 | 290 / 310 |
| hr_expenses | capped@100 | capped@100 | 1,292 / 928 |
| payroll_headers | capped@100 | capped@100 | 144 / 215 |
| payroll_lines | capped@100 | capped@100 | 4,345 / 6,438 |
| payroll_cost_allocation | capped@100 | capped@100 | 1,078 / 1,473 |
| payslip_inputs | capped@100 | capped@100 | 1,621 / 2,418 |
| worked_days | capped@100 | capped@100 | 541 / 784 |
| staff_employees | **0 — discrepancy** | **0 — discrepancy** | 31 / 52 (medium) |
| staff_list | (transient fail) | 20 ✓ | 19 / 20 |
| project_attachments | (transient fail) | 4 ✓ | 4 / 4 |
| po_rfq_attachments | (transient fail) | **0 — discrepancy** | 346 / 407 |

**19 of 22 sources returned project-scoped data live** (matching or capped@100).
Cells marked *transient fail* hit intermittent "Odoo Server Error"/timeouts during the
sweep — every one of them succeeded for the other project, proving the query is valid;
the second read pass then failed JSON-decode globally (n8n returned non-JSON), i.e. the
live infra was rate-limiting/flaky at the time, not a query defect.

### Discrepancies to verify (live = 0, audit > 0)

These three returned a clean `0` via the **deployed** workflow but were non-zero in the
audit's direct JSON-RPC sweep. Most likely the n8n Odoo **service account's record
rules** differ from the audit account, or the deployed workflow handles these specific
relational/computed links differently. They must be re-verified after the updated
workflow is deployed; **do not** treat them as live-confirmed:

- `mr_analysis_links` (`material.purchase.requisition.analysis.mr_id.project_id`)
- `staff_employees` (`hr.employee.project_id`, medium confidence)
- `po_rfq_attachments` (`ir.attachment.lead_id_po.project_id`)

## Financial / contract figures

- **Contract value (`wo_amount`)**: PRJ-001 20,580,000 (live ✓); PRJ-002 19,500,000 (audit).
- **Analytic ledger** (`account.analytic.account` balance/debit/credit): PRJ-001
  −2,970,247.86 / 8,617,742.53 / 5,647,494.67; PRJ-002 −2,804,906.79 / 10,496,527.04 /
  7,691,620.25 (audit; live header retrievable, line totals need uncapped reads).
- **Actual cost, account-move totals, PO commitments, payroll** are retrievable as line
  records but **per-line amounts require deploying the structured (`f_*`) workflow** and
  removing the 100-row search_read cap for true sums. Until then the connector returns
  the records (capped) and the audit holds the true totals.

## NOT IMPLEMENTED (with reason)

- **Medium summary/report views** not in the required category list — `project.expense`,
  `agreement.expense.breakdown.line`, `project.summary.report`,
  `project.profitability.report`, `account.payment.invoice`, `pdc.wizard`,
  `retention.line`, `vehicle.fleet.request`, `project.progress`, `project.task`,
  `employee.requests`, `employee.transfer`: deferred (medium confidence; reconcile to
  detailed line sources first).
- **Budget / BOQ / estimate** — `budget.*`, `mis.budget.*`, `boq.details`, `boq.summary`,
  `project.project.estimation_amount`: ODOO DATA GAP (zero records for both validation
  projects). Kept as "not available".
- **Attendance** — `hr.attendance.x_project_id`: NOT VERIFIED (no sample matches).
- **All ambiguous paths**: intentionally denylisted (see above).
- **True (uncapped) counts & per-line amounts**: blocked until the updated n8n workflow
  is deployed and the search_read cap is lifted for aggregation. Not done from sandbox.

## Operator follow-up (not performed here)

1. Deploy the updated `n8n/odoo_read.json` (structured `f_*` fields) via the safe bind
   script — **do not raw-import** (import strips webhook auth).
2. Set `ODOO_EXTENDED_SOURCES_ENABLED=true` to activate extended retrieval in node_08.
3. Re-run the count sweep on stable infra; confirm the three discrepancy sources and the
   true (uncapped) totals; check the n8n Odoo service-account record rules.

**No go-live claim. Production remains NOT_LIVE.**
