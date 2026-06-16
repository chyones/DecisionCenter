# Odoo Project Source Mapping Discovery — 2026-06-16

## Audit Scope And Guardrails

- **Purpose:** read-only Odoo 14 Community source-mapping audit for DecisionCenter.
- **Odoo write operations:** none.
- **Code changes:** none.
- **Filesystem output:** this Markdown evidence report only.
- **Odoo host:** `erp.elrace.com` (credentials not printed or stored in this report).
- **Odoo version:** `14.0-20211007`, `server_serie=14.0`, `protocol_version=1`.
- **Git branch:** `main`.
- **Git HEAD at audit:** `d0501d7875b4f9b9f71b8c51eed19698b4c2ff14`.
- **Preflight:** `python3 scripts/agent_preflight.py` ran. It reported clean `check_ai_context.py` and `check_doc_drift.py`, but failed the wrapper because the worktree already had pre-existing untracked files: `Audit.md`, `FULL_SYSTEM_AUDIT_REPORT.md`, `executive-decision-report.md`.

## Commands And Scripts Run

All Odoo calls used JSON-RPC read methods only: `authenticate`, `version`, `search_count`, `search_read`, `read`, `fields_get`. No `create`, `write`, `unlink`, approval, posting, import, deployment, or n8n workflow mutation was run.

- `sed -n ... AGENTS.md`, `docs/ai/SHARED_CONTEXT.md`, `docs/ai/AGENT_HANDOFF.md`, `docs/ai/agent-state.json`, `docs/ai/skills/README.md`
- `git branch --show-current`, `git rev-parse HEAD`, `git status --short`
- `python3 scripts/agent_preflight.py`
- `rg -n "ODOO|odoo|project_source_mapping|analytic_account|..." apps docs n8n scripts frontend/src`
- Read current connector/code files: `apps/edr/connectors/odoo.py`, `apps/edr/graph/node_08_odoo.py`, `apps/edr/graph/node_12_draft_json.py`, `apps/edr/app.py`, `apps/edr/rbac/project_mapping.py`, `n8n/odoo_read.json`
- Odoo JSON-RPC connection/version check.
- Odoo metadata sweep saved to `/tmp/odoo_project_source_mapping_metadata.json`.
- Odoo project validation sweep saved to `/tmp/odoo_project_source_mapping_validation_simple.json`.
- Direct Odoo ID recheck for `project.project` IDs `14602`, `14601` and `account.analytic.account` IDs `21963`, `21960`.
- Suspicious path sample checks for domains that returned full-table results.

## Global Discovery Summary

| Item | Result |
|---|---:|
| Installed modules | 878 |
| Relevant installed modules matched by business terms | 678 |
| Odoo models in `ir.model` | 1,571 |
| Fields in `ir.model.fields` | 36,688 |
| Candidate source models counted | 260 |
| Candidate models sampled with `fields_get` + `search_read` | 180 |
| Custom/manual models | 1 transient wizard (`x_partner.selection.wizard`) |
| Custom/manual or `x_` fields | 378 |
| Relevant custom/manual or `x_` fields | 214 |

## Installed Relevant Modules

This Odoo database is not standard-only. It has standard Odoo/OCA modules plus many Elrace/Pandora/Morals/custom modules that add project, accounting, payroll, material request, attachment, retention, and purchase behavior.

| Area | Installed modules observed |
|---|---|
| Project / timesheets | `project`, `sale_project`, `hr_timesheet`, `elrace_project_view`, `elrace_project_accounting_reports`, `elrace_project_attachment_list_extra`, `elrace_project_attendance`, `elrace_project_progress_update_access`, `elrace_work_order_document_fix`, `pandora_bi_project_sub_project` |
| Accounting / analytic / invoices | `account`, `analytic`, `base_accounting_kit`, `elrace_project_accounting_reports`, `elrace_customer_invoice_table_structure`, `pandora_account_move_vouchers`, `pandora_account_payment_analytics`, `pandora_invoice_advance`, `pandora_invoice_retention`, `pandora_accounting_kit_fixes`, `pandora_accounting_stages` |
| Purchase / RFQ / LPO / PDC | `purchase`, `purchase_stock`, `purchase_requisition`, `purchase_request`, `purchase_advance_payment`, `pandora_po_extra_fields`, `pandora_pdc_po_support`, `pandora_pdc_fixes`, `pandora_merge_purchase_order` |
| Material requests / MR | `material_purchase_requisitions`, `elrace_mr_type_flow`, `pandora_mr_analysis` |
| Inventory / stock | `stock`, `purchase_stock`, `stock_request` |
| HR / payroll / manpower | `hr`, `hr_contract`, `hr_attendance`, `hr_expense`, `hr_payroll_community`, `hr_payroll_account_community`, `hr_payroll_attendance`, `automatic_payroll`, `pandora_payroll_timesheet`, `pandora_payroll_operating_unit`, `elrace_labor_payroll_engine`, `elrace_staff_payroll_engine`, `elrace_payroll_costing`, `elrace_payslip_reporting`, `elrace_manpower_report` |
| Fleet / equipment | `fleet`, `elrace_fleet`, `elrace_fleet_management` |
| Attachments / documents | `elrace_supporting_document`, `elrace_s3_bucket`, `elrace_work_order_document_fix`, `elrace_project_attachment_list_extra`, `pandora_attachment_file_preview`, `document_url` |
| Retention / advance / payments | `elrace_retention_release_request`, `pandora_invoice_retention`, `purchase_advance_payment`, `ohrms_salary_advance`, `pandora_account_payment_*`, `pandora_pdc_*` |

## Custom Models And Fields

Only one `ir.model.state = manual` model was discovered: `x_partner.selection.wizard`. It is transient and not a project source.

Important custom/manual or `x_` fields discovered include:

