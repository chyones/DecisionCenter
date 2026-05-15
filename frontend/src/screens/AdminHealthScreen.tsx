import { useEffect, useState, useCallback } from 'react';
import { Activity, AlertTriangle, XCircle } from 'lucide-react';
import { StatusPill } from '../components';
import { useApi } from '../api';
import type { HealthLiveResponse, CostResponse } from '../api/types';
import { useToasts } from '../components/ToastProvider';

function Sparkline({ values, height = 24 }: { values: number[]; height?: number }) {
  if (values.length === 0) {
    return <span className="text-body text-text-muted">—</span>;
  }
  const max = Math.max(...values, 1);
  return (
    <div className="flex items-end gap-px" style={{ height }}>
      {values.map((v, i) => {
        const pct = (v / max) * 100;
        return (
          <div
            key={i}
            className="w-1 rounded-sm bg-accent/60"
            style={{ height: `${pct}%`, minHeight: 2 }}
            title={`${v}ms`}
          />
        );
      })}
    </div>
  );
}

function CostBar({
  label,
  current,
  cap,
  percent,
}: {
  label: string;
  current: number;
  cap: number;
  percent: number;
}) {
  const colorClass =
    percent >= 100
      ? 'bg-error'
      : percent >= 80
        ? 'bg-warning'
        : 'bg-success';
  return (
    <div>
      <div className="flex items-center justify-between text-body text-text-secondary">
        <span>{label}</span>
        <span className="font-mono text-mono text-text-muted">
          ${current.toFixed(2)} / ${cap.toFixed(2)}
        </span>
      </div>
      <div className="mt-2 h-2 w-full rounded-sm border border-border bg-surface-base">
        <div
          className={`h-full rounded-sm ${colorClass} transition-all`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
      <div className="mt-1 text-right text-caption text-text-muted">
        {percent.toFixed(1)}%
      </div>
    </div>
  );
}

export function AdminHealthScreen() {
  const api = useApi();
  const { addToast } = useToasts();
  const [health, setHealth] = useState<HealthLiveResponse | null>(null);
  const [cost, setCost] = useState<CostResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [h, c] = await Promise.all([
        api.get<HealthLiveResponse>('/admin/health/live'),
        api.get<CostResponse>('/admin/cost'),
      ]);
      setHealth(h);
      setCost(c);
    } catch (err) {
      addToast('error', err instanceof Error ? err.message : 'Failed to load health data', 'Health check failed');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, addToast]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const handleRefresh = () => {
    setRefreshing(true);
    void fetchData();
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Activity className="h-6 w-6 animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div>
      {/* Page header */}
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          System Health
        </h1>
        <div className="flex items-center gap-4">
          {health && (
            <span className="text-caption text-text-muted">
              Last: {new Date(health.checked_at).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="rounded-sm border border-border bg-surface-raised px-3 py-1.5 text-label text-text-secondary hover:bg-surface-overlay disabled:opacity-50"
          >
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Cost warning / exceeded banners */}
      {cost?.exceeded && (
        <div className="mb-6 flex items-center gap-3 rounded-sm border border-error/30 bg-error/10 p-4 text-body text-error">
          <XCircle className="h-5 w-5 shrink-0" />
          <span>
            Daily cost cap reached — ${cost.daily_cost.toFixed(2)} / $
            {cost.daily_cap.toFixed(2)}. New report submissions are blocked.
          </span>
        </div>
      )}
      {cost?.warning && !cost.exceeded && (
        <div className="mb-6 flex items-center gap-3 rounded-sm border border-warning/30 bg-warning/10 p-4 text-body text-warning">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span>
            Daily cost at {cost.daily_percent.toFixed(0)}% — $
            {cost.daily_cost.toFixed(2)} / ${cost.daily_cap.toFixed(2)}
          </span>
        </div>
      )}

      {/* Services table */}
      <div className="overflow-hidden rounded-sm border border-border">
        <table className="w-full border-collapse">
          <thead>
            <tr className="h-10 border-b border-border bg-surface-raised">
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                Service
              </th>
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                Status
              </th>
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                Latency
              </th>
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                SLA
              </th>
              <th className="px-3 py-2 text-left text-label font-medium text-text-secondary">
                Trend (24h)
              </th>
            </tr>
          </thead>
          <tbody>
            {health?.services.map((svc) => (
              <tr
                key={svc.name}
                className="h-9 border-b border-border bg-surface-base transition-colors duration-150 hover:bg-surface-overlay"
              >
                <td className="px-3 py-2 text-body text-text-primary">
                  {svc.display_name}
                </td>
                <td className="px-3 py-2">
                  <StatusPill
                    status={
                      svc.status === 'ok'
                        ? 'connected'
                        : svc.status === 'error'
                          ? 'disconnected'
                          : 'unknown'
                    }
                  />
                </td>
                <td
                  className={`px-3 py-2 font-mono text-mono ${svc.latency_ms > svc.sla_ms ? 'text-error' : 'text-text-secondary'}`}
                >
                  {svc.latency_ms}ms
                </td>
                <td className="px-3 py-2 font-mono text-mono text-text-secondary">
                  {svc.sla_ms}ms
                </td>
                <td className="px-3 py-2">
                  <Sparkline values={svc.sparkline_24h} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Cost Monitor */}
      <div className="mt-8 rounded-md border border-border bg-surface-raised p-6">
        <h2 className="text-heading font-semibold text-text-primary">
          Cost Monitor
        </h2>
        <div className="mt-4 space-y-6">
          {cost && (
            <>
              <CostBar
                label="Today"
                current={cost.daily_cost}
                cap={cost.daily_cap}
                percent={cost.daily_percent}
              />
              <CostBar
                label="Monthly"
                current={cost.monthly_cost}
                cap={cost.monthly_cap}
                percent={cost.monthly_percent}
              />
              {cost.llm_breakdown.length > 0 && (
                <div>
                  <h3 className="mb-3 text-label font-medium text-text-secondary">
                    LLM Today
                  </h3>
                  <div className="space-y-2">
                    {cost.llm_breakdown.map((item) => (
                      <div
                        key={item.model}
                        className="flex items-center justify-between text-body text-text-secondary"
                      >
                        <span>{item.model}</span>
                        <span className="font-mono text-mono text-text-muted">
                          {item.calls} calls · ${item.cost_usd.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
