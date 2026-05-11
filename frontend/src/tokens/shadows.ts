/**
 * Elevation tokens — Phase 1I (contract §A.2). Dark-theme depth comes from
 * surface lightness steps and thin borders; shadows are used sparingly.
 * Companion CSS variables `--shadow-sm | --shadow-md | --shadow-lg` are
 * declared in `src/index.css`.
 */
export const shadows = {
  none: 'none',
  sm: '0 1px 2px rgb(0 0 0 / 0.24)',
  md: '0 4px 12px rgb(0 0 0 / 0.32)',
  lg: '0 8px 24px rgb(0 0 0 / 0.4)',
} as const;

export type ShadowToken = keyof typeof shadows;

/** Modal backdrop scrim (contract §A.2). */
export const overlayScrim = 'rgb(0 0 0 / 0.6)';

/** Slide-in panel backdrop scrim (contract §D.6). */
export const overlayScrimPanel = 'rgb(0 0 0 / 0.4)';

/** Focus ring applied to all focusable elements (contract §A.2). */
export const focusRing =
  '0 0 0 2px var(--color-surface-base), 0 0 0 4px var(--color-accent)';
