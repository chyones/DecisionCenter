# Phase 1I UI Design Contract

> **Status:** Planning/design contract only. Phase 1I is not started.
> **Date:** 2026-05-11
> **Applies to:** Phase 1I - Frontend Foundation & Static Admin Scaffolds.
> **Primary sources:** `docs/execution/PHASE_1I_PLAN.md`, `docs/design/UI_CONTRACT_v1.md`, `docs/execution/IMPLEMENTATION_PHASES.md`, `docs/security/rbac_matrix.md`, `docs/config/project_source_mapping.json`.
> **Implementation gate:** This document does not authorize implementation. Phase 1I still requires explicit user approval. Authenticated GitHub Actions status for the latest planning/documentation HEAD must be green before Phase 1I implementation approval.

## A. Visual direction

Phase 1I must establish a quiet, operational UI foundation for a senior-management decision system, not a marketing surface. The interface should feel dense enough for repeated administrative work, but restrained enough that status, role, and route state are always easy to scan.

- Use the locked dark theme only: `surface-base` page background, raised panels, restrained borders, and high-contrast text from `UI_CONTRACT_v1.md` Section 1.4.
- Keep screens system-like and evidence-aware even while static: every route must name its state, role context, and whether it is a static Phase 1I scaffold.
- Do not add decorative artwork, marketing hero sections, gradient/orb backgrounds, product copy, or explanatory onboarding panels.
- Admin screens must read as configuration and system metadata only. They must not visually imply access to report content, evidence excerpts, query text, business artifacts, or secrets.
- Workspace screens must read as a future report-submission workspace, but Phase 1I may render only the Query Composer shell with no project data and no submit behavior.

## B. Design tokens

The Phase 1I token layer must mirror `UI_CONTRACT_v1.md` Section 1.4 exactly and centralize values so later screens do not fork the visual language.

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

Typography:

| Use | Contract |
|---|---|
| UI labels | Inter, 12px-14px |
| Body/report text | Inter, 14px-16px, line-height 1.6 |
| Headings | Inter Semibold, 18px-24px |
| Monospace | JetBrains Mono, 12px for hashes, IDs, paths |

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
| `disconnected` | error | `plug-x` |
| `unknown` | text-muted | `circle-dashed` |

Spacing and sizing:

- Use the fixed layout dimensions from `UI_CONTRACT_v1.md` Section 1.3 as hard tokens: 48px topbar, 220px sidebar, 48px collapsed sidebar rail, 960px main max width, 380px detail panel.
- Minimum supported viewport width is 768px. Mobile layout is out of scope.
- Additional spacing values may use the chosen frontend framework's standard scale when Phase 1I implementation is approved, but they must not override the fixed layout dimensions above.

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

## D. Component contract

Phase 1I reusable components are foundation pieces only.

| Component | Phase 1I contract |
|---|---|
| `StatusPill` | Must render all 13 locked statuses with the exact color token and named icon. `processing` must pulse. Labels must fit without resizing the layout. |
| `Button` | Variants: primary (`accent`), secondary (neutral/raised), danger (`error`). Buttons must support disabled and loading states without layout shift. |
| `Modal` | Uses `surface-overlay`, visible focus state, title, body, primary/secondary actions, dismiss behavior. |
| `ConfirmDialog` | Must require a typed confirmation string for destructive actions. In Phase 1I this is a component behavior contract only; no destructive backend action exists. |
| `Toast` | Transient status feedback using success/warning/error/unknown semantics. Must not claim persistence or backend writes in Phase 1I. |
| `SlideInPanel` | 380px right-side panel primitive. In Phase 1I it may show static/demo content only and must not expose evidence/report/audit data. |

Dev-only helper constraints:

- Any role switcher is local/dev-only only.
- Any component sandbox or storybook-style page is local/dev-only only.
- Neither helper may appear in production navigation.
- Neither helper is a Phase 1I user-facing screen.
- Neither helper may bypass RBAC guards.
- If implemented during Phase 1I, each helper must be excluded from or clearly disabled in production builds.

