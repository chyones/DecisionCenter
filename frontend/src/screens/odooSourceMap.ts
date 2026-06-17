/**
 * Pure helpers for the Odoo Source Map panel.
 *
 * Kept separate from the React component so the grouping / labelling logic is
 * unit-testable without a DOM. All functions are pure and carry no project
 * specific data — they operate on whatever the generic API returns.
 */
import type { StatusValue } from '../tokens/status';
import type {
  OdooScanProgress,
  OdooSourceMapEntry,
  OdooSourceMapResponse,
} from '../api';

export interface SourceMapGroup {
  group: string;
  sources: OdooSourceMapEntry[];
  mappableCount: number;
  totalCount: number;
}

/**
 * Bucket the flat source list into the response's display groups. A source can
 * appear in more than one group (e.g. worked days → Payroll + Manpower).
 */
export function groupSourcesByDisplayGroup(
  resp: OdooSourceMapResponse,
): SourceMapGroup[] {
  return resp.groups.map((group) => {
    const sources = resp.sources.filter((s) => s.groups.includes(group));
    return {
      group,
      sources,
      mappableCount: sources.filter((s) => s.mappable).length,
      totalCount: sources.length,
    };
  });
}

/** Human label for the record count of a single source after a scan. */
export function recordCountLabel(entry: OdooSourceMapEntry): string {
  if (entry.record_count == null) return '—';
  if (entry.capped) return `${entry.record_count}+`;
  return String(entry.record_count);
}

/**
 * Map a per-source scan status onto a StatusPill value + label. Covers the full
 * batched-scan vocabulary: pending, running, completed, partial, capped, empty,
 * failed, timeout, unmapped (plus the not-scanned default).
 */
export function scanStatusPill(status: string): { status: StatusValue; label: string } {
  switch (status) {
    case 'completed':
      return { status: 'connected', label: 'completed' };
    case 'running':
      return { status: 'processing', label: 'running' };
    case 'pending':
      return { status: 'unknown', label: 'pending' };
    case 'partial':
      return { status: 'degraded', label: 'partial' };
    case 'capped':
      return { status: 'degraded', label: 'capped' };
    case 'empty':
      return { status: 'unknown', label: 'empty' };
    case 'timeout':
      return { status: 'failed', label: 'timeout' };
    case 'failed':
      return { status: 'failed', label: 'failed' };
    case 'unmapped':
      return { status: 'disconnected', label: 'unmapped' };
    // Back-compat with the legacy single-shot statuses.
    case 'ok':
      return { status: 'connected', label: 'ok' };
    case 'unmapped_legacy':
      return { status: 'disconnected', label: 'unmapped' };
    default:
      if (status.startsWith('error')) return { status: 'failed', label: 'error' };
      return { status: 'unknown', label: 'not scanned' };
  }
}

/** Confidence → pill mapping. */
export function confidencePill(confidence: string): { status: StatusValue; label: string } {
  if (confidence === 'high') return { status: 'passed', label: 'high' };
  if (confidence === 'medium') return { status: 'needs_review', label: 'medium' };
  return { status: 'unknown', label: confidence || 'unknown' };
}

/** True when at least one source carries a warning (caveat). */
export function hasWarnings(resp: OdooSourceMapResponse): boolean {
  return resp.sources.some((s) => s.warning.trim().length > 0);
}

/** True while a scan session is still pending or running (poll should continue). */
export function isScanActive(resp: OdooSourceMapResponse | null): boolean {
  if (!resp || !resp.scan_session_id) return false;
  return resp.scan_state === 'pending' || resp.scan_state === 'running';
}

/** Count of sources eligible for "retry failed sources" (failed + timeout). */
export function failedSourceCount(resp: OdooSourceMapResponse | null): number {
  if (!resp) return 0;
  return resp.sources.filter(
    (s) => s.last_scan_status === 'failed' || s.last_scan_status === 'timeout',
  ).length;
}

/** A short progress summary line, e.g. "12/22 scanned · 1 failed". */
export function scanProgressLabel(progress: OdooScanProgress | null): string {
  if (!progress) return '';
  const parts = [`${progress.done}/${progress.total} scanned`];
  if (progress.running) parts.push(`${progress.running} running`);
  if (progress.partial + progress.capped > 0) {
    parts.push(`${progress.partial + progress.capped} partial`);
  }
  if (progress.failed + progress.timeout > 0) {
    parts.push(`${progress.failed + progress.timeout} failed`);
  }
  return parts.join(' · ');
}

/** 0–100 completion percentage for a progress bar. */
export function scanProgressPercent(progress: OdooScanProgress | null): number {
  if (!progress || progress.total <= 0) return 0;
  return Math.round((progress.done / progress.total) * 100);
}

/** Format a scan duration (ms) compactly, e.g. "1.2s" or "340ms". */
export function durationLabel(ms: number | null): string {
  if (ms == null) return '';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}