| Model | Field | Type / relation | Meaning / risk |
|---|---|---|---|
| `project.project` | `x_onedrive_id`, `x_internal_project`, `x_pr_lat`, `x_pr_long` | char/boolean/float | Project metadata outside current connector. |
| `purchase.order` | `x_folder_count_project_id` | many2one `project.project` | Validated as a reliable project link for LPO/RFQ counts. |
| `account.move`, `account.payment`, `account.bank.statement.line` | `x_customer_invoice_project_id` | many2one `account.analytic.account` | Custom invoice analytic/contract link not retrieved by DecisionCenter. |
| `hr.attendance` | `x_project_id`, `x_attendance_type`, `x_late_in`, `x_early_out`, `x_deductible_minutes`, `x_is_absent` | project/date/attendance fields | Attendance has project-aware custom fields, but sample projects had no matches via `x_project_id`. |
| `account.analytic.line`, `account.move.line`, `account.invoice.report` | `x_dimension_offer`, `x_dimension_asset`, `x_dimension_ass`, `x_dimension_emp` | many2one `account.analytic.tag` | Analytic dimensions not returned by current connector. |
| `ir.attachment` | `x_attachment_ids_type`, `x_create_date`, `x_create_email`, `x_is_company`, `x_is_company_doc` | attachment metadata | Supporting document metadata not returned by connector. |
| `project.attachment` | `x_client_project_attach`, `x_client_agreement_attach`, `x_pr_city_id`, `x_folder_id` | partner/agreement/city/folder | Dedicated project document layer exists outside SharePoint. |
| `hr.expense` | `x_expense_type`, `x_petty_cash_type` | selection | Petty-cash/expense classification not returned. |
| `res.users.role` | `x_is_project_progress`, `x_is_purchase_role`, `x_is_projects_role`, `x_is_project_invoices_role`, `x_is_attendance_role`, `x_is_petty_cash_holder_role` | boolean | Odoo-side role flags exist but are not part of DecisionCenter mapping. |

## Validated Project Samples

The audit validated the global mapping against both mapped DecisionCenter projects, not only PRJ-001.

| DecisionCenter project | Odoo `project.project` | Odoo `account.analytic.account` | Evidence |
|---|---:|---:|---|
| `PRJ-001` | `14602` | `21963` | Project name `Construction of Civil Defense building in Al Marfa`; `project_code=209-2025`; `wo_ref_no=209/2025`; `wo_amount=20,580,000.0`; analytic `balance=-2,970,247.86`, `debit=8,617,742.53`, `credit=5,647,494.67`. |
| `PRJ-002` | `14601` | `21960` | Project name `Construction of Civil Defense building in Zayed City Al Dhafra.`; `project_code=208/2025`; `wo_ref_no=208/2025`; `wo_amount=19,500,000.0`; analytic `balance=-2,804,906.79`, `debit=10,496,527.04`, `credit=7,691,620.25`. |

Project identity is therefore stored in both:

- `project.project.id` and fields such as `name`, `project_code`, `wo_ref_no`, `wo_amount`, `date_start`, `date`, `partner_id`, `analytic_account_id`.
- `account.analytic.account.id`, linked back through `project_ids`, with `name`, `code`, `balance`, `debit`, `credit`, `partner_id`, and analytic hierarchy display names.

## Final Project Source Mapping Table

Gap type meanings: `OK` = current connector retrieves enough for that source; `CONNECTOR FIELD GAP` = current connector reads the model but omits important fields; `CONNECTOR MAPPING GAP` = data exists but DecisionCenter does not query this source/model; `AMBIGUOUS PROJECT LINK` = field/path exists but returned unrelated rows or cannot safely isolate a project; `ODOO DATA GAP` = source/model exists but no records for validation projects; `NOT VERIFIED` = found but not proven for the samples.

