/**
 * Phase 2B Slice 5 — Permissions & Roles screen (`/admin/permissions`).
 *
 * Three tabs:
 *   1. Role Matrix     — static table from docs/security/rbac_matrix.md
 *   2. Entra Group Mapping — live CRUD via GET/PUT/DELETE /admin/entra-mappings
 *   3. Project Role Assignments — active placeholder linking to Source Mapping
 *
 * Locked spec: `docs/design/UI_CONTRACT_v1.md` §3.7.
 */
import { useCallback, useEffect, useState } from 'react';

import {
  Button,
  ConfirmDialog,
  SlideInPanel,
  useToasts,
} from '../components';
import { useApi } from '../api';
import { ApiError } from '../api';
import type {
  EntraGroupMapping,
  EntraGroupMappingListResponse,
  EntraGroupMappingUpsertRequest,
} from '../api';

// ---------------------------------------------------------------------------
// Tab 1 — Role Matrix (static, unchanged from Slice 7 scaffold)
// ---------------------------------------------------------------------------

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

function RoleMatrixTab() {
  return (
    <>
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
    </>
  );
}

// ---------------------------------------------------------------------------
// Tab 2 — Entra Group Mapping (live CRUD)
// ---------------------------------------------------------------------------

const CANONICAL_ROLES = [
  'executive',
  'project_manager',
  'finance',
  'commercial',
  'document_control',
  'procurement',
  'legal',
  'auditor',
  'admin',
];

