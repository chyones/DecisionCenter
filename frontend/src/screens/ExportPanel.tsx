/**
 * Export Panel — Phase 2A Slice 6.
 *
 * Per `docs/design/UI_CONTRACT_v1.md` §2.4:
 * - Slide-in from Report View triggered by [Export ▾].
 * - Visible only when report state is `approved` or `final`.
 * - Block all downloads when `quality_gate = "failed"`.
 * - Report formats: MD, DOCX, PDF, XLSX, PPTX via existing download endpoints.
 * - Artifacts: evidence-pack.json and audit-log.json (RBAC-gated; no endpoint
 *   exists at backend HEAD, so rows are disabled).
 *
 * Backend endpoints used:
 * - `GET /reports/staging/{request_id}/download/{fmt}`
 * - `GET /reports/final/{request_id}/download/{fmt}`
 */

import { useState } from 'react';
import {
  Download,
  FileText,
  FileSpreadsheet,
  Presentation,
  FileCode,
  ScrollText,
  AlertTriangle,
  Lock,
  Loader2,
} from 'lucide-react';

import { SlideInPanel, useToasts } from '../components';
import { useApi } from '../api';
import { isApiError } from '../api';

import type { OutputFormat } from '../api';
import type { ReportState } from '../api';
import type { Role } from '../routing/roles';

export interface ExportPanelProps {
  isOpen: boolean;
  onClose: () => void;
  requestId: string;
  reportState: ReportState;
  qualityGate: string;
  role: Role;
}

interface FormatDef {
  fmt: OutputFormat;
  label: string;
  ext: string;
  icon: React.ReactNode;
}

const REPORT_FORMATS: FormatDef[] = [
  { fmt: 'md', label: 'Markdown', ext: '.md', icon: <FileText className="h-4 w-4" /> },
  { fmt: 'docx', label: 'Word', ext: '.docx', icon: <FileText className="h-4 w-4" /> },
  { fmt: 'pdf', label: 'PDF', ext: '.pdf', icon: <FileText className="h-4 w-4" /> },
  { fmt: 'xlsx', label: 'Excel', ext: '.xlsx', icon: <FileSpreadsheet className="h-4 w-4" /> },
  { fmt: 'pptx', label: 'PowerPoint', ext: '.pptx', icon: <Presentation className="h-4 w-4" /> },
];

/** Roles that may access audit artifacts per backend download logic. */
const ARTIFACT_ROLES: Role[] = [
  'executive',
  'project_manager',
  'finance',
  'commercial',
  'document_control',
  'procurement',
  'legal',
  'auditor',
  'admin',
];

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ExportPanel({
  isOpen,
  onClose,
  requestId,
  reportState,
  qualityGate,
  role,
}: ExportPanelProps) {
  const api = useApi();
  const { addToast } = useToasts();
  const [downloadingFmt, setDownloadingFmt] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const exportsAllowed = reportState === 'approved' || reportState === 'final';
  const qgFailed = qualityGate === 'failed';
  const canAccessArtifacts = ARTIFACT_ROLES.includes(role);

  async function handleDownload(fmt: OutputFormat) {
    setErrorMsg('');
    setDownloadingFmt(fmt);

    // Determine prefix: final reports use /final/, staging-approved use /staging/
    const prefix = reportState === 'final' ? 'final' : 'staging';
    const path = `/reports/${prefix}/${requestId}/download/${fmt}`;

    try {
      const blob = await api.download(path);
      triggerDownload(blob, `executive-decision-report.${fmt}`);
    } catch (err) {
      let message = 'Download failed.';
      if (isApiError(err)) {
        message = err.message;
        if (err.status === 0) {
          message = 'Network error — please check your connection and try again.';
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setErrorMsg(message);
      addToast('error', message, 'Download failed');
    } finally {
      setDownloadingFmt(null);
    }
  }

  return (
    <SlideInPanel isOpen={isOpen} title="Export" onClose={onClose}>
      <div className="space-y-6">
        {/* Gate: exports only for approved / final */}
        {!exportsAllowed && (
          <div className="flex items-start gap-2 rounded-sm border border-border bg-surface-base p-3">
            <Lock className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
            <p className="text-body text-text-secondary">
              Exports are available only when the report is approved or finalized.
            </p>
          </div>
        )}

        {/* Gate: QG failed blocks everything */}
        {qgFailed && (
          <div className="flex items-start gap-2 rounded-sm border border-error bg-error/10 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-error" />
            <p className="text-body text-error">
              Downloads are blocked because the quality gate failed.
            </p>
          </div>
        )}

        {/* Report formats */}
        <div>
          <h3 className="mb-2 text-label font-medium text-text-secondary">
            Report formats
          </h3>
          <div className="space-y-1">
            {REPORT_FORMATS.map((f) => {
              const disabled = !exportsAllowed || qgFailed || !!downloadingFmt;
              const isActive = downloadingFmt === f.fmt;

              return (
                <button
                  type="button"
                  key={f.fmt}
                  disabled={disabled}
                  onClick={() => handleDownload(f.fmt)}
                  aria-label={`Download ${f.label} (${f.ext})`}
                  className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-body text-text-primary transition-colors hover:bg-surface-overlay disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {isActive ? (
                    <Loader2 className="h-4 w-4 animate-spin text-accent" />
                  ) : (
                    <span className="text-text-muted">{f.icon}</span>
                  )}
                  <span className="flex-1">
                    {f.label} <span className="text-text-muted">({f.ext})</span>
                  </span>
                  <Download className="h-4 w-4 text-text-muted" />
                </button>
              );
            })}
          </div>
        </div>

        {/* Artifacts */}
        <div className="border-t border-border pt-4">
          <h3 className="mb-2 text-label font-medium text-text-secondary">
            Artifacts
          </h3>
          <div className="space-y-1">
            {/* evidence-pack.json — disabled: no endpoint at HEAD */}
            <button
              type="button"
              disabled
              className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-body text-text-muted opacity-50 disabled:cursor-not-allowed"
              aria-label="evidence-pack.json — unavailable"
            >
              <FileCode className="h-4 w-4" aria-hidden="true" />
              <span className="flex-1">evidence-pack.json</span>
              <span className="text-caption">RBAC-gated · endpoint N/A</span>
            </button>

            {/* audit-log.json — disabled: no endpoint at HEAD */}
            <button
              type="button"
              disabled
              className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-body text-text-muted opacity-50 disabled:cursor-not-allowed"
              aria-label="audit-log.json — unavailable"
            >
              <ScrollText className="h-4 w-4" aria-hidden="true" />
              <span className="flex-1">audit-log.json</span>
              <span className="text-caption">RBAC-gated · endpoint N/A</span>
            </button>
          </div>
          {!canAccessArtifacts && (
            <p className="mt-2 text-caption text-text-muted">
              Artifact downloads are not available for your role.
            </p>
          )}
        </div>

        {/* Error banner */}
        {errorMsg && (
          <div role="alert" className="rounded-sm border border-error bg-error/10 p-3 text-body text-error">
            {errorMsg}
          </div>
        )}

        {/* State footer */}
        <div className="border-t border-border pt-3 text-caption text-text-muted">
          State: {reportState} · Quality gate: {qualityGate}
        </div>
      </div>
    </SlideInPanel>
  );
}
