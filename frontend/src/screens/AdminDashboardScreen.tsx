import { useEffect, useState, useCallback } from 'react';
import { useApi } from '../api';
import type { DashboardSummary, DashboardServiceStatus } from '../api/types';
import { useToasts } from '../components/ToastProvider';

function StatCard({ title, value, sub, bar, barPercent, barColor, onClick }: {
  title: string; value: string; sub?: string;
  bar?: boolean; barPercent?: number; barColor?: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={['rounded-sm border border-border bg-surface-raised p-4',
        onClick ? 'cursor-pointer hover:bg-surface-overlay transition-colors' : ''].join(' ')}
    >
      <p className="text-label text-text-secondary">{title}</p>
      <p className="mt-1 text-display font-semibold text-text-primary">{value}</p>
      {sub && <p className="text-caption text-text-muted">{sub}</p>}
      {bar && barPercent !== undefined && (
        <div className="mt-2 h-1.5 w-full rounded-sm bg-surface-base border border-border">
          <div className={`h-full rounded-sm ${barColor ?? 'bg-accent'} transition-all`}
               style={{ width: `${Math.min(barPercent, 100)}%` }} />
        </div>
      )}
    </div>
  );
}

function ServiceDot({ svc }: { svc: DashboardServiceStatus }) {
  const color = svc.status === 'ok' ? 'text-success'
    : svc.status === 'error' ? 'text-error' : 'text-text-muted';
  return (
    <div className="flex items-center gap-2 text-body text-text-secondary">
      <span className={`text-lg leading-none ${color}`}>●</span>
      <span>{svc.display_name}</span>
    </div>
  );
}

export function AdminDashboardScreen() {
  const api = useApi();
  const { addToast } = useToasts();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get<DashboardSummary>('/admin/dashboard/summary');
      setData(res);
    } catch {
      addToast('error', 'Failed to load dashboard');
    }
  }, [api, addToast]);

  useEffect(() => {
    setLoading(true);
    fetchData().finally(() => setLoading(false));
  }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-body text-text-muted">Loading dashboard…</div>
      </div>
    );
  }

  const dailyBarColor =
    (data?.daily_percent ?? 0) >= 100 ? 'bg-error'
    : (data?.daily_percent ?? 0) >= 80 ? 'bg-warning'
    : 'bg-success';

  const monthlyBarColor =
    (data?.monthly_percent ?? 0) >= 100 ? 'bg-error'
    : (data?.monthly_percent ?? 0) >= 80 ? 'bg-warning'
    : 'bg-success';

  return (
    <div className="p-6">
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">Dashboard</h1>
        <div className="flex items-center gap-4">
          {data && (
            <span className="text-caption text-text-muted">
              Last: {new Date(data.checked_at).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="rounded-sm border border-border bg-surface-raised px-3 py-1.5 text-label text-text-primary hover:bg-surface-overlay disabled:opacity-50"
          >
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Stat grid */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard
          title="Services"
          value={`${data?.services_ok ?? 0}/${data?.services_total ?? 0} ok`}
          onClick={() => window.location.replace('#/admin/health')}
        />
        <StatCard
          title="Approvals"
          value={`${data?.approvals_pending ?? 0} pending`}
          onClick={() => window.location.replace('#/admin/approvals')}
        />
        <StatCard
          title="Daily Cost"
          value={`$${(data?.daily_cost ?? 0).toFixed(2)} / $${(data?.daily_cap ?? 0).toFixed(2)}`}
          sub={`${(data?.daily_percent ?? 0).toFixed(1)}%`}
          bar
          barPercent={data?.daily_percent ?? 0}
          barColor={dailyBarColor}
          onClick={() => window.location.replace('#/admin/health')}
        />
        <StatCard
          title="Requests Today"
          value={`${data?.requests_today ?? 0}`}
          sub="report submissions"
        />
        <StatCard
          title="Failed QG Today"
          value={`${data?.failed_qg_today ?? 0}`}
          sub="quality gate failures"
        />
        <StatCard
          title="Monthly"
          value={`$${(data?.monthly_cost ?? 0).toFixed(2)} / $${(data?.monthly_cap ?? 0).toFixed(2)}`}
          sub={`${(data?.monthly_percent ?? 0).toFixed(1)}%`}
          bar
          barPercent={data?.monthly_percent ?? 0}
          barColor={monthlyBarColor}
          onClick={() => window.location.replace('#/admin/health')}
        />
      </div>

      {/* External Services grid */}
      <div className="mb-8">
        <h2 className="mb-3 text-title font-semibold text-text-primary">External Services</h2>
        <div className="grid grid-cols-3 gap-3">
          {data?.services.map((svc) => (
            <ServiceDot key={svc.name} svc={svc} />
          ))}
        </div>
      </div>

      {/* Recent events */}
      <div>
        <h2 className="mb-3 text-title font-semibold text-text-primary">Recent Events</h2>
        <div className="rounded-sm border border-border bg-surface-raised">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-2 text-label text-text-secondary">Time</th>
                <th className="px-4 py-2 text-label text-text-secondary">Event Type</th>
                <th className="px-4 py-2 text-label text-text-secondary">Project</th>
                <th className="px-4 py-2 text-label text-text-secondary">Detail</th>
              </tr>
            </thead>
            <tbody>
              {data?.recent_events && data.recent_events.length > 0 ? (
                data.recent_events.map((ev) => (
                  <tr key={ev.event_id} className="border-b border-border last:border-0">
                    <td className="px-4 py-2 text-body text-text-primary">
                      {ev.ts ? new Date(ev.ts).toLocaleTimeString() : '—'}
                    </td>
                    <td className="px-4 py-2 text-body text-text-primary">{ev.event_type}</td>
                    <td className="px-4 py-2 text-body text-text-primary">{ev.project_code ?? '—'}</td>
                    <td className="px-4 py-2 text-body text-text-primary">{ev.detail}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-4 py-4 text-center text-body text-text-muted">
                    No recent events
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
