/**
 * Compile-time contract assertions for the Phase 1I token layer.
 *
 * These are *static* checks: they run only at `tsc` time (`npm run build`), not
 * at runtime, and emit no code. If a token invariant from
 * `docs/design/PHASE_1I_UI_CONTRACT.md` is broken, the corresponding
 * `export type … = IsTrue<…>` resolves to `false`, which violates the
 * `IsTrue` constraint and fails the build. No test runner is wired in this slice.
 *
 * The typed token/registry definitions already enforce most invariants
 * (`StatusDefinition.color: ColorToken`, `StatusDefinition.icon: StatusIconName`,
 * `… satisfies Record<StatusValue, StatusDefinition>`, etc.); the checks below
 * cover the counts and a few values worth pinning explicitly.
 */
import type { ColorToken } from './colors';
import { STATUS_REGISTRY, STATUS_VALUES } from './status';
import { SCREEN_STATES } from './screenStates';
import { typography } from './typography';

/** Resolves to `T` only when `T` is exactly `true`; otherwise it is a type error. */
type IsTrue<T extends true> = T;

/** 1. There are exactly the 13 locked status values (contract §B). */
export type StatusCountIs13 = IsTrue<
  (typeof STATUS_VALUES)['length'] extends 13 ? true : false
>;

/** 2. There are exactly the 4 named screen-level states (contract §C). */
export type ScreenStateCountIs4 = IsTrue<
  (typeof SCREEN_STATES)['length'] extends 4 ? true : false
>;

/** 3. Every status maps to a real color token (also enforced by `StatusDefinition`). */
type RegistryColors = (typeof STATUS_REGISTRY)[keyof typeof STATUS_REGISTRY]['color'];
export type StatusColorsAreTokens = IsTrue<
  [RegistryColors] extends [ColorToken] ? true : false
>;

/** 4. `disconnected` uses the `unplug` icon alias (contract §B icon-set resolution). */
export type DisconnectedUsesUnplug = IsTrue<
  (typeof STATUS_REGISTRY)['disconnected']['icon'] extends 'unplug' ? true : false
>;

/** 5. Only `processing` animates (contract §B / §D.1). */
type PulsingStatuses = {
  [K in keyof typeof STATUS_REGISTRY]: (typeof STATUS_REGISTRY)[K]['pulsing'] extends true
    ? K
    : never;
}[keyof typeof STATUS_REGISTRY];
export type OnlyProcessingPulses = IsTrue<
  [PulsingStatuses] extends ['processing'] ? true : false
>;

/** 6. No typography level drops below 12px (contract §A.4). */
type TypographySizes = (typeof typography)[keyof typeof typography]['size'];
export type FontSizesWithinContract = IsTrue<
  [TypographySizes] extends ['12px' | '14px' | '16px' | '20px'] ? true : false
>;
