/**
 * Phase 2B Slice 4 — Audit Log screen (`/admin/audit`).
 *
 * Admin-only. Reads live data from:
 *   - `GET /admin/audit`           — paginated, filterable event list
 *   - `GET /admin/audit/{event_id}` — single event detail
 *   - `GET /admin/audit/export.csv` — CSV export
 *
 * Locked spec: `docs/design/UI_CONTRACT_v1.md` §3.8 (A-12 / A-13).
 * Never renders query text, report content, or evidence excerpts (C-1).
 */
import { useCallback, useEffect, useState } from 'react';

import { Button, SlideInPanel, useToasts } from '../components';
import { useApi } from '../api';
import { ApiError } from '../api';
import type {
  AuditEventDetail,
  AuditEventListResponse,
  AuditEventSummary,
  ListAuditEventsParams,
} from '../api';

const EVENT_TYPE_OPTIONS = [
  { value: '', label: 'All event types' },
  { value: 'report.submitted', label: 'Report Submitted' },
  { value: 'approve', label: 'Approve' },
  { value: 'admin_override', label: 'Admin Override' },
  { value: 'report.cancelled', label: 'Report Cancelled' },
  { value: 'connector.probe_success', label: 'Connector Probe Success' },
  { value: 'connector.error', label: 'Connector Error' },
  { value: 'connector.latency_spike', label: 'Connector Latency Spike' },
  { value: 'cost.daily_cap_warning', label: 'Cost Warning' },
  { value: 'cost.daily_cap_exceeded', label: 'Cost Exceeded' },
];

