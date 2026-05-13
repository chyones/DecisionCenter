/**
 * Report View — Phase 2A Slice 5.
 *
 * Per `docs/design/UI_CONTRACT_v1.md` §2.3:
 * - Route: `/workspace/report/{request_id}`
 * - Report content with superscript citations linking to Evidence Panel.
 * - Financial Position conditional rendering per role (`can_access_odoo_budget`).
 * - Conflicts Detected and Missing Data sections always rendered if non-empty.
 * - Report states: staging, needs_review, approved, rejected, final.
 * - needs_review requester: QG flags only. Reviewer: watermarked draft + actions.
 * - Evidence Panel slide-in.
 *
 * Limitation: `GET /reports/{id}` does not exist at backend HEAD. The screen
 * renders a contract-correct static shell with dev-only state toggles. No backend
 * data is invented.
 */

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Check,
  X,
  Eye,
} from 'lucide-react';

import { Button, StatusPill } from '../components';
import { useHashPath, useRole } from '../routing';
import { EvidencePanel } from './EvidencePanel';
import { ExportPanel } from './ExportPanel';

import type { Role } from '../routing/roles';

type ReportState = 'staging' | 'needs_review' | 'approved' | 'rejected' | 'final';

const ROLES_WITH_BUDGET: Role[] = [
  'executive',
  'project_manager',
  'finance',
  'commercial',
  'procurement',
  'legal',
  'auditor',
];

const STATE_OPTIONS: ReportState[] = [
  'staging',
  'needs_review',
  'approved',
  'rejected',
  'final',
];

function canAccessBudget(role: Role): boolean {
  return ROLES_WITH_BUDGET.includes(role);
}

function canApprove(role: Role): boolean {
  return !['auditor', 'admin'].includes(role);
}

function Watermark() {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-[0.06]">
      <span className="rotate-[-12deg] text-[4rem] font-bold uppercase tracking-widest text-text-primary">
        Draft — Awaiting Review
      </span>
    </div>
  );
}

