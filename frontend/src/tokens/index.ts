/**
 * Phase 1I design-token barrel.
 *
 * Centralizes the locked design language from
 * `docs/design/PHASE_1I_UI_CONTRACT.md` so later slices (components, layout
 * shell, screens) consume one source of truth and do not fork values. CSS
 * variables / Tailwind theme mappings of the same tokens live in `../index.css`.
 *
 * `./contract-assertions` is intentionally not re-exported — it is a build-time
 * check module with no public API — but it is still type-checked as part of the
 * `src` project.
 */
export * from './colors';
export * from './typography';
export * from './spacing';
export * from './radius';
export * from './shadows';
export * from './layout';
export * from './status';
export * from './screenStates';
