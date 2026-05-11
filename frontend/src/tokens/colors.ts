/**
 * Color tokens — Phase 1I.
 *
 * Mirrors `docs/design/PHASE_1I_UI_CONTRACT.md` §B exactly. The CSS custom
 * properties `--color-<token>` declared in `src/index.css` (`@theme` block)
 * carry the same values; keep the two definitions in sync.
 *
 * Token names use the contract's kebab-case spelling so they line up 1:1 with
 * the CSS variables and Tailwind color keys.
 */
export const colors = {
  'surface-base': '#0F1117',
  'surface-raised': '#1A1D27',
  'surface-overlay': '#242736',
  border: '#2D3142',
  accent: '#4F6EF7',
  success: '#22C55E',
  warning: '#F59E0B',
  error: '#EF4444',
  'text-primary': '#F1F5F9',
  'text-secondary': '#94A3B8',
  'text-muted': '#4B5563',
} as const;

export type ColorToken = keyof typeof colors;

/** All color token names, in contract order. */
export const COLOR_TOKENS = Object.keys(colors) as ColorToken[];

/** CSS `var(--color-<token>)` reference for a color token. */
export function colorVar(token: ColorToken): string {
  return `var(--color-${token})`;
}

/**
 * Translucent fill of a color token (e.g. status-pill backgrounds use 0.12 —
 * contract §D.1). `color-mix` keeps this anchored to the same CSS variable
 * rather than forking the hex value.
 */
export function colorAlpha(token: ColorToken, alpha: number): string {
  const pct = Math.round(Math.max(0, Math.min(1, alpha)) * 100);
  return `color-mix(in srgb, var(--color-${token}) ${pct}%, transparent)`;
}
