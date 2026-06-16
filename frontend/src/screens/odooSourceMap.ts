/**
 * Pure helpers for the Odoo Source Map panel.
 *
 * Kept separate from the React component so the grouping / labelling logic is
 * unit-testable without a DOM. All functions are pure and carry no project
 * specific data — they operate on whatever the generic API returns.
 */
import type { StatusValue } from '../tokens/status';
import type { OdooSourceMapEntry, OdooSourceMapResponse } from '../api';

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

/** Map a per-source scan status onto a StatusPill value + label. */
export function scanStatusPill(status: string): { status: StatusValue; label: string } {
  if (status === 'ok' || status === 'capped') return { status: 'connected', label: status };
  if (status === 'empty') return { status: 'unknown', label: 'empty' };
  if (status === 'unmapped') return { status: 'disconnected', label: 'unmapped' };
  if (status.startsWith('error')) return { status: 'failed', label: 'error' };
  return { status: 'unknown', label: 'not scanned' };
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
