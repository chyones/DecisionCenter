"""High-confidence Odoo project source registry.

Frozen, read-only mapping of the Odoo sources that the 2026-06-16 source-mapping
audit proved are reliably linked to a DecisionCenter project. Each entry records
the exact model, the field allowlist, and the *proven* project-link path so the
connector never guesses a model or field.

Source of truth:
    docs/evidence/uat/ODOO_PROJECT_SOURCE_MAPPING_DISCOVERY_2026-06-16.md

Two project-scope keys are used to resolve the link value at query time:

* ``project``  → ``odoo.project_external_id`` (the ``project.project`` record id,
  e.g. PRJ-001 = 14602, PRJ-002 = 14601).
* ``analytic`` → ``odoo.analytic_account_id`` (the ``account.analytic.account``
  id, e.g. PRJ-001 = 21963, PRJ-002 = 21960).

Several tempting fields returned whole unrelated tables during the audit. Those
ambiguous paths are captured in ``DENYLISTED_PATHS`` and actively rejected by
``assert_path_allowed`` so they can never be used as a project filter.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class AmbiguousOdooPathError(ValueError):
    """Raised when a denylisted/ambiguous Odoo project-link path is requested."""


@dataclass(frozen=True)
class OdooSource:
    """One proven, read-only Odoo project source.

    ``link_path`` is the domain field (possibly dotted, e.g. ``slip_id.project_id``)
    used to scope rows to a single project. ``link_scope`` selects which mapped id
    is substituted into the domain leaf.
    """

    key: str
    category: str
    model: str
    link_path: str
    link_scope: str  # "project" | "analytic"
    fields: tuple[str, ...]
    confidence: str  # "high" | "medium"
    amount_fields: tuple[str, ...] = ()
    date_field: str | None = None
    state_field: str | None = None
    aggregation: str = ""
    limit: int = 100
    # True when an existing inline node_08 query already retrieves this model;
    # such sources are skipped by the extended loop to avoid duplicate evidence.
    handled_inline: bool = False
    example_ids: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Denylist — ambiguous / full-table paths that must never be used as a filter.
# (model, path) pairs taken verbatim from the audit "ambiguous" section.
# ---------------------------------------------------------------------------

DENYLISTED_PATHS: frozenset[tuple[str, str]] = frozenset(
    {
        ("purchase.order", "project_id_mr"),
        ("purchase.order.line", "order_id.project_id_mr"),
        ("stock.picking", "purchase_id.project_id_mr"),
        ("account.move", "project"),
        ("account.payment", "project"),
        ("sale.order", "project_ids"),
        ("fleet.vehicle", "project_id"),
        ("ir.attachment", "mpr_id.project_id"),
        ("hr.payslip.cost.allocation", "cost_center_id"),
    }
)


def assert_path_allowed(model: str, path: str) -> None:
    """Raise ``AmbiguousOdooPathError`` if ``(model, path)`` is denylisted."""
    if (model, path) in DENYLISTED_PATHS:
        raise AmbiguousOdooPathError(
            f"Refusing denylisted/ambiguous Odoo project link {model}.{path}; "
            "this path returned unrelated full-table rows in the audit."
        )


# ---------------------------------------------------------------------------
# The registry — high-confidence sources only (+ the two required medium staff
# sources). Ordered by business area to keep evidence grouping readable.
# ---------------------------------------------------------------------------

ODOO_SOURCES: tuple[OdooSource, ...] = (
    # --- Identity ---------------------------------------------------------
    OdooSource(
        key="project_identity",
        category="project_identity",
        model="project.project",
        link_path="id",
        link_scope="project",
        fields=(
            "name", "project_code", "wo_ref_no", "wo_amount", "estimation_amount",
            "date_start", "date", "partner_id", "analytic_account_id",
            "project_status", "department_id", "user_id",
        ),
        amount_fields=("wo_amount", "estimation_amount"),
        date_field="date_start",
        state_field="project_status",
        aggregation="One project row; wo_amount is the contract/work-order value.",
        confidence="high",
        handled_inline=True,
        example_ids=("14602", "14601"),
    ),
    OdooSource(
        key="analytic_identity",
        category="analytic_identity",
        model="account.analytic.account",
        link_path="id",
        link_scope="analytic",
        fields=("name", "code", "project_ids", "balance", "debit", "credit",
                "partner_id", "currency_id"),
        amount_fields=("balance", "debit", "credit"),
        date_field="write_date",
        state_field="active",
        aggregation="Cost-center identity + high-level ledger balance; not detailed truth.",
        confidence="high",
        example_ids=("21963", "21960"),
    ),
    # --- Actual cost / accounting ----------------------------------------
    OdooSource(
        key="actual_cost",
        category="actual_cost",
        model="account.analytic.line",
        link_path="account_id",
        link_scope="analytic",
        fields=("name", "amount", "date", "account_id", "project_id", "move_id",
                "general_account_id", "partner_id", "employee_id", "product_id",
                "unit_amount", "currency_id", "ref"),
        amount_fields=("amount",),
        date_field="date",
        aggregation="Sum amount by analytic account; costs are negative.",
        confidence="high",
        handled_inline=True,
        example_ids=("2177525", "2177524"),
    ),
    OdooSource(
        key="account_move_lines",
        category="account_move_lines",
        model="account.move.line",
        link_path="analytic_account_id",
        link_scope="analytic",
        fields=("move_id", "date", "name", "ref", "partner_id", "account_id",
                "analytic_account_id", "product_id", "quantity", "price_subtotal",
                "price_total", "balance", "debit", "credit", "currency_id"),
        amount_fields=("balance", "debit", "credit", "price_subtotal", "price_total"),
        date_field="date",
        aggregation="Accounting truth by account/date/vendor/product; sum balance.",
        confidence="high",
        example_ids=("1013469", "1013467"),
    ),
    OdooSource(
        key="vendor_bills",
        category="vendor_bills",
        model="account.move",
        link_path="line_ids.analytic_account_id",
        link_scope="analytic",
        fields=("name", "ref", "move_type", "invoice_date", "date", "state",
                "payment_state", "partner_id", "amount_total", "amount_residual",
                "currency_id"),
        amount_fields=("amount_total", "amount_residual"),
        date_field="invoice_date",
        state_field="state",
        aggregation="Vendor bill/invoice amount by move_type/state/payment_state.",
        confidence="high",
        example_ids=("106875", "106597"),
    ),
    # --- Purchase pipeline (RFQ / LPO / PO) ------------------------------
    OdooSource(
        key="purchase_orders",
        category="purchase_orders",
        model="purchase.order",
        link_path="project_id",  # purchase.order.project_id == analytic_account_id
        link_scope="analytic",
        fields=("name", "rfq_name", "po_name", "date_order", "date_approve",
                "date_planned", "state", "partner_id", "amount_untaxed",
                "amount_total", "currency_id", "invoice_count", "picking_count",
                "custom_requisition_id", "project_id"),
        amount_fields=("amount_untaxed", "amount_total"),
        date_field="date_order",
        state_field="state",
        aggregation="Committed cost by state; separate RFQ vs PO via state/refs.",
        confidence="high",
        example_ids=("40181", "40155"),
    ),
    OdooSource(
        key="purchase_order_lines",
        category="purchase_order_lines",
        model="purchase.order.line",
        link_path="account_analytic_id",
        link_scope="analytic",
        fields=("order_id", "product_id", "product_qty", "product_uom",
                "price_unit", "price_subtotal", "price_total", "state",
                "qty_received", "qty_invoiced", "partner_id", "currency_id",
                "account_analytic_id"),
        amount_fields=("price_subtotal", "price_total", "price_unit"),
        state_field="state",
        aggregation="Committed cost = sum open/confirmed line price_subtotal.",
        confidence="high",
        example_ids=("112580", "112579"),
    ),
    # --- Material / site requests ----------------------------------------
    OdooSource(
        key="material_requests",
        category="material_requests",
        model="material.purchase.requisition",
        link_path="project_id",
        link_scope="project",
        fields=("name", "ref_no", "request_date", "date_end", "date_done",
                "state", "employee_id", "proposed_vendor_id", "project_id",
                "analytic_account_id", "task_id", "material_type_selection"),
        date_field="request_date",
        state_field="state",
        aggregation="Count requests by state/type; sum cost packages only if validated.",
        confidence="high",
        example_ids=("38055", "38053"),
    ),
    OdooSource(
        key="material_request_lines",
        category="material_request_lines",
        model="material.purchase.requisition.line",
        link_path="requisition_id.project_id",
        link_scope="project",
        fields=("requisition_id", "product_id", "qty", "partner_id",
                "requisition_type", "product_qty_available",
                "is_picking_and_po_created"),
        date_field="create_date",
        aggregation="Sum quantities by product/vendor/request type.",
        confidence="high",
        example_ids=("105769", "105767"),
    ),
    OdooSource(
        key="mr_analysis_links",
        category="mr_analysis_links",
        model="material.purchase.requisition.analysis",
        link_path="mr_id.project_id",
        link_scope="project",
        fields=("mr_id", "po_ids", "move_ids", "pdc_ids", "payment_ids",
                "attachment_ids"),
        aggregation="Relationship index MR → LPOs/invoices/PDC/payments/attachments.",
        confidence="high",
        example_ids=("88172", "88170"),
    ),
    # --- Stock receipts / issues -----------------------------------------
    OdooSource(
        key="stock_pickings",
        category="stock_pickings",
        model="stock.picking",
        link_path="purchase_id.project_id",  # == analytic_account_id
        link_scope="analytic",
        fields=("name", "origin", "state", "date", "scheduled_date", "date_done",
                "partner_id", "custom_requisition_id", "purchase_id",
                "picking_type_code"),
        date_field="date",
        state_field="state",
        aggregation="Count by state/type; join stock.move for quantities.",
        confidence="high",
        example_ids=("42385", "40679"),
    ),
    OdooSource(
        key="stock_moves",
        category="stock_moves",
        model="stock.move",
        link_path="purchase_line_id.account_analytic_id",
        link_scope="analytic",
        fields=("product_id", "product_qty", "product_uom_qty", "quantity_done",
                "price_unit", "state", "date", "origin", "picking_id",
                "purchase_line_id", "location_id", "location_dest_id"),
        amount_fields=("price_unit",),
        date_field="date",
        state_field="state",
        aggregation="Sum quantities by product/state/location; not a financial amount.",
        confidence="high",
        example_ids=("99864", "99832"),
    ),
    # --- HR expenses / payroll / manpower --------------------------------
    OdooSource(
        key="hr_expenses",
        category="hr_expenses",
        model="hr.expense",
        link_path="project_id",
        link_scope="project",
        fields=("name", "date", "employee_id", "product_id", "unit_amount",
                "quantity", "total_amount", "state", "payment_mode", "project_id",
                "analytic_account_id", "x_expense_type", "x_petty_cash_type"),
        amount_fields=("total_amount", "unit_amount"),
        date_field="date",
        state_field="state",
        aggregation="Sum total_amount by employee/product/type/state/date.",
        confidence="high",
        example_ids=("134325", "134320"),
    ),
    OdooSource(
        key="payroll_headers",
        category="payroll_headers",
        model="hr.payslip",
        link_path="project_id",
        link_scope="project",
        fields=("number", "date_from", "date_to", "employee_id", "project_id",
                "state"),
        date_field="date_from",
        state_field="state",
        aggregation="Payroll by payslip period/state; detail via lines/allocation.",
        confidence="high",
        example_ids=("176293", "176289"),
    ),
    OdooSource(
        key="payroll_lines",
        category="payroll_lines",
        model="hr.payslip.line",
        link_path="slip_id.project_id",
        link_scope="project",
        fields=("slip_id", "employee_id", "code", "category_id", "amount",
                "quantity", "total", "analytic_account_id"),
        amount_fields=("amount", "total"),
        aggregation="Sum total by salary rule/category/period/employee.",
        confidence="high",
        example_ids=("5836533", "5836532"),
    ),
    OdooSource(
        key="payroll_cost_allocation",
        category="payroll_cost_allocation",
        model="hr.payslip.cost.allocation",
        link_path="project_id",  # never cost_center_id (denylisted)
        link_scope="project",
        fields=("project_id", "cost_center_id", "employee_id", "partner_id",
                "amount"),
        amount_fields=("amount",),
        aggregation="Sum amount by project/employee/period.",
        confidence="high",
        example_ids=("946267", "946261"),
    ),
    OdooSource(
        key="payslip_inputs",
        category="payslip_inputs",
        model="hr.payslip.input",
        link_path="payslip_id.project_id",
        link_scope="project",
        fields=("payslip_id", "code", "name", "amount"),
        amount_fields=("amount",),
        aggregation="Sum input amounts by code/type/period.",
        confidence="high",
        example_ids=("3100166", "3100165"),
    ),
    OdooSource(
        key="worked_days",
        category="worked_days",
        model="hr.payslip.worked_days",
        link_path="payslip_id.project_id",
        link_scope="project",
        fields=("payslip_id", "code", "number_of_days", "number_of_hours",
                "amount"),
        amount_fields=("amount",),
        aggregation="Sum days/hours/amount by project/period/code.",
        confidence="high",
        example_ids=("1055436", "1055435"),
    ),
    OdooSource(
        key="staff_employees",
        category="staff_employees",
        model="hr.employee",
        link_path="project_id",
        link_scope="project",
        fields=("name", "employee_number", "job_id", "department_id",
                "project_id", "project_id_store", "analytic_account_id"),
        aggregation="Count employees by project/job/department; not a ledger.",
        confidence="medium",
        example_ids=("5662", "5657"),
    ),
    OdooSource(
        key="staff_list",
        category="staff_list",
        model="staff.list",
        link_path="project_id",
        link_scope="project",
        fields=("project_id",),
        aggregation="Count staff by project/category.",
        confidence="medium",
        example_ids=("50017", "49534"),
    ),
    # --- Documents -------------------------------------------------------
    OdooSource(
        key="project_attachments",
        category="project_attachments",
        model="project.attachment",
        link_path="project_id",
        link_scope="project",
        fields=("project_id", "lead_attachment_type", "file_attachment",
                "attachment_display", "project_partner_id", "project_agreement_id",
                "project_wo_amount", "project_date_start", "project_date_end"),
        amount_fields=("project_wo_amount",),
        aggregation="List project attachment records by type.",
        confidence="high",
        example_ids=("56966", "56962"),
    ),
    OdooSource(
        key="po_rfq_attachments",
        category="po_rfq_attachments",
        model="ir.attachment",
        link_path="lead_id_po.project_id",  # == analytic_account_id
        link_scope="analytic",
        fields=("name", "res_model", "res_id", "lead_id_po", "datas_fname",
                "mimetype", "create_date", "write_date"),
        date_field="create_date",
        aggregation="List supporting files for PO/RFQ records.",
        confidence="high",
        example_ids=("810057", "810048"),
    ),
)


# Validate the registry against the denylist at import time: no proven source
# may ever use a denylisted (model, path) link. This makes a regression a hard
# import error, not a silent bad query.
for _src in ODOO_SOURCES:
    assert_path_allowed(_src.model, _src.link_path)


def active_sources(*, include_medium: bool = True) -> tuple[OdooSource, ...]:
    """Sources retrieved by the extended loop (inline-handled ones excluded)."""
    return tuple(
        s for s in ODOO_SOURCES
        if not s.handled_inline and (include_medium or s.confidence == "high")
    )


def source_by_key(key: str) -> OdooSource | None:
    for s in ODOO_SOURCES:
        if s.key == key:
            return s
    return None