function formatTs(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function EntraMappingTab() {
  const api = useApi();
  const { addToast } = useToasts();

  const [mappings, setMappings] = useState<EntraGroupMapping[]>([]);
  const [loading, setLoading] = useState(false);

  const [panelOpen, setPanelOpen] = useState(false);
  const [panelGroupId, setPanelGroupId] = useState('');
  const [panelRole, setPanelRole] = useState('');

  const [deleteTarget, setDeleteTarget] = useState<EntraGroupMapping | null>(null);

  const fetchMappings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<EntraGroupMappingListResponse>('/admin/entra-mappings');
      setMappings(data.mappings);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load mappings';
      addToast('error', message, 'Load error');
    } finally {
      setLoading(false);
    }
  }, [api, addToast]);

  useEffect(() => {
    void fetchMappings();
  }, [fetchMappings]);

  const openAdd = () => {
    setPanelGroupId('');
    setPanelRole('');
    setPanelOpen(true);
  };

  const openEdit = (m: EntraGroupMapping) => {
    setPanelGroupId(m.entra_group_id);
    setPanelRole(m.role);
    setPanelOpen(true);
  };

  const handleSave = async () => {
    const groupId = panelGroupId.trim();
    const role = panelRole.trim();
    if (!groupId || !role) {
      addToast('error', 'Group ID and role are required.', 'Validation');
      return;
    }
    try {
      const body: EntraGroupMappingUpsertRequest = { role };
      await api.put<EntraGroupMapping>(`/admin/entra-mappings/${encodeURIComponent(groupId)}`, body);
      addToast('success', 'Mapping saved.', 'Saved');
      setPanelOpen(false);
      await fetchMappings();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to save mapping';
      addToast('error', message, 'Save error');
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.delete(`/admin/entra-mappings/${encodeURIComponent(deleteTarget.entra_group_id)}`);
      addToast('success', 'Mapping deleted.', 'Deleted');
      setDeleteTarget(null);
      await fetchMappings();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to delete mapping';
      addToast('error', message, 'Delete error');
    }
  };

  const isEditing = panelGroupId.trim().length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-body text-text-secondary">
          Map Microsoft Entra ID groups to canonical RBAC roles. Any non-empty group ID is accepted; live Entra validation is deferred to Phase 2C.
        </p>
        <Button variant="primary" onClick={openAdd}>
          Add Mapping
        </Button>
      </div>

      <div className="overflow-hidden rounded-sm border border-border">
        <table className="w-full border-collapse">
          <thead>
            <tr className="h-10 border-b border-border bg-surface-raised">
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                Entra Group ID
              </th>
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                Role
              </th>
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                Created
              </th>
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                Updated
              </th>
              <th className="px-3 py-2 text-right text-label font-medium text-text-secondary">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {mappings.map((m) => (
              <tr
                key={m.entra_group_id}
                className="h-9 border-b border-border bg-surface-base transition-colors duration-150 hover:bg-surface-overlay"
              >
                <td className="px-3 py-2 font-mono text-mono text-text-primary">
                  {m.entra_group_id}
                </td>
                <td className="px-3 py-2 text-body text-text-secondary">{m.role}</td>
                <td className="px-3 py-2 text-body text-text-muted">{formatTs(m.created_at)}</td>
                <td className="px-3 py-2 text-body text-text-muted">{formatTs(m.updated_at)}</td>
                <td className="px-3 py-2 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="secondary" size="compact" onClick={() => openEdit(m)}>
                      Edit
                    </Button>
                    <Button
                      variant="danger"
                      size="compact"
                      onClick={() => setDeleteTarget(m)}
                    >
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
            {mappings.length === 0 && !loading && (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-8 text-center text-body text-text-muted"
                >
                  No mappings configured.
                </td>
              </tr>
            )}
            {loading && (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-8 text-center text-body text-text-muted"
                >
                  Loading…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <SlideInPanel
        isOpen={panelOpen}
        onClose={() => setPanelOpen(false)}
        title={isEditing ? 'Edit Mapping' : 'Add Mapping'}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-label font-medium text-text-primary">
              Entra Group ID
            </label>
            <input
              type="text"
              value={panelGroupId}
              disabled={isEditing}
              onChange={(e) => setPanelGroupId(e.target.value)}
              placeholder="e.g. 12345678-1234-1234-1234-123456789012"
              className="mt-2 h-10 w-full rounded-sm border border-border bg-surface-base px-3 text-body text-text-primary disabled:opacity-50"
            />
          </div>
          <div>
            <label className="block text-label font-medium text-text-primary">
              Role
            </label>
            <select
              value={panelRole}
              onChange={(e) => setPanelRole(e.target.value)}
              className="mt-2 h-10 w-full rounded-sm border border-border bg-surface-base px-3 text-body text-text-primary"
            >
              <option value="">— Select a role —</option>
              {CANONICAL_ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 pt-2">
            <Button variant="primary" onClick={handleSave}>
              Save
            </Button>
            <Button variant="secondary" onClick={() => setPanelOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </SlideInPanel>

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="Delete Mapping"
        confirmationText={deleteTarget?.entra_group_id ?? ''}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
      >
        <p className="text-body text-text-primary">
          This will permanently remove the mapping for group{' '}
          <span className="font-mono font-medium">{deleteTarget?.entra_group_id}</span>.
          This action cannot be undone.
        </p>
      </ConfirmDialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 3 — Project Role Assignments (active placeholder)
// ---------------------------------------------------------------------------

function ProjectAssignmentsTab() {
  return (
    <div className="space-y-4">
      <p className="text-body text-text-secondary">
        Project-level role assignments are managed in the{' '}
        <a
          href="#/admin/source-mapping"
          className="text-accent underline hover:text-accent-hover"
        >
          Source Mapping
        </a>{' '}
        screen. Use that screen to map users or groups to specific projects.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

type TabKey = 'matrix' | 'entra' | 'projects';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'matrix', label: 'Role Matrix' },
  { key: 'entra', label: 'Entra Group Mapping' },
  { key: 'projects', label: 'Project Role Assignments' },
];

export function AdminPermissionsScreen() {
  const [activeTab, setActiveTab] = useState<TabKey>('matrix');

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          Permissions & Roles
        </h1>
      </div>

      {/* Tab bar */}
      <div className="mb-6 flex border-b border-border">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={[
                'px-4 py-2 text-label font-medium',
                isActive
                  ? 'border-b-2 border-accent text-accent'
                  : 'text-text-muted hover:text-text-secondary',
              ].join(' ')}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {activeTab === 'matrix' && <RoleMatrixTab />}
      {activeTab === 'entra' && <EntraMappingTab />}
      {activeTab === 'projects' && <ProjectAssignmentsTab />}
    </div>
  );
}
