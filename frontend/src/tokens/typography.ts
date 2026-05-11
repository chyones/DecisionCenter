/**
 * Typography tokens — Phase 1I.
 *
 * Mirrors `docs/design/PHASE_1I_UI_CONTRACT.md` §A.4. Companion CSS variables
 * `--font-*` and `--text-*` are declared in `src/index.css`.
 */

export const fontFamilies = {
  sans: "'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  mono: "'JetBrains Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, 'Liberation Mono', monospace",
} as const;

export type FontFamilyToken = keyof typeof fontFamilies;

export type TypographyLevel =
  | 'display'
  | 'heading'
  | 'body'
  | 'label'
  | 'caption'
  | 'mono';

/** Allowed font weights (contract §A.4: never below 400, never above 600). */
export type FontWeight = 400 | 500 | 600;

export interface TypographyStyle {
  family: string;
  weight: FontWeight;
  /** Font size in `px`; never below 12px per the contract. */
  size: `${number}px`;
  lineHeight: number;
  letterSpacing: string;
}

export const typography = {
  display: {
    family: fontFamilies.sans,
    weight: 600,
    size: '20px',
    lineHeight: 1.3,
    letterSpacing: '-0.01em',
  },
  heading: {
    family: fontFamilies.sans,
    weight: 600,
    size: '16px',
    lineHeight: 1.4,
    letterSpacing: '0',
  },
  body: {
    family: fontFamilies.sans,
    weight: 400,
    size: '14px',
    lineHeight: 1.6,
    letterSpacing: '0',
  },
  label: {
    family: fontFamilies.sans,
    weight: 500,
    size: '12px',
    lineHeight: 1.5,
    letterSpacing: '0.01em',
  },
  caption: {
    family: fontFamilies.sans,
    weight: 400,
    size: '12px',
    lineHeight: 1.5,
    letterSpacing: '0',
  },
  mono: {
    family: fontFamilies.mono,
    weight: 400,
    size: '12px',
    lineHeight: 1.4,
    letterSpacing: '0',
  },
} as const satisfies Record<TypographyLevel, TypographyStyle>;

/** Minimum font size permitted anywhere in the UI (contract §A.4). */
export const MIN_FONT_SIZE_PX = 12 as const;
