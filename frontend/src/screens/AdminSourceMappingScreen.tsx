/**
 * Phase 2B Slice 6 — Project Source Mapping screen (`/admin/source-mapping`).
 *
 * Live two-column editor wired to `GET/POST/PUT /admin/source-mappings`.
 * Left column: project list. Right column: editor with validation, diff preview,
 * risky-change confirmation, and disable.
 *
 * Locked spec: `docs/design/UI_CONTRACT_v1.md` §3.4.
 */
import { useCallback, useEffect, useState } from 'react';

import { Button, ConfirmDialog, StatusPill, useToasts } from '../components';
import { useApi } from '../api';
import { ApiError } from '../api';
import type {
  MicrosoftMappingConfirmRequest,
  MicrosoftMappingStatus,
  MicrosoftRescanResponse,
  EmailGroupEnrichmentResponse,
  EmailGroupProjectResult,
  OdooSharePointSyncResult,
  OdooSitePairResult,
  SiteCandidate,
  SourceMappingDetail,
  SourceMappingListResponse,
  SourceMappingSummary,
  SourceMappingUpsertRequest,
  SourceMappingValidateResponse,
  OdooSourceMapResponse,
  ValidationFieldError,
} from '../api';

import { OdooSourceMapPanel } from './OdooSourceMapPanel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function emptyForm(): SourceMappingUpsertRequest {
  return {
    project_name: '',
    contract_numbers: [],
    sharepoint: { site_id: '', drive_id: '', root_path: '' },
    owncloud: { base_path: '' },
    email: {
      shared_mailboxes: [],
      document_control_mailbox: '',
      client_domains: [],
      consultant_domains: [],
      contractor_domains: [],
    },
    microsoft: {
      group: { id: '', display_name: '', mail: '', mail_enabled: false },
      group_members: [],
      group_membership_status: '',
      member_count: 0,
      missing_permissions: [],
      blockers: [],
    },
    odoo: {
      project_model: '',
      cost_model: '',
      project_external_id: '',
      project_name: '',
      analytic_account_id: '',
    },
    related_people: {
      project_manager: '',
      commercial_manager: '',
      finance_owner: '',
      document_controller: '',
      other: [],
    },
    enabled_sources: [],
    allowed_roles: [],
  };
}