function formatTs(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function truncateHash(hash: string | null): string {
  if (!hash) return '—';
  return hash.length > 8 ? hash.slice(0, 8) + '…' : hash;
}

function buildQueryString(params: ListAuditEventsParams): string {
  const qs = new URLSearchParams();
  if (params.date_from) qs.set('date_from', params.date_from);
  if (params.date_to) qs.set('date_to', params.date_to);
  if (params.event_type) qs.set('event_type', params.event_type);
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  if (params.offset !== undefined) qs.set('offset', String(params.offset));
  const s = qs.toString();
  return s ? `?${s}` : '';
}

export function AdminAuditLogScreen() {
  const api = useApi();
  const { addToast } = useToasts();

  const [events, setEvents] = useState<AuditEventSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [eventType, setEventType] = useState('');

  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AuditEventDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params: ListAuditEventsParams = {
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        event_type: eventType || undefined,
        limit,
        offset,
      };
      const qs = buildQueryString(params);
      const data = await api.get<AuditEventListResponse>(`/admin/audit${qs}`);
      setEvents(data.events);
      setTotal(data.total);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load audit log';
      addToast('error', message, 'Audit log error');
    } finally {
      setLoading(false);
    }
  }, [api, addToast, dateFrom, dateTo, eventType, offset]);

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  const fetchDetail = useCallback(async () => {
    if (!selectedEventId) return;
    setLoadingDetail(true);
    try {
      const data = await api.get<AuditEventDetail>(`/admin/audit/${selectedEventId}`);
      setDetail(data);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load event detail';
      addToast('error', message, 'Event detail error');
    } finally {
      setLoadingDetail(false);
    }
  }, [api, addToast, selectedEventId]);

  useEffect(() => {
    void fetchDetail();
  }, [fetchDetail]);

  const handleExport = () => {
    const params: ListAuditEventsParams = {
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      event_type: eventType || undefined,
    };
    const qs = buildQueryString(params);
    const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';
    const full = `${base.replace(/\/$/, '')}/admin/audit/export.csv${qs}`;
    window.open(full, '_blank');
  };

  const handleReset = () => {
    setDateFrom('');
    setDateTo('');
    setEventType('');
    setOffset(0);
  };

  const startRow = total === 0 ? 0 : offset + 1;
  const endRow = Math.min(offset + limit, total);
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div className="space-y-6">
      <h1 className="text-h1 text-text-primary">Audit Log</h1>

      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-4 rounded-lg bg-surface p-4 shadow-sm">
        <div className="flex flex-col gap-1">
          <label className="text-caption text-text-secondary">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setOffset(0); }}
            className="rounded border border-border bg-surface px-3 py-2 text-body text-text-primary focus:border-accent focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-caption text-text-secondary">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setOffset(0); }}
            className="rounded border border-border bg-surface px-3 py-2 text-body text-text-primary focus:border-accent focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-caption text-text-secondary">Event Type</label>
          <select
            value={eventType}
            onChange={(e) => { setEventType(e.target.value); setOffset(0); }}
            className="rounded border border-border bg-surface px-3 py-2 text-body text-text-primary focus:border-accent focus:outline-none"
          >
            {EVENT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <Button variant="secondary" onClick={handleReset}>
          Reset
        </Button>
        <Button variant="primary" onClick={handleExport}>
          Export CSV
        </Button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-border bg-surface shadow-sm">
        <table className="w-full text-left">
          <thead className="bg-surface-alt text-caption uppercase text-text-secondary">
            <tr>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Event Type</th>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Project</th>
              <th className="px-4 py-3">Service</th>
              <th className="px-4 py-3">Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {events.map((ev) => (
              <tr
                key={ev.event_id}
                className="cursor-pointer hover:bg-surface-alt/50"
                onClick={() => setSelectedEventId(ev.event_id)}
              >
                <td className="whitespace-nowrap px-4 py-3 text-body text-text-primary">
                  {formatTs(ev.ts)}
                </td>
                <td className="px-4 py-3 text-body text-text-primary">
                  <span className="inline-flex items-center rounded-full bg-surface-alt px-2 py-0.5 text-caption font-medium text-text-secondary">
                    {ev.event_type}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-body text-text-secondary">
                  {truncateHash(ev.user_id_hash)}
                </td>
                <td className="px-4 py-3 text-body text-text-secondary">
                  {ev.project_code ?? '—'}
                </td>
                <td className="px-4 py-3 text-body text-text-secondary">
                  {ev.service ?? '—'}
                </td>
                <td className="max-w-xs truncate px-4 py-3 text-body text-text-secondary">
                  {ev.detail}
                </td>
              </tr>
            ))}
            {events.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-body text-text-muted">
                  No events found.
                </td>
              </tr>
            )}
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-body text-text-muted">
                  Loading…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-caption text-text-secondary">
          Showing {startRow}–{endRow} of {total}
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={!canPrev} onClick={() => setOffset((o) => Math.max(0, o - limit))}>
            Previous
          </Button>
          <Button variant="secondary" disabled={!canNext} onClick={() => setOffset((o) => o + limit)}>
            Next
          </Button>
        </div>
      </div>

      {/* Detail panel */}
      <SlideInPanel
        isOpen={selectedEventId !== null}
        onClose={() => setSelectedEventId(null)}
        title="Event Detail"
      >
        {loadingDetail && (
          <p className="text-body text-text-muted">Loading detail…</p>
        )}
        {detail && (
          <div className="space-y-4">
            <div>
              <span className="text-caption text-text-secondary">Event ID</span>
              <p className="font-mono text-body text-text-primary">{detail.event_id}</p>
            </div>
            <div>
              <span className="text-caption text-text-secondary">Event Type</span>
              <p className="text-body text-text-primary">{detail.event_type}</p>
            </div>
            <div>
              <span className="text-caption text-text-secondary">Time</span>
              <p className="text-body text-text-primary">{formatTs(detail.ts)}</p>
            </div>
            <div>
              <span className="text-caption text-text-secondary">User Hash</span>
              <p className="font-mono text-body text-text-primary">{detail.user_id_hash ?? '—'}</p>
            </div>
            <div>
              <span className="text-caption text-text-secondary">Project</span>
              <p className="text-body text-text-primary">{detail.project_code ?? '—'}</p>
            </div>
            <div>
              <span className="text-caption text-text-secondary">Service</span>
              <p className="text-body text-text-primary">{detail.service ?? '—'}</p>
            </div>
            <div>
              <span className="text-caption text-text-secondary">Detail</span>
              <p className="whitespace-pre-wrap text-body text-text-primary">{detail.detail}</p>
            </div>
          </div>
        )}
      </SlideInPanel>
    </div>
  );
}
