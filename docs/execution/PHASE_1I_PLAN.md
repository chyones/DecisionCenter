# Phase 1I Planning Report — Frontend Foundation & Static Admin Scaffolds

> **Status:** Planning only. Phase 1I is **not** started and **requires explicit user approval** before any implementation.
> **Date:** 2026-05-11
> **Prepared against:** HEAD `4c5b144` (truth/AI-governance cleanup commit); Phases 1A–1H + Phase 1D-fixup complete; production `NOT_LIVE`.
> **Sources of truth:** `docs/design/UI_CONTRACT_v1.md` (locked UI contract, esp. §1–§10 + Appendix A), `docs/execution/IMPLEMENTATION_PHASES.md` (§"Phase 1I"), `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/admin/FEATURE_MATRIX.md`, `docs/security/rbac_matrix.md`, `apps/edr/app.py`.

---

## A. Verified starting state

- **Phase 1H complete.** `docs/ai/agent-state.json` → `status: PHASE_1H_COMPLETE_NOT_LIVE`, `last_completed_phase: Phase 1H`, `next_allowed_phase: Phase 1I`; `docs/execution/PHASE_1H_REPORT.md` exists; `docs/execution/CURRENT_PROJECT_STATE.md` and `docs/execution/IMPLEMENTATION_PHASES.md` record 1A–1H + 1D-fixup complete.
- **Truth/governance cleanup landed.** HEAD `4c5b144` ("docs: reconcile repository truth and AI governance to Phase 1H state"), pushed to `origin/main`. `scripts/check_doc_drift.py` and `scripts/check_ai_context.py` remain clean for this planning-only document. While `docs/execution/PHASE_1I_PLAN.md` is untracked, `scripts/agent_preflight.py` is expected to fail only because this plan file is untracked; after the file is staged or committed, `scripts/agent_preflight.py` must pass. This is not a functional blocker for the plan. Authenticated GitHub Actions status for commit `4c5b144` must be verified before Phase 1I implementation approval. If `gh`/token/API access is unavailable in this environment, CI status must be treated as externally verified or pending, not inferred.
- **Production NOT_LIVE.** `agent-state.json.production_status: NOT_LIVE`, `must_not_deploy: true`; restated in `AGENTS.md`, `docs/ai/SHARED_CONTEXT.md`, `docs/admin/CONTROL_PLANE_LOCK.md` ("READY FOR PHASE 1I — production is NOT_LIVE").
- **Phase 1I not started.** No `frontend/` directory; no `package.json` / Node setup; no `npm run build`/`lint` targets; no UI CI steps. `agent-state.json.requires_explicit_user_approval_for_phase_1i: true`.
- **Phase 1I gate visible.** Restated in `AGENTS.md`, `docs/ai/SHARED_CONTEXT.md`, `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/execution/IMPLEMENTATION_PHASES.md` ("may start with explicit user approval"), `docs/admin/FEATURE_MATRIX.md` ("Phase 1I is the safe next phase").

## B. What Phase 1I means from repo evidence

Phase 1I = **stand up the frontend codebase, build system, design system, layout shell, reusable components, and role-guarded routing, plus a small set of static (data-less) admin/workspace scaffolds, and wire `frontend/` lint+build into CI** — and nothing that touches live backend data.

The UI contract's own phase recommendation (`UI_CONTRACT_v1.md` §10) puts the earliest viable full frontend build "after Phase 1F" (now satisfied: 1A–1H complete), with an explicit exception list of screens that may be scaffolded static early. Phase 1I implements exactly that exception list plus the foundation. The locked spec defines **two interfaces** (User Chat Workspace; Admin Visual Control Plane), **13 screens total** (6 workspace + 7 admin), and **9 canonical RBAC roles**; Phase 1I builds only the foundation and 4 static screen shells — the remaining 9 screens are Phases 2A/2B.

## C. UI/frontend scope (Phase 1I — IN scope)

Per `IMPLEMENTATION_PHASES.md` Phase 1I scope items 1–7 and `UI_CONTRACT_v1.md` §10 exception:

