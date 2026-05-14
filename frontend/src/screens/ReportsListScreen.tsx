import { useEffect, useMemo, useState } from 'react';
import { Filter, FolderOpen } from 'lucide-react';

import { isApiError, useApi } from '../api';
import type { ReportListResponse, ReportState, ReportSummary } from '../api';
import { StatusPill } from '../components';
import { useRole } from '../routing';
import type { StatusValue } from '../tokens';

const GROUPS: {
  title: string;
  states: ReportState[];
  emptyText: string;
}[] = [
  {
    title: 'In progress',
    states: ['staging'],
    emptyText:
      'No in-progress reports. Submit a query from the Query Composer to see reports here.',
  },
  {
    title: 'Awaiting review',
    states: ['needs_review', 'revision_requested'],
    emptyText: 'No reports awaiting review.',
  },
  {
    title: 'Approved / Final',
    states: ['approved', 'final'],
    emptyText: 'No approved or finalized reports.',
  },
];

const STATE_OPTIONS: { label: string; value: ReportState | '' }[] = [
  { label: 'All states', value: '' },
  { label: 'Staging', value: 'staging' },
  { label: 'Needs review', value: 'needs_review' },
  { label: 'Approved', value: 'approved' },
  { label: 'Final', value: 'final' },
  { label: 'Failed', value: 'failed' },
  { label: 'Cancelled', value: 'cancelled' },
];

export function ReportsListScreen() {
  const api = useApi();
  const { role } = useRole();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [projectFilter, setProjectFilter] = useState('');
  const [stateFilter, setStateFilter] = useState<ReportState | ''>('');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const isAuditor = role === 'auditor';

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams();
    if (projectFilter) params.set('project_code', projectFilter);
    if (stateFilter) params.set('state', stateFilter);

    setIsLoading(true);
    api
      .get<ReportListResponse>(`/reports${params.size ? `?${params}` : ''}`)
      .then((res) => {
        if (!active) return;
        setReports(res.reports);
        setErrorMsg('');
      })
      .catch((err) => {
        if (!active) return;
        let message = 'Unable to load reports.';
        if (isApiError(err)) {
          message = err.status === 0
            ? 'Network error — please check your connection and try again.'
            : err.message;
        } else if (err instanceof Error) {
          message = err.message;
        }
        setErrorMsg(message);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, projectFilter, stateFilter]);

  const projects = useMemo(
    () =>
      Array.from(
        new Set(reports.map((report) => report.project_code).filter(Boolean)),
      ) as string[],
    [reports],
  );

  return (
    <div>
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          My Reports
        </h1>
        <span className="text-caption text-text-muted">
          {isAuditor ? 'auditor read-only' : 'live list'}
        </span>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-sm border border-border bg-surface-raised p-3">
        <span className="text-label text-text-secondary">
          <Filter className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
          Filters:
        </span>
        <select
          value={projectFilter}
          onChange={(event) => setProjectFilter(event.target.value)}
          className="h-8 rounded-sm border border-border bg-surface-base px-2 text-label text-text-secondary"
        >
          <option value="">All projects</option>
          {projects.map((project) => (
            <option key={project} value={project}>{project}</option>
          ))}
        </select>
        <select
          value={stateFilter}
          onChange={(event) => setStateFilter(event.target.value as ReportState | '')}
          className="h-8 rounded-sm border border-border bg-surface-base px-2 text-label text-text-secondary"
        >
          {STATE_OPTIONS.map((option) => (
            <option key={option.label} value={option.value}>{option.label}</option>
          ))}
        </select>
        <span className="ml-auto text-caption text-text-muted">
          {isAuditor ? 'Auditor view: read-only' : 'Showing your requests only'}
        </span>
      </div>

      {errorMsg && (
        <div role="alert" className="mb-4 rounded-sm border border-error bg-error/10 p-3 text-body text-error">
          {errorMsg}
        </div>
      )}

      {isLoading ? (
        <div className="rounded-sm border border-border bg-surface-raised p-6 text-body text-text-secondary">
          Loading reports…
        </div>
      ) : (
        <div className="space-y-8">
          {GROUPS.map((group) => {
            const rows = reports.filter((report) => group.states.includes(report.state));
            return (
              <ReportGroup
                key={group.title}
                title={group.title}
                rows={rows}
                emptyText={group.emptyText}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

function ReportGroup({
  title,
  rows,
  emptyText,
}: {
  title: string;
  rows: ReportSummary[];
  emptyText: string;
}) {
  return (
    <section>
      <h2 className="mb-3 text-heading font-semibold text-text-primary">
        {title}
      </h2>
      <div className="rounded-sm border border-border">
        <div className="grid grid-cols-[1fr_120px_140px_120px] gap-3 border-b border-border bg-surface-raised px-4 py-2 text-label font-medium text-text-secondary">
          <span>Query</span>
          <span>Project</span>
          <span>Status</span>
          <span>Submitted</span>
        </div>
        {rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
            <FolderOpen className="h-8 w-8 text-text-muted" aria-hidden="true" />
            <p className="mt-2 max-w-[400px] text-body text-text-secondary">
              {emptyText}
            </p>
          </div>
        ) : (
          rows.map((report) => (
            <a
              key={report.request_id}
              href={`#/workspace/report/${report.request_id}`}
              className="grid grid-cols-[1fr_120px_140px_120px] gap-3 border-b border-border px-4 py-3 text-body text-text-secondary transition-colors last:border-b-0 hover:bg-surface-overlay"
            >
              <span className="truncate text-text-primary">
                {report.query_excerpt || 'Untitled report'}
              </span>
              <span>{report.project_code || '—'}</span>
              <StatusPill status={statusForState(report.state)} label={labelForState(report.state)} />
              <span>{report.created_at ? new Date(report.created_at).toLocaleDateString() : '—'}</span>
            </a>
          ))
        )}
      </div>
    </section>
  );
}

function statusForState(state: ReportState): StatusValue {
  if (state === 'revision_requested') return 'needs_review';
  if (state === 'cancelled') return 'rejected';
  return state === 'failed' ? 'failed' : state;
}

function labelForState(state: ReportState): string {
  return state.replace(/_/g, ' ');
}