## E. Route-by-route UI contract

| Route | Phase 1I UI state | Visibility | Required behavior |
|---|---|---|---|
| `/` | Role-based redirect entrypoint | All roles | Redirect to the role's default landing using static/client role context only. No auth implementation. |
| `/workspace/new` | Query Composer shell | `executive`, `project_manager`, `finance`, `commercial`, `document_control`, `procurement`, `legal` | Render the form shell: disabled/empty project selector, query textarea with character counter, optional filters, upload-files placeholder, output-format checkboxes, disabled/non-submitting generate button. No project data, no submit handler, no upload handler. |
| `/workspace/reports` | Phase 2A placeholder | Business roles plus `auditor`; not `admin` | Static placeholder only. No report list, no MinIO/audit data, no API calls. Auditor default landing may point here as a placeholder until Phase 2A. |
| `/workspace/*` other | Phase 2A placeholder or forbidden | Business roles; not `admin` | Static later-phase placeholder only. No Processing View, Report View, Evidence Panel, Export Panel, or report content. |
| `/admin` | Admin Dashboard placeholder | `admin` only | Static Phase 2B placeholder. No live service counts, no recent events, no costs, no business data. |
| `/admin/health` | Static System Health scaffold | `admin` only | Render a static table shaped like the System Health screen. No `/healthz` call, no latency probes, no cost monitor wiring, no auto-refresh. |
| `/admin/permissions` | Permissions & Roles, Role Matrix tab only | `admin` only | Render the canonical role matrix from `docs/security/rbac_matrix.md` as baked static data. No Entra edit tab, no project assignments editor, no save actions. |
| `/admin/source-mapping` | Source Mapping read-only scaffold | `admin` only | Render the shape of `docs/config/project_source_mapping.json` as static read-only source references. No editor, no validate/save/disable actions, no credential fields. |
| `/admin/*` other | Phase 2B placeholder or forbidden | `admin` only | Static later-phase placeholder only. No Connectors, Approval Queue, Audit Log, Cost Monitor, live Dashboard, or editable Source Mapping. |
| Forbidden route | `forbidden` | All roles | Render a static 403/forbidden state for guard violations. Server-side 403 remains authoritative and unchanged. |

Global route prohibitions:

- No API client implementation.
- No `fetch`, `axios`, `XMLHttpRequest`, websocket, event stream, or data-fetching abstraction.
- No report content rendering.
- No evidence excerpts or evidence-pack rendering.
- No backend, API, schema, RBAC, retrieval, evaluation, persistence, CI, deployment, or agent-state changes.

## F. RBAC UX contract

Phase 1I RBAC behavior is UX-only and must never be described as security enforcement. The backend remains the authority for real 403 decisions.

Default landings:

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

Guard rules:

- Business roles are blocked from all `/admin/*` routes.
- `auditor` is blocked from `/workspace/new` and any submit action.
- `admin` is blocked from all `/workspace/*` routes and from any report/evidence/query content surface.
- Non-admin users must not see admin navigation items.
- Admin users must not see workspace navigation items.
- The client guard must route denied access to a static forbidden state or role-appropriate landing. It must not create or weaken backend authorization.

Admin boundary:

- Admin is a configuration role only.
- Admin sees system metadata, role matrices, static health rows, and source-reference metadata.
- Admin never sees report content, query text, evidence excerpts, evidence-pack contents, business-data artifacts, or credentials.

## G. Frontend architecture contract

This section describes the future Phase 1I implementation shape only. It does not create files or authorize implementation.

Approved foundation:

- Vite + React + TypeScript + Tailwind in `frontend/`.
- Central token module or Tailwind theme mapping the exact values in Section B.
- Route definitions for workspace/admin/forbidden paths.
- Static fixtures copied from approved docs where needed for Phase 1I scaffolds.
- No runtime dependency on backend services.

Suggested internal structure for the future implementation:

