/**
 * Fixed layout dimensions — Phase 1I (contract §B "Spacing and sizing" and §C
 * "Layout contract"). These are hard tokens, not part of the spacing scale.
 * Companion CSS variables `--layout-*` are declared in `src/index.css`.
 *
 * Values are in pixels (numbers) so they can be used in calculations; append
 * `px` when emitting CSS.
 */
export const layout = {
  /** Topbar height (fixed). */
  topbarHeight: 48,
  /** Sidebar width when expanded. */
  sidebarWidth: 220,
  /** Sidebar width when collapsed to the icon rail. */
  sidebarRailWidth: 48,
  /** Max width of the centered main content column. */
  mainMaxWidth: 960,
  /** Right-side slide-in detail panel width. */
  detailPanelWidth: 380,
  /** Minimum supported viewport width; below this, show the unsupported-width state. */
  minAppWidth: 768,
} as const;

export type LayoutDimension = keyof typeof layout;

/** Sidebar/topbar motion timings (contract §C.1 / §C.2). */
export const motion = {
  sidebarWidthMs: 200,
  sidebarLabelFadeMs: 150,
  tooltipDelayMs: 200,
  modalBackdropMs: 150,
  modalScaleMs: 200,
  panelOpenMs: 250,
  panelCloseMs: 200,
  toastEnterMs: 200,
  toastExitMs: 150,
  buttonPressMs: 100,
} as const;
