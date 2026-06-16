import type { OdooSourceMapEntry, OdooSourceMapResponse } from '../../api';

/** A generic 13-group sample response with arbitrary (non-PRJ-001/002) ids. */
const GROUPS = [
  'Project identity',
  'Contract value',
  'Actual cost',
  'Accounting / journal lines',
  'Vendor bills',
  'RFQ / LPO / PO',
  'Purchase lines',
  'Material requests',
  'Stock / deliveries',
  'HR expenses',
  'Payroll',
  'Manpower / staff',
  'Attachments',
];

function entry(over: Partial<OdooSourceMapEntry>): OdooSourceMapEntry {
  return {
    key: 'k',
    group: 'Project identity',
    groups: ['Project identity'],
    source_name: 'Source',
    model: 'some.model',
    link_path: 'project_id',
    link_scope: 'project',
    key_fields: ['a', 'b', 'c'],
    confidence: 'high',
    gap_type: 'CONNECTOR MAPPING GAP',
    aggregation: 'agg',
    handled_inline: false,
    warning: '',
    mappable: true,
    link_value: '99001',
    last_scan_status: 'not_scanned',
    record_count: null,
    capped: false,
    ...over,
  };
}

export function makeSourceMap(over: Partial<OdooSourceMapResponse> = {}): OdooSourceMapResponse {
  const sources: OdooSourceMapEntry[] = [
    entry({ key: 'project_identity', source_name: 'Project identity / contract header', model: 'project.project', link_path: 'id', groups: ['Project identity', 'Contract value'], gap_type: 'CONNECTOR FIELD GAP', handled_inline: true }),
    entry({ key: 'analytic_identity', source_name: 'Analytic identity', model: 'account.analytic.account', link_path: 'id', link_scope: 'analytic', link_value: '88002', groups: ['Project identity'] }),
    entry({ key: 'actual_cost', source_name: 'Actual cost', model: 'account.analytic.line', link_path: 'account_id', link_scope: 'analytic', link_value: '88002', groups: ['Actual cost'], gap_type: 'CONNECTOR FIELD GAP', handled_inline: true }),
    entry({ key: 'account_move_lines', source_name: 'Journal items', model: 'account.move.line', link_path: 'analytic_account_id', link_scope: 'analytic', link_value: '88002', groups: ['Accounting / journal lines'] }),
    entry({ key: 'vendor_bills', source_name: 'Vendor bills', model: 'account.move', link_path: 'line_ids.analytic_account_id', link_scope: 'analytic', link_value: '88002', groups: ['Vendor bills'] }),
    entry({ key: 'purchase_orders', source_name: 'RFQ / LPO / PO', model: 'purchase.order', link_path: 'project_id', link_scope: 'analytic', link_value: '88002', groups: ['RFQ / LPO / PO'] }),
    entry({ key: 'purchase_order_lines', source_name: 'PO lines', model: 'purchase.order.line', link_path: 'account_analytic_id', link_scope: 'analytic', link_value: '88002', groups: ['Purchase lines'] }),
    entry({ key: 'material_requests', source_name: 'Material requests', model: 'material.purchase.requisition', groups: ['Material requests'] }),
    entry({ key: 'stock_pickings', source_name: 'Stock receipts', model: 'stock.picking', link_path: 'purchase_id.project_id', link_scope: 'analytic', link_value: '88002', groups: ['Stock / deliveries'] }),
    entry({ key: 'hr_expenses', source_name: 'HR expenses', model: 'hr.expense', groups: ['HR expenses'] }),
    entry({ key: 'payroll_lines', source_name: 'Payroll lines', model: 'hr.payslip.line', link_path: 'slip_id.project_id', groups: ['Payroll'] }),
    entry({ key: 'worked_days', source_name: 'Worked days', model: 'hr.payslip.worked_days', link_path: 'payslip_id.project_id', groups: ['Payroll', 'Manpower / staff'] }),
    entry({ key: 'staff_list', source_name: 'Staff list', model: 'staff.list', confidence: 'medium', groups: ['Manpower / staff'] }),
    entry({ key: 'project_attachments', source_name: 'Project documents', model: 'project.attachment', groups: ['Attachments'] }),
    entry({ key: 'po_rfq_attachments', source_name: 'PO/RFQ files', model: 'ir.attachment', link_path: 'lead_id_po.project_id', link_scope: 'analytic', link_value: '88002', groups: ['Attachments'], warning: 'Re-verify after deploy.' }),
  ];

  return {
    project_code: 'ZED-777',
    generic: true,
    odoo_enabled: true,
    extended_enabled: false,
    odoo_project_id: '99001',
    analytic_account_id: '88002',
    project_source_status: 'complete',
    groups: GROUPS,
    enabled_categories: GROUPS,
    sources,
    denylisted_paths: [
      'account.move.project',
      'account.payment.project',
      'fleet.vehicle.project_id',
      'hr.payslip.cost.allocation.cost_center_id',
      'ir.attachment.mpr_id.project_id',
      'purchase.order.line.order_id.project_id_mr',
      'purchase.order.project_id_mr',
      'sale.order.project_ids',
      'stock.picking.purchase_id.project_id_mr',
    ],
    missing_sources: [],
    notes: [
      'This Source Map is generic: it is built from the Odoo source registry, not from per-project hardcoded data.',
      'PRJ-001 and PRJ-002 are audit validation samples only — they are not fixed logic.',
    ],
    last_scanned_at: null,
    ...over,
  };
}