1. **Project init in `frontend/`** — Vite + React + TypeScript + Tailwind.
2. **Design tokens** from `UI_CONTRACT_v1.md` §1.4 — color tokens (`surface-base/raised/overlay`, `border`, `accent`, `success`, `warning`, `error`, `text-primary/secondary/muted`), typography (Inter for UI/body/headings, JetBrains Mono for hashes/IDs/paths), spacing scale, and the 13 status-pill definitions (value → color token → icon).
3. **Layout shell** (`UI_CONTRACT_v1.md` §1.3) — Topbar (48px fixed: logo · breadcrumb · interface label · role badge · avatar), Sidebar (220px fixed, collapsible to a 48px icon rail), Main Content (max-width 960px, centered), Detail Panel (380px slide-in from right). Minimum supported width 768px; no mobile layout.
4. **Reusable components** — `StatusPill`, `Button`, `Modal`, `Toast`, `ConfirmDialog` (requires typed confirmation string for destructive actions per §8.6), `SlideInPanel`.
5. **Role-guarded client-side routing** — `/workspace/*` → User Chat Workspace, `/admin/*` → Admin Visual Control Plane; role-based default-landing redirects and forbidden-route guards per `UI_CONTRACT_v1.md` §1.5 (e.g. `admin` → `/admin` Dashboard, blocked from all `/workspace/*` and any report/evidence content; `auditor` → workspace My Reports, read-only, blocked from Query Composer and any submit action; the 7 business roles → Query Composer). These guards are **UX only** — the server returns 403 on violations (no server change in 1I).
6. **Static scaffolds (no API wiring, no `fetch`/`axios`):**
   - **Admin → System Health** (`/admin/health`) — static table; no live `/healthz` call.
   - **Admin → Permissions & Roles, Tab 1 "Role Matrix"** (`/admin/permissions`) — read-only matrix sourced from `docs/security/rbac_matrix.md` content baked in as static data.
   - **Admin → Source Mapping, read-only view** (`/admin/source-mapping`) — read-only render of `docs/config/project_source_mapping.json` (shape only; the editor is Phase 2B per `UI_CONTRACT_v1.md` §10).
   - **Workspace → Query Composer shell** (`/workspace/new`) — form layout per `UI_CONTRACT_v1.md` §2.1 (project selector, query textarea with char counter, optional filters, upload-files section placeholder, output-format checkboxes, "Generate Report →" button) with **no** project-dropdown data and **no** submit handler.
7. **CI integration** — add `frontend/` lint and build steps; gate on `npm run build` exit 0 and `npm run lint` exit 0.

## D. Non-scope items (Phase 1I — explicitly OUT)

From `IMPLEMENTATION_PHASES.md` Phase 1I "Forbidden in 1I", `UI_CONTRACT_v1.md` §10 + Appendix A, and `docs/admin/CONTROL_PLANE_LOCK.md`:

- No API client; no `fetch`/`axios`/data fetching of any kind.
- No report content rendering; no Evidence Panel with real data; no Processing View wiring; no upload handler.
- No Phase 2A/2B screen implementations: Processing View (live), Report View (content), Export Panel (functional), Upload Zone (functional), My Reports List (data), Admin Dashboard (live counts), Connectors & APIs (live status), Permissions & Roles Entra-edit tab, Project Source Mapping **editor**, Approval Queue, Audit Log (live rows), Cost Monitor.
- No backend/runtime/schema/API/RBAC/retrieval/evaluation/persistence changes; no edits to the locked spec; no Admin screen that exposes report content, evidence, or query text.
- No deployment; production stays `NOT_LIVE`; no secrets/`.env` committed; `docker-compose`/server config unchanged.
- Hard out-of-scope per Appendix A: any write to SharePoint/ownCloud/email/Odoo, email compose, ERP approval creation, document editing, AI-generated financial input, CAD viewer, report template editor, user profile management (Entra-delegated), Phase 2 Action Gateway, mobile-native layout, real-time collaboration, notification email.

## E. Required screens and routes (Phase 1I)

| Route | Screen | Phase 1I state | Visible to (per `UI_CONTRACT_v1.md` §1.5/§4) |
|---|---|---|---|
| `/` | Role-based redirect entrypoint | implemented (routing only) | all roles → their default landing |
| `/workspace/new` | Query Composer **shell** | static form, no data, no submit | 7 business roles; `auditor` redirected to My Reports; `admin` redirected to `/admin` |
| `/workspace/*` (others) | placeholders / "available in Phase 2A" | static | business roles; not `admin` |
| `/admin` | Admin Dashboard placeholder ("Phase 2B") | static placeholder | `admin` only |
| `/admin/health` | System Health | static table | `admin` only |
| `/admin/permissions` | Permissions & Roles — Role Matrix tab (read-only) | static, from `rbac_matrix.md` | `admin` only |
| `/admin/source-mapping` | Source Mapping — read-only view | static, from `project_source_mapping.json` shape | `admin` only |
| `/admin/*` (others) | placeholders ("Phase 2B") | static | `admin` only |
| 403 / not-authorized | Forbidden screen | static | all (on guard violation) |

Routing acceptance (from `IMPLEMENTATION_PHASES.md` gate): all 9 roles land on the correct default screen; forbidden routes redirect/deny in the client; the server-side 403 contract is not changed.

## F. Design system requirements

Single source of truth: `UI_CONTRACT_v1.md` §1.2–§1.4.