export function ReportViewScreen() {
  const path = useHashPath();
  const { role } = useRole();
  const requestId = useMemo(() => {
    const m = path.match(/^\/workspace\/report\/([^/]+)$/);
    return m ? m[1] : null;
  }, [path]);

  const [reportState, setReportState] = useState<ReportState>('approved');
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  if (!requestId) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <AlertCircle className="h-12 w-12 text-error" aria-hidden="true" />
        <h2 className="mt-3 text-heading font-semibold text-text-primary">
          Invalid URL
        </h2>
        <p className="mt-2 max-w-[400px] text-body text-text-secondary">
          Report request ID is missing from the URL.
        </p>
      </div>
    );
  }

  const isReviewer = canApprove(role);
  const showBudget = canAccessBudget(role);

  // needs_review requester view (QG flags only)
  if (reportState === 'needs_review' && !isReviewer) {
    return (
      <div>
        <PageHeader requestId={requestId} reportState={reportState} />

        <div className="rounded-sm border border-warning bg-warning/10 p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
            <div>
              <h2 className="text-heading font-semibold text-warning">
                Report flagged for mandatory review
              </h2>
              <p className="mt-2 text-body text-text-secondary">
                Your report has been flagged for mandatory review. Report content
                is not available until a reviewer has approved it.
              </p>
              <div className="mt-4">
                <h3 className="text-label font-medium text-text-secondary">
                  Quality gate flags:
                </h3>
                <ul className="mt-2 space-y-1 text-body text-text-secondary">
                  <li className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-warning" />
                    Section 3 claim has no Odoo evidence_id
                  </li>
                  <li className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-warning" />
                    Missing Data section is non-empty
                  </li>
                </ul>
              </div>
              <div className="mt-6">
                <Button
                  variant="primary"
                  onClick={() => {
                    window.location.hash = '/workspace/new';
                  }}
                >
                  New query
                </Button>
              </div>
            </div>
          </div>
        </div>

        {import.meta.env.DEV && <DevStateToggle state={reportState} onChange={setReportState} />}
      </div>
    );
  }

  return (
    <div className="relative">
      <PageHeader requestId={requestId} reportState={reportState} />

      {/* needs_review reviewer watermark */}
      {reportState === 'needs_review' && isReviewer && <Watermark />}

      {/* needs_review reviewer QG banner */}
      {reportState === 'needs_review' && isReviewer && (
        <div className="mb-4 rounded-sm border border-warning bg-warning/10 p-4">
          <h3 className="flex items-center gap-2 text-body font-medium text-warning">
            <AlertTriangle className="h-4 w-4" />
            Quality gate flags (2)
          </h3>
          <ul className="mt-2 space-y-1 text-body text-text-secondary">
            <li className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              Section 3 claim: no Odoo ID
            </li>
            <li className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              Missing Data: non-empty
            </li>
          </ul>
        </div>
      )}

      {/* rejected banner */}
      {reportState === 'rejected' && (
        <div className="mb-4 rounded-sm border border-error bg-error/10 p-4">
          <h3 className="flex items-center gap-2 text-body font-medium text-error">
            <X className="h-4 w-4" />
            Report rejected
          </h3>
          <p className="mt-1 text-body text-text-secondary">
            This report was rejected by a reviewer. Reason: Insufficient evidence
            for Section 3 claims.
          </p>
        </div>
      )}

      {/* Action bar */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            icon={<Eye className="h-4 w-4" />}
            onClick={() => setEvidenceOpen(true)}
          >
            Evidence
          </Button>
          <Button
            variant="secondary"
            onClick={() => setExportOpen(true)}
            disabled={reportState === 'needs_review'}
          >
            Export ▾
          </Button>
        </div>

        {/* Reviewer actions for needs_review */}
        {reportState === 'needs_review' && isReviewer && (
          <div className="flex items-center gap-2">
            <Button variant="primary" icon={<Check className="h-4 w-4" />} disabled>
              Approve
            </Button>
            <Button variant="danger" icon={<X className="h-4 w-4" />} disabled>
              Reject
            </Button>
            <Button
              variant="secondary"
              icon={<AlertCircle className="h-4 w-4" />}
              disabled
            >
              Request revision
            </Button>
          </div>
        )}
      </div>

      {/* Report content */}
      <div className="space-y-6">
        {/* Executive Summary */}
        <section className="rounded-sm border border-border bg-surface-raised p-4">
          <h2 className="text-heading font-semibold text-text-primary">
            Executive Summary
          </h2>
          <div className="mt-3 space-y-2 text-body text-text-secondary">
            <p>
              Contract CON-001 with Vendor X is active. Outstanding payment is AED
              142,000 as of{' '}
              <sup className="cursor-pointer text-accent hover:underline">1</sup>{' '}
              2026-04-30, per Odoo records{' '}
              <sup className="cursor-pointer text-accent hover:underline">2</sup>.
            </p>
            <p>
              The project timeline remains on track with no identified blockers.
              All deliverables for Phase 1 have been accepted.
            </p>
          </div>
        </section>

        {/* Financial Position — conditional */}
        <section className="rounded-sm border border-border bg-surface-raised p-4">
          <h2 className="text-heading font-semibold text-text-primary">
            Financial Position
          </h2>
          {showBudget ? (
            <div className="mt-3 space-y-2 text-body text-text-secondary">
              <p>
                Total contract value: AED 1,250,000. Invoiced to date: AED
                980,000. Outstanding: AED 270,000.
              </p>
              <p>
                Budget utilization: 78%. Forecast completion: within budget.
              </p>
            </div>
          ) : (
            <p className="mt-3 text-body text-text-muted">
              [Financial data is not available for your role]
            </p>
          )}
        </section>

        {/* Conflicts Detected */}
        <section className="rounded-sm border border-border bg-surface-raised p-4">
          <h2 className="text-heading font-semibold text-text-primary">
            Conflicts Detected
          </h2>
          <div className="mt-3 space-y-2 text-body text-text-secondary">
            <p className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              Invoice date in Odoo (2026-04-15) differs from email confirmation
              (2026-04-18).
            </p>
          </div>
        </section>

        {/* Missing Data */}
        <section className="rounded-sm border border-border bg-surface-raised p-4">
          <h2 className="text-heading font-semibold text-text-primary">
            Missing Data
          </h2>
          <div className="mt-3 space-y-2 text-body text-text-secondary">
            <p className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
              No PO reference found for Change Order #3.
            </p>
          </div>
        </section>

        {/* Sources */}
        <section className="rounded-sm border border-border bg-surface-raised p-4">
          <h2 className="text-heading font-semibold text-text-primary">Sources</h2>
          <div className="mt-3 flex flex-wrap gap-3 text-body text-text-secondary">
            <span>
              <sup className="text-accent">1</sup> Odoo · account.analytic.line
            </span>
            <span>
              <sup className="text-accent">2</sup> SharePoint · Contract doc
            </span>
            <span>
              <sup className="text-accent">3</sup> Email · Shared mailbox
            </span>
          </div>
        </section>
      </div>

      {/* Evidence Panel */}
      <EvidencePanel isOpen={evidenceOpen} onClose={() => setEvidenceOpen(false)} />

      {/* Export Panel */}
      <ExportPanel
        isOpen={exportOpen}
        onClose={() => setExportOpen(false)}
        requestId={requestId}
        reportState={reportState}
        qualityGate="passed"
        role={role}
      />

      {/* Dev-only state toggle */}
      {import.meta.env.DEV && <DevStateToggle state={reportState} onChange={setReportState} />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                     */
/* ------------------------------------------------------------------ */

function PageHeader({
  requestId,
  reportState,
}: {
  requestId: string;
  reportState: ReportState;
}) {
  const statusMap: Record<ReportState, { status: 'staging' | 'needs_review' | 'approved' | 'rejected' | 'final'; label: string }> = {
    staging: { status: 'staging', label: 'Staging' },
    needs_review: { status: 'needs_review', label: 'Needs review' },
    approved: { status: 'approved', label: 'Approved' },
    rejected: { status: 'rejected', label: 'Rejected' },
    final: { status: 'final', label: 'Final' },
  };

  const mapped = statusMap[reportState];

  return (
    <div className="mb-6 flex items-baseline justify-between">
      <div>
        <div className="flex items-center gap-2">
          <StatusPill status={mapped.status} label={mapped.label} />
          <span className="text-body font-medium text-text-primary">
            PRJ-001
          </span>
        </div>
        <p className="mt-1 text-caption text-text-muted">
          Request: <code className="text-text-secondary">{requestId}</code> ·
          2026-05-06 14:22 · executive
        </p>
      </div>
      <span className="text-caption text-text-muted">
        static shell — no report endpoint
      </span>
    </div>
  );
}

function DevStateToggle({
  state,
  onChange,
}: {
  state: ReportState;
  onChange: (s: ReportState) => void;
}) {
  return (
    <div className="mt-8 rounded-sm border border-dashed border-border bg-surface-raised p-3">
      <span className="text-label font-medium text-text-secondary">
        Dev — preview report state:
      </span>
      <div className="mt-2 flex flex-wrap gap-2">
        {STATE_OPTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onChange(s)}
            className={`rounded-sm px-2 py-1 text-caption ${
              state === s
                ? 'bg-accent text-text-primary'
                : 'bg-surface-overlay text-text-secondary hover:bg-surface-base'
            }`}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
