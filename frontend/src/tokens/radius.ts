/**
 * Border-radius tokens — Phase 1I (contract §A.3). Companion CSS variables
 * `--radius-sm | --radius-md | --radius-lg` are declared in `src/index.css`.
 */
export const radius = {
  sm: '4px',
  md: '6px',
  lg: '8px',
  /** Fully rounded — only for single-icon / initials containers (contract §A.3). */
  full: '9999px',
} as const;

export type RadiusToken = keyof typeof radius;
