# Phase 1I UI Design Contract

> **Status:** Planning/design contract only. Phase 1I is not started.
> **Date:** 2026-05-11
> **Applies to:** Phase 1I - Frontend Foundation & Static Admin Scaffolds.
> **Primary sources:** `docs/execution/PHASE_1I_PLAN.md`, `docs/design/UI_CONTRACT_v1.md`, `docs/execution/IMPLEMENTATION_PHASES.md`, `docs/security/rbac_matrix.md`, `docs/config/project_source_mapping.example.json`.
> **Implementation gate:** This document does not authorize implementation. Phase 1I still requires explicit user approval. Authenticated GitHub Actions status for the latest planning/documentation HEAD must be green before Phase 1I implementation approval.

---

## A. Visual direction

Phase 1I must establish a quiet, operational UI foundation for a senior-management decision system, not a marketing surface. The interface should feel dense enough for repeated administrative work, but restrained enough that status, role, and route state are always easy to scan.

- Use the locked dark theme only: `surface-base` page background, raised panels, restrained borders, and high-contrast text from `UI_CONTRACT_v1.md` Section 1.4.
- Keep screens system-like and evidence-aware even while static: every route must name its state, role context, and whether it is a static Phase 1I scaffold.
- Do not add decorative artwork, marketing hero sections, gradient/orb backgrounds, product copy, or explanatory onboarding panels.
- Admin screens must read as configuration and system metadata only. They must not visually imply access to report content, evidence excerpts, query text, business artifacts, or secrets.
- Workspace screens must read as a future report-submission workspace, but Phase 1I may render only the Query Composer shell with no project data and no submit behavior.

### A.1 Spacing and density system

Phase 1I uses a 4px base grid. All spacing values must resolve to multiples of 4px to prevent subpixel misalignment.

| Token | Value | Usage |
|---|---|---|
| `space-1` | `4px` | Tight inline gaps, icon-text pairs |
| `space-2` | `8px` | Button internal padding (vertical), pill padding |
| `space-3` | `12px` | Compact row gaps, metadata clusters |
| `space-4` | `16px` | Card internal padding, form field gaps |
| `space-5` | `20px` | Section separations inside cards |
| `space-6` | `24px` | Page content padding, modal internal padding |
| `space-8` | `32px` | Section breaks, page header to content |
| `space-10` | `40px` | Major layout gaps |
| `space-12` | `48px` | Topbar height, sidebar collapsed rail width |

Density rules:
- **Compact density** for tables and admin metadata rows: `space-3` row height, `space-2` cell vertical padding.
- **Comfortable density** for forms and cards: `space-4` internal padding, `space-3` between fields.
- **No spacious density** in Phase 1I. The target is an operational tool, not a consumer app.
- Maximum one level of nesting: card inside main content area is allowed; card-inside-card is prohibited.

### A.2 Depth and elevation

Dark-theme depth is conveyed through surface lightness steps and thin borders, never through heavy drop shadows.

| Token | Value | Usage |
|---|---|---|
| `shadow-none` | none | Flat elements inside raised surfaces |
| `shadow-sm` | `0 1px 2px rgba(0,0,0,0.24)` | Buttons, pills, small interactive elements |
| `shadow-md` | `0 4px 12px rgba(0,0,0,0.32)` | Modals, popovers, dropdowns |
| `shadow-lg` | `0 8px 24px rgba(0,0,0,0.40)` | Slide-in panel, fullscreen overlays |

Shadow rules:
- Shadows are used sparingly. If an element is on `surface-base`, it may use a shadow; if it is on `surface-raised`, it must not cast a shadow onto an identical surface.
- Modal backdrop: `rgba(0,0,0,0.60)` fixed overlay, `z-index` above all content but below toasts.
- Focus rings: `0 0 0 2px surface-base, 0 0 0 4px accent` for all focusable elements. This creates a high-contrast halo on dark backgrounds without clashing with component borders.

### A.3 Border radius system

| Token | Value | Usage |
|---|---|---|
| `radius-sm` | `4px` | Buttons, pills, inputs, small tags |
| `radius-md` | `6px` | Cards, modals, table rows (if rounded) |
| `radius-lg` | `8px` | Slide-in panel, large containers |

Radius rules:
- Do not mix radii arbitrarily within a single component family.
- Tables use `radius-sm` on outer container only; inner rows are flush.
- Avatars and icon containers are fully rounded (`9999px`) only when they contain a single icon or initials.

### A.4 Typography hierarchy

The contract in `UI_CONTRACT_v1.md` Section 1.4 is the baseline. Phase 1I tightens it into a strict hierarchy:

| Level | Font | Weight | Size | Line-height | Letter-spacing | Usage |
|---|---|---|---|---|---|---|
| `display` | Inter | 600 | `20px` | `1.3` | `-0.01em` | Page titles only |
| `heading` | Inter | 600 | `16px` | `1.4` | `0` | Section headers, card titles |
| `body` | Inter | 400 | `14px` | `1.6` | `0` | Primary content, labels |
| `label` | Inter | 500 | `12px` | `1.5` | `0.01em` | Form labels, column headers, metadata keys |
| `caption` | Inter | 400 | `12px` | `1.5` | `0` | Timestamps, helper text, disabled copy |
| `mono` | JetBrains Mono | 400 | `12px` | `1.4` | `0` | IDs, hashes, paths, code snippets |

Typography rules:
- Never use font sizes below `12px`.
- Never use font weights below `400` or above `600`.
- `text-muted` must not be used for primary actions or navigation labels.
- Monospace text is always `12px`; if a hash needs emphasis, use `text-secondary` or a lighter color, not a larger size.

### A.5 Color discipline

- `accent` (`#4F6EF7`) is reserved for primary actions, active navigation, links, and `processing`/`final` states. It must not be used for decorative accents, icons that are not interactive, or background fills larger than a button.
- `success`/`warning`/`error` are reserved for status, validation, and destructive actions. They must not tint backgrounds of large regions.
- `surface-overlay` must not be used as a page background.
- Borders must be `1px solid border` except for focus rings.
- No gradients. No transparency on text (opacity < 1.0) except for disabled states.

---

## B. Design tokens

The Phase 1I token layer must mirror `UI_CONTRACT_v1.md` Section 1.4 exactly, extended by the spacing, depth, and radius tokens above, and centralized so later screens do not fork the visual language.

| Token | Value | Required use |
|---|---|---|
| `surface-base` | `#0F1117` | Page background |
| `surface-raised` | `#1A1D27` | Cards and panels |
| `surface-overlay` | `#242736` | Modals, overlays, confirmation surfaces |
| `border` | `#2D3142` | Separators and component borders |
| `accent` | `#4F6EF7` | Primary actions, links, `final`, `processing` |
| `success` | `#22C55E` | `ok`, `passed`, `connected`, `authorized`, approved states |
| `warning` | `#F59E0B` | `needs_review`, `degraded`, staging, warning states |
| `error` | `#EF4444` | Failed, disconnected, denied, destructive actions |
| `text-primary` | `#F1F5F9` | Main copy and primary labels |
| `text-secondary` | `#94A3B8` | Metadata, secondary labels |
| `text-muted` | `#4B5563` | Timestamps, hashes, low-emphasis metadata |

Typography tokens: see Section A.4.

Status pills:

