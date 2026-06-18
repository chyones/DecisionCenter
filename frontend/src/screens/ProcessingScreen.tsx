/**
 * Processing View — Phase 2A Slice 4.
 *
 * Per `docs/design/UI_CONTRACT_v1.md` §2.2:
 * - Route: `/workspace/report/{request_id}/processing`
 * - 18 workflow node labels mapped to user-facing labels (internal IDs never exposed).
 * - Progress bar, elapsed timer, state banner, cancel action shell.
 * - All 9 screen states: running, self_correct_retry, quality_gate_passed,
 *   quality_gate_needs_review, quality_gate_failed, awaiting_reviewer,
 *   timed_out, rbac_denied, cancelled.
 *
 * Uses `GET /reports/{id}/status` and `DELETE /reports/{id}` for live Phase 2A
 * status/cancel behavior.
 */

import { useEffect, useMemo, useState } from 'react';
import {
  Check,
  Circle,
  Loader2,
  X,
  AlertTriangle,
  AlertCircle,
  Info,
  Clock,
  ShieldX,
  Ban,
} from 'lucide-react';

import { Button, ConfirmDialog, StatusPill, useToasts } from '../components';
import { useApi } from '../api';
import { isApiError } from '../api';
import type { CancelReportResponse, ReportStatusResponse } from '../api';
import { useHashPath } from '../routing';

type ProcessingState =
  | 'running'
  | 'self_correct_retry'
  | 'quality_gate_passed'
  | 'quality_gate_needs_review'
  | 'quality_gate_failed'
  | 'awaiting_reviewer'
  | 'timed_out'
  | 'rbac_denied'
  | 'cancelled';

interface NodeStep {
  id: string;
  label: string;
}

const NODES: NodeStep[] = [
  { id: 'node_00_begin', label: 'Starting' },
  { id: 'node_01_auth', label: 'Verifying access' },
  { id: 'node_02_intent', label: 'Understanding your question' },
  { id: 'node_03_scope', label: 'Determining scope' },
  { id: 'node_04_plan', label: 'Planning retrieval' },
  { id: 'node_05_sharepoint', label: 'Searching SharePoint' },
  { id: 'node_06_owncloud', label: 'Checking ownCloud' },
  { id: 'node_07_email', label: 'Searching email' },
  { id: 'node_08_odoo', label: 'Reading Odoo records' },
  { id: 'node_09_normalize', label: 'Organizing evidence' },
  { id: 'node_10_sufficiency', label: 'Checking evidence quality' },
  { id: 'node_11_self_correct', label: 'Refining search' },
  { id: 'node_12_draft_json', label: 'Drafting report' },
  { id: 'node_13_quality_gate', label: 'Quality gate' },
  { id: 'node_14_compose_md', label: 'Composing report' },
  { id: 'node_15_save_audit', label: 'Saving to staging' },
  { id: 'node_16_review', label: 'Awaiting reviewer' },
  { id: 'node_17_publish', label: 'Publishing' },
];

/** Initial active node index until the first backend status response arrives. */
const INITIAL_ACTIVE_INDEX = 0;

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function getStateBanner(
  state: ProcessingState,
  qgFailureReason?: string | null,
  jobError?: string | null,
): {
  text: string;
  tone: 'success' | 'warning' | 'error' | 'info';
  icon: React.ReactNode;
} | null {
  switch (state) {
    case 'quality_gate_passed':
      return {
        text: 'Quality gate passed.',
        tone: 'success',
        icon: <Check className="h-4 w-4" />,
      };
    case 'quality_gate_needs_review':
      return {
        text: 'Report flagged for mandatory review. Proceeding to staging.',
        tone: 'warning',
        icon: <AlertTriangle className="h-4 w-4" />,
      };
    case 'quality_gate_failed': {
      const text =
        qgFailureReason === 'evidence'
          ? 'Evidence insufficient — report cannot be generated.'
          : 'Analysis incomplete — report blocked by quality gate.';
      return {
        text,
        tone: 'error',
        icon: <AlertCircle className="h-4 w-4" />,
      };
    }
    case 'awaiting_reviewer':
      return {
        text: 'Report submitted for review. You will be notified when a decision is made.',
        tone: 'info',
        icon: <Info className="h-4 w-4" />,
      };
    case 'timed_out':
      return {
        text: jobError || 'Processing timed out. Please try again.',
        tone: 'error',
        icon: <Clock className="h-4 w-4" />,
      };
    case 'rbac_denied':
      return {
        text: 'Access denied.',
        tone: 'error',
        icon: <ShieldX className="h-4 w-4" />,
      };
    case 'cancelled':
      return {
        text: 'Report generation was cancelled.',
        tone: 'error',
        icon: <Ban className="h-4 w-4" />,
      };
    default:
      return null;
  }
}