| Business topic | Odoo model | Important fields | Project link field/path | Amount field | Date field | Status/state field | Vendor/employee/material/account fields | Recommended filter | Aggregation rule | Example record IDs | Confidence | Gap type |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Project identity / contract header | `project.project` | `id`, `name`, `project_code`, `wo_ref_no`, `wo_amount`, `estimation_amount`, `date_start`, `date`, `partner_id`, `analytic_account_id`, `project_status`, `department_id` | `id` | `wo_amount`, `estimation_amount` | `date_start`, `date` | `active`, `project_status` | `partner_id`, `department_id`, `user_id` | `id = project_external_id` | One project row per DecisionCenter project. Use `wo_amount` as contract/work-order value when present. | `14602`, `14601` | high | CONNECTOR FIELD GAP |
| Analytic project identity / cost center | `account.analytic.account` | `id`, `name`, `code`, `project_ids`, `balance`, `debit`, `credit`, `partner_id`, `currency_id` | `id`; reverse `project_ids` | `balance`, `debit`, `credit` | `write_date` | `active`, `stage_id` | `partner_id`, `group_id` | `id = analytic_account_id` or `project_ids = project_id` | Treat as cost-center identity and high-level ledger balance; do not replace detailed lines. | `21963`, `21960` | high | CONNECTOR MAPPING GAP |
| Actual cost / analytic transactions | `account.analytic.line` | `name`, `amount`, `date`, `account_id`, `project_id`, `move_id`, `general_account_id`, `partner_id`, `employee_id`, `product_id`, `unit_amount`, `currency_id`, `ref` | `account_id = analytic_account_id`; also `project_id = project_id` | `amount` | `date` | `sheet_state` for timesheets where present | `general_account_id`, `move_id`, `partner_id`, `employee_id`, `product_id` | Prefer `account_id = analytic_account_id`; validation counts: PRJ-001 4,906; PRJ-002 6,566. | Sum `amount` by analytic account; costs are typically negative. Group by account/product/employee/date as needed. | `2177525`, `2177524`, `2177446`, `2177445` | high | CONNECTOR FIELD GAP |
| Project financial summary report | `project.summary.report` | `project_id`, `project_code`, `date`, `journal_id`, `parent_state`, `net_amount` | `project_id = analytic_account_id` | `net_amount` | `date` | `parent_state` | `journal_id` | `project_id = analytic_account_id`; counts PRJ-001 1,737; PRJ-002 1,534. | Sum `net_amount` by journal/date/state; use as report view, not sole ledger truth. | `1013469`, `1013467`, `1013405`, `1013403` | high | CONNECTOR MAPPING GAP |
| Project profitability / invoiceable vs invoiced | `project.profitability.report` | `analytic_account_id`, `project_id`, `line_date`, `sale_order_id`, `sale_line_id`, `product_id`, `amount_untaxed_to_invoice`, `amount_untaxed_invoiced`, `expense_amount_untaxed_to_invoice`, `expense_amount_untaxed_invoiced` | `analytic_account_id = analytic_account_id` or `project_id = project_id` | untaxed/invoiced amount fields | `line_date`, `order_confirmation_date` | not a workflow state | `partner_id`, `product_id`, `sale_order_id` | `analytic_account_id = analytic_account_id`; counts PRJ-001 167; PRJ-002 178. | Sum invoiceable/invoiced fields by product/sale line/date. | `74166`, `74165`, `73999`, `73998` | high | CONNECTOR MAPPING GAP |
| Project expense summary | `project.expense` | `project_id`, `analytic_account_id`, `total_expenses`, `total_expense`, `staff_performance_total`, `labor_performance_total`, `invoice_lpo_count`, `invoice_count`, `mr_count`, `total_client_invoice` | `project_id = project_id` | summary total fields | `last_update_*`, `write_date` | not primary state | project/analytic fields | `project_id = project_id`; counts PRJ-001 8; PRJ-002 8. | Use as summary only; detailed truth should come from analytic/account/purchase/payroll lines. | `15583`, `15582`, `15575`, `15574` | medium | CONNECTOR MAPPING GAP; computed-field reliability issue |
| Agreement / expense breakdown view | `agreement.expense.breakdown.line` | `analytic_account_id`, accounting-like line fields | `analytic_account_id = analytic_account_id` | line amount fields | line/report date | line/report state | account/partner/project fields | `analytic_account_id = analytic_account_id`; counts PRJ-001 1,803; PRJ-002 1,618. | Use as reporting view; reconcile to `account.move.line`. | `1013469`, `1013467`, `1013405`, `1013403` | medium | CONNECTOR MAPPING GAP |
| RFQ / LPO / PO header pipeline | `purchase.order` | `name`, `rfq_name`, `po_name`, `date_order`, `date_approve`, `date_planned`, `state`, `partner_id`, `amount_untaxed`, `amount_total`, `currency_id`, `invoice_count`, `picking_count`, `custom_requisition_id`, `project_id`, `x_folder_count_project_id` | `project_id = analytic_account_id` or `x_folder_count_project_id = project_id` | `amount_untaxed`, `amount_total`, `amount_residual` | `date_order`, `date_approve`, `date_planned` | `state`, `invoice_status`, `advance_payment_status` | `partner_id`, `custom_requisition_id`, `purchase_order_id` | Prefer `project_id = analytic_account_id`; counts PRJ-001 142; PRJ-002 154. `x_folder_count_project_id` matched same counts. | Committed cost by PO state: sum `amount_untaxed`/`amount_total`; separate RFQ vs PO by `state` and reference fields. | `40181`, `40155`, `40180`, `40159` | high | CONNECTOR MAPPING GAP |
| PO line commitments / materials | `purchase.order.line` | `order_id`, `product_id`, `product_qty`, `product_uom`, `price_unit`, `price_subtotal`, `price_total`, `state`, `qty_received`, `qty_invoiced`, `partner_id`, `currency_id`, `account_analytic_id`, `project_id` | `account_analytic_id = analytic_account_id`; also `project_id = project_id` | `price_subtotal`, `price_total`, `price_unit` | `date_order`, `date_planned` | `state` | `product_id`, `partner_id`, `order_id` | `account_analytic_id = analytic_account_id`; counts PRJ-001 269; PRJ-002 318. | Committed cost = sum open/confirmed line `price_subtotal` or `price_total`, grouped by order/state/product/vendor. | `112580`, `112579`, `112576`, `112575` | high | CONNECTOR MAPPING GAP |
| Purchase analysis view | `purchase.report` | `account_analytic_id`, `order_id`, `partner_id`, `product_id`, `price_total`, `untaxed_total`, `qty_ordered`, `qty_received`, `qty_billed`, `state`, `date_order` | `account_analytic_id = analytic_account_id` | `price_total`, `untaxed_total`, `price_average` | `date_order`, `date_approve`, `effective_date` | `state` | `partner_id`, `product_id`, `order_id` | `account_analytic_id = analytic_account_id`; counts PRJ-001 262; PRJ-002 303. | Use as rollup/check against PO lines. | `112580`, `112579`, `112576`, `112575` | high | CONNECTOR MAPPING GAP |
| Material / site request header | `material.purchase.requisition` | `name`, `ref_no`, `request_date`, `date_end`, `date_done`, `state`, `employee_id`, `proposed_vendor_id`, `project_id`, `analytic_account_id`, `task_id`, `purchase_order_ids`, `attachment_ids`, `material_type_selection` | `project_id = project_id` or `analytic_account_id = analytic_account_id` | cost summary fields: `equipment_machine_total`, `worker_resource_total`, `subcontract_total`, `work_cost_package_total` | `request_date`, approval/date fields | `state` | `employee_id`, `proposed_vendor_id`, `material_type_id`, `task_id` | `project_id = project_id`; counts PRJ-001 158; PRJ-002 178. | Count requests by state/type; sum cost package fields only if validated against lines/POs. | `38055`, `38053`, `38080`, `38071` | high | CONNECTOR MAPPING GAP |
| Material request lines | `material.purchase.requisition.line` | `requisition_id`, `product_id`, `qty`, `partner_id`, `requisition_type`, `product_qty_available`, `is_picking_and_po_created` | `requisition_id.project_id = project_id` | no reliable amount field found on line | `create_date`, `write_date` | `requisition_type`, parent `state` | `product_id`, `qty`, `partner_id` | `requisition_id.project_id = project_id`; counts PRJ-001 481; PRJ-002 489. | Sum quantities by product/vendor/request type; join parent for state/date. | `105769`, `105767`, `105877`, `105829` | high | CONNECTOR MAPPING GAP |
| MR-to-LPO/invoice/payment/supporting docs | `material.purchase.requisition.analysis` | `mr_id`, `po_ids`, `move_ids`, `pdc_ids`, `payment_ids`, `attachment_ids` | `mr_id.project_id = project_id` | linked records carry amounts | parent/link dates | linked record states | MR/PO/invoice/payment/attachment links | `mr_id.project_id = project_id`; counts PRJ-001 158; PRJ-002 178. | Use as relationship index from MR to LPOs, invoices, PDC, payments, attachments. | `88172`, `88170`, `88197`, `88188` | high | CONNECTOR MAPPING GAP |
| Stock receipts / deliveries | `stock.picking` | `name`, `origin`, `state`, `date`, `scheduled_date`, `date_done`, `partner_id`, `custom_requisition_id`, `purchase_id`, `move_lines`, `invoice_ids`, `picking_type_code` | `custom_requisition_id.project_id = project_id` or `purchase_id.project_id = analytic_account_id` | no header amount; use move/account valuation if required | `date`, `scheduled_date`, `date_done` | `state`, `picking_type_code` | `partner_id`, `purchase_id`, `custom_requisition_id`, locations | Use `custom_requisition_id.project_id` for MR-linked pickings; counts PRJ-001 10; PRJ-002 12. Use `purchase_id.project_id` for PO-linked pickings; counts PRJ-001 152; PRJ-002 158. | Count by state/type; join `stock.move` for quantities/products. | `42385`, `40679`, `42375`, `42357` | high | CONNECTOR MAPPING GAP |
| Stock move quantities | `stock.move` | `product_id`, `product_qty`, `product_uom_qty`, `quantity_done`, `price_unit`, `state`, `date`, `origin`, `picking_id`, `purchase_line_id`, `custom_requisition_line_id`, `location_id`, `location_dest_id` | `purchase_line_id.account_analytic_id = analytic_account_id`; MR path also valid | `price_unit` only; valuation elsewhere | `date`, `date_deadline` | `state` | `product_id`, `purchase_line_id`, `picking_id`, locations | `purchase_line_id.account_analytic_id = analytic_account_id`; counts PRJ-001 290; PRJ-002 310. | Sum quantities by product/state/location; do not use as financial amount without valuation/account lines. | `99864`, `99832`, `99863`, `99792` | high | CONNECTOR MAPPING GAP |
| Stock move line execution | `stock.move.line` | `move_id`, `picking_id`, `product_id`, `qty_done`, `product_qty`, `date`, `state`, `reference`, `origin`, locations | `move_id.purchase_line_id.account_analytic_id = analytic_account_id` | no amount | `date` | `state` | `product_id`, locations, picking/move refs | `move_id.purchase_line_id.account_analytic_id = analytic_account_id`; counts PRJ-001 239; PRJ-002 268. | Sum `qty_done` by product/date/location. | `95468`, `95396`, `95467`, `95399` | high | CONNECTOR MAPPING GAP |
| Vendor bills / journal entry headers | `account.move` | `name`, `ref`, `move_type`, `invoice_date`, `date`, `state`, `payment_state`, `partner_id`, `amount_total`, `amount_residual`, `currency_id`, `project_id`, `line_ids`, `invoice_line_ids` | `project_id = analytic_account_id`; or `line_ids.analytic_account_id = analytic_account_id` | `amount_total`, `amount_residual`, line balances | `invoice_date`, `date`, `create_date` | `state`, `payment_state` | `partner_id`, `journal_id`, `invoice_line_ids` | Prefer `line_ids.analytic_account_id = analytic_account_id` for analytic allocation; counts PRJ-001 302; PRJ-002 326. Header `project_id` counts PRJ-001 90; PRJ-002 120. | Vendor bill/invoice amount by `move_type`, `state`, `payment_state`; detailed accounting from `account.move.line`. | `106875`, `106597`, `106910`, `106907` | high | CONNECTOR MAPPING GAP |
| Journal items / invoice lines | `account.move.line` | `move_id`, `date`, `name`, `ref`, `partner_id`, `account_id`, `analytic_account_id`, `product_id`, `quantity`, `price_subtotal`, `price_total`, `balance`, `debit`, `credit`, `currency_id`, `payment_id` | `analytic_account_id = analytic_account_id` | `balance`, `debit`, `credit`, `price_subtotal`, `price_total` | `date`, `create_date` | parent move state | `account_id`, `partner_id`, `product_id`, `move_id`, `payment_id` | `analytic_account_id = analytic_account_id`; counts PRJ-001 1,803; PRJ-002 1,618. | Actual cost/accounting truth by account/date/vendor/product; sum `balance`/debit/credit per reporting need. | `1013469`, `1013467`, `1013405`, `1013403` | high | CONNECTOR MAPPING GAP |
| Invoice reporting | `account.invoice.report` | `move_id`, `move_type`, `state`, `payment_state`, `invoice_date`, `partner_id`, `product_id`, `quantity`, `account_id`, `analytic_account_id`, `price_subtotal` | `analytic_account_id = analytic_account_id` | `price_subtotal`, `quantity`, `price_average` | `invoice_date`, `invoice_date_due` | `state`, `payment_state` | `partner_id`, `product_id`, `account_id`, `move_id` | `analytic_account_id = analytic_account_id`; counts PRJ-001 195; PRJ-002 268. | Use as report view for invoices/bills; reconcile to `account.move.line`. | `1012951`, `1010759`, `1012957`, `1012339` | high | CONNECTOR MAPPING GAP |
| Payment allocation helper | `account.payment.invoice` | `project_id`, payment/invoice relation fields | `project_id = analytic_account_id` | payment/invoice amount fields | payment/invoice dates | payment state on related models | payment/invoice partners/accounts | `project_id = analytic_account_id`; counts PRJ-001 58; PRJ-002 80. | Use only as payment-to-project allocation helper; verify against `account.payment`/`account.move`. | `50167`, `50166`, `50177`, `50176` | medium | CONNECTOR MAPPING GAP |
| PDC / cheque payments | `pdc.wizard` | `name`, `payment_type`, `payment_amount`, `payment_date`, `due_date`, `state`, `partner_id`, `analytic_account_id`, `lpo_ref`, `purchase_order_id`, `invoice_id`, `attachment_ids` | `analytic_account_id = analytic_account_id`; `lpo_ref.project_id` also matched | `payment_amount` | `payment_date`, `due_date`, `done_date` | `state` | `partner_id`, `invoice_id`, `purchase_order_id`, `account_id` | `analytic_account_id = analytic_account_id`; counts PRJ-001 31; PRJ-002 27. | Sum `payment_amount` by state/date/payment type. | `8688`, `8664`, `8689`, `8678` | high | CONNECTOR MAPPING GAP |
| Retention | `retention.line` | `project_id`, retention amount fields, invoice/payment relation fields | `project_id = analytic_account_id` | retention amount fields | related invoice/payment dates | related state fields | analytic/project, invoice/payment refs | `project_id = analytic_account_id`; counts PRJ-001 4; PRJ-002 4. | Sum retention by project/invoice/state. | `5987`, `5956`, `5694`, `5689` | medium | CONNECTOR MAPPING GAP |
| HR expenses / petty cash | `hr.expense` | `name`, `date`, `employee_id`, `product_id`, `unit_amount`, `quantity`, `total_amount`, `state`, `payment_mode`, `project_id`, `analytic_account_id`, `x_expense_type`, `x_petty_cash_type` | `project_id = project_id` or `analytic_account_id = analytic_account_id` | `total_amount`, `unit_amount`, `quantity` | `date`, `create_date` | `state` | `employee_id`, `product_id`, `analytic_account_id` | `project_id = project_id`; counts PRJ-001 1,292; PRJ-002 928. | Sum `total_amount` by employee/product/type/state/date. | `134325`, `134320`, `134323`, `134322` | high | CONNECTOR MAPPING GAP |
| Current project manpower | `hr.employee` | `name`, `employee_number`, `job_id`, `department_id`, `project_id`, `project_id_store`, `analytic_account_id`, `wage`-adjacent profile fields | `project_id = project_id`; `project_id_store = project_id` | not payroll amount source | profile dates/status fields | employee active/status fields | `job_id`, `department_id`, employee fields | `project_id = project_id`; counts PRJ-001 31; PRJ-002 52. | Count employees by project/job/department; not a historical manpower ledger. | `5662`, `5657`, `5649`, `5642` | medium | CONNECTOR MAPPING GAP |
| Staff list / manpower listing | `staff.list` | `project_id`, employee/staff fields | `project_id = project_id` | not primary amount source | list/report dates | staff status if present | employee/project fields | `project_id = project_id`; counts PRJ-001 19; PRJ-002 20. | Count staff by project/category. | `50017`, `49534`, `50016`, `49533` | medium | CONNECTOR MAPPING GAP |
| Attendance summary | `project.attendance.summary` | `project_ids`, attendance summary fields | `project_ids = project_id` | not primary amount source | summary period fields | summary status fields | project/employee counts | `project_ids contains project_id`; counts PRJ-001 2; PRJ-002 2. | Use as project-level attendance summary if period fields are validated. | `924`, `911` | medium | CONNECTOR MAPPING GAP |
| Payroll header | `hr.payslip` | `number`, `date_from`, `date_to`, `employee_id`, `project_id`, `state`, `line_ids`, salary totals | `project_id = project_id` | payslip total fields | `date_from`, `date_to` | `state` | `employee_id`, `contract_id`, `struct_id` | `project_id = project_id`; counts PRJ-001 144; PRJ-002 215. | Payroll by payslip period/state; use lines/allocation for detail. | `176293`, `176289`, `176290`, `176252` | high | CONNECTOR MAPPING GAP |
| Payroll lines | `hr.payslip.line` | `slip_id`, `employee_id`, `code`, `category_id`, `amount`, `quantity`, `total`, `analytic_account_id` | `slip_id.project_id = project_id` | `amount`, `quantity`, `total` | parent payslip dates | parent payslip state | `employee_id`, salary rule/category | `slip_id.project_id = project_id`; counts PRJ-001 4,345; PRJ-002 6,438. | Sum `total` by salary rule/category/period/employee. | `5836533`, `5836532`, `5837618`, `5837617` | high | CONNECTOR MAPPING GAP |
| Payroll cost allocation | `hr.payslip.cost.allocation` | `project_id`, `cost_center_id`, `employee_id`, `partner_id`, `amount` | `project_id = project_id` | `amount` | linked payslip period if present | linked state if present | `employee_id`, `cost_center_id`, `partner_id` | `project_id = project_id`; counts PRJ-001 1,078; PRJ-002 1,473. Do **not** use `cost_center_id` alone; it returned unrelated full-table samples. | Sum `amount` by project/employee/period. | `946267`, `946261`, `946268`, `946259` | high | CONNECTOR MAPPING GAP |
| Payslip input / allowances / deductions | `hr.payslip.input` | `payslip_id`, `code`, `name`, `amount`, input type fields | `payslip_id.project_id = project_id` | `amount` | parent payslip dates | parent payslip state | employee through payslip | `payslip_id.project_id = project_id`; counts PRJ-001 1,621; PRJ-002 2,418. | Sum input amounts by code/type/period. | `3100166`, `3100165`, `3100738`, `3100737` | high | CONNECTOR MAPPING GAP |
| Payslip worked days / manpower days | `hr.payslip.worked_days` | `payslip_id`, `code`, `number_of_days`, `number_of_hours`, `amount` | `payslip_id.project_id = project_id` | `amount`; day/hour fields | parent payslip dates | parent state | employee through payslip | `payslip_id.project_id = project_id`; counts PRJ-001 541; PRJ-002 784. | Sum days/hours/amount by project/period/code. | `1055436`, `1055435`, `1055584`, `1055583` | high | CONNECTOR MAPPING GAP |
| Employee requests | `employee.requests` | request type/date/state fields, `employee_id`, `project_id`, `current_project_id`, salary/allowance request fields | `project_id = project_id` | salary/loan/gratuity fields where applicable | request/effective dates | request status fields | `employee_id`, requester/approver fields | `project_id = project_id`; counts PRJ-001 3; PRJ-002 1. | Count/list project employee requests; do not treat as payroll truth without approval/state filters. | `38179`, `37877`, `32786` | medium | CONNECTOR MAPPING GAP |
| Employee transfers | `employee.transfer`, `employee.transfer.line` | `project_id`, `current_project_id`, `new_project_id`, `employee_id`, `effective_date`, `state` | `project_id = project_id`; line `new_project_id` also relevant | no amount | `request_date`, `effective_date` | `state` | `employee_id`, manager/foreman fields | Use header and line project fields; counts header PRJ-001 3, PRJ-002 1; line PRJ-001 4, PRJ-002 1. | Count transfers by from/to project and effective date. | `303`, `302`, `205`, `203` | medium | CONNECTOR MAPPING GAP |
| Fleet maintenance request | `vehicle.fleet.request` | `project_id`, `vehicle_id`, `driver_id`, `vendor`, `total_po_amount`, `total_invoice_amount`, `state`, date fields | `project_id = project_id` | `total_po_amount`, `total_invoice_amount` | request/assign/approve dates | state fields | `vehicle_id`, `driver_id`, `vendor`, `purchase_order_ids` | `project_id = project_id`; counts PRJ-001 4; PRJ-002 5. | Sum fleet request PO/invoice totals by state/date. | `833`, `729`, `814`, `796` | medium | CONNECTOR MAPPING GAP |
| Project document records | `project.attachment` | `project_id`, `lead_attachment_type`, `file_attachment`, `attachment_display`, `project_partner_id`, `project_agreement_id`, `project_wo_amount`, `project_date_start`, `project_date_end` | `project_id = project_id` | `project_wo_amount` | project date fields | attachment type | client/agreement fields | `project_id = project_id`; counts PRJ-001 4; PRJ-002 4. | List project attachment records by type; join `ir.attachment` through file fields if needed. | `56966`, `56962`, `56955`, `56951` | high | CONNECTOR MAPPING GAP |
| PO/RFQ supporting files | `ir.attachment` | `name`, `res_model`, `res_id`, `lead_id_po`, `datas_fname`, `mimetype`, create metadata, custom attachment type | `lead_id_po.project_id = analytic_account_id` | no amount | `create_date`, `write_date` | no state | linked PO/vendor via `lead_id_po` | `lead_id_po.project_id = analytic_account_id`; counts PRJ-001 346; PRJ-002 407. | List supporting files for PO/RFQ records; do not use invalid `mpr_id.project_id` path. | `810057`, `810048`, `810060`, `809979` | high | CONNECTOR MAPPING GAP |
| Project progress reports | `project.progress` | `project_id`, `employee_id`, `date`, progress fields | `project_id = project_id` | no amount | `date` | progress/status fields if present | `employee_id` | `project_id = project_id`; counts PRJ-001 56; PRJ-002 55. | Latest progress by date/project/employee. | `4709`, `4566`, `4710`, `4565` | medium | CONNECTOR MAPPING GAP |
| Tasks / job orders | `project.task` | `project_id`, `analytic_account_id`, `date_deadline`, `stage_id`, `employee_id`, `total_hours_spent`, `overtime`, `stock_request_order_ids`, `picking_ids` | `project_id = project_id` | time fields, not money | task dates/deadlines | `stage_id`, `kanban_state` | employee, stock/MR links | `project_id = project_id`; counts PRJ-001 9; PRJ-002 6. | Count/list task status; join timesheets/stock only through validated paths. | `11143`, `10930`, `10916`, `10751` | medium | CONNECTOR MAPPING GAP |

