/**
 * Status registry — Phase 1I.
 *
 * The 13 locked status values from `docs/design/PHASE_1I_UI_CONTRACT.md` §B
 * ("Status pills"), each mapped to its semantic color token, icon, label, and
 * animation flag. This is the single source of truth for the `StatusPill`
 * component (built in a later slice) and any status-aware UI.
 *
 * Icon-set note: the contract names `plug-x` for `disconnected`, but the Lucide
 * icon set does not ship that glyph (it ships `plug`, `plug-2`, `plug-zap`,
 * `unplug`). Per the contract's "icon-set resolution" paragraph, `disconnected`
 * uses `unplug`. This is the only icon-name deviation from the locked spec; the
 * `error` color token and the semantics are unchanged.
 */
import type { ColorToken } from './colors';

/** The 13 locked status values, in contract order. */
export const STATUS_VALUES = [
  'authorized',
  'processing',
  'passed',
  'needs_review',
  'failed',
  'staging',
  'approved',
  'rejected',
  'final',
  'connected',
  'degraded',
  'disconnected',
  'unknown',
] as const;

export type StatusValue = (typeof STATUS_VALUES)[number];

/**
 * Lucide icon names used by the status registry. `unplug` stands in for the
 * contract's `plug-x` (see module note); every other name is the contract's
 * literal value and must exist in the pinned Lucide version.
 */
export type StatusIconName =
  | 'shield-check'
  | 'loader'
  | 'circle-check'
  | 'triangle-alert'
  | 'x-circle'
  | 'clock'
  | 'stamp'
  | 'ban'
  | 'lock'
  | 'plug'
  | 'plug-zap'
  | 'unplug'
  | 'circle-dashed';

export interface StatusDefinition {
  /** Sentence-case label for display (contract §D.1). */
  label: string;
  /** Semantic color token from contract §B. */
  color: ColorToken;
  /** Lucide icon name (see module note re: `disconnected` / `unplug`). */
  icon: StatusIconName;
  /** Whether the icon animates; only `processing` per contract §B / §D.1. */
  pulsing: boolean;
}

export const STATUS_REGISTRY = {
  authorized: { label: 'Authorized', color: 'success', icon: 'shield-check', pulsing: false },
  processing: { label: 'Processing', color: 'accent', icon: 'loader', pulsing: true },
  passed: { label: 'Passed', color: 'success', icon: 'circle-check', pulsing: false },
  needs_review: { label: 'Needs review', color: 'warning', icon: 'triangle-alert', pulsing: false },
  failed: { label: 'Failed', color: 'error', icon: 'x-circle', pulsing: false },
  staging: { label: 'Staging', color: 'warning', icon: 'clock', pulsing: false },
  approved: { label: 'Approved', color: 'success', icon: 'stamp', pulsing: false },
  rejected: { label: 'Rejected', color: 'error', icon: 'ban', pulsing: false },
  final: { label: 'Final', color: 'accent', icon: 'lock', pulsing: false },
  connected: { label: 'Connected', color: 'success', icon: 'plug', pulsing: false },
  degraded: { label: 'Degraded', color: 'warning', icon: 'plug-zap', pulsing: false },
  disconnected: { label: 'Disconnected', color: 'error', icon: 'unplug', pulsing: false },
  unknown: { label: 'Unknown', color: 'text-muted', icon: 'circle-dashed', pulsing: false },
} as const satisfies Record<StatusValue, StatusDefinition>;

/** Number of locked status values. */
export const STATUS_COUNT = STATUS_VALUES.length;

/** Type guard: is `value` one of the 13 locked status values? */
export function isStatusValue(value: string): value is StatusValue {
  return (STATUS_VALUES as readonly string[]).includes(value);
}

/** Look up a status definition; throws on an unknown value. */
export function getStatusDefinition(value: StatusValue): StatusDefinition {
  return STATUS_REGISTRY[value];
}
