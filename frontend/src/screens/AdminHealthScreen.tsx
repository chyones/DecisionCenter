import { StatusPill } from '../components';
import type { StatusValue } from '../tokens';

interface ServiceRow {
  name: string;
  status: StatusValue;
  latency: string;
  sla: string;
}

/** Static fixture — mirrors the expected System Health layout (contract §E.6). */
const SERVICES: ServiceRow[] = [
  { name: 'PostgreSQL', status: 'connected', latency: '12ms', sla: '200ms' },
  { name: 'Redis', status: 'connected', latency: '3ms', sla: '100ms' },
  { name: 'Qdrant', status: 'connected', latency: '28ms', sla: '300ms' },
  { name: 'MinIO', status: 'connected', latency: '45ms', sla: '500ms' },
  { name: 'n8n', status: 'connected', latency: '102ms', sla: '500ms' },
  { name: 'SharePoint', status: 'connected', latency: '340ms', sla: '1000ms' },
  { name: 'Graph API', status: 'connected', latency: '280ms', sla: '1000ms' },
  { name: 'ownCloud', status: 'degraded', latency: '2340ms', sla: '500ms' },
  { name: 'Odoo', status: 'connected', latency: '190ms', sla: '500ms' },
  { name: 'Langfuse', status: 'connected', latency: '210ms', sla: '500ms' },
];

export function AdminHealthScreen() {
  return (
    <div>
      {/* Page header (contract §I.3) */}
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          System Health
        </h1>
        <span className="text-caption text-text-muted">
          static_scaffold — no backend data
        </span>
      </div>

      {/* Subheader (contract §E.6) */}
      <p className="mb-6 text-body text-text-secondary">
        This table shows the expected layout. No live data is displayed.
      </p>

      {/* Table container with outer radius (contract §D.7) */}
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
                Trend
              </th>
            </tr>
          </thead>
          <tbody>
            {SERVICES.map((svc) => (
              <tr
                key={svc.name}
                className="h-9 border-b border-border bg-surface-base transition-colors duration-150 hover:bg-surface-overlay"
              >
                <td className="px-3 py-2 text-body text-text-primary">
                  {svc.name}
                </td>
                <td className="px-3 py-2">
                  <StatusPill status={svc.status} />
                </td>
                <td className="px-3 py-2 font-mono text-mono text-text-secondary">
                  {svc.latency}
                </td>
                <td className="px-3 py-2 font-mono text-mono text-text-secondary">
                  {svc.sla}
                </td>
                <td className="px-3 py-2 text-body text-text-muted">—</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Cost Monitor section (contract §E.6) */}
      <div className="mt-8 rounded-md border border-border bg-surface-raised p-6">
        <h2 className="text-heading font-semibold text-text-primary">
          Cost Monitor
        </h2>
        <div className="mt-4 space-y-4">
          <div>
            <div className="flex items-center justify-between text-body text-text-secondary">
              <span>Daily cost</span>
              <span className="text-caption text-text-muted">—</span>
            </div>
            <div className="mt-2 h-2 w-full rounded-sm border border-border bg-surface-base" />
          </div>
          <div>
            <div className="flex items-center justify-between text-body text-text-secondary">
              <span>Monthly cost</span>
              <span className="text-caption text-text-muted">—</span>
            </div>
            <div className="mt-2 h-2 w-full rounded-sm border border-border bg-surface-base" />
          </div>
        </div>
      </div>
    </div>
  );
}