## Answers To Required Questions

### 1. What Odoo modules are installed and relevant?

Relevant modules include standard `project`, `account`, `analytic`, `purchase`, `stock`, `hr`, `hr_attendance`, `hr_expense`, `hr_contract`, `fleet`; OCA/community modules such as `purchase_request`, `stock_request`, `hr_payroll_community`, `hr_payroll_account_community`; and many Elrace/Pandora/Morals custom modules listed above. The database is heavily customized and cannot be mapped as standard Odoo only.

### 2. What custom models and custom fields exist?

One manual transient model exists: `x_partner.selection.wizard`. More important are 378 custom/manual/`x_` fields, including project, invoice, attendance, attachment, and analytic dimension fields. See the custom-fields table above. The strongest source-impact fields are `purchase.order.x_folder_count_project_id`, `account.move/account.payment.x_customer_invoice_project_id`, `hr.attendance.x_project_id`, `project.attachment.x_*`, `ir.attachment.x_*`, and analytic dimension fields on `account.analytic.line`, `account.move.line`, and `account.invoice.report`.

### 3. Where is project identity stored?

Project identity is stored in `project.project` and linked to `account.analytic.account` through `project.project.analytic_account_id` and `account.analytic.account.project_ids`. The validated mappings are `PRJ-001 -> project 14602 -> analytic 21963` and `PRJ-002 -> project 14601 -> analytic 21960`.

