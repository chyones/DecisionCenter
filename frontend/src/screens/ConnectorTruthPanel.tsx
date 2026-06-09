/**
 * Connector Status Truth panel.
 *
 * Renders the honest connector states from `GET /admin/connectors/truth`. It
 * NEVER shows green unless the backend reported `LIVE_OK`, `VALIDATED`, or
 * accepted current evidence. `CONFIGURED_NOT_TESTED` and `NOT_CONFIGURED` are
 * neutral/grey — not success.
 * Surfaces explicit state, evidence, verification/check timestamps, missing
 * non-secret config, data source, and go-live blocking.
 *
 * `variant="banner"` renders only the top readiness banner (used on the
 * Dashboard); `variant="full"` adds the grouped connector breakdown (used on
 * the Connectors screen).
 */
import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';

import { useApi, ApiError } from '../api';
import { acquireAccessToken, productionAuthEnabled } from '../auth/msalConfig';
import { Button, useToasts } from '../components';
import type {
  ConnectorState,
  ConnectorTruth,
  ConnectorTruthReport,
  Readiness,
  ReportGeneration,
} from '../api';

function formatTs(iso: string | null): string {
  if (!iso) return 'never';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

const STATE_LABEL: Record<ConnectorState, string> = {
  LIVE_OK: 'Live',
  VALIDATED: 'Validated',
  PREVIOUSLY_VALIDATED_TOKEN_EXPIRED: 'Expired',
  VERIFIED_FROM_EVIDENCE: 'Verified from evidence',
  CONNECTED_NO_DATA: 'Connected — no data',
  CONFIGURED_NOT_TESTED: 'Configured — not tested',
  NOT_CONFIGURED: 'Not configured',
  AUTH_FAILED: 'Auth failed',
  PERMISSION_FAILED: 'Permission missing',
  NETWORK_FAILED: 'Unreachable',
  MOCK_ONLY: 'Sample / mock only',
  DISABLED: 'Disabled',
  UNKNOWN: 'Unknown',
};

// Only live probes or accepted current evidence are green. Failures are red.
// Everything unproven is neutral grey.
const STATE_CLASS: Record<ConnectorState, string> = {
  LIVE_OK: 'bg-success/15 text-success border-success/40',
  VALIDATED: 'bg-success/15 text-success border-success/40',
  PREVIOUSLY_VALIDATED_TOKEN_EXPIRED:
    'bg-warning/15 text-warning border-warning/40',
  VERIFIED_FROM_EVIDENCE: 'bg-success/15 text-success border-success/40',
  CONNECTED_NO_DATA: 'bg-warning/15 text-warning border-warning/40',
  MOCK_ONLY: 'bg-warning/15 text-warning border-warning/40',
  AUTH_FAILED: 'bg-error/15 text-error border-error/40',
  PERMISSION_FAILED: 'bg-error/15 text-error border-error/40',
  NETWORK_FAILED: 'bg-error/15 text-error border-error/40',
  CONFIGURED_NOT_TESTED: 'bg-surface-base text-text-secondary border-border',
  NOT_CONFIGURED: 'bg-surface-base text-text-muted border-border',
  DISABLED: 'bg-surface-base text-text-muted border-border',
  UNKNOWN: 'bg-surface-base text-text-muted border-border',
};

function StatePill({ state }: { state: ConnectorState }) {
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-sm border px-2 py-0.5 text-caption font-medium ${STATE_CLASS[state]}`}
    >
      {STATE_LABEL[state]}
    </span>
  );
}

const READINESS_LABEL: Record<Readiness, string> = {
  READY_FOR_UAT: 'Ready for UAT',
  PARTIAL_READY: 'Partial — core up, connectors pending',
  NOT_READY: 'Not ready',
};

const READINESS_CLASS: Record<Readiness, string> = {
  READY_FOR_UAT: 'bg-success/15 text-success border-success/40',
  PARTIAL_READY: 'bg-warning/15 text-warning border-warning/40',
  NOT_READY: 'bg-error/15 text-error border-error/40',
};

const REPORTGEN_LABEL: Record<ReportGeneration, string> = {
  READY: 'AI report generation: provider keys present (not yet live-verified)',
  DEGRADED: 'AI report generation: Degraded — some providers missing',
  BLOCKED: 'AI report generation: Blocked — provider keys missing',
};

const REPORTGEN_CLASS: Record<ReportGeneration, string> = {
  READY: 'text-success',
  DEGRADED: 'text-warning',
  BLOCKED: 'text-error',
};

/** Dynamic title for PARTIAL_READY: when only AI providers are blocking,
 *  show "Microsoft connectors ready — AI providers pending" instead of the
 *  generic "connectors pending" which falsely implies Microsoft connectors
 *  are still unverified. */
function readinessTitle(report: ConnectorTruthReport): string {
  if (report.readiness !== 'PARTIAL_READY') return READINESS_LABEL[report.readiness];
  const aiNames = new Set(report.ai_providers.map((t) => t.name));
  if (report.blocking.length > 0 && report.blocking.every((n) => aiNames.has(n))) {
    return 'Microsoft connectors ready — AI providers pending';
  }
  return READINESS_LABEL['PARTIAL_READY'];
}

/** Format the blocking list contextually.
 *  When all blockers are AI providers, emit "AI providers missing: …" with
 *  display names rather than raw internal names. */
function blockingLine(report: ConnectorTruthReport): string {
  if (report.blocking.length === 0) return '';
  const aiNames = new Set(report.ai_providers.map((t) => t.name));
  const allAI = report.blocking.every((n) => aiNames.has(n));
  if (allAI) {
    const displayNames = report.blocking
      .map((n) => report.ai_providers.find((t) => t.name === n)?.display_name ?? n)
      .join(', ');
    return `AI providers missing: ${displayNames}`;
  }
  return `Blocking go-live: ${report.blocking.join(', ')}`;
}

/** Render the data-source chip and record count for a connector row. */
function dataSourceChip(t: ConnectorTruth): React.ReactNode {
  if (t.data_source === 'none') return null;
  if (
    t.name === 'entra_auth' &&
    t.state === 'VALIDATED' &&
    t.data_source === 'evidence'
  ) {
    return (
      <span className="ml-2 rounded-sm border border-border px-1">
        Current validation evidence
      </span>
    );
  }
  if (
    t.name === 'entra_auth' &&
    t.state === 'PREVIOUSLY_VALIDATED_TOKEN_EXPIRED'
  ) {
    return null;
  }
  return (
    <>
      <span className="ml-2 rounded-sm border border-border px-1">
        data: {t.data_source}
      </span>
      {t.sample_count != null && (
        <span className="ml-2">· {t.sample_count} records</span>
      )}
    </>
  );
}

function ReadinessBanner({ report }: { report: ConnectorTruthReport }) {
  return (
    <div className={`rounded-sm border px-4 py-3 ${READINESS_CLASS[report.readiness]}`}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-title font-semibold">{readinessTitle(report)}</p>
        <span className="text-caption opacity-80">
          verified {formatTs(report.generated_at)}
        </span>
      </div>
      <p className="mt-1 text-body opacity-90">{report.readiness_reason}</p>
      <p className={`mt-2 text-body font-medium ${REPORTGEN_CLASS[report.report_generation]}`}>
        {REPORTGEN_LABEL[report.report_generation]}
      </p>
      {report.blocking.length > 0 && (
        <p className="mt-1 text-caption text-text-muted">
          {blockingLine(report)}
        </p>
      )}
    </div>
  );
}

function ConnectorRow({
  t,
  onRevalidate,
  revalidating = false,
  revalidationError = null,
}: {
  t: ConnectorTruth;
  onRevalidate?: () => void;
  revalidating?: boolean;
  revalidationError?: string | null;
}) {
  const isExpiredEntra =
    t.name === 'entra_auth' &&
    t.state === 'PREVIOUSLY_VALIDATED_TOKEN_EXPIRED';
  const hasEntraValidationHistory =
    t.name === 'entra_auth' &&
    (t.state === 'VALIDATED' || isExpiredEntra);

  return (
    <li className="border-b border-border py-3 last:border-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-body font-medium text-text-primary">
          {t.display_name}
        </span>
        <StatePill state={t.state} />
      </div>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-caption text-text-muted">
        <dt>Evidence</dt>
        <dd className="text-text-secondary">{t.evidence || '—'}</dd>
        {hasEntraValidationHistory ? (
          <>
            <dt>Last successful validation</dt>
            <dd className="text-text-secondary">
              {formatTs(t.last_success_at)}
              {dataSourceChip(t)}
            </dd>
            <dt>{isExpiredEntra ? 'Token expired at' : 'Token expires at'}</dt>
            <dd className={isExpiredEntra ? 'text-warning' : 'text-text-secondary'}>
              {formatTs(t.token_expires_at)}
            </dd>
            <dt>Last checked</dt>
            <dd className="text-text-secondary">{formatTs(t.last_probe_at)}</dd>
          </>
        ) : (
          <>
            <dt>Last verified</dt>
            <dd className="text-text-secondary">
              {formatTs(t.last_success_at ?? t.last_probe_at)}
              {dataSourceChip(t)}
            </dd>
          </>
        )}
        {t.missing_required_config.length > 0 && (
          <>
            <dt>Missing config</dt>
            <dd className="font-mono text-mono text-warning">
              {t.missing_required_config.join(', ')}
              {!t.secret_present && ' · required secret missing'}
            </dd>
          </>
        )}
        {t.last_error_safe && (
          <>
            <dt>Last error</dt>
            <dd className="text-error">{t.last_error_safe}</dd>
          </>
        )}
        {isExpiredEntra && onRevalidate && (
          <>
            <dt className="sr-only">Action</dt>
            <dd className="col-span-2 mt-2">
              <Button
                variant="secondary"
                size="compact"
                icon={<RefreshCw aria-hidden="true" className="h-4 w-4" />}
                isLoading={revalidating}
                onClick={onRevalidate}
              >
                Revalidate with current browser session
              </Button>
              {revalidationError && (
                <p role="alert" className="mt-2 text-caption text-error">
                  {revalidationError}
                </p>
              )}
            </dd>
          </>
        )}
      </dl>
    </li>
  );
}

function Group({
  title,
  items,
  onRevalidate,
  revalidating,
  revalidationError,
}: {
  title: string;
  items: ConnectorTruth[];
  onRevalidate?: () => void;
  revalidating?: boolean;
  revalidationError?: string | null;
}) {
  if (items.length === 0) return null;
  return (
    <section className="mb-6">
      <h3 className="mb-1 text-label font-semibold uppercase tracking-wide text-text-secondary">
        {title}
      </h3>
      <ul className="rounded-sm border border-border bg-surface-raised px-4">
        {items.map((t) => (
          <ConnectorRow
            key={t.name}
            t={t}
            onRevalidate={onRevalidate}
            revalidating={revalidating}
            revalidationError={revalidationError}
          />
        ))}
      </ul>
    </section>
  );
}

export function ConnectorTruthPanel({
  variant = 'full',
}: {
  variant?: 'full' | 'banner';
}) {
  const api = useApi();
  const { addToast } = useToasts();
  const [report, setReport] = useState<ConnectorTruthReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revalidating, setRevalidating] = useState(false);
  const [revalidationError, setRevalidationError] = useState<string | null>(
    null,
  );

  const fetchReport = useCallback(
    async (probe: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.get<ConnectorTruthReport>(
          `/admin/connectors/truth?probe=${probe ? 'true' : 'false'}`,
        );
        setReport(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          // Backend truth endpoint not deployed yet (pending app rebuild).
          setError('PENDING_DEPLOY');
        } else {
          setError(
            err instanceof ApiError ? err.message : 'Failed to load connector status',
          );
        }
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  const revalidateEntra = useCallback(async () => {
    setRevalidating(true);
    setRevalidationError(null);
    try {
      let headers: HeadersInit | undefined;
      if (productionAuthEnabled) {
        const token = await acquireAccessToken({ forceRefresh: true });
        if (!token) {
          setRevalidationError(
            'Sign in to Microsoft again, then retry revalidation.',
          );
          return;
        }
        headers = { Authorization: `Bearer ${token}` };
      }

      await api.post(
        '/admin/connectors/entra/revalidate-current-token',
        {},
        headers ? { headers } : undefined,
      );
      await fetchReport(true);
      addToast(
        'success',
        'Microsoft Entra validation is current.',
        'Revalidation complete',
      );
    } catch (err) {
      const message =
        err instanceof ApiError && (err.status === 400 || err.status === 401)
          ? 'Your Microsoft session could not be validated. Sign in again, then retry.'
          : 'Revalidation failed. Refresh your Microsoft login and retry.';
      setRevalidationError(message);
    } finally {
      setRevalidating(false);
    }
  }, [addToast, api, fetchReport]);

  useEffect(() => {
    void fetchReport(true);
  }, [fetchReport]);

  if (loading && !report) {
    return <p className="text-body text-text-muted">Checking connectors…</p>;
  }
  if (error === 'PENDING_DEPLOY') {
    return (
      <p className="text-body text-text-muted">
        Connector status service is pending deployment (app rebuild required).
      </p>
    );
  }
  if (error) {
    return <p className="text-body text-error">{error}</p>;
  }
  if (!report) return null;

  if (variant === 'banner') {
    return <ReadinessBanner report={report} />;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <ReadinessBanner report={report} />
      </div>
      <div className="mb-4 flex justify-end">
        <button
          type="button"
          onClick={() => void fetchReport(true)}
          disabled={loading}
          className="rounded-sm border border-border bg-surface-raised px-3 py-1.5 text-label text-text-primary hover:bg-surface-overlay disabled:opacity-50"
        >
          {loading ? 'Re-testing…' : 'Re-run live probes'}
        </button>
      </div>
      <Group title="Core platform" items={report.core_platform} />
      <Group title="Public edge" items={report.edge} />
      <Group
        title="Microsoft login"
        items={report.auth}
        onRevalidate={() => void revalidateEntra()}
        revalidating={revalidating}
        revalidationError={revalidationError}
      />
      <Group title="External connectors" items={report.external_connectors} />
      <Group title="AI providers" items={report.ai_providers} />
    </div>
  );
}