function formatTs(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function isRiskyChange(detail: SourceMappingDetail, form: SourceMappingUpsertRequest): boolean {
  const oldSources = new Set(detail.enabled_sources);
  const newSources = new Set(form.enabled_sources);
  const sourceRemoved = Array.from(oldSources).some((s) => !newSources.has(s));

  const oldRoles = new Set(detail.allowed_roles);
  const newRoles = new Set(form.allowed_roles);
  const roleRemoved = Array.from(oldRoles).some((r) => !newRoles.has(r));

  const odooChanged = form.odoo.project_external_id !== detail.odoo.project_external_id;
  const spChanged = form.sharepoint.root_path !== detail.sharepoint.root_path;
  const ocChanged = form.owncloud.base_path !== detail.owncloud.base_path;

  return sourceRemoved || roleRemoved || odooChanged || spChanged || ocChanged;
}

function statusPillVariant(status: string): 'connected' | 'degraded' | 'disconnected' {
  if (status === 'complete') return 'connected';
  if (status === 'disabled') return 'disconnected';
  return 'degraded';
}

function groupStatusVariant(status: string, hasMailbox: boolean): 'connected' | 'degraded' | 'disconnected' {
  if (hasMailbox && (status === 'GROUP_MEMBERS_READ' || status === 'GROUP_FOUND_NO_MEMBERS')) return 'connected';
  if (status.startsWith('BLOCKED') || status === 'NO_GROUP_SOURCE' || status === 'NO_SHAREPOINT_SITE') {
    return 'disconnected';
  }
  return 'degraded';
}

function isPlaceholderValue(value: string): boolean {
  const lower = value.trim().toLowerCase();
  return (
    lower.includes('example-') ||
    lower.includes('example.com') ||
    /^\/projects\/prj-\d+(?:\/|$)/.test(lower)
  );
}

function realEmail(value: string): boolean {
  const trimmed = value.trim();
  return trimmed.includes('@') && !isPlaceholderValue(trimmed);
}

function collectLocalBlockers(form: SourceMappingUpsertRequest): ValidationFieldError[] {
  const errors: ValidationFieldError[] = [];
  const add = (field: string, message: string) => {
    if (!errors.some((e) => e.field === field && e.message === message)) {
      errors.push({ field, message });
    }
  };
  const placeholder = (field: string, value: string) => {
    if (value && isPlaceholderValue(value)) {
      add(field, 'Placeholder value is not allowed');
    }
  };
  const placeholderList = (field: string, values: string[]) => {
    values.forEach((v) => placeholder(field, v));
  };

  if (form.enabled_sources.length === 0) {
    add('enabled_sources', 'At least one verified source must be enabled');
  }

  placeholder('project_name', form.project_name);
  placeholderList('contract_numbers', form.contract_numbers);
  placeholder('sharepoint.site_id', form.sharepoint.site_id);
  placeholder('sharepoint.drive_id', form.sharepoint.drive_id);
  placeholder('sharepoint.root_path', form.sharepoint.root_path);
  placeholder('owncloud.base_path', form.owncloud.base_path);
  placeholderList('email.shared_mailboxes', form.email.shared_mailboxes);
  placeholder('email.document_control_mailbox', form.email.document_control_mailbox);
  placeholderList('email.client_domains', form.email.client_domains);
  placeholderList('email.consultant_domains', form.email.consultant_domains);
  placeholderList('email.contractor_domains', form.email.contractor_domains);
  placeholder('microsoft.group.id', form.microsoft.group.id);
  placeholder('microsoft.group.display_name', form.microsoft.group.display_name);
  placeholder('microsoft.group.mail', form.microsoft.group.mail);
  placeholder('microsoft.group_membership_status', form.microsoft.group_membership_status);
  placeholderList('microsoft.missing_permissions', form.microsoft.missing_permissions);
  placeholderList('microsoft.blockers', form.microsoft.blockers);
  form.microsoft.group_members.forEach((member) => {
    placeholder('microsoft.group_members.id', member.id);
    placeholder('microsoft.group_members.display_name', member.display_name);
    placeholder('microsoft.group_members.mail', member.mail);
    placeholder('microsoft.group_members.user_principal_name', member.user_principal_name);
    placeholder('microsoft.group_members.job_title', member.job_title);
    placeholder('microsoft.group_members.department', member.department);
    placeholder('microsoft.group_members.email', member.email);
  });
  placeholder('odoo.project_external_id', form.odoo.project_external_id);
  placeholder('odoo.project_name', form.odoo.project_name);
  placeholder('odoo.project_model', form.odoo.project_model);
  placeholder('odoo.cost_model', form.odoo.cost_model);
  placeholder('odoo.analytic_account_id', form.odoo.analytic_account_id);

  if (form.microsoft.group_membership_status.trim().toUpperCase().startsWith('BLOCKED')) {
    add('microsoft.group_membership_status', 'Email group enrichment is blocked');
  }
  if (form.microsoft.missing_permissions.length > 0) {
    add('microsoft.missing_permissions', 'Required Graph group/member permission is missing');
  }
  if (form.microsoft.blockers.length > 0) {
    add('microsoft.blockers', 'Source mapping has unresolved Microsoft group/email blockers');
  }

  if (form.enabled_sources.includes('sharepoint')) {
    if (!form.sharepoint.site_id) add('sharepoint.site_id', 'Required for SharePoint source');
    if (!form.sharepoint.drive_id) add('sharepoint.drive_id', 'Required for SharePoint source');
    if (!form.sharepoint.root_path) add('sharepoint.root_path', 'Required for SharePoint source');
  }

  if (form.enabled_sources.includes('owncloud')) {
    add('enabled_sources', 'ownCloud cannot be enabled until ownCloud is configured');
    if (!form.owncloud.base_path) add('owncloud.base_path', 'Required for ownCloud source');
  }

  if (form.enabled_sources.includes('email')) {
    const mailboxes = [...form.email.shared_mailboxes, form.email.document_control_mailbox];
    const groupMailboxValid = form.microsoft.group.mail_enabled && realEmail(form.microsoft.group.mail);
    const memberEmails = new Set(
      form.microsoft.group_members.map((member) => member.email.trim().toLowerCase()).filter(Boolean),
    );
    mailboxes.forEach((mailbox) => {
      if (realEmail(mailbox) && memberEmails.has(mailbox.trim().toLowerCase())) {
        add('email.shared_mailboxes', 'Group members must be stored under microsoft.group_members');
      }
    });
    if (form.microsoft.group.mail.trim() && !form.microsoft.group.mail_enabled) {
      add('microsoft.group.mail_enabled', 'Group mailbox must be mailEnabled');
    }
    if (!mailboxes.some(realEmail) && !groupMailboxValid) {
      add('email.shared_mailboxes', 'At least one real mailbox or Microsoft 365 group mailbox required');
    }
  }

  if (form.enabled_sources.includes('odoo')) {
    const externalId = form.odoo.project_external_id.trim();
    if (!externalId) add('odoo.project_external_id', 'Real Odoo project ID is required');
    else if (/^PRJ-\d+$/i.test(externalId)) {
      add('odoo.project_external_id', 'Internal PRJ codes cannot be used as Odoo external IDs');
    } else if (!/^\d+$/.test(externalId)) {
      add('odoo.project_external_id', 'Odoo project external ID must be numeric');
    }
    if (!form.odoo.project_name.trim()) add('odoo.project_name', 'Odoo project name is required');
    if (form.project_name.trim() && form.odoo.project_name.trim() && form.project_name.trim() !== form.odoo.project_name.trim()) {
      add('project_name', 'Project Name must match Odoo project.project.name');
    }
    if (!form.odoo.project_model) add('odoo.project_model', 'Odoo project model is required');
    if (!form.odoo.cost_model) add('odoo.cost_model', 'Odoo cost model is required');
  }

  return errors;
}

// ---------------------------------------------------------------------------
// DiffPreviewModal (local component)
// ---------------------------------------------------------------------------

function DiffPreviewModal({
  isOpen,
  projectCode,
  oldData,
  newData,
  onClose,
  onConfirm,
}: {
  isOpen: boolean;
  projectCode: string;
  oldData: SourceMappingDetail | null;
  newData: SourceMappingUpsertRequest;
  onClose: () => void;
  onConfirm: () => void;
}) {
  if (!isOpen) return null;

  const changes: { field: string; old?: string; new: string; type: 'add' | 'change' }[] = [];

  const push = (field: string, oldVal: string | undefined, newVal: string) => {
    if (oldVal === undefined) {
      changes.push({ field, new: newVal, type: 'add' });
    } else if (oldVal !== newVal) {
      changes.push({ field, old: oldVal, new: newVal, type: 'change' });
    }
  };

  push('Project Name', oldData?.project_name, newData.project_name);
  push('Contract Numbers', oldData?.contract_numbers.join(', '), newData.contract_numbers.join(', '));
  push('SharePoint Site ID', oldData?.sharepoint.site_id, newData.sharepoint.site_id);
  push('SharePoint Drive ID', oldData?.sharepoint.drive_id, newData.sharepoint.drive_id);
  push('SharePoint Root Path', oldData?.sharepoint.root_path, newData.sharepoint.root_path);
  push('ownCloud Base Path', oldData?.owncloud.base_path, newData.owncloud.base_path);
  push('Email Shared Mailboxes', oldData?.email.shared_mailboxes.join(', '), newData.email.shared_mailboxes.join(', '));
  push('Email Doc Control', oldData?.email.document_control_mailbox, newData.email.document_control_mailbox);
  push('Microsoft Group ID', oldData?.microsoft.group.id, newData.microsoft.group.id);
  push('Microsoft Group Display Name', oldData?.microsoft.group.display_name, newData.microsoft.group.display_name);
  push('Microsoft Group Mailbox', oldData?.microsoft.group.mail, newData.microsoft.group.mail);
  push('Microsoft Group Status', oldData?.microsoft.group_membership_status, newData.microsoft.group_membership_status);
  push('Microsoft Member Count', String(oldData?.microsoft.member_count ?? 0), String(newData.microsoft.member_count));
  push('Odoo Project External ID', oldData?.odoo.project_external_id, newData.odoo.project_external_id);
  push('Odoo Project Name', oldData?.odoo.project_name, newData.odoo.project_name);
  push('Odoo Project Model', oldData?.odoo.project_model, newData.odoo.project_model);
  push('Odoo Cost Model', oldData?.odoo.cost_model, newData.odoo.cost_model);
  push('Odoo Analytic Account ID', oldData?.odoo.analytic_account_id, newData.odoo.analytic_account_id);
  push('Related PM', oldData?.related_people.project_manager, newData.related_people.project_manager);
  push('Related Commercial', oldData?.related_people.commercial_manager, newData.related_people.commercial_manager);
  push('Related Finance', oldData?.related_people.finance_owner, newData.related_people.finance_owner);
  push('Related Doc Control', oldData?.related_people.document_controller, newData.related_people.document_controller);
  push('Enabled Sources', oldData?.enabled_sources.join(', '), newData.enabled_sources.join(', '));
  push('Allowed Roles', oldData?.allowed_roles.join(', '), newData.allowed_roles.join(', '));

  if (changes.length === 0) {
    changes.push({ field: 'No changes detected', new: '', type: 'add' });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-sm border border-border bg-surface-raised p-6 shadow-lg">
        <h2 className="mb-4 text-heading font-semibold text-text-primary">
          Review changes — {projectCode}
        </h2>
        <div className="space-y-2">
          {changes.map((c) => (
            <div key={c.field} className="flex items-start gap-2 text-body">
              {c.type === 'add' ? (
                <span className="text-success">+</span>
              ) : (
                <span className="text-warning">~</span>
              )}
              <span className="text-text-secondary">{c.field}:</span>
              {c.type === 'change' ? (
                <span className="text-text-primary">
                  <span className="line-through opacity-50">{c.old}</span>
                  {' → '}
                  <span className="font-medium">{c.new}</span>
                </span>
              ) : (
                <span className="font-medium text-text-primary">{c.new}</span>
              )}
            </div>
          ))}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onConfirm}>
            Confirm Save
          </Button>
        </div>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// RescanPanel (local component)
// ---------------------------------------------------------------------------

function spStatusVariant(status: MicrosoftMappingStatus): 'connected' | 'degraded' | 'disconnected' {
  if (status === 'AUTO_MAPPED') return 'connected';
  if (status === 'MISSING_SHAREPOINT' || status === 'DISABLED') return 'disconnected';
  return 'degraded';
}

function RescanPanel({
  isOpen,
  result,
  onClose,
  onAccept,
  acceptingCode,
}: {
  isOpen: boolean;
  result: MicrosoftRescanResponse | null;
  onClose: () => void;
  onAccept: (code: string, candidate: SiteCandidate) => Promise<void>;
  acceptingCode: string | null;
}) {
  if (!isOpen || !result) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[80vh] w-full max-w-3xl overflow-auto rounded-sm border border-border bg-surface-raised p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-heading font-semibold text-text-primary">Microsoft Source Rescan</h2>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-4 text-caption text-text-muted">
          <span>Scanned: {new Date(result.scanned_at).toLocaleString()}</span>
          <StatusPill
            status={result.has_sites_read_all ? 'connected' : 'disconnected'}
            label="Sites.Read.All"
          />
          <StatusPill
            status={result.has_mail_read ? 'connected' : 'disconnected'}
            label="Mail.Read"
          />
          <span>{result.total_sites_discovered} site(s) discovered</span>
        </div>

        {result.project_results.length === 0 && (
          <p className="text-body text-text-muted">{result.summary}</p>
        )}

        <div className="space-y-4">
          {result.project_results.map((prj) => (
            <div
              key={prj.project_code}
              className="rounded-sm border border-border bg-surface-base p-4"
            >
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-mono font-medium text-text-primary">
                    {prj.project_code}
                  </span>
                  {prj.project_name && (
                    <span className="text-body text-text-secondary">{prj.project_name}</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill
                    status={spStatusVariant(prj.sharepoint_status)}
                    label={`SP: ${prj.sharepoint_status}`}
                  />
                  <StatusPill
                    status={spStatusVariant(prj.mailbox_status)}
                    label={`Mail: ${prj.mailbox_status}`}
                  />
                </div>
              </div>

              <p className="mb-3 text-caption text-text-muted">{prj.reason}</p>

              {prj.sharepoint_status === 'NEEDS_CONFIRMATION' && prj.site_candidates.length > 0 && (
                <div className="space-y-2">
                  <p className="text-caption font-medium text-text-secondary">
                    Candidates — select one to accept:
                  </p>
                  {prj.site_candidates.map((c) => (
                    <div
                      key={c.site_id}
                      className="flex items-center justify-between rounded-sm border border-border bg-surface-raised px-3 py-2"
                    >
                      <div>
                        <p className="text-body text-text-primary">{c.display_name}</p>
                        <p className="text-caption text-text-muted">
                          {c.match_strength} · {Math.round(c.confidence * 100)}% confidence
                          {c.root_item_count != null && ` · ${c.root_item_count} items`}
                        </p>
                        <p className="truncate text-caption text-text-muted">{c.web_url}</p>
                      </div>
                      <Button
                        variant="primary"
                        size="compact"
                        onClick={() => void onAccept(prj.project_code, c)}
                        isLoading={acceptingCode === prj.project_code}
                      >
                        Accept
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {prj.sharepoint_status === 'AUTO_MAPPED' && prj.recommended_site_id && (
                <div className="text-caption text-success">
                  Auto-mapped:{' '}
                  {prj.site_candidates.find((c) => c.site_id === prj.recommended_site_id)
                    ?.display_name ?? prj.recommended_site_id}
                  {prj.recommended_drive_id && (
                    <>
                      {' · Drive: '}
                      <span className="font-mono">{prj.recommended_drive_id.slice(0, 14)}…</span>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        <p className="mt-4 text-caption text-text-muted">{result.summary}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmailGroupEnrichPanel (local component)
// ---------------------------------------------------------------------------

function enrichGroupVariant(r: EmailGroupProjectResult): 'connected' | 'degraded' | 'disconnected' {
  if (r.email_enabled && r.blockers.length === 0) return 'connected';
  if (r.group.id) return 'degraded';
  return 'disconnected';
}

function EmailGroupEnrichPanel({
  isOpen,
  result,
  onClose,
}: {
  isOpen: boolean;
  result: EmailGroupEnrichmentResponse | null;
  onClose: () => void;
}) {
  if (!isOpen || !result) return null;

  const missingPerms = result.missing_permissions;
  const blocked = result.verdict.startsWith('SOURCE_MAPPING_EMAIL_GROUP_BLOCKED');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[80vh] w-full max-w-3xl overflow-auto rounded-sm border border-border bg-surface-raised p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-heading font-semibold text-text-primary">Email Group Enrichment</h2>
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </div>

        {/* Compliance badges */}
        <div className="mb-4 flex flex-wrap gap-2">
          <span className="rounded bg-success/10 px-2 py-0.5 text-caption text-success">
            Odoo emails: not used
          </span>
          <span className="rounded bg-success/10 px-2 py-0.5 text-caption text-success">
            ownCloud: disabled
          </span>
          <span className="rounded bg-surface-overlay px-2 py-0.5 font-mono text-caption text-text-muted">
            {result.verdict}
          </span>
        </div>

        <p className="mb-4 break-all font-mono text-caption text-text-muted">{result.summary}</p>

        {result.token_roles.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-1">
            {result.token_roles.map((r) => (
              <span
                key={r}
                className="rounded bg-surface-overlay px-1.5 py-0.5 font-mono text-caption text-text-muted"
              >
                {r}
              </span>
            ))}
          </div>
        )}

        {blocked && missingPerms.length > 0 && (
          <div className="mb-4 rounded-sm border border-error/40 bg-error/10 p-3">
            <p className="mb-1 text-label font-medium text-error">Missing Graph permissions</p>
            {missingPerms.map((p) => (
              <p key={p} className="font-mono text-caption text-text-secondary">{p}</p>
            ))}
          </div>
        )}

        {result.project_results.length > 0 && (
          <div className="mb-4 space-y-3">
            <p className="text-label font-medium text-text-secondary">Project results</p>
            {result.project_results.map((pr) => (
              <div
                key={pr.project_code}
                className="rounded-sm border border-border bg-surface-base p-3"
              >
                <div className="mb-2 flex items-center justify-between">
                  <div>
                    <p className="text-body font-medium text-text-primary">
                      {pr.project_name || pr.project_code}
                    </p>
                    <p className="font-mono text-caption text-text-muted">{pr.project_code}</p>
                  </div>
                  <StatusPill
                    status={enrichGroupVariant(pr)}
                    label={
                      pr.email_enabled
                        ? 'Email enabled'
                        : pr.group.id
                          ? 'Group found'
                          : 'No group'
                    }
                  />
                </div>
                <div className="space-y-1 text-caption text-text-muted">
                  <p>
                    <span className="text-text-secondary">Status: </span>
                    {pr.group_membership_status || 'PENDING'}
                  </p>
                  {pr.group.id && (
                    <>
                      <p>
                        <span className="text-text-secondary">Group: </span>
                        {pr.group.display_name}
                        {pr.group.mail ? ` · ${pr.group.mail}` : ''}
                        {pr.group.mail_enabled ? ' (mail-enabled)' : ' (not mail-enabled)'}
                      </p>
                      <p>
                        <span className="text-text-secondary">Members: </span>
                        {pr.member_count === 0 ? 'none read' : `${pr.member_count} read`}
                      </p>
                    </>
                  )}
                  {pr.blockers.length > 0 && (
                    <p className="text-warning">Blockers: {pr.blockers.join(', ')}</p>
                  )}
                  {pr.missing_permissions.length > 0 && (
                    <p className="text-warning">
                      Missing permissions: {pr.missing_permissions.join(', ')}
                    </p>
                  )}
                </div>
                {pr.group_members.length > 0 && (
                  <div className="mt-2 max-h-40 overflow-auto rounded-sm border border-border bg-surface-raised p-2">
                    <p className="mb-1 text-caption font-medium text-text-secondary">
                      Members ({pr.group_members.length})
                    </p>
                    {pr.group_members.map((m) => (
                      <div key={m.id || m.email} className="text-caption text-text-muted">
                        {m.display_name || m.email}
                        {m.job_title ? ` · ${m.job_title}` : ''}
                        {m.department ? ` · ${m.department}` : ''}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// OdooSyncPanel (local component)
// ---------------------------------------------------------------------------

function syncMatchVariant(pair: OdooSitePairResult): 'connected' | 'degraded' | 'disconnected' {
  if (pair.auto_saved) return 'connected';
  if (pair.save_skipped_reason) return 'degraded';
  return 'disconnected';
}

function OdooSyncPanel({
  isOpen,
  result,
  onClose,
}: {
  isOpen: boolean;
  result: OdooSharePointSyncResult | null;
  onClose: () => void;
}) {
  if (!isOpen || !result) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[80vh] w-full max-w-3xl overflow-auto rounded-sm border border-border bg-surface-raised p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-heading font-semibold text-text-primary">Sync Odoo + SharePoint</h2>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>

        {/* Summary row */}
        <div className="mb-4 flex flex-wrap items-center gap-4 text-caption text-text-muted">
          <span>Scanned: {new Date(result.scanned_at).toLocaleString()}</span>
          <StatusPill
            status={result.odoo_configured ? 'connected' : 'disconnected'}
            label={`Odoo: ${result.odoo_configured ? 'configured' : 'not configured'}`}
          />
          <StatusPill
            status={result.sharepoint_configured ? 'connected' : 'disconnected'}
            label={`SharePoint: ${result.sharepoint_configured ? 'configured' : 'not configured'}`}
          />
          <span>{result.odoo_projects_scanned} Odoo project(s)</span>
          <span>{result.sharepoint_sites_scanned} SharePoint site(s)</span>
        </div>

        {/* Match counters */}
        <div className="mb-4 grid grid-cols-4 gap-3 text-center">
          {[
            { label: 'Exact matches', value: result.exact_matches },
            { label: 'Auto-saved', value: result.auto_saved_count },
            { label: 'No match', value: result.no_match_count },
            { label: 'Multi-match', value: result.multiple_match_count },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-sm border border-border bg-surface-base p-2">
              <p className="text-display font-semibold text-text-primary">{value}</p>
              <p className="text-caption text-text-muted">{label}</p>
            </div>
          ))}
        </div>

        {/* Matched pairs */}
        {result.matched_pairs.length > 0 && (
          <div className="mb-4 space-y-3">
            <p className="text-label font-medium text-text-secondary">Matched pairs</p>
            {result.matched_pairs.map((pair) => (
              <div
                key={pair.internal_key}
                className="rounded-sm border border-border bg-surface-base p-3"
              >
                <div className="mb-2 flex items-center justify-between">
                  <div>
                    <p className="text-body font-medium text-text-primary">{pair.odoo_project_name}</p>
                    <p className="text-caption text-text-muted font-mono">{pair.internal_key}</p>
                  </div>
                  <StatusPill
                    status={syncMatchVariant(pair)}
                    label={pair.auto_saved ? 'Auto-saved' : (pair.save_skipped_reason ? 'Skipped' : 'Not saved')}
                  />
                </div>
                <div className="space-y-1 text-caption text-text-muted">
                  <p>
                    <span className="text-text-secondary">SharePoint site:</span>{' '}
                    {pair.sharepoint_display_name || pair.sharepoint_site_name}
                  </p>
                  <p>
                    <span className="text-text-secondary">Match:</span>{' '}
                    {pair.mapping_method} · confidence={pair.match_confidence}%
                  </p>
                  <p>
                    <span className="text-text-secondary">Members ({pair.project_member_emails.length}):</span>{' '}
                    {pair.project_member_emails.length > 0
                      ? pair.project_member_emails.join(', ')
                      : `none (${pair.member_read_status})`}
                  </p>
                  {pair.save_skipped_reason && (
                    <p className="text-warning">Skipped: {pair.save_skipped_reason}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Unmatched Odoo */}
        {result.unmatched_odoo_names.length > 0 && (
          <div className="mb-3">
            <p className="mb-1 text-label font-medium text-text-secondary">
              Unmatched Odoo projects ({result.unmatched_odoo_names.length})
            </p>
            <div className="flex flex-wrap gap-2">
              {result.unmatched_odoo_names.map((n) => (
                <span key={n} className="rounded bg-surface-overlay px-2 py-0.5 text-caption text-text-muted">
                  {n}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Confirmation badges */}
        <div className="mt-4 flex flex-wrap gap-3 border-t border-border pt-3 text-caption text-text-muted">
          <StatusPill
            status={result.odoo_emails_used ? 'disconnected' : 'connected'}
            label="Odoo emails: not used"
          />
          <StatusPill
            status={result.odoo_followers_used ? 'disconnected' : 'connected'}
            label="Odoo followers: not used"
          />
          <span className="text-text-muted">{result.summary}</span>
        </div>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Main screen
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

const SOURCE_OPTIONS = [
  { key: 'sharepoint', label: 'SharePoint' },
  { key: 'owncloud', label: 'ownCloud' },
  { key: 'email', label: 'Email' },
  { key: 'odoo', label: 'Odoo' },
];

export function AdminSourceMappingScreen() {
  const api = useApi();
  const { addToast } = useToasts();

  const [mappings, setMappings] = useState<SourceMappingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [detail, setDetail] = useState<SourceMappingDetail | null>(null);
  const [, setDetailLoading] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [newCodeInput, setNewCodeInput] = useState('');
  const [form, setForm] = useState<SourceMappingUpsertRequest>(emptyForm);
  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);
  const [validating, setValidating] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [showRiskyConfirm, setShowRiskyConfirm] = useState(false);
  const [showDisableConfirm, setShowDisableConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [disabling, setDisabling] = useState(false);
  const [rescanLoading, setRescanLoading] = useState(false);
  const [showRescan, setShowRescan] = useState(false);
  const [rescanResult, setRescanResult] = useState<MicrosoftRescanResponse | null>(null);
  const [acceptingCode, setAcceptingCode] = useState<string | null>(null);
  const [enrichLoading, setEnrichLoading] = useState(false);
  const [showEnrich, setShowEnrich] = useState(false);
  const [enrichResult, setEnrichResult] = useState<EmailGroupEnrichmentResponse | null>(null);
  const [odooSyncLoading, setOdooSyncLoading] = useState(false);
  const [showOdooSync, setShowOdooSync] = useState(false);
  const [odooSyncResult, setOdooSyncResult] = useState<OdooSharePointSyncResult | null>(null);
  const [activeTab, setActiveTab] = useState<'mapping' | 'sourcemap'>('mapping');
  const [sourceMap, setSourceMap] = useState<OdooSourceMapResponse | null>(null);
  const [sourceMapLoading, setSourceMapLoading] = useState(false);
  const [scanning, setScanning] = useState(false);

  const fetchMappings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<SourceMappingListResponse>('/admin/source-mappings');
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

  const fetchDetail = useCallback(
    async (code: string) => {
      setDetailLoading(true);
      try {
        const data = await api.get<SourceMappingDetail>(`/admin/source-mappings/${encodeURIComponent(code)}`);
        setDetail(data);
        setForm({
          project_name: data.project_name,
          contract_numbers: data.contract_numbers,
          sharepoint: { ...data.sharepoint },
          owncloud: { ...data.owncloud },
          email: { ...data.email },
          microsoft: data.microsoft
            ? {
                group: { ...data.microsoft.group },
                group_members: data.microsoft.group_members.map((member) => ({ ...member })),
                group_membership_status: data.microsoft.group_membership_status,
                member_count: data.microsoft.member_count,
                missing_permissions: [...data.microsoft.missing_permissions],
                blockers: [...data.microsoft.blockers],
              }
            : emptyForm().microsoft,
          odoo: { ...data.odoo },
          related_people: { ...data.related_people },
          enabled_sources: [...data.enabled_sources],
          allowed_roles: [...data.allowed_roles],
        });
        setValidationErrors([]);
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Failed to load detail';
        addToast('error', message, 'Detail error');
      } finally {
        setDetailLoading(false);
      }
    },
    [api, addToast],
  );

  const handleSelect = (code: string) => {
    setSelectedCode(code);
    setIsAdding(false);
    setNewCodeInput('');
    setActiveTab('mapping');
    setSourceMap(null);
    void fetchDetail(code);
  };

  const handleAdd = () => {
    setIsAdding(true);
    setSelectedCode(null);
    setDetail(null);
    setForm(emptyForm());
    setNewCodeInput('');
    setValidationErrors([]);
    setActiveTab('mapping');
    setSourceMap(null);
  };

  const updateForm = (patch: Partial<SourceMappingUpsertRequest>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  };

  const toggleSource = (key: string) => {
    setForm((prev) => {
      const next = new Set(prev.enabled_sources);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return { ...prev, enabled_sources: Array.from(next) };
    });
  };

  const toggleRole = (role: string) => {
    setForm((prev) => {
      const next = new Set(prev.allowed_roles);
      if (next.has(role)) next.delete(role);
      else next.add(role);
      return { ...prev, allowed_roles: Array.from(next) };
    });
  };

  const handleValidate = async () => {
    const activeCode = isAdding ? newCodeInput.trim() : selectedCode;
    if (!activeCode) {
      addToast('error', 'Project code is required.', 'Validation');
      return;
    }
    setValidating(true);
    try {
      const result = await api.post<SourceMappingValidateResponse>(
        `/admin/source-mappings/${encodeURIComponent(activeCode)}/validate`,
        form,
      );
      setValidationErrors(result.errors);
      addToast(
        result.valid ? 'success' : 'warning',
        result.valid ? 'Validation passed' : `${result.errors.length} field(s) need attention`,
        'Validate',
      );
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Validation failed';
      addToast('error', message, 'Validation error');
    } finally {
      setValidating(false);
    }
  };

  const handleSave = () => {
    setShowDiff(true);
  };

  const handleDiffConfirm = () => {
    setShowDiff(false);
    if (detail && isRiskyChange(detail, form)) {
      setShowRiskyConfirm(true);
    } else {
      void doSave();
    }
  };

  const doSave = async () => {
    const activeCode = isAdding ? newCodeInput.trim() : selectedCode;
    if (!activeCode) {
      addToast('error', 'Project code is required.', 'Validation');
      return;
    }
    setSubmitting(true);
    try {
      const saved = await api.put<SourceMappingDetail>(
        `/admin/source-mappings/${encodeURIComponent(activeCode)}`,
        form,
      );
      setDetail(saved);
      setSelectedCode(activeCode);
      setIsAdding(false);
      await fetchMappings();
      addToast('success', 'Saved. Changes affect the next report request.', 'Source Mapping');
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Save failed';
      addToast('error', message, 'Save error');
    } finally {
      setSubmitting(false);
      setShowRiskyConfirm(false);
    }
  };

  const handleDisableConfirm = async () => {
    if (!selectedCode) return;
    setDisabling(true);
    try {
      await api.post<void>(`/admin/source-mappings/${encodeURIComponent(selectedCode)}/disable`, {});
      await fetchMappings();
      const refreshed = await api.get<SourceMappingDetail>(
        `/admin/source-mappings/${encodeURIComponent(selectedCode)}`,
      );
      setDetail(refreshed);
      addToast('success', 'Mapping disabled.', 'Source Mapping');
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Disable failed';
      addToast('error', message, 'Disable error');
    } finally {
      setDisabling(false);
      setShowDisableConfirm(false);
    }
  };

  const handleRescan = async () => {
    setRescanLoading(true);
    try {
      const result = await api.post<MicrosoftRescanResponse>('/admin/microsoft-mapping/rescan', {
        project_codes: [],
      });
      setRescanResult(result);
      setShowRescan(true);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Rescan failed';
      addToast('error', message, 'Rescan');
    } finally {
      setRescanLoading(false);
    }
  };

  const handleEnrichEmailGroups = async () => {
    setEnrichLoading(true);
    try {
      // Empty list defers to the backend's supported enrichment scope
      // (pilot: PRJ-001/PRJ-002), keeping the scope defined in one place.
      const result = await api.post<EmailGroupEnrichmentResponse>(
        '/admin/source-mappings/enrich-email-groups',
        { project_codes: [] },
      );
      setEnrichResult(result);
      setShowEnrich(true);
      void fetchMappings();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Email group enrichment failed';
      addToast('error', message, 'Enrichment error');
    } finally {
      setEnrichLoading(false);
    }
  };

  const handleOdooSync = async () => {
    setOdooSyncLoading(true);
    try {
      const result = await api.post<OdooSharePointSyncResult>(
        '/admin/source-mappings/sync-odoo-sharepoint',
        {},
      );
      setOdooSyncResult(result);
      setShowOdooSync(true);
      if (result.auto_saved_count > 0) {
        await fetchMappings();
        addToast(
          'success',
          `${result.auto_saved_count} mapping(s) auto-saved from exact Odoo↔SharePoint match.`,
          'Odoo Sync',
        );
      } else if (result.exact_matches === 0) {
        addToast('warning', 'No exact Odoo↔SharePoint name matches found.', 'Odoo Sync');
      } else {
        addToast('info', `${result.exact_matches} match(es) found; check panel for details.`, 'Odoo Sync');
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Sync failed';
      addToast('error', message, 'Odoo Sync');
    } finally {
      setOdooSyncLoading(false);
    }
  };

  const handleAcceptCandidate = async (code: string, candidate: SiteCandidate) => {
    setAcceptingCode(code);
    try {
      const body: MicrosoftMappingConfirmRequest = {
        site_id: candidate.site_id,
        drive_id: candidate.drive_id ?? '',
      };
      await api.post<SourceMappingDetail>(
        `/admin/microsoft-mapping/${encodeURIComponent(code)}/confirm`,
        body,
      );
      addToast('success', `${code} mapping confirmed.`, 'Rescan');
      const refreshed = await api.post<MicrosoftRescanResponse>(
        '/admin/microsoft-mapping/rescan',
        { project_codes: [code] },
      );
      setRescanResult((prev) => {
        if (!prev) return refreshed;
        return {
          ...prev,
          project_results: prev.project_results.map((p) =>
            p.project_code === code ? (refreshed.project_results[0] ?? p) : p,
          ),
        };
      });
      await fetchMappings();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Confirm failed';
      addToast('error', message, 'Confirm error');
    } finally {
      setAcceptingCode(null);
    }
  };

  const fetchSourceMap = useCallback(
    async (code: string) => {
      setSourceMapLoading(true);
      try {
        const data = await api.get<OdooSourceMapResponse>(
          `/admin/source-mappings/${encodeURIComponent(code)}/odoo-source-map`,
        );
        setSourceMap(data);
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Failed to load Odoo source map';
        addToast('error', message, 'Source Map');
      } finally {
        setSourceMapLoading(false);
      }
    },
    [api, addToast],
  );

  useEffect(() => {
    if (activeTab === 'sourcemap' && selectedCode && !isAdding) {
      void fetchSourceMap(selectedCode);
    }
  }, [activeTab, selectedCode, isAdding, fetchSourceMap]);

  const handleScan = async () => {
    if (!selectedCode) return;
    setScanning(true);
    try {
      const data = await api.post<OdooSourceMapResponse>(
        `/admin/source-mappings/${encodeURIComponent(selectedCode)}/odoo-source-map/scan`,
        {},
      );
      setSourceMap(data);
      addToast('success', 'Odoo source scan complete.', 'Source Map');
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Odoo source scan failed';
      addToast('error', message, 'Source Map');
    } finally {
      setScanning(false);
    }
  };

  const localValidationErrors = collectLocalBlockers(form);
  const activeValidationErrors = [...validationErrors];
  localValidationErrors.forEach((err) => {
    if (!activeValidationErrors.some((e) => e.field === err.field && e.message === err.message)) {
      activeValidationErrors.push(err);
    }
  });
  const fieldError = (field: string) =>
    activeValidationErrors.find((e) => e.field === field)?.message;
  const detailStatus =
    detail && detail.mapping_status === 'complete' && activeValidationErrors.length > 0
      ? 'incomplete'
      : detail?.mapping_status;
  const groupMailboxVerified = form.microsoft.group.mail_enabled && realEmail(form.microsoft.group.mail);
  const groupStatus = form.microsoft.group_membership_status || 'Missing';
  const emailSourceEnabled = form.enabled_sources.includes('email');
  const editorVisible = selectedCode !== null || isAdding;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-display font-semibold text-text-primary">Project Source Mapping</h1>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => void handleEnrichEmailGroups()} isLoading={enrichLoading}>
            Enrich Email Groups
          </Button>
          <Button variant="secondary" onClick={() => void handleOdooSync()} isLoading={odooSyncLoading}>
            Sync Odoo + SharePoint
          </Button>
          <Button variant="secondary" onClick={() => void handleRescan()} isLoading={rescanLoading}>
            Rescan Microsoft Sources
          </Button>
        </div>
      </div>

      {/* Two-column card */}
      <div className="flex overflow-hidden rounded-md border border-border bg-surface-raised">
        {/* Left column — project list (280px) */}
        <div className="w-[280px] shrink-0 border-r border-border">
          <div className="flex h-10 items-center justify-between border-b border-border bg-surface-base px-3 py-2">
            <span className="text-label font-medium text-text-secondary">Projects</span>
            <Button variant="primary" size="compact" onClick={handleAdd}>
              + Add
            </Button>
          </div>
          <div className="divide-y divide-border">
            {mappings.map((m) => {
              const isActive = selectedCode === m.project_code;
              return (
                <button
                  key={m.project_code}
                  type="button"
                  onClick={() => handleSelect(m.project_code)}
                  className={[
                    'flex w-full items-center justify-between px-3 py-2 text-left transition-colors duration-150',
                    isActive
                      ? 'border-l-2 border-accent bg-accent/[0.08]'
                      : 'border-l-2 border-transparent hover:bg-surface-overlay',
                  ].join(' ')}
                >
                  <div className="min-w-0 flex-1 pr-2">
                    {m.project_name ? (
                      <>
                        <p className="truncate text-body font-medium text-text-primary">{m.project_name}</p>
                        <p className="font-mono text-caption text-text-muted">{m.project_code}</p>
                      </>
                    ) : (
                      <span className="font-mono text-mono text-text-primary">{m.project_code}</span>
                    )}
                  </div>
                  <StatusPill
                    status={statusPillVariant(m.mapping_status)}
                    label={m.mapping_status}
                  />
                </button>
              );
            })}
            {mappings.length === 0 && !loading && (
              <p className="px-3 py-4 text-body text-text-muted">No mappings found.</p>
            )}
            {loading && (
              <p className="px-3 py-4 text-body text-text-muted">Loading…</p>
            )}
          </div>
        </div>

        {/* Right column — editor */}
        <div className="min-w-0 flex-1 p-6">
          {!editorVisible && (
            <p className="text-body text-text-muted">Select a project from the list or add a new one.</p>
          )}

          {editorVisible && (
            <div className="space-y-6">
              {!isAdding && selectedCode && (
                <div className="flex gap-1 border-b border-border" role="tablist">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab === 'mapping'}
                    onClick={() => setActiveTab('mapping')}
                    className={`px-3 py-1.5 text-body ${activeTab === 'mapping' ? 'border-b-2 border-accent font-medium text-text-primary' : 'text-text-muted'}`}
                  >
                    Mapping
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab === 'sourcemap'}
                    onClick={() => setActiveTab('sourcemap')}
                    className={`px-3 py-1.5 text-body ${activeTab === 'sourcemap' ? 'border-b-2 border-accent font-medium text-text-primary' : 'text-text-muted'}`}
                  >
                    Odoo Source Map
                  </button>
                </div>
              )}

              {activeTab === 'sourcemap' && !isAdding && selectedCode ? (
                <OdooSourceMapPanel
                  data={sourceMap}
                  loading={sourceMapLoading}
                  scanning={scanning}
                  onScan={() => void handleScan()}
                />
              ) : (
              <>
              {/* Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {isAdding ? (
                    <div>
                      <label className="block text-label font-medium text-text-primary">
                        Project Code
                      </label>
                      <input
                        type="text"
                        value={newCodeInput}
                        onChange={(e) => setNewCodeInput(e.target.value)}
                        placeholder="e.g. PRJ-003"
                        className="mt-1 h-9 rounded-sm border border-border bg-surface-base px-2 font-mono text-mono text-text-primary"
                      />
                    </div>
                  ) : (
                    <h2 className="font-mono text-heading font-semibold text-text-primary">
                      {selectedCode}
                    </h2>
                  )}
                  {detail && (
                    <StatusPill
                      status={statusPillVariant(detailStatus ?? detail.mapping_status)}
                      label={detailStatus ?? detail.mapping_status}
                    />
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" onClick={handleValidate} isLoading={validating}>
                    Validate
                  </Button>
                  <Button variant="primary" onClick={handleSave} isLoading={submitting}>
                    Save
                  </Button>
                  {detail && detail.mapping_status !== 'disabled' && !isAdding && (
                    <Button
                      variant="danger"
                      onClick={() => setShowDisableConfirm(true)}
                      isLoading={disabling}
                    >
                      Disable
                    </Button>
                  )}
                </div>
              </div>

              {/* Audit metadata */}
              {detail && (
                <div className="flex flex-wrap gap-4 text-caption text-text-muted">
                  <span>Created: {formatTs(detail.created_at)}</span>
                  <span>by {detail.created_by_hash?.slice(0, 8) ?? '—'}</span>
                  <span>Updated: {formatTs(detail.updated_at)}</span>
                  <span>by {detail.updated_by_hash?.slice(0, 8) ?? '—'}</span>
                </div>
              )}

              {activeValidationErrors.length > 0 && (
                <div className="rounded-sm border border-warning/40 bg-warning/10 p-3">
                  <p className="text-label font-medium text-text-primary">Validation blockers</p>
                  <div className="mt-2 space-y-1">
                    {activeValidationErrors.map((err) => (
                      <p key={`${err.field}:${err.message}`} className="text-caption text-text-secondary">
                        <span className="font-mono text-warning">{err.field}</span>
                        {' — '}
                        {err.message}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {/* Form sections */}
              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">Project</legend>
                <div>
                  <label className="block text-caption text-text-secondary">Project Name</label>
                  <input
                    type="text"
                    value={form.project_name}
                    placeholder="Missing"
                    onChange={(e) => updateForm({ project_name: e.target.value })}
                    className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                  />
                  {fieldError('project_name') && (
                    <span className="text-caption text-error">{fieldError('project_name')}</span>
                  )}
                </div>
                <div>
                  <label className="block text-caption text-text-secondary">
                    Contract Numbers (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={form.contract_numbers.join(', ')}
                    onChange={(e) =>
                      updateForm({
                        contract_numbers: e.target.value
                          .split(',')
                          .map((s) => s.trim())
                          .filter(Boolean),
                      })
                    }
                    className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                  />
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">Odoo</legend>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-caption text-text-secondary">Project External ID</label>
                    <input
                      type="text"
                      value={form.odoo.project_external_id}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({ odoo: { ...form.odoo, project_external_id: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('odoo.project_external_id') && (
                      <span className="text-caption text-error">{fieldError('odoo.project_external_id')}</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Project Name</label>
                    <input
                      type="text"
                      value={form.odoo.project_name}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({ odoo: { ...form.odoo, project_name: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('odoo.project_name') && (
                      <span className="text-caption text-error">{fieldError('odoo.project_name')}</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Project Model</label>
                    <input
                      type="text"
                      value={form.odoo.project_model}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({ odoo: { ...form.odoo, project_model: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('odoo.project_model') && (
                      <span className="text-caption text-error">{fieldError('odoo.project_model')}</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Cost Model</label>
                    <input
                      type="text"
                      value={form.odoo.cost_model}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({ odoo: { ...form.odoo, cost_model: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('odoo.cost_model') && (
                      <span className="text-caption text-error">{fieldError('odoo.cost_model')}</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Analytic Account ID</label>
                    <input
                      type="text"
                      value={form.odoo.analytic_account_id}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({ odoo: { ...form.odoo, analytic_account_id: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('odoo.analytic_account_id') && (
                      <span className="text-caption text-error">{fieldError('odoo.analytic_account_id')}</span>
                    )}
                  </div>
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">SharePoint</legend>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-caption text-text-secondary">Site ID</label>
                    <input
                      type="text"
                      value={form.sharepoint.site_id}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({ sharepoint: { ...form.sharepoint, site_id: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('sharepoint.site_id') && (
                      <span className="text-caption text-error">{fieldError('sharepoint.site_id')}</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Drive ID</label>
                    <input
                      type="text"
                      value={form.sharepoint.drive_id}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({ sharepoint: { ...form.sharepoint, drive_id: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('sharepoint.drive_id') && (
                      <span className="text-caption text-error">{fieldError('sharepoint.drive_id')}</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Root Path</label>
                    <input
                      type="text"
                      value={form.sharepoint.root_path}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({ sharepoint: { ...form.sharepoint, root_path: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('sharepoint.root_path') && (
                      <span className="text-caption text-error">{fieldError('sharepoint.root_path')}</span>
                    )}
                  </div>
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">ownCloud</legend>
                <div>
                  <label className="block text-caption text-text-secondary">Base Path</label>
                  <input
                    type="text"
                    value={form.owncloud.base_path}
                    placeholder="Missing"
                    onChange={(e) =>
                      updateForm({ owncloud: { ...form.owncloud, base_path: e.target.value } })
                    }
                    className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                  />
                  {fieldError('owncloud.base_path') && (
                    <span className="text-caption text-error">{fieldError('owncloud.base_path')}</span>
                  )}
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">Email</legend>
                <div className="flex flex-wrap items-center gap-3">
                  <StatusPill
                    status={emailSourceEnabled ? (activeValidationErrors.length > 0 ? 'degraded' : 'connected') : 'disconnected'}
                    label={`Email: ${emailSourceEnabled ? 'enabled' : 'off'}`}
                  />
                  <StatusPill
                    status={groupStatusVariant(groupStatus, groupMailboxVerified)}
                    label={`Group: ${groupStatus}`}
                  />
                  <StatusPill
                    status={groupMailboxVerified ? 'connected' : 'disconnected'}
                    label={`Group mailbox: ${groupMailboxVerified ? 'verified' : 'Missing'}`}
                  />
                  <span className="text-caption text-text-muted">
                    Members: {form.microsoft.member_count || form.microsoft.group_members.length || 0}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-caption text-text-secondary">
                      Shared Mailboxes (one per line)
                    </label>
                    <textarea
                      value={form.email.shared_mailboxes.join('\n')}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          email: {
                            ...form.email,
                            shared_mailboxes: e.target.value
                              .split('\n')
                              .map((s) => s.trim())
                              .filter(Boolean),
                          },
                        })
                      }
                      rows={3}
                      className="mt-1 w-full rounded-sm border border-border bg-surface-base px-2 py-1 text-body text-text-primary"
                    />
                    {fieldError('email.shared_mailboxes') && (
                      <span className="text-caption text-error">{fieldError('email.shared_mailboxes')}</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">
                      Client Domains (one per line)
                    </label>
                    <textarea
                      value={form.email.client_domains.join('\n')}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          email: {
                            ...form.email,
                            client_domains: e.target.value
                              .split('\n')
                              .map((s) => s.trim())
                              .filter(Boolean),
                          },
                        })
                      }
                      rows={3}
                      className="mt-1 w-full rounded-sm border border-border bg-surface-base px-2 py-1 text-body text-text-primary"
                    />
                  </div>
	                  <div>
	                    <label className="block text-caption text-text-secondary">
	                      Document Control Mailbox
	                    </label>
                    <input
                      type="text"
                      value={form.email.document_control_mailbox}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          email: { ...form.email, document_control_mailbox: e.target.value },
                        })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
	                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Microsoft Group ID</label>
                    <input
                      type="text"
                      value={form.microsoft.group.id}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          microsoft: {
                            ...form.microsoft,
                            group: { ...form.microsoft.group, id: e.target.value },
                          },
                        })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Microsoft Group Display Name</label>
                    <input
                      type="text"
                      value={form.microsoft.group.display_name}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          microsoft: {
                            ...form.microsoft,
                            group: { ...form.microsoft.group, display_name: e.target.value },
                          },
                        })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Microsoft Group Mailbox</label>
                    <input
                      type="text"
                      value={form.microsoft.group.mail}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          microsoft: {
                            ...form.microsoft,
                            group: { ...form.microsoft.group, mail: e.target.value },
                          },
                        })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('microsoft.group.mail_enabled') && (
                      <span className="text-caption text-error">{fieldError('microsoft.group.mail_enabled')}</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Group Membership Status</label>
                    <input
                      type="text"
                      value={form.microsoft.group_membership_status}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          microsoft: { ...form.microsoft, group_membership_status: e.target.value },
                        })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                    {fieldError('microsoft.group_membership_status') && (
                      <span className="text-caption text-error">{fieldError('microsoft.group_membership_status')}</span>
                    )}
                  </div>
                  <label className="flex items-center gap-2 text-body text-text-primary">
                    <input
                      type="checkbox"
                      checked={form.microsoft.group.mail_enabled}
                      onChange={(e) =>
                        updateForm({
                          microsoft: {
                            ...form.microsoft,
                            group: { ...form.microsoft.group, mail_enabled: e.target.checked },
                          },
                        })
                      }
                      className="h-4 w-4"
                    />
                    Group mail enabled
                  </label>
                  <div>
                    <label className="block text-caption text-text-secondary">Member Count</label>
                    <input
                      type="number"
                      value={form.microsoft.member_count}
                      min={0}
                      onChange={(e) =>
                        updateForm({
                          microsoft: {
                            ...form.microsoft,
                            member_count: Number(e.target.value) || 0,
                          },
                        })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">
                      Consultant Domains (one per line)
                    </label>
                    <textarea
                      value={form.email.consultant_domains.join('\n')}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          email: {
                            ...form.email,
                            consultant_domains: e.target.value
                              .split('\n')
                              .map((s) => s.trim())
                              .filter(Boolean),
                          },
                        })
                      }
                      rows={2}
                      className="mt-1 w-full rounded-sm border border-border bg-surface-base px-2 py-1 text-body text-text-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">
                      Contractor Domains (one per line)
                    </label>
                    <textarea
                      value={form.email.contractor_domains.join('\n')}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          email: {
                            ...form.email,
                            contractor_domains: e.target.value
                              .split('\n')
                              .map((s) => s.trim())
                              .filter(Boolean),
                          },
                        })
                      }
                      rows={2}
	                      className="mt-1 w-full rounded-sm border border-border bg-surface-base px-2 py-1 text-body text-text-primary"
	                    />
	                  </div>
	                </div>
                {(form.microsoft.missing_permissions.length > 0 || form.microsoft.blockers.length > 0) && (
                  <div className="rounded-sm border border-warning/40 bg-warning/10 p-3">
                    <p className="text-label font-medium text-text-primary">Email blockers</p>
                    <div className="mt-2 space-y-1">
                      {form.microsoft.missing_permissions.map((permission) => (
                        <p key={`perm:${permission}`} className="text-caption text-text-secondary">
                          <span className="font-mono text-warning">permission</span>
                          {' — '}
                          {permission}
                        </p>
                      ))}
                      {form.microsoft.blockers.map((blocker) => (
                        <p key={`blocker:${blocker}`} className="text-caption text-text-secondary">
                          <span className="font-mono text-warning">blocker</span>
                          {' — '}
                          {blocker}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
                <div className="rounded-sm border border-border bg-surface-base p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-label font-medium text-text-secondary">Microsoft Group Members</p>
                    <span className="text-caption text-text-muted">
                      {form.microsoft.group_members.length > 0 ? `${form.microsoft.group_members.length} shown` : 'Missing'}
                    </span>
                  </div>
                  {form.microsoft.group_members.length > 0 ? (
                    <div className="space-y-2">
                      {form.microsoft.group_members.map((member) => (
                        <div
                          key={member.id || member.email}
                          className="grid grid-cols-[1.2fr_1.2fr_1fr_1fr] gap-2 rounded-sm border border-border bg-surface-raised px-2 py-1 text-caption"
                        >
                          <span className="truncate text-text-primary">{member.display_name || 'Missing'}</span>
                          <span className="truncate font-mono text-text-secondary">{member.email || 'Missing'}</span>
                          <span className="truncate text-text-muted">{member.job_title || 'Missing'}</span>
                          <span className="truncate text-text-muted">{member.department || 'Missing'}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-caption text-text-muted">Missing</p>
                  )}
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">
                  Related Project People
                </legend>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { key: 'project_manager', label: 'Project Manager' },
                    { key: 'commercial_manager', label: 'Commercial Manager' },
                    { key: 'finance_owner', label: 'Finance Owner' },
                    { key: 'document_controller', label: 'Document Controller' },
                  ].map(({ key, label }) => (
                    <div key={key}>
                      <label className="block text-caption text-text-secondary">{label}</label>
                      <input
                        type="text"
                        value={form.related_people[key as keyof typeof form.related_people] as string}
                        placeholder="Missing"
                        onChange={(e) =>
                          updateForm({
                            related_people: { ...form.related_people, [key]: e.target.value },
                          })
                        }
                        className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                      />
                    </div>
                  ))}
                  <div className="col-span-2">
                    <label className="block text-caption text-text-secondary">Other (one per line)</label>
                    <textarea
                      value={form.related_people.other.join('\n')}
                      placeholder="Missing"
                      onChange={(e) =>
                        updateForm({
                          related_people: {
                            ...form.related_people,
                            other: e.target.value
                              .split('\n')
                              .map((s) => s.trim())
                              .filter(Boolean),
                          },
                        })
                      }
                      rows={2}
                      className="mt-1 w-full rounded-sm border border-border bg-surface-base px-2 py-1 text-body text-text-primary"
                    />
                  </div>
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">Enabled Sources</legend>
                <div className="flex flex-wrap gap-3">
                  {SOURCE_OPTIONS.map((s) => (
                    <label key={s.key} className="flex items-center gap-2 text-body text-text-primary">
	                      <input
	                        type="checkbox"
	                        checked={form.enabled_sources.includes(s.key)}
	                        disabled={s.key === 'owncloud'}
	                        onChange={() => {
	                          if (s.key !== 'owncloud') toggleSource(s.key);
	                        }}
	                        className="h-4 w-4"
	                      />
                      {s.label}
                    </label>
                  ))}
                </div>
                {fieldError('enabled_sources') && (
                  <span className="text-caption text-error">{fieldError('enabled_sources')}</span>
                )}
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">Allowed Roles</legend>
                <div className="flex flex-wrap gap-3">
                  {CANONICAL_ROLES.map((r) => (
                    <label key={r} className="flex items-center gap-2 text-body text-text-primary">
                      <input
                        type="checkbox"
                        checked={form.allowed_roles.includes(r)}
                        onChange={() => toggleRole(r)}
                        className="h-4 w-4"
                      />
                      {r}
                    </label>
                  ))}
                </div>
              </fieldset>
              </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Diff preview modal */}
      <DiffPreviewModal
        isOpen={showDiff}
        projectCode={isAdding ? newCodeInput : selectedCode ?? ''}
        oldData={detail}
        newData={form}
        onClose={() => setShowDiff(false)}
        onConfirm={handleDiffConfirm}
      />

      {/* Risky change confirm */}
      <ConfirmDialog
        isOpen={showRiskyConfirm}
        title="Confirm risky changes"
        confirmationText={selectedCode ?? ''}
        confirmLabel="Save anyway"
        variant="danger"
        onClose={() => setShowRiskyConfirm(false)}
        onConfirm={() => void doSave()}
      >
        <p className="text-body text-text-primary">
          This save removes a source, role, or changes a critical path. Type the project code to confirm.
        </p>
      </ConfirmDialog>

      {/* Email Group Enrichment panel */}
      <EmailGroupEnrichPanel
        isOpen={showEnrich}
        result={enrichResult}
        onClose={() => setShowEnrich(false)}
      />

      {/* Odoo + SharePoint Sync panel */}
      <OdooSyncPanel
        isOpen={showOdooSync}
        result={odooSyncResult}
        onClose={() => setShowOdooSync(false)}
      />

      {/* Rescan Microsoft Sources panel */}
      <RescanPanel
        isOpen={showRescan}
        result={rescanResult}
        onClose={() => setShowRescan(false)}
        onAccept={handleAcceptCandidate}
        acceptingCode={acceptingCode}
      />

      {/* Disable confirm */}
      <ConfirmDialog
        isOpen={showDisableConfirm}
        title={`Disable ${selectedCode}?`}
        confirmationText={selectedCode ?? ''}
        confirmLabel="Disable"
        variant="danger"
        onClose={() => setShowDisableConfirm(false)}
        onConfirm={() => void handleDisableConfirm()}
      >
        <p className="text-body text-text-primary">
          New report generation for this project will be blocked until the mapping is re-enabled. Existing reports are not affected.
        </p>
      </ConfirmDialog>
    </div>
  );
}