### 4. How are projects linked to costs, purchases, HR, salaries, accounting, stock, and documents?

- Costs/accounting: mostly through `account.analytic.account` and `account_id`/`analytic_account_id` on analytic/accounting lines.
- Purchases/RFQs/LPOs: `purchase.order.project_id = analytic_account_id`; `purchase.order.line.account_analytic_id = analytic_account_id`; custom `purchase.order.x_folder_count_project_id = project_id` also validated.
- Material requests: `material.purchase.requisition.project_id` and `.analytic_account_id`; lines through `requisition_id.project_id`.
- Stock: `stock.picking.custom_requisition_id.project_id`, `stock.picking.purchase_id.project_id`, `stock.move.purchase_line_id.account_analytic_id`, and `stock.move.line.move_id.purchase_line_id.account_analytic_id`.
- HR/payroll: `hr.employee.project_id`, `staff.list.project_id`, `hr.payslip.project_id`, `hr.payslip.line.slip_id.project_id`, `hr.payslip.cost.allocation.project_id`, `hr.payslip.input/ worked_days -> payslip_id.project_id`.
- Documents: `project.attachment.project_id` and `ir.attachment.lead_id_po.project_id` for PO/RFQ files.

### 5. Which fields identify the project relation?

High-confidence relation fields/paths are: `project.project.id`, `project.project.analytic_account_id`, `account.analytic.account.id`, `account.analytic.account.project_ids`, `account.analytic.line.account_id`, `purchase.order.project_id`, `purchase.order.x_folder_count_project_id`, `purchase.order.line.account_analytic_id`, `material.purchase.requisition.project_id`, `material.purchase.requisition.analytic_account_id`, `material.purchase.requisition.line.requisition_id.project_id`, `stock.picking.custom_requisition_id.project_id`, `stock.picking.purchase_id.project_id`, `account.move.line.analytic_account_id`, `account.move.line.move_id`, `hr.expense.project_id`, `hr.payslip.project_id`, `hr.payslip.line.slip_id.project_id`, `hr.payslip.cost.allocation.project_id`, `project.attachment.project_id`, and `ir.attachment.lead_id_po.project_id`.

