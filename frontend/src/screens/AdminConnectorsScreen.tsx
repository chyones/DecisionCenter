/**
 * Phase 2B Slice 2 — Connectors & APIs (`/admin/connectors`).
 *
 * Admin-only. Reads live data from:
 *   - `GET /admin/services`         — service list with status pills
 *   - `GET /admin/services/{name}`  — env-key presence + recent events
 *   - `POST /admin/services/{name}/probe` — read-only [Test connection]
 *
 * Locked spec: `docs/design/UI_CONTRACT_v1.md` §3.2 (A-03 / A-04 / A-05).
 * Never renders credential values — only key-presence booleans, hostname,
 * and auth-mechanism type. The backend is the C-6 authoritative gate; this
 * UI is its visible contract.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Button, StatusPill, useToasts } from '../components';
import { useApi } from '../api';
import { ApiError } from '../api';
import type {
  ConnectorLastProbeStatus,
  ProbeResult,
  ServiceDetail,
  ServiceSummary,
} from '../api';
import type { StatusValue } from '../tokens';

function pillStatus(s: ConnectorLastProbeStatus): StatusValue {
  if (s === 'pass') return 'connected';
  if (s === 'fail') return 'disconnected';
  return 'unknown';
}

function formatLatency(ms: number | null): string {
  if (ms === null || ms === undefined) return '—';
  return `${ms}ms`;
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function AdminConnectorsScreen() {
  const api = useApi();
  const { addToast } = useToasts();
  const [summaries, setSummaries] = useState<ServiceSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ServiceDetail | null>(null);
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [probing, setProbing] = useState<boolean>(false);
  const [listError, setListError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const data = await api.get<ServiceSummary[]>('/admin/services');
      setSummaries(data);
      if (data.length > 0 && selected === null) {
        setSelected(data[0].name);
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'Failed to load services';
      setListError(message);
    } finally {
      setLoadingList(false);
    }
  }, [api, selected]);

  const fetchDetail = useCallback(
    async (name: string) => {
      setLoadingDetail(true);
      setDetailError(null);
      try {
        const data = await api.get<ServiceDetail>(`/admin/services/${name}`);
        setDetail(data);
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : `Failed to load ${name} details`;
        setDetailError(message);
        setDetail(null);
      } finally {
        setLoadingDetail(false);
      }
    },
    [api],
  );

  useEffect(() => {
    void fetchList();
    // Run once on mount; refetches are triggered by the probe button.
  }, []);

  useEffect(() => {
    if (selected) {
      void fetchDetail(selected);
    }
  }, [selected, fetchDetail]);

  const handleProbe = useCallback(async () => {
    if (!selected) return;
    setProbing(true);
    try {
      const result = await api.post<ProbeResult>(
        `/admin/services/${selected}/probe`,
        {},
      );
      addToast(
        result.status === 'pass' ? 'success' : 'error',
        `${result.status === 'pass' ? 'OK' : 'Failed'} — ${formatLatency(result.latency_ms)}`,
        `Probe: ${selected}`,
      );
      // Refresh both the summary (so the pill updates) and the detail panel.
      await Promise.all([fetchList(), fetchDetail(selected)]);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'Probe request failed';
      addToast('error', message, `Probe: ${selected}`);
    } finally {
      setProbing(false);
    }
  }, [api, selected, addToast, fetchList, fetchDetail]);

  const selectedSummary = useMemo(
    () => summaries.find((s) => s.name === selected) ?? null,
    [summaries, selected],
  );

  return (
    <div>
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          Connectors &amp; APIs
        </h1>
        <span className="text-caption text-text-muted">
          read-only · admin
        </span>
      </div>

      <div className="flex gap-6">
        {/* Left panel — service list */}
        <aside className="w-[280px] shrink-0 rounded-sm border border-border bg-surface-raised">
          <div className="border-b border-border px-3 py-2 text-label font-medium text-text-secondary">
            Services
          </div>
          {loadingList ? (
            <p className="px-3 py-4 text-body text-text-muted">Loading…</p>
          ) : listError ? (
            <p className="px-3 py-4 text-body text-error">{listError}</p>
          ) : summaries.length === 0 ? (
            <p className="px-3 py-4 text-body text-text-muted">No services.</p>
          ) : (
            <ul>
              {summaries.map((svc) => {
                const isActive = svc.name === selected;
                return (
                  <li key={svc.name}>
                    <button
                      type="button"
                      onClick={() => setSelected(svc.name)}
                      className={[
                        'flex w-full items-center justify-between gap-2 border-l-2 px-3 py-2 text-left transition-colors duration-150',
                        isActive
                          ? 'border-accent bg-accent/10 text-accent'
                          : 'border-transparent text-text-secondary hover:bg-surface-overlay',
                      ].join(' ')}
                      aria-current={isActive ? 'true' : undefined}
                    >
                      <span className="text-body">{svc.display_name}</span>
                      <StatusPill status={pillStatus(svc.last_probe_status)} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        {/* Right panel — detail */}
        <section className="flex-1 rounded-sm border border-border bg-surface-raised p-6">
          {!selectedSummary ? (
            <p className="text-body text-text-muted">
              Select a service to view its detail.
            </p>
          ) : loadingDetail ? (
            <p className="text-body text-text-muted">Loading detail…</p>
          ) : detailError ? (
            <p className="text-body text-error">{detailError}</p>
          ) : detail ? (
            <>
              <div className="mb-4 flex items-baseline justify-between">
                <h2 className="text-heading font-semibold text-text-primary">
                  {detail.display_name}
                </h2>
                <StatusPill status={pillStatus(detail.last_probe_status)} />
              </div>

              <dl className="mb-6 grid grid-cols-2 gap-x-6 gap-y-2 text-body">
                <dt className="text-text-muted">Category</dt>
                <dd className="text-text-primary">{detail.category}</dd>
                <dt className="text-text-muted">Auth mechanism</dt>
                <dd className="text-text-primary">{detail.auth_mechanism}</dd>
                <dt className="text-text-muted">Hostname</dt>
                <dd className="font-mono text-mono text-text-primary">
                  {detail.hostname ?? '—'}
                </dd>
                <dt className="text-text-muted">Last probe</dt>
                <dd className="text-text-primary">
                  {formatTimestamp(detail.last_probe_at)} ·{' '}
                  {formatLatency(detail.last_latency_ms)}
                </dd>
                {detail.category === 'workflow' && (
                  <>
                    <dt className="text-text-muted">Workflow</dt>
                    <dd className="text-text-primary">
                      {detail.workflow_status === 'deployed'
                        ? `deployed (${detail.workflow_node_count ?? 0} nodes)`
                        : 'empty'}
                    </dd>
                  </>
                )}
              </dl>

              <p className="mb-6 text-body text-text-secondary">
                {detail.description}
              </p>

              <div className="mb-6">
                <h3 className="mb-2 text-label font-medium text-text-secondary">
                  .env key presence
                </h3>
                <ul className="space-y-1">
                  {detail.env_keys.map((k) => (
                    <li
                      key={k.name}
                      className="flex items-center justify-between border-b border-border py-1 font-mono text-mono"
                    >
                      <span className="text-text-primary">{k.name}</span>
                      <span
                        className={
                          k.present ? 'text-success' : 'text-text-muted'
                        }
                        aria-label={k.present ? 'set' : 'missing'}
                      >
                        {k.present ? '✓ set' : '✗ missing'}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mb-6">
                <Button
                  variant="secondary"
                  size="default"
                  isLoading={probing}
                  onClick={handleProbe}
                >
                  Test connection
                </Button>
              </div>

              <div>
                <h3 className="mb-2 text-label font-medium text-text-secondary">
                  Recent events
                </h3>
                {detail.recent_events.length === 0 ? (
                  <p className="text-body text-text-muted">No events yet.</p>
                ) : (
                  <ul className="space-y-1">
                    {detail.recent_events.map((e, idx) => (
                      <li
                        key={`${e.ts}-${idx}`}
                        className="flex items-baseline justify-between gap-3 border-b border-border py-1 text-body"
                      >
                        <span className="font-mono text-mono text-text-muted">
                          {formatTimestamp(e.ts)}
                        </span>
                        <span className="text-text-secondary">
                          {e.event_type}
                        </span>
                        <span className="font-mono text-mono text-text-primary">
                          {formatLatency(e.latency_ms)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}
