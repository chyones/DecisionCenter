import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Check,
  Eye,
  Lock,
  Stamp,
  X,
} from 'lucide-react';

import { Button, StatusPill, useToasts } from '../components';
import { isApiError, useApi } from '../api';
import type { EvidencePanelEntry, ReportContentResponse, ReportState } from '../api';
import { useHashPath, useRole } from '../routing';
import type { StatusValue } from '../tokens';
import { EvidencePanel } from './EvidencePanel';
import { ExportPanel } from './ExportPanel';

import type { Role } from '../routing/roles';

const ROLES_WITH_BUDGET: Role[] = [
  'executive',
  'project_manager',
  'finance',
  'commercial',
  'procurement',
  'legal',
  'auditor',
  'admin',
];

function canAccessBudget(role: Role): boolean {
  return ROLES_WITH_BUDGET.includes(role);
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
  const api = useApi();
  const { addToast } = useToasts();
  const path = useHashPath();
  const { role } = useRole();
  const requestId = useMemo(() => {
    const m = path.match(/^\/workspace\/report\/([^/]+)$/);
    return m ? m[1] : null;
  }, [path]);

  const [report, setReport] = useState<ReportContentResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [actionBusy, setActionBusy] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    if (!requestId) return;
    setIsLoading(true);
    setErrorMsg('');
    try {
      const res = await api.get<ReportContentResponse>(`/reports/${requestId}/content`);
      setReport(res);
    } catch (err) {
      let message = 'Unable to load report.';
      if (isApiError(err)) {
        message = err.status === 0
          ? 'Network error — please check your connection and try again.'
          : err.message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setErrorMsg(message);
    } finally {
      setIsLoading(false);
    }
  }, [api, requestId]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  async function runReviewAction(action: 'approve' | 'reject' | 'request-revision') {
    if (!requestId) return;
    setActionBusy(action);
    try {
      if (action === 'approve') {
        await api.post(`/reports/staging/${requestId}/approve`, {
          comment: 'Approved from Phase 2A workspace.',
        });
      } else if (action === 'reject') {
        const reason = window.prompt('Reason for rejection');
        if (!reason) return;
        await api.post(`/reports/staging/${requestId}/reject`, { reason });
      } else {
        const reason = window.prompt('Requested revision');
        if (!reason) return;
        await api.post(`/reports/staging/${requestId}/request-revision`, { reason });
      }
      addToast('success', 'Review action recorded.', 'Report updated');
      await loadReport();
    } catch (err) {
      let message = 'Review action failed.';
      if (isApiError(err)) message = err.message;
      else if (err instanceof Error) message = err.message;
      addToast('error', message, 'Review action failed');
    } finally {
      setActionBusy(null);
    }
  }

  if (!requestId) {
    return <InvalidReport message="Report request ID is missing from the URL." />;
  }

  if (isLoading) {
    return (
      <div className="rounded-sm border border-border bg-surface-raised p-6 text-body text-text-secondary">
        Loading report…
      </div>
    );
  }

  if (errorMsg || !report) {
    return <InvalidReport message={errorMsg || 'Report not found.'} />;
  }

  const showBudget = canAccessBudget(role);
  const exportsAllowed =
    (report.state === 'approved' || report.state === 'final') &&
    report.quality_gate !== 'failed';
  const showReviewActions = report.can_review && (
    report.state === 'staging' || report.state === 'needs_review'
  );
  const showWatermark = report.can_review && report.state === 'needs_review';
  const failed = report.quality_gate === 'failed' || report.state === 'failed';

  return (
    <div className="relative">
      <PageHeader report={report} />

      {showWatermark && <Watermark />}

      {failed && (
        <div role="alert" className="mb-4 rounded-sm border border-error bg-error/10 p-4">
          <h3 className="flex items-center gap-2 text-body font-medium text-error">
            <X className="h-4 w-4" aria-hidden="true" />
            Quality gate failed
          </h3>
          <p className="mt-1 text-body text-text-secondary">
            Report content and exports are blocked because the quality gate failed.
          </p>
        </div>
      )}

      {report.state === 'staging' && (
        <div role="status" className="mb-4 rounded-sm border border-warning bg-warning/10 p-4">
          <h3 className="flex items-center gap-2 text-body font-medium text-warning">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            Awaiting review
          </h3>
          <p className="mt-1 text-body text-text-secondary">
            This staged report is waiting for an authorized reviewer.
          </p>
        </div>
      )}

      {report.state === 'needs_review' && (
        <div role="alert" className="mb-4 rounded-sm border border-warning bg-warning/10 p-4">
          <h3 className="flex items-center gap-2 text-body font-medium text-warning">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            Quality gate flags ({report.quality_gate_flags.length})
          </h3>
          <FlagList flags={report.quality_gate_flags} />
        </div>
      )}

      {report.immutable && (
        <div role="status" className="mb-4 rounded-sm border border-success bg-success/10 p-4">
          <h3 className="flex items-center gap-2 text-body font-medium text-success">
            <Lock className="h-4 w-4" aria-hidden="true" />
            Locked immutable final report
          </h3>
        </div>
      )}

      <div className="mb-6 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {report.evidence.length > 0 && (
            <Button
              variant="secondary"
              icon={<Eye className="h-4 w-4" aria-hidden="true" />}
              onClick={() => setEvidenceOpen(true)}
            >
              Evidence
            </Button>
          )}
          {exportsAllowed && (
            <Button variant="secondary" onClick={() => setExportOpen(true)}>
              Export
            </Button>
          )}
        </div>

        {showReviewActions && (
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              icon={<Check className="h-4 w-4" aria-hidden="true" />}
              isLoading={actionBusy === 'approve'}
              onClick={() => void runReviewAction('approve')}
            >
              Approve
            </Button>
            <Button
              variant="danger"
              icon={<X className="h-4 w-4" aria-hidden="true" />}
              isLoading={actionBusy === 'reject'}
              onClick={() => void runReviewAction('reject')}
            >
              Reject
            </Button>
            <Button
              variant="secondary"
              icon={<AlertCircle className="h-4 w-4" aria-hidden="true" />}
              isLoading={actionBusy === 'request-revision'}
              onClick={() => void runReviewAction('request-revision')}
            >
              Request revision
            </Button>
          </div>
        )}
      </div>

      {!showBudget && (
        <section className="mb-6 rounded-sm border border-border bg-surface-raised p-4">
          <h2 className="text-heading font-semibold text-text-primary">
            Financial Position
          </h2>
          <p className="mt-3 text-body text-text-muted">
            [Financial data is not available for your role]
          </p>
        </section>
      )}

      {report.content_available && report.markdown ? (
        <MarkdownReport
          markdown={report.markdown}
          evidence={report.evidence}
          showBudget={showBudget}
          onCitation={(evidenceId) => {
            setHighlightedEvidenceId(evidenceId);
            setEvidenceOpen(true);
          }}
        />
      ) : (
        <div className="rounded-sm border border-border bg-surface-raised p-6">
          <p className="text-body text-text-secondary">
            {report.content_unavailable_reason || 'Report content is not available.'}
          </p>
          <FlagList flags={report.quality_gate_flags} />
        </div>
      )}

      <EvidencePanel
        isOpen={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        evidence={report.evidence}
        highlightedEvidenceId={highlightedEvidenceId}
      />

      {exportsAllowed && (
        <ExportPanel
          isOpen={exportOpen}
          onClose={() => setExportOpen(false)}
          requestId={requestId}
          reportState={report.state}
          qualityGate={report.quality_gate || 'needs_review'}
          role={role}
        />
      )}
    </div>
  );
}