### 6. Which fields contain amount, date, state, vendor, employee, quantity, product/material, account, currency, and reference number?

The mapping table lists these per source. In summary: amounts are in `account.analytic.line.amount`, `account.move.line.balance/debit/credit/price_*`, `purchase.order.amount_*`, `purchase.order.line.price_*`, `hr.expense.total_amount`, `hr.payslip.line.amount/total`, `hr.payslip.cost.allocation.amount`, `pdc.wizard.payment_amount`, `project.project.wo_amount`, and report view amount fields. Dates are usually `date`, `date_order`, `date_approve`, `date_planned`, `invoice_date`, `payment_date`, `request_date`, payslip `date_from/date_to`, or `create_date/write_date`. States are `state`, plus accounting `payment_state` and purchase `invoice_status`. Vendors are usually `partner_id`; employees are `employee_id`; material/product is `product_id`; accounts are `account_id`, `general_account_id`, `analytic_account_id`, `account_analytic_id`, or `account_id`; currency is `currency_id`; references are `name`, `ref`, `origin`, `rfq_name`, `po_name`, `ref_no`, `wo_ref_no`.

### 7. Which sources represent actual cost?

High-confidence actual-cost sources are `account.analytic.line`, `account.move.line`, `project.summary.report`, `agreement.expense.breakdown.line`, `hr.expense`, `hr.payslip.line`, `hr.payslip.cost.allocation`, and `pdc.wizard`/payment allocation sources where state filters are applied. Use `account.analytic.line` and `account.move.line` as the primary detailed truth; use report views for summaries/reconciliation.

