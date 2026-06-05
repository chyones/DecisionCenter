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
  OdooSharePointSyncResult,
  OdooSitePairResult,
  SiteCandidate,
  SourceMappingDetail,
  SourceMappingListResponse,
  SourceMappingSummary,
  SourceMappingUpsertRequest,
  SourceMappingValidateResponse,
  ValidationFieldError,
} from '../api';

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
    odoo: { project_model: '', cost_model: '', project_external_id: '', project_name: '' },
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
  push('Odoo Project External ID', oldData?.odoo.project_external_id, newData.odoo.project_external_id);
  push('Odoo Project Name', oldData?.odoo.project_name, newData.odoo.project_name);
  push('Odoo Project Model', oldData?.odoo.project_model, newData.odoo.project_model);
  push('Odoo Cost Model', oldData?.odoo.cost_model, newData.odoo.cost_model);
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
  const [odooSyncLoading, setOdooSyncLoading] = useState(false);
  const [showOdooSync, setShowOdooSync] = useState(false);
  const [odooSyncResult, setOdooSyncResult] = useState<OdooSharePointSyncResult | null>(null);

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
    void fetchDetail(code);
  };

  const handleAdd = () => {
    setIsAdding(true);
    setSelectedCode(null);
    setDetail(null);
    setForm(emptyForm());
    setNewCodeInput('');
    setValidationErrors([]);
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

  const fieldError = (field: string) =>
    validationErrors.find((e) => e.field === field)?.message;

  const editorVisible = selectedCode !== null || isAdding;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-display font-semibold text-text-primary">Project Source Mapping</h1>
        <div className="flex items-center gap-2">
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
                      status={statusPillVariant(detail.mapping_status)}
                      label={detail.mapping_status}
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

              {/* Form sections */}
              <fieldset className="space-y-2">
                <legend className="text-label font-medium text-text-secondary">Project</legend>
                <div>
                  <label className="block text-caption text-text-secondary">Project Name</label>
                  <input
                    type="text"
                    value={form.project_name}
                    onChange={(e) => updateForm({ project_name: e.target.value })}
                    className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                  />
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
                      onChange={(e) =>
                        updateForm({ odoo: { ...form.odoo, project_name: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Project Model</label>
                    <input
                      type="text"
                      value={form.odoo.project_model}
                      onChange={(e) =>
                        updateForm({ odoo: { ...form.odoo, project_model: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-caption text-text-secondary">Cost Model</label>
                    <input
                      type="text"
                      value={form.odoo.cost_model}
                      onChange={(e) =>
                        updateForm({ odoo: { ...form.odoo, cost_model: e.target.value } })
                      }
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-surface-base px-2 text-body text-text-primary"
                    />
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
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-caption text-text-secondary">
                      Shared Mailboxes (one per line)
                    </label>
                    <textarea
                      value={form.email.shared_mailboxes.join('\n')}
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
                      onChange={(e) =>
                        updateForm({
                          email: { ...form.email, document_control_mailbox: e.target.value },
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
                        onChange={() => toggleSource(s.key)}
                        className="h-4 w-4"
                      />
                      {s.label}
                    </label>
                  ))}
                </div>
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
