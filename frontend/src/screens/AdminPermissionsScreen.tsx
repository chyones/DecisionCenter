/**
 * Static Permissions & Roles — Role Matrix tab only (Phase 1I Slice 7).
 *
 * Per `docs/design/PHASE_1I_UI_CONTRACT.md` §E.7:
 * - Single tab: "Role Matrix".
 * - Read-only table sourced from `docs/security/rbac_matrix.md`.
 * - No Entra edit tab, no Project Assignments editor, no save actions.
 */

interface MatrixRow {
  role: string;
  sharepoint: string;
  owncloud: string;
  userMailbox: string;
  sharedMailboxes: string;
  odooBudget: string;
  odooActualCost: string;
  approval: string;
  auditLogs: string;
}

/** Baked static fixture from `docs/security/rbac_matrix.md` §Permission Matrix. */
const MATRIX_ROWS: MatrixRow[] = [
  {
    role: 'executive',
    sharepoint: 'Allowed projects',
    owncloud: 'Allowed projects',
    userMailbox: 'No',
    sharedMailboxes: 'If mapped',
    odooBudget: 'If permitted',
    odooActualCost: 'If permitted',
    approval: 'Yes',
    auditLogs: 'Summary',
  },
  {
    role: 'project_manager',
    sharepoint: 'Assigned projects',
    owncloud: 'Assigned projects',
    userMailbox: 'Own only',
    sharedMailboxes: 'Project-mapped only',
    odooBudget: 'If permitted',
    odooActualCost: 'If permitted',
    approval: 'Review only',
    auditLogs: 'Own project',
  },
  {
    role: 'finance',
    sharepoint: 'If permitted',
    owncloud: 'If permitted',
    userMailbox: 'Own only',
    sharedMailboxes: 'If mapped',
    odooBudget: 'Yes',
    odooActualCost: 'Yes',
    approval: 'Finance review',
    auditLogs: 'Finance-related',
  },
  {
    role: 'commercial',
    sharepoint: 'Contracts and claims',
    owncloud: 'Contracts and claims',
    userMailbox: 'Own only',
    sharedMailboxes: 'If mapped',
    odooBudget: 'If permitted',
    odooActualCost: 'If permitted',
    approval: 'Commercial review',
    auditLogs: 'Commercial-related',
  },
  {
    role: 'document_control',
    sharepoint: 'Controlled docs',
    owncloud: 'Controlled docs',
    userMailbox: 'Own only',
    sharedMailboxes: 'Document-control mapped',
    odooBudget: 'No by default',
    odooActualCost: 'No by default',
    approval: 'Review only',
    auditLogs: 'Document-related',
  },
  {
    role: 'procurement',
    sharepoint: 'Procurement docs',
    owncloud: 'Procurement docs',
    userMailbox: 'Own only',
    sharedMailboxes: 'If mapped',
    odooBudget: 'PO-related only',
    odooActualCost: 'If permitted',
    approval: 'Review only',
    auditLogs: 'Procurement-related',
  },
  {
    role: 'legal',
    sharepoint: 'Contracts, notices, claims',
    owncloud: 'Contracts, notices, claims',
    userMailbox: 'Own only',
    sharedMailboxes: 'If mapped',
    odooBudget: 'If permitted',
    odooActualCost: 'If permitted',
    approval: 'Legal review',
    auditLogs: 'Legal-related',
  },
  {
    role: 'auditor',
    sharepoint: 'References only unless permitted',
    owncloud: 'References only unless permitted',
    userMailbox: 'No',
    sharedMailboxes: 'No by default',
    odooBudget: 'If permitted',
    odooActualCost: 'If permitted',
    approval: 'No',
    auditLogs: 'Yes',
  },
  {
    role: 'admin',
    sharepoint: 'Configure only',
    owncloud: 'Configure only',
    userMailbox: 'No by default',
    sharedMailboxes: 'No by default',
    odooBudget: 'No by default',
    odooActualCost: 'No by default',
    approval: 'No by default',
    auditLogs: 'System logs',
  },
];

const COLUMNS: { key: keyof MatrixRow; label: string }[] = [
  { key: 'role', label: 'Role' },
  { key: 'sharepoint', label: 'SharePoint Project Docs' },
  { key: 'owncloud', label: 'ownCloud Project Docs' },
  { key: 'userMailbox', label: 'User Mailbox' },
  { key: 'sharedMailboxes', label: 'Shared Mailboxes' },
  { key: 'odooBudget', label: 'Odoo Budget' },
  { key: 'odooActualCost', label: 'Odoo Actual Cost' },
  { key: 'approval', label: 'Approval' },
  { key: 'auditLogs', label: 'Audit Logs' },
];

export function AdminPermissionsScreen() {
  return (
    <div>
      {/* Page header (contract §I.3) */}
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          Permissions & Roles
        </h1>
        <span className="text-caption text-text-muted">
          static_scaffold — no backend data
        </span>
      </div>

      {/* Tab bar — Role Matrix only (contract §E.7) */}
      <div className="mb-6 flex border-b border-border">
        <button
          type="button"
          className="border-b-2 border-accent px-4 py-2 text-label font-medium text-accent"
        >
          Role Matrix
        </button>
        <span className="px-4 py-2 text-label font-medium text-text-muted opacity-40">
          Entra Group Mapping
        </span>
        <span className="px-4 py-2 text-label font-medium text-text-muted opacity-40">
          Project Role Assignments
        </span>
      </div>

      {/* Table container (contract §D.7) */}
      <div className="overflow-hidden rounded-sm border border-border">
        <table className="w-full border-collapse">
          <thead>
            <tr className="h-10 border-b border-border bg-surface-raised">
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="px-3 py-2 text-left text-label font-medium text-text-secondary"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MATRIX_ROWS.map((row) => (
              <tr
                key={row.role}
                className="h-9 border-b border-border bg-surface-base transition-colors duration-150 hover:bg-surface-overlay"
              >
                <td className="px-3 py-2 font-mono text-mono text-text-primary">
                  {row.role}
                </td>
                {COLUMNS.slice(1).map((col) => (
                  <td
                    key={col.key}
                    className="px-3 py-2 text-body text-text-secondary"
                  >
                    {row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-caption text-text-muted">
        Source: docs/security/rbac_matrix.md. Changes require a spec update.
      </p>
    </div>
  );
}
