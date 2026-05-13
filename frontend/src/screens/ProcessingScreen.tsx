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
 * Limitation: `GET /reports/{id}/status` and `DELETE /reports/{id}` do not exist
 * at backend HEAD. The screen renders a contract-correct static shell with a
 * local state toggle (dev-only) and an elapsed timer. No backend polling occurs.
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

import { Button, StatusPill } from '../components';
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
  { id: 'node_06_owncloud', label: 'Searching ownCloud' },
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

/** Demo active node index for the "running" static shell. */
const DEMO_ACTIVE_INDEX = 5;

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function getStateBanner(state: ProcessingState): {
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
    case 'quality_gate_failed':
      return {
        text: 'Evidence insufficient — report cannot be generated.',
        tone: 'error',
        icon: <AlertCircle className="h-4 w-4" />,
      };
    case 'awaiting_reviewer':
      return {
        text: 'Report submitted for review. You will be notified when a decision is made.',
        tone: 'info',
        icon: <Info className="h-4 w-4" />,
      };
    case 'timed_out':
      return {
        text: 'Processing timed out. Please try again.',
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

const STATE_OPTIONS: ProcessingState[] = [
  'running',
  'self_correct_retry',
  'quality_gate_passed',
  'quality_gate_needs_review',
  'quality_gate_failed',
  'awaiting_reviewer',
  'timed_out',
  'rbac_denied',
  'cancelled',
];

export function ProcessingScreen() {
  const path = useHashPath();
  const requestId = useMemo(() => {
    const m = path.match(/^\/workspace\/report\/([^/]+)\/processing$/);
    return m ? m[1] : null;
  }, [path]);

  const [state, setState] = useState<ProcessingState>('running');
  const [elapsed, setElapsed] = useState(0);

  // Elapsed timer — local only, counts up every second.
  useEffect(() => {
    if (state === 'cancelled' || state === 'timed_out' || state === 'rbac_denied') {
      return;
    }
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [state]);

  const activeIndex = useMemo(() => {
    if (state === 'cancelled') return -1;
    if (state === 'rbac_denied') return -1;
    if (state === 'timed_out') return DEMO_ACTIVE_INDEX;
    if (state === 'quality_gate_failed') return 12; // up to Drafting report
    if (state === 'awaiting_reviewer') return 15; // up to Saving to staging
    if (state === 'quality_gate_needs_review') return 13;
    if (state === 'quality_gate_passed') return 13;
    if (state === 'self_correct_retry') return 10;
    return DEMO_ACTIVE_INDEX;
  }, [state]);

  const progress = useMemo(() => {
    if (state === 'cancelled') return 0;
    if (state === 'rbac_denied') return 0;
    if (activeIndex < 0) return 0;
    return Math.round(((activeIndex + 1) / NODES.length) * 100);
  }, [state, activeIndex]);

  const banner = getStateBanner(state);

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
          static shell — no status endpoint
        </span>
      </div>

      {/* State banner */}
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

        {/* Cancel action — disabled because no DELETE endpoint exists */}
        <Button variant="danger" disabled title="Cancel action requires a backend endpoint that is not yet available">
          <X className="h-4 w-4" />
          Cancel
        </Button>
      </div>

      {/* Dev-only state toggle */}
      {import.meta.env.DEV && (
        <div className="mt-8 rounded-sm border border-dashed border-border bg-surface-raised p-3">
          <span className="text-label font-medium text-text-secondary">
            Dev — preview state:
          </span>
          <div className="mt-2 flex flex-wrap gap-2">
            {STATE_OPTIONS.map((s) => (
              <button
                type="button"
                key={s}
                onClick={() => setState(s)}
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
      )}
    </div>
  );
}