| Area | Responsibility |
|---|---|
| `tokens` | Color, typography, fixed layout dimensions, status definitions. |
| `components` | `StatusPill`, `Button`, `Modal`, `Toast`, `ConfirmDialog`, `SlideInPanel`. |
| `layout` | Topbar, Sidebar, Main content wrapper, optional Detail Panel primitive. |
| `routes` | Client-side route table and role guards. |
| `fixtures` | Static role matrix and source-mapping shape derived from docs. |
| `screens` | Static Phase 1I scaffolds and later-phase placeholders only. |

Architecture prohibitions:

- No generated API client.
- No network layer.
- No environment-driven API base URL.
- No auth/token implementation.
- No state store for live backend data.
- No test connection actions or live health probes.
- No hidden production access to dev-only role switchers or sandboxes.

## H. Quality bar

The Phase 1I implementation cannot close unless these checks pass:

- `npm run build` exits 0 in `frontend/`.
- `npm run lint` exits 0 in `frontend/`.
- All 9 canonical roles land on their correct default route.
- Forbidden route attempts are denied by client UX without claiming to replace server authorization.
- `StatusPill` renders all 13 states with correct colors and icons.
- `ConfirmDialog` requires a typed confirmation string for destructive actions.
- No `fetch`, `axios`, `XMLHttpRequest`, websocket, event stream, or network abstraction exists in `frontend/`.
- Static System Health does not call `/healthz`.
- Query Composer has no submit handler and no project-dropdown data.
- Source Mapping is read-only and contains no credential values.
- Permissions & Roles includes only the read-only Role Matrix tab.
- Admin cannot see workspace/report/evidence/query surfaces.
- Business roles and auditor cannot see admin routes.
- Production remains `NOT_LIVE`.

Recommended supporting checks:

- A grep-style CI assertion for forbidden network APIs in `frontend/`.
- A routing unit test or equivalent static route matrix for the 9 roles.
- A status-pill rendering test covering all 13 statuses.
- A production-build check that dev-only helpers are absent or disabled.

## I. Implementation slices refinement

The implementation plan in `docs/execution/PHASE_1I_PLAN.md` is valid. Refine the eventual Phase 1I sequence as follows:

1. **Bootstrap only:** Create `frontend/`, install the approved Vite/React/TypeScript/Tailwind toolchain, and prove empty-app build/lint. Do not add API/client/auth code.
2. **Tokens and status registry:** Implement locked colors, typography, fixed layout dimensions, and all 13 status definitions before building screens.
3. **Foundation components:** Build the reusable components with stable dimensions and disabled/loading/error states; keep any sandbox local/dev-only and absent from production navigation.
4. **Layout shell:** Implement topbar, role badge, sidebar, main content wrapper, and slide-in panel primitive with the 768px minimum width rule.
5. **Role route matrix:** Implement static/client route guards for the 9 roles and a forbidden screen; keep any role switcher local/dev-only and production-disabled.
6. **Static admin scaffolds:** Add `/admin/health`, `/admin/permissions`, `/admin/source-mapping`, and `/admin` placeholder with no API calls and no editable actions.
7. **Static workspace scaffolds:** Add `/workspace/new`, `/workspace/reports` placeholder, and other Phase 2A placeholders without submit, upload, report, evidence, or export behavior.
8. **No-network verification:** Add explicit lint/test/grep coverage proving no `fetch`/`axios`/network layer exists.
9. **CI wiring:** Add `frontend/` lint/build checks only after the frontend exists. Do not change backend gates except to keep them green.
10. **Closeout docs:** Only after implementation and validation, update the required phase closeout docs and create `PHASE_1I_REPORT.md`; do not advance state before validation and approval evidence exists.

## J. Final verdict

**PHASE_1I_UI_CONTRACT_READY_FOR_IMPLEMENTATION_APPROVAL**

This contract is derivable from the live Phase 1I plan and locked UI contract. It does not start Phase 1I, does not create frontend implementation files, and does not authorize API wiring, backend changes, deployment, or production use.