const TONE_COLORS: Record<
  'success' | 'warning' | 'error' | 'info',
  { border: string; bg: string; text: string }
> = {
  success: {
    border: 'border-success',
    bg: 'bg-success/10',
    text: 'text-success',
  },
  warning: {
    border: 'border-warning',
    bg: 'bg-warning/10',
    text: 'text-warning',
  },
  error: {
    border: 'border-error',
    bg: 'bg-error/10',
    text: 'text-error',
  },
  info: {
    border: 'border-accent',
    bg: 'bg-accent/10',
    text: 'text-accent',
  },
};

export function ProcessingScreen() {
  const api = useApi();
  const { addToast } = useToasts();
  const path = useHashPath();
  const requestId = useMemo(() => {
    const m = path.match(/^\/workspace\/report\/([^/]+)\/processing$/);
    return m ? m[1] : null;
  }, [path]);

  const [state, setState] = useState<ProcessingState>('running');
  const [status, setStatus] = useState<ReportStatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [cancelOpen, setCancelOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  // Elapsed timer — local only, counts up every second.
  useEffect(() => {
    if (state === 'cancelled' || state === 'timed_out' || state === 'rbac_denied') {
      return;
    }
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [state]);

  useEffect(() => {
    if (!requestId) return;
    let active = true;

    async function loadStatus() {
      try {
        const res = await api.get<ReportStatusResponse>(`/reports/${requestId}/status`);
        if (!active) return;
        setStatus(res);
        setErrorMsg('');
        if (
          res.is_terminal &&
          (res.state === 'staging' ||
            res.state === 'needs_review' ||
            res.state === 'approved' ||
            res.state === 'final')
        ) {
          window.location.replace(`#/workspace/report/${requestId}`);
          return;
        }
        if (res.state === 'queued' || res.state === 'running') setState('running');
        else if (res.state === 'timed_out') setState('timed_out');
        else if (res.state === 'cancelled') setState('cancelled');
        else if (res.state === 'failed' || res.quality_gate === 'failed') setState('quality_gate_failed');
        else if (res.state === 'needs_review' || res.quality_gate === 'needs_review') setState('quality_gate_needs_review');
        else if (res.state === 'staging') setState('awaiting_reviewer');
        else if (res.state === 'approved' || res.state === 'final') setState('quality_gate_passed');
      } catch (err) {
        if (!active) return;
        let message = 'Unable to load processing status.';
        if (isApiError(err)) {
          message = err.status === 0
            ? 'Network error — please check your connection and try again.'
            : err.message;
        } else if (err instanceof Error) {
          message = err.message;
        }
        setErrorMsg(message);
      }
    }

    void loadStatus();
    const id = window.setInterval(() => {
      if (!status?.is_terminal) void loadStatus();
    }, 3000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [api, requestId, status?.is_terminal]);

  async function handleCancel() {
    if (!requestId) return;
    const res = await api.delete<CancelReportResponse>(`/reports/${requestId}`);
    setState('cancelled');
    setStatus((current) =>
      current
        ? { ...current, state: res.state, is_terminal: true, current_node: 0 }
        : current,
    );
    setCancelOpen(false);
    addToast('info', 'Report generation was cancelled.', 'Cancelled');
  }

  const activeIndex = useMemo(() => {
    if (state === 'cancelled') return -1;
    if (state === 'rbac_denied') return -1;
    if (status && status.current_node > 0) {
      return Math.max(0, Math.min(NODES.length - 1, status.current_node - 1));
    }
    if (state === 'timed_out') return INITIAL_ACTIVE_INDEX;
    if (state === 'quality_gate_failed') return 12; // up to Drafting report
    if (state === 'awaiting_reviewer') return 15; // up to Saving to staging
    if (state === 'quality_gate_needs_review') return 13;
    if (state === 'quality_gate_passed') return 13;
    if (state === 'self_correct_retry') return 10;
    return INITIAL_ACTIVE_INDEX;
  }, [state, status]);

  const progress = useMemo(() => {
    if (state === 'cancelled') return 0;
    if (state === 'rbac_denied') return 0;
    if (activeIndex < 0) return 0;
    return Math.round(((activeIndex + 1) / NODES.length) * 100);
  }, [state, activeIndex]);

  const banner = getStateBanner(state, status?.qg_failure_reason, status?.error_message);
  const cancelAllowed = status
    ? status.state === 'queued' || status.state === 'running'
    : state === 'running' || state === 'self_correct_retry';

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

  return (
    <div>
      {/* Page header */}
      <div className="mb-6 flex items-baseline justify-between">
        <div>
          <h1 className="text-display font-semibold text-text-primary">
            Generating report
          </h1>
          <p className="mt-1 text-caption text-text-muted">
            Request: <code className="text-text-secondary">{requestId}</code>
          </p>
        </div>
        <span className="text-caption text-text-muted">
          Live backend status
        </span>
      </div>

      {/* State banner */}
      {errorMsg && (
        <div role="alert" className="mb-4 rounded-sm border border-error bg-error/10 p-3 text-body text-error">
          {errorMsg}
        </div>
      )}

      {banner && (
        <div
          role={banner.tone === 'error' ? 'alert' : 'status'}
          className={`mb-4 flex items-center gap-2 rounded-sm border ${TONE_COLORS[banner.tone].border} ${TONE_COLORS[banner.tone].bg} p-3`}
        >
          <span className={TONE_COLORS[banner.tone].text}>{banner.icon}</span>
          <span className={`text-body font-medium ${TONE_COLORS[banner.tone].text}`}>
            {banner.text}
          </span>
        </div>
      )}

      {/* Cancelled badge replaces progress bar */}
      {state === 'cancelled' ? (
        <div className="mb-6">
          <StatusPill status="rejected" label="Cancelled" />
        </div>
      ) : (
        <>
          {/* Progress bar */}
          <div className="mb-6">
            <div className="mb-2 flex items-center justify-between text-label text-text-secondary">
              <span>Progress</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 w-full rounded-sm bg-surface-overlay">
              <div
                className="h-full rounded-sm bg-accent transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </>
      )}

      {/* Node list */}
      <div className="mb-6 rounded-sm border border-border bg-surface-raised p-4">
        <ul className="space-y-2">
          {NODES.map((node, idx) => {
            const isCompleted = idx < activeIndex;
            const isActive = idx === activeIndex && state !== 'cancelled' && state !== 'rbac_denied';
            const isGreyed =
              state === 'quality_gate_failed' && idx > activeIndex;

            let icon: React.ReactNode;
            if (isCompleted) {
              icon = (
                <Check className="h-4 w-4 shrink-0 text-success" aria-hidden="true" />
              );
            } else if (isActive) {
              icon = (
                <Loader2
                  className="h-4 w-4 shrink-0 animate-spin text-accent"
                  aria-hidden="true"
                />
              );
            } else {
              icon = (
                <Circle
                  className={`h-4 w-4 shrink-0 ${isGreyed ? 'text-text-muted' : 'text-text-muted'}`}
                  aria-hidden="true"
                />
              );
            }

            const labelText =
              isActive && state === 'self_correct_retry'
                ? `${node.label} — attempt 2 of 3`
                : node.label;

            return (
              <li
                key={node.id}
                className={`flex items-center gap-2 text-body ${
                  isGreyed
                    ? 'text-text-muted line-through'
                    : isActive
                      ? 'font-medium text-text-primary'
                      : isCompleted
                        ? 'text-text-secondary'
                        : 'text-text-muted'
                }`}
              >
                {icon}
                <span>{labelText}</span>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Footer row */}
      <div className="flex items-center justify-between">
        <div className="text-body text-text-secondary">
          Elapsed: <span className="font-medium text-text-primary">{formatElapsed(elapsed)}</span>
        </div>

        <Button
          variant="danger"
          disabled={!cancelAllowed || state === 'cancelled'}
          onClick={() => setCancelOpen(true)}
        >
          <X className="h-4 w-4" />
          Cancel
        </Button>
      </div>

      <ConfirmDialog
        isOpen={cancelOpen}
        title="Cancel report generation"
        confirmationText="cancel"
        confirmLabel="Cancel report"
        onClose={() => setCancelOpen(false)}
        onConfirm={handleCancel}
      >
        <p className="text-body text-text-secondary">
          This will stop the workflow and write a cancellation audit event.
        </p>
      </ConfirmDialog>

    </div>
  );
}
