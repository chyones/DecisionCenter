/**
 * My Reports List — Phase 2A Slice 3.
 *
 * Per `docs/design/UI_CONTRACT_v1.md` §2.6:
 * - Group by state: In progress, Awaiting review, Approved / Final.
 * - Role-scoped: own requests only (auditor sees project-scoped read-only).
 * - Filters by project, state, date range.
 * - Click row → Report View.
 *
 * Limitation: `GET /reports` does not exist at backend HEAD. The structural layout
 * is rendered with empty-state messaging per group. No backend data is invented.
 */

import { Filter, FolderOpen } from 'lucide-react';

import { StatusPill } from '../components';
import { useRole } from '../routing';

const GROUPS = [
  {
    title: 'In progress',
    statuses: ['processing' as const, 'staging' as const],
    emptyText:
      'No in-progress reports. Submit a query from the Query Composer to see reports here.',
  },
  {
    title: 'Awaiting review',
    statuses: ['needs_review' as const],
    emptyText: 'No reports awaiting review.',
  },
  {
    title: 'Approved / Final',
    statuses: ['approved' as const, 'final' as const],
    emptyText: 'No approved or finalized reports.',
  },
];

export function ReportsListScreen() {
  const { role } = useRole();

  const isAuditor = role === 'auditor';

  return (
    <div>
      {/* Page header */}
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          My Reports
        </h1>
        <span className="text-caption text-text-muted">
          backend endpoint unavailable
        </span>
      </div>

      {/* Filter bar — disabled placeholders (backend endpoint missing) */}
      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-sm border border-border bg-surface-raised p-3">
        <span className="text-label text-text-secondary">
          <Filter className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
          Filters:
        </span>
        <select
          disabled
          className="h-8 cursor-not-allowed rounded-sm border border-border bg-surface-base px-2 text-label text-text-muted opacity-50"
        >
          <option>All projects</option>
        </select>
        <select
          disabled
          className="h-8 cursor-not-allowed rounded-sm border border-border bg-surface-base px-2 text-label text-text-muted opacity-50"
        >
          <option>All states</option>
        </select>
        <input
          type="text"
          disabled
          placeholder="Date range"
          className="h-8 cursor-not-allowed rounded-sm border border-border bg-surface-base px-2 text-label text-text-muted opacity-50"
        />
        <span className="ml-auto text-caption text-text-muted">
          {isAuditor
            ? 'Auditor view: project-scoped read-only'
            : 'Showing your requests only'}
        </span>
      </div>

      {/* Report groups */}
      <div className="space-y-8">
        {GROUPS.map((group) => (
          <section key={group.title}>
            <h2 className="mb-3 text-heading font-semibold text-text-primary">
              {group.title}
            </h2>
            <div className="rounded-sm border border-border">
              {/* Header row */}
              <div className="grid grid-cols-[1fr_120px_140px_120px] gap-3 border-b border-border bg-surface-raised px-4 py-2 text-label font-medium text-text-secondary">
                <span>Query</span>
                <span>Project</span>
                <span>Status</span>
                <span>Submitted</span>
              </div>

              {/* Empty state */}
              <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
                <FolderOpen
                  className="h-8 w-8 text-text-muted"
                  aria-hidden="true"
                />
                <p className="mt-2 max-w-[400px] text-body text-text-secondary">
                  {group.emptyText}
                </p>
                <p className="mt-1 text-caption text-text-muted">
                  Report listing requires a live backend endpoint (
                  <code>GET /reports</code>) that is not yet available.
                </p>
              </div>

              {/* Status legend (contract-correct examples, non-interactive) */}
              <div className="flex flex-wrap items-center gap-2 border-t border-border bg-surface-raised px-4 py-2">
                <span className="text-caption text-text-muted">
                  Status types:
                </span>
                {group.statuses.map((s) => (
                  <StatusPill key={s} status={s} />
                ))}
              </div>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