function InvalidReport({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <AlertCircle className="h-12 w-12 text-error" aria-hidden="true" />
      <h2 className="mt-3 text-heading font-semibold text-text-primary">
        Report unavailable
      </h2>
      <p className="mt-2 max-w-[400px] text-body text-text-secondary">
        {message}
      </p>
    </div>
  );
}

function PageHeader({ report }: { report: ReportContentResponse }) {
  const status = toStatusPill(report.state);
  return (
    <div className="mb-6 flex items-baseline justify-between">
      <div>
        <div className="flex items-center gap-2">
          <StatusPill status={status} label={labelForState(report.state)} />
          {report.immutable && <Stamp className="h-4 w-4 text-success" aria-hidden="true" />}
          <span className="text-body font-medium text-text-primary">
            {report.project_name || report.project_code || 'No project'}
          </span>
        </div>
        <p className="mt-1 text-caption text-text-muted">
          Request: <code className="text-text-secondary">{report.request_id}</code>
        </p>
      </div>
    </div>
  );
}

function toStatusPill(state: ReportState): StatusValue {
  if (state === 'revision_requested') return 'needs_review';
  if (state === 'cancelled') return 'rejected';
  if (state === 'failed') return 'failed';
  return state;
}

function labelForState(state: ReportState): string {
  return state.replace(/_/g, ' ');
}

function FlagList({ flags }: { flags: string[] }) {
  if (flags.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1 text-body text-text-secondary">
      {flags.map((flag) => (
        <li key={flag} className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
          {flag}
        </li>
      ))}
    </ul>
  );
}

// Financial section headings the renderer must be able to hide, independent of
// section numbering and report language (en + ar).
const FINANCIAL_HEADING_RE = /Financial Snapshot|الموقف المالي/;

function isTableRow(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith('|') && trimmed.endsWith('|');
}

function isTableSeparator(line: string): boolean {
  return /^\|[\s:|-]+\|$/.test(line.trim());
}

function splitTableRow(line: string): string[] {
  const trimmed = line.trim();
  return trimmed.slice(1, -1).split('|').map((cell) => cell.trim());
}