- **Tokens as code** — colors, typography, spacing exported as Tailwind theme + CSS variables exactly matching §1.4 values.
- **Status pills** — `StatusPill` component covering all 13 states (`authorized`, `processing` (pulsing), `passed`, `needs_review`, `failed`, `staging`, `approved`, `rejected`, `final`, `connected`, `degraded`, `disconnected`, `unknown`) with the specified color token + icon; this is an explicit acceptance item in the Phase 1I gate.
- **Layout primitives** — fixed Topbar/Sidebar/Main/Detail Panel dimensions; sidebar collapse; ≥768px min width; dark theme only.
- **Component contracts** — `Button` (primary/secondary/danger variants on `accent`/neutral/`error`), `Modal` on `surface-overlay`, `Toast`, `ConfirmDialog` with mandatory typed-confirmation string for destructive actions (§8.6), `SlideInPanel` for the 380px detail panel.
- **Design principles enforced structurally** — state-explicit (every screen has a named, visible state — no unmarked spinners), minimal-surface (no element without a spec requirement); evidence-first/role-bounded are honored by *not* rendering any content surfaces yet.
- Icon set: choose one (e.g. Lucide) that provides the named icons (`shield-check`, `loader`, `circle-check`, `triangle-alert`, `x-circle`, `clock`, `stamp`, `ban`, `lock`, `plug`, `plug-zap`, `plug-x`, `circle-dashed`).

## G. API/RBAC integration requirements

**Phase 1I performs no API integration.** This section records what *exists* so Phases 2A/2B can wire to it, and confirms nothing is missing for the foundation:

- **Existing backend endpoints** (`apps/edr/app.py`): `GET /healthz`; `POST /reports/staging`; `POST /reports/staging/{id}/approve`; `POST /reports/staging/{id}/reject`; `POST /reports/staging/{id}/request-revision`; `GET /reports/staging/{id}/download/{fmt}`; `GET /reports/final/{id}/download/{fmt}`. These are the contracts Phases 2A/2B consume; Phase 1I must not call them.
- **RBAC** — 9 canonical roles in `docs/security/rbac_matrix.md` and `apps/edr/rbac/roles.py`; Node 01 (`node_01_auth.py`) is the authoritative gate and returns `allowed_projects`. Phase 1I encodes the *navigation* matrix (`UI_CONTRACT_v1.md` §1.5, §4.3 Admin screen visibility) as client-side guards only; authorization remains server-enforced (403). No new roles, no RBAC changes.
- **Auth** — `UI_CONTRACT_v1.md` §8.1: Microsoft Entra SSO. Phase 1I may stub the "current role" for routing demonstration with a local/dev-only role switcher, but it must not implement real auth flows or token handling; that is later-phase work. If implemented, the role switcher must not be visible in production navigation, must not be treated as a Phase 1I user-facing screen, must not bypass RBAC guards, and must be excluded or clearly disabled in production builds.
- **Static-data sources for the scaffolds** — `docs/security/rbac_matrix.md` (Role Matrix tab), `docs/config/project_source_mapping.json` and `…example.json` (Source Mapping read-only shape), `UI_CONTRACT_v1.md` §3.7 (System Health table layout). Baked in as static fixtures, not fetched.

## H. Implementation slices (proposed for the eventual Phase 1I session)

Each slice = small, auditable commit. Run the Phase 1I validation gate (Section I) at the end of each.

1. **Project bootstrap** — `frontend/` with Vite + React + TS + Tailwind; `package.json`, `tsconfig`, ESLint/Prettier config; `npm install`, `npm run build`, `npm run lint` succeed on an empty app.
2. **Design tokens** — Tailwind theme + CSS variables from `UI_CONTRACT_v1.md` §1.4 (colors, type, spacing); icon library wired.
3. **Reusable components** — `StatusPill` (all 13 states), `Button`, `Modal`, `Toast`, `ConfirmDialog` (typed-confirmation), `SlideInPanel`; any component sandbox / storybook-style page is local/dev-only only, must not be visible in production navigation, must not be treated as a Phase 1I user-facing screen, must not bypass RBAC guards, and must be excluded or clearly disabled in production builds.
4. **Layout shell** — Topbar/Sidebar(collapsible)/Main/DetailPanel per §1.3; ≥768px min width.
5. **Routing + role guards** — `/workspace/*`, `/admin/*`, default-landing redirects and forbidden-route handling per §1.5; any role switcher is local/dev-only only, must not be visible in production navigation, must not be treated as a Phase 1I user-facing screen, must not bypass RBAC guards, and must be excluded or clearly disabled in production builds; 403/forbidden screen.
6. **Static scaffold: Admin System Health** (`/admin/health`) — static table per §3.7.
7. **Static scaffold: Permissions & Roles — Role Matrix tab** (`/admin/permissions`) — read-only from `rbac_matrix.md`.
8. **Static scaffold: Source Mapping read-only view** (`/admin/source-mapping`) — read-only render of `project_source_mapping.json` shape.
9. **Static scaffold: Query Composer shell** (`/workspace/new`) — form layout per §2.1, no data, no submit handler.
10. **CI integration + closeout** — add `frontend/` `npm ci` + `npm run lint` + `npm run build` steps to `.github/workflows/ci.yml` (or a parallel job); update `docs/admin/FEATURE_MATRIX.md`, `docs/execution/CURRENT_PROJECT_STATE.md`, `docs/execution/IMPLEMENTATION_PHASES.md`, `docs/admin/CONTROL_PLANE_LOCK.md`, `README.md`, `docs/ai/*`, and `docs/ai/agent-state.json` for the Phase 1I closeout; create `docs/execution/PHASE_1I_REPORT.md`. (Note: `scripts/check_doc_drift.py` `EXPECTED_NEXT_PHASE`/`EXPECTED_NEXT_PHASE_TITLE` must move to `2A` / its title at closeout.)