| Value | Color | Icon |
|---|---|---|
| `authorized` | success | `shield-check` |
| `processing` | accent, pulsing | `loader` |
| `passed` | success | `circle-check` |
| `needs_review` | warning | `triangle-alert` |
| `failed` | error | `x-circle` |
| `staging` | warning | `clock` |
| `approved` | success | `stamp` |
| `rejected` | error | `ban` |
| `final` | accent | `lock` |
| `connected` | success | `plug` |
| `degraded` | warning | `plug-zap` |
| `disconnected` | error | `unplug` (alias of the spec's `plug-x` — see icon-set resolution) |
| `unknown` | text-muted | `circle-dashed` |

Icon-set resolution: `UI_CONTRACT_v1.md` Section 1.4 names `plug-x` for `disconnected`, but the current Lucide icon set does not ship a `plug-x` glyph (it ships `plug`, `plug-2`, `plug-zap`, `unplug`). Phase 1I must render `disconnected` with `unplug` and record this as a deliberate, documented deviation from the locked spec's icon *name* (the `error` color token and the semantics are unchanged). Before implementation, the chosen icon library and version must be pinned, and every other named glyph in this table (`shield-check`, `loader`, `circle-check`, `triangle-alert`, `x-circle`, `clock`, `stamp`, `ban`, `lock`, `plug`, `plug-zap`, `circle-dashed`) verified to exist in that version; any further substitution must be documented the same way and must not change the status color or meaning.

Spacing and sizing:

- Use the fixed layout dimensions from `UI_CONTRACT_v1.md` Section 1.3 as hard tokens: 48px topbar, 220px sidebar, 48px collapsed sidebar rail, 960px main max width, 380px detail panel.
- Minimum supported viewport width is 768px. Mobile layout is out of scope.
- Additional spacing values use the 4px grid defined in Section A.1.

---

## C. Layout contract

Every Phase 1I route must sit inside the same shell:

- Topbar: 48px fixed. Required content: product/logo label, breadcrumb, interface label, current role badge, avatar/user affordance placeholder.
- Sidebar: 220px fixed, collapsible to a 48px icon rail. Navigation contents must be role-filtered.
- Main content: max-width 960px, horizontally centered, no nested card-inside-card page structure.
- Detail panel: 380px slide-in from the right. In Phase 1I it may exist as a reusable primitive only; it must not render real evidence, report content, audit details, or live health charts.
- Width floor: 768px. Below that, the app may show an unsupported-width state rather than inventing a mobile layout.

Layout state rules:

- Every screen must show a visible named state such as `static_scaffold`, `phase_2a_placeholder`, `phase_2b_placeholder`, or `forbidden`.
- No unmarked spinners are allowed.
- Placeholder routes must clearly indicate later-phase availability without adding feature descriptions that operate like in-app documentation.

> **New vocabulary note.** The named layout/route states above (`static_scaffold`, `phase_2a_placeholder`, `phase_2b_placeholder`, `forbidden`) are introduced by this Phase 1I contract; they do not appear in `UI_CONTRACT_v1.md` or `docs/execution/PHASE_1I_PLAN.md`. They are a Phase 1I refinement, not a restatement of the locked spec. The implementation must define them once in the central state/token registry (alongside the status-pill definitions) so screens cannot fork the names, and must not retroactively treat them as locked-spec terms. The locked status pills in Section B and these screen-level states are distinct registries and must not be conflated.

### C.1 Sidebar behavior

- Default state: expanded (220px).
- Collapse trigger: icon button at the sidebar footer or topbar toggle.
- Collapsed state: 48px icon rail. Icons remain visible and clickable. Tooltips show the full label on hover after a `200ms` delay.
- Active route: left border indicator (`2px solid accent`) on the active item in expanded mode; `accent` background tint (`rgba(79,110,247,0.12)`) in collapsed mode.
- Hover: `surface-overlay` background on the hovered item.
- Transition: `width 200ms ease`, `opacity 150ms ease` for label fade. No layout shift in main content — main content margin-left adjusts smoothly.
- Role-filtered: items that are not visible to the current role are removed from the DOM, not hidden with `display: none`.

### C.2 Topbar behavior

- Fixed at `z-index` above sidebar and main content.
- Background: `surface-raised` with `1px solid border` bottom edge.
- Breadcrumb uses `text-secondary` for inactive segments, `text-primary` for the current page. Separator is a chevron icon (`text-muted`, `12px`).
- Role badge: `StatusPill`-shaped compact badge using the role identifier text and `accent` color for business roles, `warning` for `auditor`, `text-muted` for `admin`.
- Avatar placeholder: initials or a generic user icon. No live user profile photo in Phase 1I.

### C.3 Unsupported width state

If viewport width falls below 768px:
- Show a centered fullscreen overlay: `surface-overlay` background.
- Text: "Minimum viewport width is 768px. Resize your browser to continue."
- No sidebar, no topbar, no content peek-through.
- This is a static scaffold state, not a responsive layout.

---

## D. Component contract

Phase 1I reusable components are foundation pieces only. Every component below must specify visual rules, interaction rules, accessibility rules, and unacceptable implementation examples.

### D.1 `StatusPill`

**Visual rules:**
- Height: `24px` minimum, `28px` maximum. Padding: `0 space-2` (0 8px).
- Border-radius: `radius-sm` (4px).
- Background: `rgba(token, 0.12)` where token is the status color. Text: the same status color at full opacity.
- Icon: `14px`, left of label, `space-1` gap.
- Label: `label` typography (`12px`, weight 500), uppercase first letter only (sentence case).
- `processing`: icon rotates continuously with `animation: spin 1s linear infinite`.

**Interaction rules:**
- StatusPill is non-interactive in Phase 1I. No hover state, no click handler, no cursor change.
- Exception: if a future phase makes pills clickable (e.g., filter by status), the hover state is `rgba(token, 0.20)` background.

**Accessibility rules:**
- `aria-label` must include the status text (e.g., "Status: processing").
- `processing` must use `aria-live="polite"` when it is the only dynamic element on the page.

**Unacceptable implementation examples:**
- Pill height that changes based on label length.
- Pill text in all-caps.
- `processing` with a static icon instead of rotation.
- Using `accent` background for `success` status.
- Missing `aria-label` on non-interactive pills inside tables.

### D.2 `Button`

**Visual rules:**
- Height: `32px` (compact) and `40px` (default). Phase 1I uses `32px` for dense admin tables and `40px` for primary actions.
- Padding: `0 space-3` (0 12px) for compact; `0 space-4` (0 16px) for default.
- Border-radius: `radius-sm` (4px).
- Typography: `label` (`12px`, weight 500) for compact; `body` (`14px`, weight 500) for default.
- Icon placement: left of text with `space-1` gap. Icon size: `16px`.

| Variant | Background | Text | Border | Shadow |
|---|---|---|---|---|
| Primary | `accent` | `text-primary` | none | `shadow-sm` |
| Secondary | `surface-raised` | `text-primary` | `1px solid border` | none |
| Danger | `error` | `text-primary` | none | `shadow-sm` |
| Ghost | transparent | `text-secondary` | none | none |

**Interaction rules:**
- Hover: Primary → `lighten(accent, 8%)`; Secondary → `surface-overlay`; Danger → `lighten(error, 8%)`; Ghost → `rgba(text-secondary, 0.08)` background.
- Active (press): scale `0.98`, transition `100ms`.
- Focus: `focus-ring` token (Section A.2).
- Disabled: `opacity: 0.45`, `cursor: not-allowed`, no hover or active transform.
- Loading: spinner icon replaces the left icon (or appears left of text if no icon). Text remains visible. Button is disabled. No layout shift — spinner must occupy the same space as the original icon.

**Accessibility rules:**
- Minimum touch target: `32px × 32px` even for compact buttons.
- `disabled` attribute, not just visual opacity, for `<button>` elements.
- Loading state must include `aria-busy="true"`.

**Unacceptable implementation examples:**
- Button height changing between default and loading states.
- Using `<div>` instead of `<button>` for clickable buttons.
- Ghost button used for primary actions.
- Danger variant used for non-destructive cancel actions.
- Missing focus ring.

### D.3 `Modal`

**Visual rules:**
- Width: `480px` default; `640px` for wide confirmations.
- Max-height: `85vh` with internal scroll.
- Background: `surface-overlay`.
- Border: `1px solid border`.
- Border-radius: `radius-md` (6px).
- Padding: `space-6` (24px).
- Shadow: `shadow-md`.
- Title: `heading` typography (`16px`, weight 600).
- Body: `body` typography (`14px`, weight 400), `space-4` below title.

**Interaction rules:**
- Open: fade-in backdrop (`150ms`) + scale-up modal from `0.96` to `1.0` (`200ms ease-out`).
- Close: reverse animation.
- Dismiss: click backdrop, press Escape, or click the close icon (top-right, `16px`).
- Focus trap: first focusable element receives focus on open; focus cycles within modal.
- Scroll lock: body scroll is disabled while modal is open.

**Accessibility rules:**
- `role="dialog"`, `aria-modal="true"`.
- Title has `id` referenced by `aria-labelledby`.
- Close button has `aria-label="Close dialog"`.

**Unacceptable implementation examples:**
- Modal without backdrop.
- Modal that does not trap focus.
- Modal that does not return focus to the trigger on close.
- Body scroll continuing underneath modal.
- Modal width that is a percentage of viewport without a max-width cap.

### D.4 `ConfirmDialog`

Inherits all `Modal` rules, with these additions:

**Visual rules:**
- Confirmation input field: full-width text input, `space-4` height, `surface-base` background, `1px solid border`, `radius-sm`.
- Action bar: primary action (danger or confirm) aligned right, secondary action (cancel) to its left, `space-3` gap.
- Destructive confirmations use the `danger` button variant.
- Warning confirmations (non-destructive but risky) use the `primary` button variant with a `warning` icon.

**Interaction rules:**
- Primary action is disabled until the typed confirmation string matches exactly.
- Error state on mismatch: input border turns `error` with caption text "Confirmation does not match." below the input.
- On confirm: primary action enters loading state. Modal stays open until the action resolves (future phase). In Phase 1I, confirm is a no-op; the loading state must still be defined.

**Accessibility rules:**
- Confirmation input must have an associated `<label>` referencing the required text (e.g., "Type 'PRJ-001' to confirm").
- `aria-describedby` on the input pointing to helper text.

**Unacceptable implementation examples:**
- Confirm button enabled before the string matches.
- Using a checkbox instead of typed confirmation for destructive actions.
- Modal closing on backdrop click during a destructive confirmation.
- No visual difference between cancel and confirm buttons.

### D.5 `Toast`

**Visual rules:**
- Position: fixed, top-right, `space-4` from viewport edges.
- Width: `360px` max. Min-height: `48px`.
- Background: `surface-raised`.
- Border-left: `3px solid` using the toast color (`success`, `warning`, `error`, or `accent` for info).
- Border-radius: `radius-sm`.
- Shadow: `shadow-md`.
- Padding: `space-3 space-4`.
- Icon: `16px`, left, color matches border-left.
- Title (optional): `label` weight 500. Body: `caption`.

**Interaction rules:**
- Auto-dismiss: `5000ms` for success/info; `8000ms` for warning/error.
- Hover: pause auto-dismiss timer.
- Manual dismiss: close icon (`16px`) top-right.
- Stacking: up to 3 toasts visible. Additional toasts queue behind. Newest appears on top with `8px` vertical offset between items.
- Entry: slide in from right (`translateX(100%) → 0`, `200ms ease-out`) + fade.
- Exit: slide out to right + fade, `150ms`.

**Accessibility rules:**
- `role="status"` for info/success; `role="alert"` for warning/error.
- `aria-live="polite"` region wrapping the toast container.
- Dismiss button has `aria-label="Dismiss notification"`.

**Unacceptable implementation examples:**
- Toasts that never auto-dismiss.
- More than 3 toasts visible simultaneously.
- Toasts appearing at the bottom-center (obscures content).
- Success toasts with `role="alert"` (causes unnecessary screen-reader interruption).
- Toasts claiming backend persistence or writes in Phase 1I.

### D.6 `SlideInPanel`

**Visual rules:**
- Width: `380px` fixed.
- Height: `100vh`, offset by topbar height (`48px`), positioned below topbar.
- Background: `surface-raised`.
- Border-left: `1px solid border`.
- Shadow: `shadow-lg` on the left edge only (or full shadow if overlay is used).
- Header: `space-4` padding, `heading` typography, close icon top-right.
- Body: `space-4` padding, scrollable.

**Interaction rules:**
- Open: slide in from right (`translateX(100%) → 0`, `250ms ease-out`).
- Close: slide out to right, `200ms`.
- Backdrop: `rgba(0,0,0,0.40)` overlay behind panel but above main content. Click backdrop to close.
- Focus: first focusable element in panel receives focus on open.
- Scroll: independent scroll inside panel; main content scroll is not locked.

**Accessibility rules:**
- `aria-label` on the panel container describing its purpose (e.g., "Detail panel").
- Close button has explicit `aria-label`.

**Unacceptable implementation examples:**
- Panel sliding over the topbar.
- Panel without a close affordance.
- Panel width that is a percentage of viewport.
- Panel rendering real evidence, report content, or audit data in Phase 1I.

### D.7 `Table`

**Visual rules:**
- Header row: `surface-raised` background, `label` typography (`12px`, weight 500, `text-secondary`), uppercase first letter only. Border-bottom: `1px solid border`.
- Body rows: `surface-base` background. Border-bottom: `1px solid border`.
- Row height: `44px` minimum for comfortable density; `36px` allowed for compact admin tables.
- Cell padding: `space-3` horizontal (12px), `space-2` vertical (8px).
- Empty row: centered `text-secondary` text inside a single row spanning all columns.
- No zebra striping. No vertical borders between columns.
- Border-radius: `radius-sm` on the outer container only.

**Interaction rules:**
- Hover row: `surface-overlay` background (`150ms` transition).
- Active/selected row: `rgba(accent, 0.08)` background + left `2px solid accent` indicator.
- Sortable header: hover shows a `text-muted` sort icon; active sort shows `accent` icon.
- No row click in Phase 1I unless the row navigates to a detail view (not implemented yet).

**Accessibility rules:**
- `<table>` markup with proper `<thead>` and `<tbody>`.
- Column headers have `scope="col"`.
- Empty state has `aria-live="polite"` if the table content changes dynamically.

**Unacceptable implementation examples:**
- Table built with CSS Grid or Flexbox instead of semantic `<table>`.
- Zebra striping.
- Row hover that changes text color (causes flicker).
- Missing empty state.
- Fake data rows in static scaffolds that look like live data.

### D.8 `FormField`

**Visual rules:**
- Label: `label` typography, `text-secondary`, `space-1` (4px) below label.
- Input: height `40px`, `surface-base` background, `1px solid border`, `radius-sm`, `space-3` horizontal padding.
- Textarea: min-height `96px`, same padding and border.
- Helper text: `caption`, `text-muted`, `space-1` below input.
- Error text: `caption`, `error`, `space-1` below input, preceded by `x-circle` icon (`12px`).
- Disabled: `opacity: 0.5`, `cursor: not-allowed`.

**Interaction rules:**
- Focus: border color transitions to `accent`, `150ms`.
- Focus ring: `focus-ring` token (Section A.2) applied to the input container, not just the border.
- Error: border color `error`. Shake animation on first appearance is optional (`translateX(-4px → 4px → 0)`, `200ms`).
- Character counter (for textarea): `caption`, `text-muted`, right-aligned below input. Turns `warning` at 90% of max, `error` at 100%+.

**Accessibility rules:**
- Every input has an associated `<label>` with `htmlFor`.
- Error text linked via `aria-describedby`.
- Required fields marked with `aria-required="true"` and a visual indicator (red asterisk, `error` color, `space-1` after label).

**Unacceptable implementation examples:**
- Placeholder used as a substitute for a label.
- Inputs without visible borders on `surface-base`.
- Error state that only changes border color without text.
- Character counter that changes the textarea height.

### D.9 `RoleBadge`

**Visual rules:**
- A compact `StatusPill`-like badge used exclusively in the topbar and route guards.
- Height: `24px`. Padding: `0 space-2`.
- Background: `rgba(accent, 0.12)` for business roles; `rgba(warning, 0.12)` for `auditor`; `rgba(text-muted, 0.12)` for `admin`.
- Text: role identifier in sentence case, `label` typography, color matching background tint.

**Interaction rules:**
- Non-interactive in Phase 1I.
- In future phases with real auth, clicking may open a user menu; Phase 1I must not implement this.

**Accessibility rules:**
- `aria-label="Current role: {role}"`.

**Unacceptable implementation examples:**
- Role badge styled differently from `StatusPill` (breaking visual consistency).
- Role badge used inside tables or lists.
- All roles using the same color.

### D.10 `PlaceholderScreen`

**Visual rules:**
- Centered vertically and horizontally within the main content area.
- Icon: `48px`, `text-muted`, centered above text.
- Title: `heading` typography (`16px`, weight 600, `text-primary`), `space-3` below icon.
- Body: `body` typography (`14px`, `text-secondary`), max-width `400px`, centered, `space-4` below title.
- Optional metadata: `caption`, `text-muted`, showing the named state (e.g., "State: phase_2a_placeholder").

**Interaction rules:**
- No interactive elements unless a "Go back" or "Return to dashboard" link is provided.
- No loading spinners.

**Accessibility rules:**
- `role="status"`, `aria-live="polite"`.

**Unacceptable implementation examples:**
- Placeholder screen with a spinner.
- Placeholder screen describing features in marketing language ("Unlock powerful reports...").
- Placeholder screen with a "Learn more" button linking to documentation.
- Fake UI chrome that implies functionality (e.g., a disabled search bar with placeholder text "Search reports" when no search exists yet).

### D.11 `ForbiddenScreen`

Inherits `PlaceholderScreen` rules, with these additions:

**Visual rules:**
- Icon: `shield-check` or `ban`, `error` color, `48px`.
- Title: "Access denied" or "Forbidden".
- Body: "You do not have permission to view this page." + role context if helpful (e.g., "Your role: admin").
- No secondary actions beyond a link to the role's default landing.

**Interaction rules:**
- Rendered on client-side guard violations.
- No retry button, no "Contact support" button.
- Auto-redirect to the role-appropriate landing after `5000ms` is optional and must be clearly indicated with a countdown.

**Accessibility rules:**
- `role="alert"`, `aria-live="assertive"`.

**Unacceptable implementation examples:**
- Forbidden screen with a login form.
- Forbidden screen blaming the user ("You are not authorized" instead of "Access denied").
- Forbidden screen showing a stack trace or error code.
- Forbidden screen that looks like a broken page (missing styles, misaligned text).

### D.12 `SidebarNavItem`

**Visual rules:**
- Height: `36px`. Padding: `space-3` horizontal (12px).
- Layout: flex row, `space-2` gap between icon and label.
- Icon: `16px`, `text-secondary` default.
- Label: `body` typography (`14px`, weight 400), `text-secondary` default.
- Border-radius: `radius-sm` on the container.
- Collapsed mode: icon centered, no label, width `48px`.

**Interaction rules:**
- Default: transparent background.
- Hover: `surface-overlay` background (`150ms`).
- Active/current route: `accent` left border (`2px solid`), `rgba(accent, 0.08)` background. Icon and label become `accent`.
- Collapsed active: `accent` background tint (`rgba(accent, 0.12)`), no left border.
- Click: client-side navigation only. No page reload.

**Accessibility rules:**
- Use native `<a>` with `href`.
- `aria-current="page"` on the active item.
- In collapsed mode, `aria-label` must contain the full label text.
- Items hidden by role filtering are removed from the DOM, not just visually hidden.

**Unacceptable implementation examples:**
- Using `<div>` without `role="link"` or button semantics.
- Hiding inactive items with `display: none` while keeping them in the DOM for screen readers.
- Active state that only changes text color without a background or border indicator.
- Nav item that triggers a full page reload in a single-page app.

### D.13 `PageHeader`

**Visual rules:**
- Single row, full width of main content area.
- Left: title (`display` typography, `20px`, weight 600, `text-primary`).
- Right: optional metadata tag (`caption`, `text-muted`) aligned to the same baseline.
- Margin-bottom: `space-8` (32px).
- No border-bottom. No background. No shadow.

**Interaction rules:**
- Non-interactive.
- Metadata tag may update if the screen state changes (e.g., from `static_scaffold` to `phase_2a_placeholder`), but only via local/client state.

**Accessibility rules:**
- Title is an `<h1>`.
- If a metadata tag is present, it is a `<span>` with `aria-hidden="true"` (decorative) or `aria-label` describing the state.

**Unacceptable implementation examples:**
- Multiple `<h1>` elements on one screen.
- Page header missing on any route.
- Title that does not match the route purpose.
- Page header styled as a card or panel.

### D.14 `EmptyState`

**Visual rules:**
- Centered within its parent container (table, list, or card).
- Icon: `48px`, `text-muted`.
- Title: `heading` typography (`16px`, weight 600, `text-primary`), `space-3` below icon.
- Body: `body` typography (`14px`, `text-secondary`), max-width `320px`, centered, `space-4` below title.
- No background. No border. No shadow.

**Interaction rules:**
- Non-interactive by default.
- May contain a single action button if the corresponding feature is implemented. In Phase 1I, no action button is permitted because no data-creating features exist yet.

**Accessibility rules:**
- `role="status"`, `aria-live="polite"`.
- If an action is present, it must not be the only focusable element in the container (provide an escape path).

**Unacceptable implementation examples:**
- Using `PlaceholderScreen` inside a table cell or list item.
- Showing a "Create new" or "Add" button for a feature that is not implemented.
- Empty state with a spinner.
- Empty state that uses marketing language.
- Missing empty state on any table or list component.

### D.15 `DisabledActionTooltip`

**Visual rules:**
- Trigger: hover or focus on a wrapper around a disabled action.
- Tooltip surface: `surface-overlay` background, `1px solid border`, `radius-sm`, `shadow-md`.
- Padding: `space-2 space-3` (8px 12px).
- Text: `caption` typography (`12px`, `text-primary`), max-width `240px`.
- Arrow: `6px` triangle pointing to the trigger, `surface-overlay` fill.
- Position: above the trigger by default; below if space is insufficient.

**Interaction rules:**
- Delay: `300ms` before showing on hover/focus.
- Hide: `100ms` delay on mouse leave.
- The disabled element itself must be wrapped in a `<span>` (or equivalent) because most browsers do not fire mouse events on disabled `<button>` elements.
- Content must explain why the action is disabled (e.g., "Not available in Phase 1I", "Requires project selection").

**Accessibility rules:**
- The wrapper has `aria-describedby` pointing to the tooltip content.
- Tooltip content is in a `role="tooltip"` element.
- Focus management: tooltip appears on focus and hides on blur.

**Unacceptable implementation examples:**
- Attaching tooltip directly to a disabled `<button>` (mouse events may not fire).
- Tooltip that looks like an error banner or inline validation message.
- Tooltip without an arrow, making it unclear which element it belongs to.
- Tooltip that persists after the user navigates away with the keyboard.
- Using a tooltip to describe an enabled action (use a label or helper text instead).

---

## E. Route-by-route UI contract

Every route below must declare its visual layout, interaction behavior, empty/static state wording, role boundary, and what must not appear.

### E.1 `/` — Role-based redirect entrypoint

- **Visual layout:** No visible content. A brief centered `PlaceholderScreen` with state `redirecting` may be shown for `< 300ms` to prevent a blank flash.
- **Interaction behavior:** Immediate client-side redirect to the role's default landing using static/client role context only.
- **Empty/static state wording:** "Redirecting…" (if shown).
- **Role boundary:** All roles.
- **What must not appear:** Any dashboard content, any API call, any auth implementation.

### E.2 `/workspace/new` — Query Composer shell

- **Visual layout:**
  - Page header: "Query Composer" (`display` typography) + `static_scaffold` metadata tag (`caption`, `text-muted`).
  - Form card (`surface-raised`, `radius-md`, `space-6` padding):
    - Project selector: `FormField` with a disabled dropdown showing placeholder "No projects available in Phase 1I".
    - Query textarea: `FormField`, `2000` max length, character counter visible at `0/2000`, placeholder: "Enter your management question…".
    - Filters section: collapsed by default. Toggle header "Filters (optional)". Inside: four disabled `FormField` inputs (Contract No., Vendor, Date range, Document type).
    - Upload zone: placeholder box (`surface-base`, `1px dashed border`, `radius-sm`, `space-8` height) with text "File upload will be available in a later phase." and icon `upload` (`text-muted`).
    - Output formats: horizontal row of 5 checkboxes. Only MD is checked and disabled. Others are unchecked and disabled. Label: "Output formats:".
    - Action row: right-aligned `Button` primary, disabled, label "Generate Report →".
- **Interaction behavior:**
  - All inputs are disabled or read-only.
  - Query textarea is enabled for local typing only. Character counter updates locally. Text is ephemeral — not persisted, transmitted, or validated against a backend.
  - Generate button remains disabled. No submit handler.
  - No project dropdown data. No upload handler.
- **Empty/static state wording:**
  - Project dropdown placeholder: "No projects available in Phase 1I".
  - Upload zone: "File upload will be available in a later phase.".
  - Page metadata tag: "static_scaffold — no backend data".
- **Role boundary:** `executive`, `project_manager`, `finance`, `commercial`, `document_control`, `procurement`, `legal`. `auditor` and `admin` are redirected.
- **What must not appear:** Live project list, live submit behavior, live upload, Processing View link, evidence panel, report preview, fake project names, API wiring.

### E.3 `/workspace/reports` — Phase 2A placeholder

- **Visual layout:** `PlaceholderScreen` centered in main content.
- **Interaction behavior:** None.
- **Empty/static state wording:**
  - Icon: `folder-open` (or equivalent from pinned icon set).
  - Title: "Reports — Available in Phase 2A".
  - Body: "This screen will list your reports and their status. It is not available in the current phase.".
  - Metadata: "State: phase_2a_placeholder".
- **Role boundary:** Business roles plus `auditor`; not `admin`.
- **What must not appear:** Report list, MinIO/audit data, API calls, fake report rows, fake status pills, search or filter controls.

### E.4 `/workspace/*` other — Phase 2A placeholder or forbidden

- **Visual layout:** `PlaceholderScreen` or `ForbiddenScreen`.
- **Interaction behavior:** None.
- **Empty/static state wording:** Same pattern as `/workspace/reports` with route-specific placeholder text, or "Access denied" for forbidden routes.
- **Role boundary:** Business roles plus `auditor`; not `admin`.
- **What must not appear:** Processing View, Report View, Evidence Panel, Export Panel, report content, any live data.

### E.5 `/admin` — Admin Dashboard placeholder

- **Visual layout:** `PlaceholderScreen` centered in main content.
- **Interaction behavior:** None.
- **Empty/static state wording:**
  - Icon: `layout-dashboard`.
  - Title: "Admin Dashboard — Available in Phase 2B".
  - Body: "System overview, service status, and operational metrics will appear here.".
  - Metadata: "State: phase_2b_placeholder".
- **Role boundary:** `admin` only.
- **What must not appear:** Live service counts, recent events, cost data, business data, cards with fake numbers, charts, sparklines.

### E.6 `/admin/health` — Static System Health scaffold

- **Visual layout:**
  - Page header: "System Health" (`display`) + `static_scaffold` metadata tag.
  - Subheader: "This table shows the expected layout. No live data is displayed." (`body`, `text-secondary`).
  - `Table` component with 5 columns: Service, Status, Latency, SLA, Trend.
  - 10 static rows (PostgreSQL, Redis, Qdrant, MinIO, n8n, SharePoint, Graph API, ownCloud, Odoo, Langfuse).
  - Status column: `StatusPill` with static values (`connected`, `degraded`, etc.) per row. ownCloud shows `degraded` as a deliberate example.
  - Latency column: `mono` typography, static values (e.g., "12ms", "2340ms").
  - SLA column: `mono` typography, static values (e.g., "200ms").
  - Trend column: placeholder text "—" (`text-muted`). No sparkline.
  - Cost Monitor section below table: `surface-raised` card with static labels "Daily cost" and "Monthly cost" and progress-bar-shaped placeholder bars (`surface-base` background, `border`, no fill animation).
- **Interaction behavior:**
  - Table rows are non-interactive. No hover that implies clickability.
  - No refresh button. No auto-refresh. No `/healthz` call.
  - Forbidden: `[Test connection]`, `[Open n8n ↗]`, cost-monitor drill-down, sparkline click, service-row click.
- **Empty/static state wording:**
  - Subheader: "This table shows the expected layout. No live data is displayed.".
  - Trend column: "—".
  - Cost bars: empty track only.
- **Role boundary:** `admin` only.
- **What must not appear:** Live `/healthz` call, latency probes, cost monitor wiring, auto-refresh, animated progress bars, sparklines, real timestamps.

### E.7 `/admin/permissions` — Permissions & Roles, Role Matrix tab only

- **Visual layout:**
  - Page header: "Permissions & Roles" (`display`) + `static_scaffold` metadata tag.
  - Single tab bar with one active tab: "Role Matrix". No second or third tabs in Phase 1I.
  - `Table` component:
    - Header: Role, SharePoint Project Docs, ownCloud Project Docs, User Mailbox, Shared Mailboxes, Odoo Budget, Odoo Actual Cost, Approval, Audit Logs.
    - 9 data rows from `docs/security/rbac_matrix.md`, baked as static fixtures.
    - Cell content: `text-secondary` for plain text; `StatusPill` (`approved` or `unknown`) only where a boolean-like state is needed. In Phase 1I, text values are acceptable.
  - Below table: `caption` text: "Source: docs/security/rbac_matrix.md. Changes require a spec update." (`text-muted`).
- **Interaction behavior:**
  - Table is read-only. No inline editing. No save.
  - No Entra edit tab. No project assignments editor.
  - Forbidden: `[Edit]`, `[Save]`, `[Add mapping]`, `[Remove]`, `[Assign project]` buttons or links.
- **Empty/static state wording:** N/A — table always has 9 rows.
- **Role boundary:** `admin` only.
- **What must not appear:** Entra Group Mapping tab, Project Role Assignments tab, editable cells, save actions, Add/Remove buttons, fake Entra group data.

### E.8 `/admin/source-mapping` — Source Mapping read-only scaffold

- **Visual layout:**
  - Page header: "Project Source Mapping" (`display`) + `static_scaffold` metadata tag.
  - Subheader: "Read-only view of the mapping shape. No credentials are shown." (`body`, `text-secondary`).
  - Two-column layout inside a `surface-raised` card:
    - Left column (`280px` wide): list of project codes from `docs/config/project_source_mapping.example.json` (e.g., "PRJ-001"). Each item shows project code + `StatusPill` (`complete`).
    - Right column (remaining width): static metadata for the selected project rendered as metadata rows (key-value pairs, `space-3` row height, `label` key, `body` value):
      - Project Code
      - SharePoint Site ID
      - SharePoint Drive ID
      - SharePoint Root Path
      - ownCloud Base Path
      - Shared Mailboxes
      - Document Control Mailbox
      - Odoo Project Model
      - Odoo Cost Model
      - Odoo Project External ID
      - Contract Numbers
  - Values are taken directly from the example JSON file. No credential fields.
- **Interaction behavior:**
  - Project list items are selectable. Clicking highlights the row (`active` table row style).
  - Right column updates to show the selected project's data. No API call — data is baked fixtures.
  - No editor. No validate/save/disable actions.
  - Forbidden: `[Add mapping]`, `[Edit]`, `[Save]`, `[Validate]`, `[Disable]`, `[Delete]` buttons or links.
- **Empty/static state wording:** N/A — example file has at least one project.
- **Role boundary:** `admin` only.
- **What must not appear:** Live `project_source_mapping.json` (the non-example file), credential values, editor UI, Validate/Save buttons, Add mapping button, source-enable toggles.

### E.9 `/admin/*` other — Phase 2B placeholder or forbidden

- **Visual layout:** `PlaceholderScreen` or `ForbiddenScreen`.
- **Interaction behavior:** None.
- **Empty/static state wording:** Same pattern as `/admin` with route-specific placeholder text.
- **Role boundary:** `admin` only.
- **What must not appear:** Connectors, Approval Queue, Audit Log, Cost Monitor, live Dashboard, editable Source Mapping, any business data.

### E.10 Forbidden route (`/403` or guard catch-all)

- **Visual layout:** `ForbiddenScreen`.
- **Interaction behavior:** Static. Optional auto-redirect to role default after `5000ms` with visible countdown.
- **Empty/static state wording:**
  - Title: "Access denied".
  - Body: "You do not have permission to view this page." + "Your role: {role}.".
  - Optional: "Redirecting to your default landing in {N}s…".
- **Role boundary:** All roles.
- **What must not appear:** Login form, backend error details, stack traces, retry button, "Contact support" button.

### E.11 Global route prohibitions

- No API client implementation.
- No `fetch`, `axios`, `XMLHttpRequest`, websocket, event stream, or data-fetching abstraction.
- No report content rendering.
- No evidence excerpts or evidence-pack rendering.
- No backend, API, schema, RBAC, retrieval, evaluation, persistence, CI, deployment, or agent-state changes.

### E.12 Route-by-route action matrix

This matrix is the authoritative reference for which actions are permitted, disabled, or forbidden in Phase 1I. Any action not listed here is forbidden.

| Label | Route | Visible role | State | Allowed behavior | Forbidden behavior | Production visibility |
|---|---|---|---|---|---|---|
| Query textarea | `/workspace/new` | Business roles | **Enabled** | Local typing only. Character counter updates locally. Text is ephemeral. | Submit, validate against backend, persist, auto-save. | Visible |
| Generate Report | `/workspace/new` | Business roles | **Disabled** | Visual shell only. No click handler. | Submit, call API, navigate to Processing View, show loading state. | Visible |
| Upload zone | `/workspace/new` | Business roles | **Disabled / Non-interactive** | Visual placeholder only. No click, drag, or drop handler. | Open file picker, accept files, validate MIME type, upload. | Visible |
| Filter toggle | `/workspace/new` | Business roles | **Enabled** | Expand/collapse local UI state only. | Filter data, call API, persist filter selection. | Visible |
| Filter inputs | `/workspace/new` | Business roles | **Disabled** | Visual shell only. | Accept input, validate, auto-suggest. | Visible |
| Output format checkboxes | `/workspace/new` | Business roles | **Disabled** | Visual shell only. | Change selection, persist preference. | Visible |
| Project list select | `/admin/source-mapping` | `admin` | **Enabled** | Local selection only. Highlights row. Updates right panel from baked fixtures. | Save selection, call API, validate mapping. | Visible |
| Go to dashboard | `/403` | All roles | **Enabled** | Client-side navigation to role default landing. | Login redirect, auth retry, backend request. | Visible |
| Sidebar collapse | All routes | All roles | **Enabled** | Toggle sidebar width between 220px and 48px. | Persist preference to backend. | Visible |
| Sidebar nav item | All routes | Role-filtered | **Enabled** | Client-side navigation to permitted route. | Navigate to forbidden routes, bypass guards. | Visible |
| Dev role switcher | Any | All roles (dev-only) | **Enabled** | Switch static role context for local testing. | Persist role, bypass backend auth, appear in production. | **Hidden** |
| Component sandbox | Any | All roles (dev-only) | **Enabled** | Render isolated component states for local testing. | Appear in production navigation, bypass RBAC guards. | **Hidden** |

Explicitly forbidden actions (must not appear as enabled buttons or links):

| Forbidden label | Route | Why forbidden |
|---|---|---|
| Refresh / Reload | `/admin/health` | No live `/healthz` call in Phase 1I. |
| Test connection | `/admin/health`, `/admin/connectors` | No live probe actions in Phase 1I. |
| Save / Update | `/admin/permissions`, `/admin/source-mapping` | No write operations in Phase 1I. |
| Edit / Add / Remove / Assign | `/admin/permissions`, `/admin/source-mapping` | No editor UI in Phase 1I. |
| Validate / Disable / Delete | `/admin/source-mapping` | No mapping lifecycle actions in Phase 1I. |
| Submit / Send / Post | `/workspace/new` | No backend submit in Phase 1I. |
| Export / Download | Any workspace route | No report or evidence rendering in Phase 1I. |
| Approve / Reject / Request revision | Any | No approval actions in Phase 1I. |
| Search / Filter (live) | `/workspace/reports`, `/admin/audit` | No live data to search or filter. |
| Notification bell / Alerts | Any | No notification system in Phase 1I. |

---

## F. RBAC UX contract

Phase 1I RBAC behavior is UX-only and must never be described as security enforcement. The backend remains the authority for real 403 decisions.

### F.1 Default landings

| Role | Phase 1I default landing |
|---|---|
| `executive` | `/workspace/new` |
| `project_manager` | `/workspace/new` |
| `finance` | `/workspace/new` |
| `commercial` | `/workspace/new` |
| `document_control` | `/workspace/new` |
| `procurement` | `/workspace/new` |
| `legal` | `/workspace/new` |
| `auditor` | `/workspace/reports` placeholder |
| `admin` | `/admin` placeholder |

### F.2 Guard rules

- Business roles are blocked from all `/admin/*` routes.
- `auditor` is blocked from `/workspace/new` and any submit action.
- `admin` is blocked from all `/workspace/*` routes and from any report/evidence/query content surface.
- Non-admin users must not see admin navigation items.
- Admin users must not see workspace navigation items.
- The client guard must route denied access to a static forbidden state or role-appropriate landing. It must not create or weaken backend authorization.

### F.3 Admin boundary

- Admin is a configuration role only.
- Admin sees system metadata, role matrices, static health rows, and source-reference metadata.
- Admin never sees report content, query text, evidence excerpts, evidence-pack contents, business-data artifacts, or credentials.

---

## G. Frontend architecture contract

This section describes the future Phase 1I implementation shape only. It does not create files or authorize implementation.

### G.1 Approved foundation

- Vite + React + TypeScript + Tailwind in `frontend/`.
- Central token module or Tailwind theme mapping the exact values in Section B and Section A.
- Route definitions for workspace/admin/forbidden paths.
- Static fixtures copied from approved docs where needed for Phase 1I scaffolds. The Source Mapping scaffold fixture must be derived from `docs/config/project_source_mapping.example.json` (the sanitized example), never from the live `docs/config/project_source_mapping.json`, and must contain no credential or secret values.
- No runtime dependency on backend services.

### G.2 Suggested internal structure

| Area | Responsibility |
|---|---|
| `tokens` | Color, typography, fixed layout dimensions, spacing, depth, radius, the 13 status-pill definitions, and the named screen-level states (`static_scaffold`, `phase_2a_placeholder`, `phase_2b_placeholder`, `forbidden`). |
| `components` | `StatusPill`, `Button`, `Modal`, `Toast`, `ConfirmDialog`, `SlideInPanel`, `Table`, `FormField`, `RoleBadge`, `PlaceholderScreen`, `ForbiddenScreen`, `SidebarNavItem`, `PageHeader`, `EmptyState`, `DisabledActionTooltip`. |
| `layout` | Topbar, Sidebar, Main content wrapper, optional Detail Panel primitive. |
| `routes` | Client-side route table and role guards. |
| `fixtures` | Static role matrix (from `rbac_matrix.md`) and source-mapping shape (from `project_source_mapping.example.json`) derived from docs. |
| `screens` | Static Phase 1I scaffolds and later-phase placeholders only. |

### G.3 Architecture prohibitions

- No generated API client.
- No network layer.
- No environment-driven API base URL.
- No auth/token implementation.
- No state store for live backend data.
- No test connection actions or live health probes.
- No hidden production access to dev-only role switchers or sandboxes.

---

## H. Quality bar

The Phase 1I implementation cannot close unless these checks pass:

- `npm run build` exits 0 in `frontend/`.
- `npm run lint` exits 0 in `frontend/`.
- All 9 canonical roles land on their correct default route.
- Forbidden route attempts are denied by client UX without claiming to replace server authorization.
- `StatusPill` renders all 13 states with correct colors and icons (`disconnected` using the `unplug` alias per Section B).
- `ConfirmDialog` requires a typed confirmation string for destructive actions.
- No `fetch`, `axios`, `XMLHttpRequest`, websocket, event stream, or network abstraction exists in `frontend/`.
- Static System Health does not call `/healthz`.
- Query Composer has no submit handler and no project-dropdown data.
- Source Mapping is read-only, is built from `project_source_mapping.example.json`, and contains no credential values.
- Permissions & Roles includes only the read-only Role Matrix tab.
- Admin cannot see workspace/report/evidence/query surfaces.
- Business roles and auditor cannot see admin routes.
- Production remains `NOT_LIVE`.

### H.1 UI quality checks (new for design review)

- Every interactive element has a visible focus state using the `focus-ring` token.
- No focus ring is clipped by `overflow: hidden` containers.
- All disabled states use `opacity: 0.45` + `cursor: not-allowed`.
- All loading states preserve button dimensions (no layout shift).
- Toasts auto-dismiss and do not stack beyond 3.
- Placeholder screens do not use spinners or marketing language.
- Tables have a defined empty state and do not use fake data.
- Sidebar collapse animation is smooth (`200ms`) and does not cause horizontal scroll.
- Modal traps focus and returns focus to trigger on close.
- No decorative gradients, orbs, or illustrations.
- No fake live data (numbers, charts, graphs, activity feeds).
- No misleading buttons (buttons that look enabled but do nothing, or buttons labeled as actions that are not implemented).

### H.2 Recommended supporting checks

- A grep-style CI assertion for forbidden network APIs in `frontend/`.
- A routing unit test or equivalent static route matrix for the 9 roles.
- A status-pill rendering test covering all 13 statuses.
- A production-build check that dev-only helpers are absent or disabled.
- A visual regression check (optional) that placeholder screens render consistently.

---

## I. Professional polish rules

These rules apply to every screen and component in Phase 1I.

### I.1 Consistent alignment

- All page headers align to the same left edge as the main content container.
- All cards align to the same grid. No arbitrary left margins.
- Right-aligned actions (buttons, metadata) share a single vertical alignment line.
- Form labels align left with their inputs. No center-aligned form labels.

### I.2 Consistent spacing

- Use the 4px grid exclusively. No `5px`, `7px`, `11px`, `13px`, `15px`, `17px`, `19px`, `21px`, or `23px` values.
- Section spacing inside a page: `space-8` (32px) minimum between unrelated sections.
- Card internal padding: `space-6` (24px) default; `space-4` (16px) only for compact tables.
- No arbitrary margins inserted to "balance" a layout. Use the token scale.

### I.3 Page headers

- Every route has exactly one page header.
- Format: title (`display` typography) + optional metadata tag (`caption`, `text-muted`) on the same baseline, right-aligned.
- No subtitle below the title unless the route is a static scaffold that requires an explicit disclaimer.

### I.4 Section headers

- Format: `heading` typography (`16px`, weight 600) + optional `text-muted` count or status to the right.
- Border-bottom: `1px solid border` below the header, `space-3` padding-bottom.
- No section header without content below it.

### I.5 Metadata rows

- Used in admin screens and detail panels.
- Format: key (`label`, `text-secondary`, `140px` min-width) + value (`body`, `text-primary`).
- Alignment: key right-aligned, value left-aligned, `space-3` gap.
- Monospace values (IDs, hashes) use `mono` typography.

### I.6 Table density

- Default: `44px` row height, `space-3` horizontal padding.
- Compact (admin health, role matrix): `36px` row height, `space-2` vertical padding.
- Header row is always `40px` height, regardless of body density.
- Text inside cells is vertically centered. No top-aligned table text.

### I.7 Icon usage

- Icon size inside buttons and pills: `16px`.
- Icon size inside table cells and metadata rows: `14px`.
- Icon size in placeholder and empty states: `48px`.
- Icon color must match the adjacent text color or use `text-muted` for decorative context.
- Never use an icon alone without a text label unless the icon is universally understood (close `×`, search magnifier, chevron for expand/collapse).

### I.8 Animation limits

- All transitions: `150ms–250ms` duration.
- Easing: `ease` or `ease-out` for enter; `ease-in` for exit.
- `prefers-reduced-motion`: all motion transitions must reduce to `0ms` or `opacity` only.
- No parallax, no spring physics, no bouncy overshoot.
- `processing` spin is the only continuous animation allowed.

### I.9 No decorative clutter

- No illustrations, hero images, gradient backgrounds, orb effects, or animated backgrounds.
- No decorative dividers that do not separate named sections.
- No shadow on every element. Shadows are reserved for elements that float above the base layer (modals, panels, dropdowns, toasts).
- No border on every element. Use whitespace to separate groups.

### I.10 No fake live data

- Static scaffolds must never display numbers, counts, percentages, or charts that look like live metrics.
- Health rows use static labels and placeholder text ("—") where a live value would appear.
- Progress bars are empty tracks only; no animated fill.
- No timestamps that update.
- No "Last updated: now" or relative time strings (e.g., "2 minutes ago").

### I.11 No misleading buttons

- Any button that is not wired to an action must be disabled in Phase 1I.
- A disabled button must look disabled (`opacity: 0.45`).
- No button may say "Save" or "Submit" unless it performs that action.
- No button may say "Refresh" or "Test connection" in Phase 1I.
- Placeholder screens must not contain buttons that imply navigation to unimplemented features.

---

## J. Implementation slices refinement

The implementation plan in `docs/execution/PHASE_1I_PLAN.md` is valid. This section *refines* — does not replace — its slice sequence:

1. **Bootstrap only:** Create `frontend/`, install the approved Vite/React/TypeScript/Tailwind toolchain, and prove empty-app build/lint. Do not add API/client/auth code.
2. **Tokens and status registry:** Implement locked colors, typography, fixed layout dimensions, spacing, depth, radius, all 13 status definitions, and the named screen-level states before building screens.
3. **Foundation components:** Build the reusable components with stable dimensions and disabled/loading/error states; keep any sandbox local/dev-only and absent from production navigation.
4. **Layout shell:** Implement topbar, role badge, sidebar, main content wrapper, and slide-in panel primitive with the 768px minimum width rule.
5. **Role route matrix:** Implement static/client route guards for the 9 roles and a forbidden screen; keep any role switcher local/dev-only and production-disabled.
6. **Static admin scaffolds:** Add `/admin/health`, `/admin/permissions`, `/admin/source-mapping`, and `/admin` placeholder with no API calls and no editable actions.
7. **Static workspace scaffolds:** Add `/workspace/new`, `/workspace/reports` placeholder, and other Phase 2A placeholders without submit, upload, report, evidence, or export behavior.
8. **No-network verification:** Add explicit lint/test/grep coverage proving no `fetch`/`axios`/network layer exists.
9. **CI wiring:** Add `frontend/` lint/build checks only after the frontend exists. Do not change backend gates except to keep them green.
10. **Closeout docs:** Only after implementation and validation, update the required phase closeout docs and create `PHASE_1I_REPORT.md`; do not advance state before validation and approval evidence exists.

---

## K. Design review output

### K.1 Design review verdict

**The original `PHASE_1I_UI_CONTRACT.md` was structurally sound but insufficiently detailed for implementation.** It correctly scoped Phase 1I constraints and cited locked sources, but it lacked the density of visual, interaction, and component specifications needed to produce a consistent, modern, professional SaaS/admin UI without drift during implementation.

### K.2 Weak points found

1. **No spacing or density system:** The original contract referenced "standard scale when approved" without defining the grid, density levels, or prohibited values. This leads to arbitrary pixel values during implementation.
2. **No depth/elevation tokens:** Dark-theme quality depends on surface layering. The original contract had no shadow, backdrop, or z-index rules.
3. **Missing component specifications:** `Table`, `FormField`, `RoleBadge`, `PlaceholderScreen`, and `ForbiddenScreen` were not defined. `Button`, `Modal`, `Toast`, `ConfirmDialog`, and `SlideInPanel` had only one-line descriptions.
4. **Missing interaction states:** No hover, focus, active, disabled, or loading state specifications for any component. No focus-ring token.
5. **Missing accessibility rules:** Only a passing mention of "visible focus state." No ARIA rules, no reduced-motion handling.
6. **Thin route specifications:** Each route had a single sentence. No layout details, no empty-state wording, no "what must not appear" per route.
7. **No professional polish rules:** No alignment rules, no animation limits, no anti-clutter rules, no prohibition on fake live data or misleading buttons.
8. **No sidebar behavior specification:** Collapse/expand, active state, tooltips, and transitions were undefined.
9. **No unsupported-width state:** The 768px floor was mentioned but not designed.

### K.3 Required improvements

All improvements have been applied in this revision:
- Added Sections A.1–A.5 (spacing, depth, radius, typography hierarchy, color discipline).
- Added Section C.1–C.3 (sidebar, topbar, unsupported width).
- Expanded Section D into per-component contracts with visual, interaction, accessibility rules, and unacceptable examples for all 11 components.
- Expanded Section E into per-route contracts with layout, interaction, empty-state wording, role boundary, and must-not-appear lists.
- Added Section I (professional polish rules) covering alignment, spacing, headers, metadata, tables, icons, animation, clutter, fake data, and misleading buttons.
- Added Section H.1 (UI quality checks) to the quality bar.

### K.4 Whether the contract should be updated

**Yes.** The contract has been updated in place. No other files were modified. All Phase 1I scope constraints remain intact. No implementation was started.

### K.5 Final implementation acceptance checklist

- [ ] `npm run build` exits 0 in `frontend/`.
- [ ] `npm run lint` exits 0 in `frontend/`.
- [ ] All 9 canonical roles land on their correct default route.
- [ ] Forbidden route attempts are denied by client UX without claiming to replace server authorization.
- [ ] `StatusPill` renders all 13 states with correct colors and icons (`disconnected` using `unplug`).
- [ ] `ConfirmDialog` requires a typed confirmation string for destructive actions.
- [ ] No `fetch`, `axios`, `XMLHttpRequest`, websocket, event stream, or network abstraction exists in `frontend/`.
- [ ] Static System Health does not call `/healthz`.
- [ ] Query Composer has no submit handler and no project-dropdown data.
- [ ] Source Mapping is read-only, is built from `project_source_mapping.example.json`, and contains no credential values.
- [ ] Permissions & Roles includes only the read-only Role Matrix tab.
- [ ] Admin cannot see workspace/report/evidence/query surfaces.
- [ ] Business roles and auditor cannot see admin routes.
- [ ] Production remains `NOT_LIVE`.
- [ ] Every interactive element has a visible focus state.
- [ ] All disabled states use `opacity: 0.45` + `cursor: not-allowed`.
- [ ] All loading states preserve button dimensions.
- [ ] Toasts auto-dismiss and do not stack beyond 3.
- [ ] Placeholder screens do not use spinners or marketing language.
- [ ] Tables have a defined empty state and do not use fake data.
- [ ] Sidebar collapse animation is smooth and does not cause horizontal scroll.
- [ ] Modal traps focus and returns focus to trigger on close.
- [ ] No decorative gradients, orbs, or illustrations.
- [ ] No fake live data.
- [ ] No misleading buttons.

---

## L. Final verdict

**PHASE_1I_UI_DESIGN_REVIEW_COMPLETE**  
**PHASE_1I_UI_CONTRACT_UPDATED_FOR_MODERN_UI**

This contract is derivable from the live Phase 1I plan and locked UI contract. It does not start Phase 1I, does not create frontend implementation files, and does not authorize API wiring, backend changes, deployment, or production use.