function MarkdownReport({
  markdown,
  evidence,
  showBudget,
  onCitation,
}: {
  markdown: string;
  evidence: EvidencePanelEntry[];
  showBudget: boolean;
  onCitation: (evidenceId: string) => void;
}) {
  const evidenceById = new Map(evidence.map((entry) => [entry.evidence_id, entry]));
  const lines = markdown.split('\n');
  const rendered: ReactNode[] = [];
  let skipFinancial = false;
  let tableRows: string[][] = [];

  const flushTable = (key: number) => {
    if (tableRows.length === 0) return;
    const [header, ...body] = tableRows;
    rendered.push(
      <div key={`table-${key}`} className="overflow-x-auto">
        <table className="w-full border-collapse text-body">
          <thead>
            <tr>
              {header.map((cell, i) => (
                <th
                  key={i}
                  className="border-b border-border px-3 py-2 text-start font-semibold text-text-primary"
                >
                  {renderInline(cell, evidenceById, onCitation)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, r) => (
              <tr key={r}>
                {row.map((cell, c) => (
                  <td key={c} className="border-b border-border px-3 py-2 text-text-secondary">
                    {renderInline(cell, evidenceById, onCitation)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    tableRows = [];
  };

  lines.forEach((line, idx) => {
    if (!showBudget && line.startsWith('## ') && FINANCIAL_HEADING_RE.test(line)) {
      skipFinancial = true;
      return;
    }
    if (skipFinancial && line.startsWith('## ') && !FINANCIAL_HEADING_RE.test(line)) {
      skipFinancial = false;
    }
    if (skipFinancial) return;

    if (isTableRow(line)) {
      if (!isTableSeparator(line)) {
        tableRows.push(splitTableRow(line));
      }
      return;
    }
    flushTable(idx);

    if (!line.trim()) return;

    if (line.startsWith('# ')) {
      rendered.push(
        <h1 key={idx} className="text-display font-semibold text-text-primary">
          {renderInline(line.replace(/^# /, ''), evidenceById, onCitation)}
        </h1>,
      );
    } else if (line.startsWith('### ')) {
      rendered.push(
        <h3 key={idx} className="mt-4 text-body font-semibold text-text-primary">
          {renderInline(line.replace(/^### /, ''), evidenceById, onCitation)}
        </h3>,
      );
    } else if (line.startsWith('## ')) {
      rendered.push(
        <h2 key={idx} className="mt-6 text-heading font-semibold text-text-primary">
          {renderInline(line.replace(/^## /, ''), evidenceById, onCitation)}
        </h2>,
      );
    } else if (line.startsWith('> ')) {
      rendered.push(
        <p key={idx} className="border-s-2 border-border ps-3 text-body italic text-text-muted">
          {renderInline(line.replace(/^> /, ''), evidenceById, onCitation)}
        </p>,
      );
    } else if (line.startsWith('- ')) {
      rendered.push(
        <p key={idx} className="ps-4 text-body text-text-secondary">
          • {renderInline(line.replace(/^- /, ''), evidenceById, onCitation)}
        </p>,
      );
    } else if (!line.startsWith('---')) {
      rendered.push(
        <p key={idx} className="text-body text-text-secondary">
          {renderInline(line, evidenceById, onCitation)}
        </p>,
      );
    }
  });
  flushTable(lines.length);

  return (
    <article dir="auto" className="space-y-3 rounded-sm border border-border bg-surface-raised p-4">
      {rendered}
    </article>
  );
}

function renderFormatted(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let k = 0;

  while ((match = pattern.exec(text))) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    if (match[1] !== undefined) {
      nodes.push(
        <strong key={`${keyPrefix}-b${k}`} className="font-semibold text-text-primary">
          {match[1]}
        </strong>,
      );
    } else if (match[2] !== undefined) {
      nodes.push(
        <em key={`${keyPrefix}-i${k}`} className="text-text-muted">
          {match[2]}
        </em>,
      );
    } else {
      nodes.push(
        <code key={`${keyPrefix}-c${k}`} className="rounded-sm bg-surface-base px-1 text-caption">
          {match[3]}
        </code>,
      );
    }
    k += 1;
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function renderInline(
  text: string,
  evidenceById: Map<string, EvidencePanelEntry>,
  onCitation: (evidenceId: string) => void,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /\[([A-Za-z0-9_.:-]+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text))) {
    const evidenceId = match[1];
    const entry = evidenceById.get(evidenceId);
    if (!entry) continue;

    if (match.index > lastIndex) {
      nodes.push(...renderFormatted(text.slice(lastIndex, match.index), `f${match.index}`));
    }
    nodes.push(
      <sup
        key={`${evidenceId}-${match.index}`}
        tabIndex={0}
        role="button"
        aria-label={`View evidence source ${entry.citation_label}`}
        className="cursor-pointer rounded-sm text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface-base"
        onClick={() => onCitation(evidenceId)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onCitation(evidenceId);
          }
        }}
      >
        {entry.citation_label}
      </sup>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(...renderFormatted(text.slice(lastIndex), 'tail'));
  }
  return nodes.length > 0 ? nodes : [text];
}