## I. Validation and CI plan

Per `IMPLEMENTATION_PHASES.md` Phase 1I validation gate before 2A, plus the repo's existing gates:

- `npm run build` exits 0 (in `frontend/`).
- `npm run lint` exits 0.
- All 9 roles route to their correct default landing screens (manual + ideally a routing unit test).
- All 13 status pills render with correct colors + icons (visual check + snapshot test).
- `ConfirmDialog` requires a typed confirmation string for destructive actions.
- No `fetch`/`axios`/network calls anywhere in `frontend/` (grep-able check; can be a CI assertion).
- Existing Python gates remain green and untouched: `make smoke`, `make test`, `make eval`, `ruff check .`, `python3 -m compileall apps scripts`, `scripts/check_doc_drift.py`, `scripts/check_ai_context.py` (extend `agent-state.json.required_validation` with the frontend commands at closeout).
- `.github/workflows/ci.yml`: add a `frontend` job (or steps) running `npm ci`, `npm run lint`, `npm run build` on Node LTS.
- Closeout: `scripts/check_doc_drift.py` must still pass after the doc updates (it asserts the 5 truth docs name the then-current safe-next phase — 1I→2A — and the 40-key env baseline).

## J. Risks and blockers

- **CI verification required for `4c5b144`** — Authenticated GitHub Actions status for commit `4c5b144` must be verified before Phase 1I implementation approval. If `gh`/token/API access is unavailable in this environment, CI status must be treated as externally verified or pending, not inferred. This does not block Phase 1I planning, but Phase 1I implementation approval must not proceed without CI verification.
- **No Node toolchain in repo yet** — Phase 1I introduces the first non-Python build; CI will need Node + a frontend job. Mitigated by Slices 1 and 10.
- **`UI_CONTRACT_v1.md` is large and detailed (1,373 lines, 13 screens)** — risk of scope creep into Phase 2A screens. Mitigation: Phase 1I builds only the 4 static shells in §10's exception list; treat the other 9 screens as Phase 2A/2B; "minimal surface" principle.
- **Routing/RBAC guards are UX-only** — must not be mistaken for security. Mitigation: server 403 unchanged; document the guard as cosmetic; no auth implementation in 1I.
- **Source Mapping read-only view vs. editor** — `UI_CONTRACT_v1.md` §10 puts the editor in Phase 2B; Phase 1I ships read-only only.
- **Design-token fidelity** — exact hex/typography values must match §1.4; drift propagates to every later screen. Mitigation: tokens centralized in one file; a token-vs-spec check is cheap to add.
- No blockers requiring a repo fix were found: every backend phase Phase 1I screens depend on (1A System Health, 1B RBAC/Query Composer data, 1C connectors, 1D evidence, 1E reports, 1F persistence/cost, 1G approval) is complete; the locked UI contract exists and is detailed; `project_source_mapping.json` and `rbac_matrix.md` exist for the static scaffolds.

## K. Final verdict

**PHASE_1I_PLAN_READY_FOR_USER_APPROVAL**

Phase 1I scope, non-scope, screens/routes, design-system requirements, API/RBAC posture, slices, and validation are fully derivable from the live repo; all prerequisite phases (1A–1H + 1D-fixup) are complete; production remains `NOT_LIVE`; Phase 1I is not started and stays gated behind explicit user approval. No repository fix is required before Phase 1I planning; authenticated GitHub Actions status for commit `4c5b144` must still be verified before Phase 1I implementation approval.

> This document is a plan, not an authorization. Do not start Phase 1I implementation without explicit user approval in the working session.
