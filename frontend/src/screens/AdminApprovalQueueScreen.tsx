/**
 * Phase 2B Slice 7 — Approval Queue screen (`/admin/approvals`).
 *
 * Admin-only. Reads live data from:
 *   - `GET /admin/approvals`           — paginated approval queue
 *   - `GET /admin/approvals/{id}`      — single item detail
 *   - `POST /admin/approvals/{id}/override-approve` — admin override
 *   - `POST /admin/approvals/{id}/override-reject`  — admin override
 *
 * Locked spec: `docs/design/UI_CONTRACT_v1.md` §3.5.
 * Never renders query text, markdown, or evidence excerpts (C-1).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Button, SlideInPanel, StatusPill, useToasts } from '../components';
import { useApi } from '../api';
import { ApiError } from '../api';
import type {
  ApprovalQueueDetail,
  ApprovalQueueItem,
  ApprovalQueueResponse,
  AdminOverrideRequest,
} from '../api';

function formatTs(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function statePillVariant(state: string): 'staging' | 'needs_review' | 'approved' | 'rejected' | 'failed' | 'unknown' {
  if (state === 'staging') return 'staging';
  if (state === 'needs_review') return 'needs_review';
  if (state === 'approved') return 'approved';
  if (state === 'rejected') return 'rejected';
  if (state === 'failed') return 'failed';
  return 'unknown';
}

export function AdminApprovalQueueScreen() {
  const api = useApi();
  const { addToast } = useToasts();

  const [items, setItems] = useState<ApprovalQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const [projectFilter, setProjectFilter] = useState('');
  const [stateFilter, setStateFilter] = useState('');

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApprovalQueueDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [comment, setComment] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (projectFilter) qs.set('project_code', projectFilter);
      qs.set('limit', String(limit));
      qs.set('offset', String(offset));
      const data = await api.get<ApprovalQueueResponse>(`/admin/approvals?${qs}`);
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load queue';
      addToast('error', message, 'Queue error');
    } finally {
      setLoading(false);
    }
  }, [api, addToast, projectFilter, offset]);

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  const fetchDetail = useCallback(async () => {
    if (!selectedId) return;
    setDetailLoading(true);
    try {
      const data = await api.get<ApprovalQueueDetail>(`/admin/approvals/${selectedId}`);
      setDetail(data);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load detail';
      addToast('error', message, 'Detail error');
    } finally {
      setDetailLoading(false);
    }
  }, [api, addToast, selectedId]);

  useEffect(() => {
    void fetchDetail();
  }, [fetchDetail]);

  const projectOptions = useMemo(() => {
    const codes = new Set<string>();
    items.forEach((i) => {
      if (i.project_code) codes.add(i.project_code);
    });
    return Array.from(codes).sort();
  }, [items]);

  const handleApprove = async () => {
    if (!selectedId || !comment.trim()) return;
    setActionLoading(true);
    try {
      const body: AdminOverrideRequest = { comment: comment.trim() };
      await api.post(`/admin/approvals/${selectedId}/override-approve`, body);
      addToast('success', 'Report approved via admin override.', 'Approved');
      setSelectedId(null);
      setComment('');
      await fetchList();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Approval failed';
      addToast('error', message, 'Approval error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedId || !comment.trim()) return;
    setActionLoading(true);
    try {
      const body: AdminOverrideRequest = { comment: comment.trim() };
      await api.post(`/admin/approvals/${selectedId}/override-reject`, body);
      addToast('success', 'Report rejected via admin override.', 'Rejected');
      setSelectedId(null);
      setComment('');
      await fetchList();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Rejection failed';
      addToast('error', message, 'Rejection error');
    } finally {
      setActionLoading(false);
    }
  };

  const filteredItems = useMemo(() => {
    if (!stateFilter) return items;
    return items.filter((i) => i.review_state === stateFilter);
  }, [items, stateFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">Approval Queue</h1>
        {total > 0 && (
          <span className="rounded-sm bg-warning/10 px-2 py-1 text-caption font-medium text-warning">
            {total} pending
          </span>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-4 rounded-lg bg-surface p-4 shadow-sm">
        <div className="flex flex-col gap-1">
          <label className="text-caption text-text-secondary">Project</label>
          <select
            value={projectFilter}
            onChange={(e) => { setProjectFilter(e.target.value); setOffset(0); }}
            className="rounded border border-border bg-surface px-3 py-2 text-body text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="">All projects</option>
            {projectOptions.map((code) => (
              <option key={code} value={code}>{code}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-caption text-text-secondary">State</label>
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="rounded border border-border bg-surface px-3 py-2 text-body text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="">All states</option>
            <option value="staging">staging</option>
            <option value="needs_review">needs_review</option>
          </select>
        </div>
        <Button variant="secondary" onClick={() => { setProjectFilter(''); setStateFilter(''); setOffset(0); }}>
          Reset
        </Button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-border bg-surface shadow-sm">
        <table className="w-full text-left">
          <thead className="bg-surface-alt text-caption uppercase text-text-secondary">
            <tr>
              <th className="px-4 py-3">Request ID</th>
              <th className="px-4 py-3">Project</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Submitted</th>
              <th className="px-4 py-3">Requester</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredItems.map((item) => (
              <tr
                key={item.request_id}
                className="cursor-pointer hover:bg-surface-alt/50"
                onClick={() => { setSelectedId(item.request_id); setComment(''); }}
              >
                <td className="whitespace-nowrap px-4 py-3 font-mono text-mono text-text-primary">
                  {item.request_id.slice(0, 8)}
                </td>
                <td className="px-4 py-3 text-body text-text-primary">
                  {item.project_code ?? '—'}
                </td>
                <td className="px-4 py-3">
                  <StatusPill status={statePillVariant(item.review_state)} label={item.review_state} />
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-body text-text-secondary">
                  {formatTs(item.submitted_at)}
                </td>
                <td className="px-4 py-3 font-mono text-body text-text-secondary">
                  {item.requester_hash ? item.requester_hash.slice(0, 8) + '…' : '—'}
                </td>
              </tr>
            ))}
            {filteredItems.length === 0 && !loading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-body text-text-muted">
                  No pending approvals.
                </td>
              </tr>
            )}
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-body text-text-muted">
                  Loading…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Load more */}
      {items.length < total && (
        <div className="flex justify-center">
          <Button variant="secondary" onClick={() => setOffset((o) => o + limit)}>
            Load more
          </Button>
        </div>
      )}

      {/* Detail panel */}
      <SlideInPanel
        isOpen={selectedId !== null}
        onClose={() => setSelectedId(null)}
        title="Approval Detail"
      >
        {detailLoading && (
          <p className="text-body text-text-muted">Loading detail…</p>
        )}
        {detail && (
          <div className="space-y-6">
            {/* Status + project */}
            <div className="flex items-center gap-3">
              <StatusPill status={statePillVariant(detail.review_state)} label={detail.review_state} />
              <span className="font-mono text-heading font-semibold text-text-primary">
                {detail.project_code ?? 'No project'}
              </span>
            </div>

            {/* Metadata grid */}
            <div className="grid grid-cols-2 gap-4 text-body">
              <div>
                <span className="text-caption text-text-secondary">Project</span>
                <p className="text-text-primary">{detail.project_code ?? '—'}</p>
              </div>
              <div>
                <span className="text-caption text-text-secondary">Submitted</span>
                <p className="text-text-primary">{formatTs(detail.submitted_at)}</p>
              </div>
              <div>
                <span className="text-caption text-text-secondary">Requester hash</span>
                <p className="font-mono text-text-primary">{detail.requester_hash?.slice(0, 8) ?? '—'}</p>
              </div>
              <div>
                <span className="text-caption text-text-secondary">Quality gate</span>
                <p className="text-text-primary">{detail.quality_gate_status ?? '—'}</p>
              </div>
              <div>
                <span className="text-caption text-text-secondary">Cost (USD)</span>
                <p className="text-text-primary">{detail.cost_total_usd.toFixed(4)}</p>
              </div>
              <div>
                <span className="text-caption text-text-secondary">Approval required</span>
                <p className="text-text-primary">{detail.requires_approval ? 'Yes' : 'No'}</p>
              </div>
            </div>

            {/* QG flags */}
            {detail.quality_gate_flags.length > 0 && (
              <div>
                <h3 className="mb-2 text-label font-medium text-text-secondary">Quality Gate Flags</h3>
                <ul className="space-y-1">
                  {detail.quality_gate_flags.map((flag, idx) => (
                    <li key={idx} className="flex items-center gap-2 text-body text-warning">
                      <span>⚠</span>
                      {flag}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Token counts */}
            {detail.token_counts && Object.keys(detail.token_counts).length > 0 && (
              <div>
                <h3 className="mb-2 text-label font-medium text-text-secondary">Token Counts</h3>
                <table className="w-full text-left text-body">
                  <tbody>
                    {Object.entries(detail.token_counts).map(([model, count]) => (
                      <tr key={model} className="border-b border-border">
                        <td className="py-1 text-text-secondary">{model}</td>
                        <td className="py-1 text-text-primary">{count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <hr className="border-border" />

            {/* Warning banner */}
            <div className="rounded-sm bg-warning/10 p-3 text-body text-warning">
              ⚠ Admin approval is logged as admin_override. Content visibility is not granted to admin role.
            </div>

            {/* Admin action */}
            <div className="space-y-3">
              <label className="block text-label font-medium text-text-primary">
                Admin override comment (required)
              </label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                placeholder="Enter a mandatory comment explaining the override decision…"
                className="w-full rounded-sm border border-border bg-surface-base px-3 py-2 text-body text-text-primary focus:border-accent focus:outline-none"
              />
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  onClick={handleApprove}
                  disabled={!comment.trim() || actionLoading}
                  isLoading={actionLoading}
                >
                  Admin Approve
                </Button>
                <Button
                  variant="danger"
                  onClick={handleReject}
                  disabled={!comment.trim() || actionLoading}
                  isLoading={actionLoading}
                >
                  Admin Reject
                </Button>
              </div>
            </div>
          </div>
        )}
      </SlideInPanel>
    </div>
  );
}
