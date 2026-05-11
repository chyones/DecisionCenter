/**
 * Spacing scale — Phase 1I (contract §A.1). 4px base grid.
 *
 * These values deliberately coincide with Tailwind's default numeric spacing
 * scale (`1` = 0.25rem = 4px, … `12` = 3rem = 48px), so the `p-1`…`p-12`,
 * `gap-*`, `m-*` utilities map 1:1 onto `space-1`…`space-12`. No custom Tailwind
 * spacing keys are added. Use these constants only where a raw value is needed
 * (inline styles, computed layout).
 */
export const spacing = {
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  8: '32px',
  10: '40px',
  12: '48px',
} as const;

export type SpacingStep = keyof typeof spacing;

/** Base grid unit in pixels (contract §A.1). */
export const SPACING_BASE_PX = 4 as const;

/** Density presets (contract §A.1). */
export const density = {
  compact: { padding: spacing[2], gap: spacing[3] },
  comfortable: { padding: spacing[4], gap: spacing[3] },
} as const;

export type Density = keyof typeof density;
