/**
 * Odoo Source Map panel — read-only visibility over where DecisionCenter
 * searches inside Odoo for a project.
 *
 * Presentational: all data arrives via props so it can be unit-tested without
 * the API. The container (AdminSourceMappingScreen) starts a batched scan
 * session, polls it, and feeds each live snapshot back in as `data`.
 *
 * Shows, per project: Odoo project id, analytic account id, project source
 * status, enabled categories, and every registry source (name, model, link
 * path, key fields, gap type, confidence, live scan status, count/total,
 * duration, error, warnings). While a scan runs it shows source-by-source
 * progress and partial results; failed sources can be retried without
 * re-scanning everything.
 */
import { Button, StatusPill } from '../components';
import type { OdooSourceMapResponse } from '../api';
import {
  confidencePill,
  durationLabel,
  failedSourceCount,
  groupSourcesByDisplayGroup,
  isScanActive,
  recordCountLabel,
  scanProgressLabel,
  scanProgressPercent,
  scanStatusPill,
} from './odooSourceMap';

export interface OdooSourceMapPanelProps {
  data: OdooSourceMapResponse | null;
  loading: boolean;
  scanning: boolean;
  retrying?: boolean;
  onScan: () => void;
  onRetryFailed?: () => void;
}

export function OdooSourceMapPanel({
  data,
  loading,
  scanning,
  retrying = false,
  onScan,
  onRetryFailed,
}: OdooSourceMapPanelProps) {
  if (loading && !data) {
    return <p className="text-body text-text-muted">Loading Odoo source map…</p>;
  }
  if (!data) {
    return <p className="text-body text-text-muted">No Odoo source map available.</p>;
  }

  const groups = groupSourcesByDisplayGroup(data);
  const active = isScanActive(data);
  const failedCount = failedSourceCount(data);
  const progress = data.scan_progress;
  const pct = scanProgressPercent(progress);

  return (
    <div className="space-y-6" data-testid="odoo-source-map">
      {/* Header: runtime ids + scan */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded bg-accent/10 px-2 py-0.5 text-caption font-medium text-accent">
              Generic Source Map
            </span>
            <StatusPill
              status={data.odoo_enabled ? 'connected' : 'disconnected'}
              label={`Odoo: ${data.odoo_enabled ? 'enabled' : 'off'}`}
            />
            <StatusPill
              status={data.extended_enabled ? 'connected' : 'degraded'}
              label={`Extended retrieval: ${data.extended_enabled ? 'on' : 'off'}`}
            />
            <span className="rounded bg-surface-overlay px-2 py-0.5 font-mono text-caption text-text-muted">
              status: {data.project_source_status}
            </span>
          </div>
          <div className="flex flex-wrap gap-4 text-caption text-text-muted">
            <span>
              Odoo project id:{' '}
              <span className="font-mono text-text-secondary">
                {data.odoo_project_id ?? 'not set'}
              </span>
            </span>
            <span>
              Analytic account id:{' '}
              <span className="font-mono text-text-secondary">
                {data.analytic_account_id ?? 'not set'}
              </span>
            </span>
            <span>{data.sources.length} sources</span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {failedCount > 0 && onRetryFailed && (
            <Button
              variant="secondary"
              onClick={onRetryFailed}
              isLoading={retrying}
              disabled={active || scanning}
            >
              Retry failed ({failedCount})
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={onScan}
            isLoading={scanning || active}
            disabled={!data.odoo_enabled}
          >
            {active ? 'Scanning…' : 'Scan Odoo Sources'}
          </Button>
        </div>
      </div>

      {/* Live scan progress */}
      {data.scan_session_id && progress && (
        <div
          className="rounded-sm border border-border bg-surface-base p-3"
          data-testid="scan-progress"
        >
          <div className="mb-1 flex items-center justify-between">
            <span className="text-label font-medium text-text-secondary">
              Scan progress
            </span>
            <span className="font-mono text-caption text-text-muted">
              {scanProgressLabel(progress)}
              {data.scan_count_supported === false ? ' · counts capped' : ''}
              {data.scan_count_supported ? ' · exact totals' : ''}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded bg-surface-overlay">
            <div
              className={`h-full transition-all ${
                data.scan_state === 'failed'
                  ? 'bg-error'
                  : data.scan_state === 'partial'
                    ? 'bg-warning'
                    : 'bg-accent'
              }`}
              style={{ width: `${pct}%` }}
              data-testid="scan-progress-bar"
            />
          </div>
          <p className="mt-1 text-caption text-text-muted">
            {active
              ? 'Scanning in safe batches — this view updates as each source completes.'
              : `Scan ${data.scan_state ?? 'finished'}.`}
          </p>
        </div>
      )}

      {/* Generic notices */}
      <div className="rounded-sm border border-border bg-surface-base p-3">
        <p className="mb-1 text-label font-medium text-text-secondary">About this map</p>
        <ul className="list-disc space-y-0.5 pl-5 text-caption text-text-muted">
          {data.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
        {data.last_scanned_at && (
          <p className="mt-2 text-caption text-text-muted">
            Last scan: {new Date(data.last_scanned_at).toLocaleString()}
          </p>
        )}
      </div>

      {/* Enabled categories */}
      <div>
        <p className="mb-1 text-label font-medium text-text-secondary">
          Enabled Odoo source categories ({data.enabled_categories.length}/{data.groups.length})
        </p>
        {data.enabled_categories.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {data.enabled_categories.map((c) => (
              <span
                key={c}
                className="rounded bg-success/10 px-2 py-0.5 text-caption text-success"
              >
                {c}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-caption text-warning">
            No active categories — set the Odoo project id and analytic account id (and enable Odoo).
          </p>
        )}
      </div>

      {/* Source groups */}
      <div className="space-y-4">
        {groups.map((g) => (
          <div
            key={g.group}
            className="overflow-hidden rounded-sm border border-border bg-surface-raised"
            data-testid={`source-group-${g.group}`}
          >
            <div className="flex items-center justify-between border-b border-border bg-surface-base px-3 py-2">
              <span className="text-label font-medium text-text-primary">{g.group}</span>
              <span className="text-caption text-text-muted">
                {g.mappableCount}/{g.totalCount} active
              </span>
            </div>
            <div className="divide-y divide-border">
              {g.sources.map((s) => {
                const scan = scanStatusPill(s.last_scan_status);
                const conf = confidencePill(s.confidence);
                const dur = durationLabel(s.duration_ms);
                return (
                  <div key={`${g.group}:${s.key}`} className="px-3 py-2" data-testid={`source-row-${s.key}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-body font-medium text-text-primary">
                          {s.source_name}
                        </p>
                        <p className="truncate font-mono text-caption text-text-muted">
                          {s.model} · {s.link_path} ({s.link_scope})
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                        <StatusPill status={conf.status} label={conf.label} />
                        <StatusPill
                          status={s.mappable ? 'connected' : 'disconnected'}
                          label={s.mappable ? `→ ${s.link_value}` : 'not mappable'}
                        />
                        <StatusPill status={scan.status} label={scan.label} />
                        <span
                          className="rounded bg-surface-overlay px-2 py-0.5 font-mono text-caption text-text-secondary"
                          data-testid={`source-count-${s.key}`}
                        >
                          {recordCountLabel(s)} records
                        </span>
                        {dur && (
                          <span className="font-mono text-caption text-text-muted">{dur}</span>
                        )}
                      </div>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-text-muted">
                      <span className="rounded bg-surface-overlay px-1.5 py-0.5">{s.gap_type}</span>
                      {s.complete && s.total != null && (
                        <span className="text-success">exact total: {s.total}</span>
                      )}
                      {s.pages_done > 0 && <span>{s.pages_done} batch(es)</span>}
                      <span>
                        Key fields:{' '}
                        <span className="font-mono text-text-secondary">
                          {s.key_fields.slice(0, 6).join(', ')}
                          {s.key_fields.length > 6 ? ` +${s.key_fields.length - 6}` : ''}
                        </span>
                      </span>
                    </div>
                    {s.error && (
                      <p className="mt-1 text-caption text-error" data-testid={`source-error-${s.key}`}>
                        ✕ {s.error}
                      </p>
                    )}
                    {s.warning && (
                      <p className="mt-1 text-caption text-warning">⚠ {s.warning}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Missing / disabled sources */}
      {data.missing_sources.length > 0 && (
        <div className="rounded-sm border border-warning/40 bg-warning/10 p-3">
          <p className="text-label font-medium text-text-primary">
            Missing / disabled sources ({data.missing_sources.length})
          </p>
          <p className="mt-1 text-caption text-text-secondary">
            These sources cannot run for this project (Odoo disabled, or the required project /
            analytic id is not set): {data.missing_sources.join(', ')}
          </p>
        </div>
      )}

      {/* Denylisted / ambiguous paths */}
      <div className="rounded-sm border border-error/30 bg-error/5 p-3" data-testid="denylisted-paths">
        <p className="text-label font-medium text-text-primary">
          Ambiguous / denylisted paths — never queried ({data.denylisted_paths.length})
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {data.denylisted_paths.map((p) => (
            <span
              key={p}
              className="rounded bg-surface-overlay px-2 py-0.5 font-mono text-caption text-text-muted line-through"
            >
              {p}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
