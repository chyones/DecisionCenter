/**
 * Named screen-level states — Phase 1I.
 *
 * Introduced by `docs/design/PHASE_1I_UI_CONTRACT.md` §C ("Layout state rules"
 * and the "New vocabulary note"): every screen must show a visible named state.
 * These are a Phase 1I refinement, not part of the locked `UI_CONTRACT_v1.md`.
 *
 * This is a SEPARATE registry from the status-pill registry in `./status` —
 * the two must not be conflated (a screen state is not a `StatusPill` value).
 */
export const SCREEN_STATES = [
  /** A static, data-less Phase 1I scaffold of a real screen. */
  'static_scaffold',
  /** Placeholder for a screen that becomes available in Phase 2A. */
  'phase_2a_placeholder',
  /** Placeholder for a screen that becomes available in Phase 2B. */
  'phase_2b_placeholder',
  /** Client-side guard outcome for a disallowed route (server 403 is authoritative). */
  'forbidden',
] as const;

export type ScreenState = (typeof SCREEN_STATES)[number];

/** Number of named screen-level states. */
export const SCREEN_STATE_COUNT = SCREEN_STATES.length;

/** Short, human-readable labels for the named screen states. */
export const SCREEN_STATE_LABELS = {
  static_scaffold: 'Static scaffold',
  phase_2a_placeholder: 'Available in Phase 2A',
  phase_2b_placeholder: 'Available in Phase 2B',
  forbidden: 'Forbidden',
} as const satisfies Record<ScreenState, string>;

/** Type guard: is `value` one of the named screen states? */
export function isScreenState(value: string): value is ScreenState {
  return (SCREEN_STATES as readonly string[]).includes(value);
}