### 8. Which sources represent committed cost?

High-confidence committed-cost sources are `purchase.order` and `purchase.order.line`, with supporting rollup `purchase.report`. `material.purchase.requisition` and `.line` represent request demand; they become committed cost only when linked to RFQ/LPO/PO records and state filters confirm approval/order stage.

### 9. Which sources represent RFQ / LPO / PO / purchase pipeline?

`purchase.order`, `purchase.order.line`, `purchase.report`, `material.purchase.requisition`, `material.purchase.requisition.line`, and `material.purchase.requisition.analysis`. For supporting documents, use `ir.attachment.lead_id_po.project_id`.

### 10. Which sources represent material requests or site requests?

`material.purchase.requisition`, `material.purchase.requisition.line`, and `material.purchase.requisition.analysis` are the validated material/site request sources. `stock.picking`, `stock.move`, and `stock.move.line` represent downstream receipt/issue movement when linked through MR or purchase lines.

### 11. Which sources represent payroll, salary, labor, staff, attendance, or timesheets?

Validated: `hr.employee`, `staff.list`, `project.attendance.summary`, `hr.payslip`, `hr.payslip.line`, `hr.payslip.cost.allocation`, `hr.payslip.input`, `hr.payslip.worked_days`, `employee.requests`, `employee.transfer`, `employee.transfer.line`, `account.analytic.line` timesheets, and `project.task` time fields. `hr.attendance.x_project_id` exists but had no matches for PRJ-001/PRJ-002, so direct attendance rows are not verified for these projects. `hr.work.entry` only linked through the employee's current project and is ambiguous for historical allocation.

### 12. Which sources represent invoices, vendor bills, journal entries, and payments?

`account.move`, `account.move.line`, `account.invoice.report`, `account.payment.invoice`, `pdc.wizard`, `retention.line`, and `account.analytic.line`. Direct `account.payment.project` returned unrelated full-table records and must not be used. Use payment allocation helper/PDC/linked invoices until payment relations are mapped more precisely.

### 13. Which sources represent budget, contract value, BOQ, or estimate?

- Contract/work-order value: `project.project.wo_amount` was validated for both projects.
- Estimate: `project.project.estimation_amount` exists but was `0.0` for both validated projects.
- BOQ models: `boq.details` and `boq.summary` exist but had zero records for both validation projects.
- Budget models: `budget.lines`, `budget.budget`, `mis.budget.item`, and `mis.budget.by.account.item` exist but had zero records for both validation projects. Treat as `ODOO DATA GAP` for these samples.

### 14. Which sources contain attachments or supporting documents?

Validated: `project.attachment.project_id` and `ir.attachment.lead_id_po.project_id`. `material.purchase.requisition.analysis.attachment_ids` also exists as an MR analysis attachment relation. Direct `ir.attachment.res_model/res_id = project.project`, `lead_id`, and `work_order_id` returned zero for the sample projects; `ir.attachment.mpr_id.project_id` returned the whole table and is invalid as a filter.

### 15. Which current DecisionCenter/Odoo connector fields are missing?

Current connector reads only:

- Project: `name`, `date_start`, `date`, `user_id`, `partner_id` from `project.project`.
- Cost: `name`, `amount`, `date` from `account.analytic.line`.

Missing connector fields include:

- Project identity: `project_code`, `wo_ref_no`, `contract_no`, `wo_amount`, `estimation_amount`, `analytic_account_id`, `currency_id`, `project_status`, `department_id`, attachment fields.
- Analytic/accounting: `account_id`, `project_id`, `move_id`, `general_account_id`, `partner_id`, `employee_id`, `product_id`, `unit_amount`, `currency_id`, `ref`, analytic dimensions.
- Purchase/MR/stock/accounting/payroll/document models listed in the mapping table are not currently queried at all.
- n8n response format collapses records into an excerpt and metadata with only `model`, `record_id`, and currency. It does not return structured fields needed for reliable aggregation.
- `allowed_odoo_ids` is passed by DecisionCenter but the current n8n Odoo workflow does not enforce it inside the JSON-RPC query.

### 16. Which data exists in Odoo but is not currently retrieved by DecisionCenter?

Everything in the final mapping table except basic `project.project` fields and `account.analytic.line.name/amount/date` is currently not retrieved. This includes purchase orders, RFQs/LPOs, purchase lines, material requests, MR analysis, stock pickings/moves, journal entries, vendor bills, invoice reports, payment allocations, PDC payments, retention lines, HR expenses, payroll/payslip records, staff/manpower lists, employee requests/transfers, fleet maintenance requests, project progress records, project attachments, and PO/RFQ attachments.

### 17. Which data is ambiguous or not reliably linked to projects?

The following paths/models must not be used as proven mappings:

| Source/path | Finding |
|---|---|
| `purchase.order.project_id_mr = project_id` | Returned all/recent unrelated purchase orders for both PRJ-001 and PRJ-002. Use `purchase.order.project_id = analytic_account_id` or `x_folder_count_project_id = project_id` instead. |
| `purchase.order.line.order_id.project_id_mr = project_id` | Returned all/recent unrelated lines. Use `purchase.order.line.account_analytic_id = analytic_account_id`. |
| `stock.picking.purchase_id.project_id_mr = project_id` | Returned unrelated/all purchase-linked pickings. Use `stock.picking.purchase_id.project_id = analytic_account_id` or `custom_requisition_id.project_id`. |
| `account.move.project = project_id` | Returned unrelated/all journal entries. Use `account.move.project_id = analytic_account_id` or `line_ids.analytic_account_id`. |
| `account.payment.project = project_id` | Returned unrelated/all payments. Direct payment-to-project mapping not proven. |
| `sale.order.project_ids = project_id` | Returned all 67 sale orders for both sample projects with unrelated samples. Not reliable. |
| `fleet.vehicle.project_id = project_id` | Returned all fleet vehicles for both sample projects with unrelated sample project values. Not reliable. |
| `ir.attachment.mpr_id.project_id = project_id` | Returned all attachments for both sample projects. Not reliable. |
| `hr.payslip.cost.allocation.cost_center_id = analytic_account_id` | Returned all allocation records with unrelated samples. Use `project_id = project_id`. |
| `hr.work.entry.employee_id.project_id = project_id` | Returns many records but uses employee current project, not necessarily historical work-entry project. Ambiguous. |
| `hr.contract.employee_id.project_id = project_id` | Useful for current employee contract context, but historical salary allocation should use payslip/allocation records. |
| `fleet.vehicle.cost.report.project_id` | Query errored (`bus.Bus unavailable`). NOT VERIFIED. |
| `hr.attendance.x_project_id` | Field exists, but no PRJ-001/PRJ-002 matches. Use `project.attendance.summary`/payroll/worked-days unless direct attendance mapping is proven. |
| `budget.lines`, `budget.budget`, `mis.budget.*`, `boq.details`, `boq.summary` | Models exist but no records for validation projects. ODOO DATA GAP for current samples. |

## Current DecisionCenter Connector Assessment

Current source-mapping configuration supports only:

```json
{
  "project_model": "project.project",
  "cost_model": "account.analytic.line",
  "project_external_id": "14602",
  "project_name": "...",
  "analytic_account_id": "21963"
}
```

Current `node_08_odoo.py` retrieves the project row and analytic lines only. `node_12_draft_json.py` then treats Odoo financials as a simple analytic-line cost summary. This is not sufficient for the required business coverage.

Connector gaps:

| Gap | Evidence |
|---|---|
| Source model gap | Validated models outside connector: `purchase.order`, `purchase.order.line`, `material.purchase.requisition`, `stock.picking`, `account.move`, `account.move.line`, `hr.payslip`, `hr.expense`, `project.attachment`, etc. |
| Field gap | Current `PROJECT_FIELDS` omit `project_code`, `wo_ref_no`, `wo_amount`, `analytic_account_id`; current `COST_FIELDS` omit account/vendor/employee/product/currency/ref/move fields. |
| Mapping schema gap | No per-project source definitions for purchase, MR, stock, payroll, attachments, reports, invoices, payments, retention, fleet. |
| Structured response gap | n8n returns short excerpts, not raw structured fields needed for deterministic aggregation. |
| Scope enforcement gap | `allowed_odoo_ids` is passed but not enforced by the n8n `odoo_read` workflow. |
| Invalid path risk | Several tempting fields return full unrelated tables; hardcoded field assumptions would produce false reports. |

## Recommended Next Implementation Steps

These steps are recommended only for the high-confidence proven mappings above. Do not implement unverified/ambiguous paths.

1. Freeze a per-source Odoo mapping config that lists model, fields, project-link path, safe filter, and aggregation rule for each high-confidence source.
2. Extend the Odoo connector to support multiple read-only model queries per project, not only `project.project` and `account.analytic.line`.
3. Return structured Odoo records in evidence metadata, not only string excerpts.
4. Add connector-side field allowlists per model to avoid broken computed fields such as `project.expense.total_expenses` multi-row reads.
5. Add explicit invalid-path denylist: `purchase.order.project_id_mr`, `account.move.project`, `account.payment.project`, `ir.attachment.mpr_id.project_id`, `fleet.vehicle.project_id`, and the other ambiguous paths listed above.
6. Enforce Odoo project/analytic scope in the n8n workflow or backend connector, not only in the caller.
7. Validate a third real project with older accounting/payroll history before using payroll/fleet/budget mappings broadly.
8. Keep budget/BOQ as `Not available` until Odoo records are found for the target project.

## Exact NOT VERIFIED / NOT FOUND / Data-Gap Items

| Item | Status |
|---|---|
| `hr.timesheet.sheet` | NOT FOUND as exact expected model; actual installed model is `hr_timesheet.sheet` with 12 rows and project/time relations. Not validated for PRJ-001/PRJ-002. |
| `crossovered.budget`, `crossovered.budget.lines` | NOT FOUND. |
| `budget.lines`, `budget.budget`, `mis.budget.item`, `mis.budget.by.account.item` | FOUND but zero validation records. ODOO DATA GAP for PRJ-001/PRJ-002. |
| `boq.details`, `boq.summary` | FOUND but zero validation records. ODOO DATA GAP for PRJ-001/PRJ-002. |
| `purchase.request`, `purchase.request.line` | FOUND globally (`1` row each) but no PRJ-001/PRJ-002 matches. NOT VERIFIED for mapped projects. |
| `purchase.requisition`, `purchase.requisition.line` | FOUND; line count `0`; no project-validated records. NOT VERIFIED / ODOO DATA GAP. |
| `client.payment`, `work.order`, `project.completion`, `project.completion.line`, `project.variation` | FOUND but no PRJ-001/PRJ-002 matches. NOT VERIFIED for these projects. |
| `hr.attendance.x_project_id` | Field exists, no sample matches. NOT VERIFIED. |
| `hr.leave`, `hr.leave.salary` | FOUND but no sample matches through tested project/analytic paths. NOT VERIFIED. |
| `fleet.vehicle.cost.report` | FOUND but validation query errored. NOT VERIFIED. |
| Direct `account.payment` project fields | FOUND but not reliably linked. AMBIGUOUS PROJECT LINK. |
| Direct `ir.attachment` project/MR paths except `lead_id_po.project_id` | Zero or full-table invalid results. AMBIGUOUS PROJECT LINK / NOT VERIFIED. |

## Bottom Line

DecisionCenter’s current Odoo connector is safe but far too narrow. The live Odoo database has proven, project-linked sources for costs, commitments, RFQ/LPO/PO pipeline, material requests, stock receipts/issues, vendor bills/journal lines, payroll/manpower, HR expenses, fleet requests, project progress, and supporting documents. Most of that data is currently a `CONNECTOR MAPPING GAP`, and the connector must avoid several misleading fields that returned unrelated full-table results.
