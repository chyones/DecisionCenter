# Phase 2D Slice 2 — Production Auth (Slice Report)

> **Phase / Slice:** 2D Slice 2 — Production Auth
> **Slice status (proposed on commit):** `PHASE_2D_SLICE_2_COMPLETE_NOT_LIVE`
> **Repo status (unchanged):** `PHASE_2C_COMPLETE_NOT_LIVE`
> **Committed:** `4693d6c` (feature) + `e1bd284` (governance) — pushed to `main`
> **CI:** run `26384373013` on `e1bd284` (smoke + frontend)
> **Production:** `NOT_LIVE` (no deploy, no go-live in this slice)
> **Plan:** `/root/.claude/plans/continue-to-phase-2d-slice-2-after-ci-gr-playful-sutton.md`

---

## Summary

Slice 2 closes go-live blocker **G15 — production Entra/MSAL frontend auth
missing**. The React app now requires Microsoft sign-in in production builds,
sends `Authorization: Bearer <token>` on API calls, and resolves the caller's
canonical role from `GET /me`. Local dev and CI keep the RoleSwitcher +
`X-User-Role` bypass unchanged, so the Playwright suite is unaffected.

Decisions (from the approved plan): **Model A — Entra App Roles (direct)** for
role mapping (no DB lookup in the auth path; the Phase 2B `entra_group_mappings`
table stays admin-managed metadata), and a small authenticated **`GET /me`**
endpoint as the frontend's authoritative role source.

The backend already validated Entra Bearer tokens (`_extract_claims` +
`EntraJWTValidator`), so backend work was limited to `GET /me` plus a hardening
guard that rejects dev bypass headers in production.

---

## Changes

### Backend (`apps/edr/`)

| File | Change |
|---|---|
| `app.py` | Added `MeResponse` model and `GET /me` (authenticated; returns `{user_id_hash, role}` via `hash_user_id` + `_validated_role`; metadata-only, all roles incl. admin — no business data, preserves C-1/C-6). Added a guard in `_extract_claims`: when `APP_ENV == "production"`, any `X-User-Role`/`X-User-Id` header → `400`. |
| `tests/integration/test_me_endpoint.py` | New: 20 tests — `/me` per canonical role, admin metadata-only, 401 unauth, 403 invalid/missing role, empty-hash; and `_extract_claims` production rejects dev headers (even alongside a Bearer), validates a Bearer, 500 when prod+Entra unconfigured, and local bypass unchanged. |

The `EntraJWTValidator` is unchanged (Model A: the token `roles[0]` already maps
to a canonical `Role`).

### Frontend (`frontend/`)

| File | Change |
|---|---|
| `package.json` / `package-lock.json` | Added `@azure/msal-browser@^5.11.0`, `@azure/msal-react@^5.4.2` (React 19 compatible). |
| `src/auth/msalConfig.ts` (new) | MSAL config from `VITE_ENTRA_*`; `pca` singleton (only when client id present); `productionAuthEnabled = import.meta.env.PROD && pca != null`; `initAuth`, `acquireAccessToken` (silent → redirect fallback), `signOut`. |
| `src/auth/LoginGate.tsx` (new) | Production-only sign-in screen; after auth, fetches `GET /me` and sets RoleContext before rendering children. |
| `src/App.tsx` | Production branch wraps the tree in `<MsalProvider>` + `<LoginGate>` (no RoleSwitcher); dev branch unchanged. |
| `src/main.tsx` | Awaits `initAuth()` (no-op in dev) before render. |
| `src/api/useApi.ts` | Production attaches `Authorization: Bearer <token>` from MSAL; dev keeps `X-User-Role`/`X-User-Id`. |
| `src/layout/Topbar.tsx` | Production-only sign-out button. |
| `src/vite-env.d.ts` | Declared `VITE_*` env types. |
| `.env.example` (new) | Documents `VITE_API_BASE_URL`, `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_API_SCOPE`. |

**Design invariant:** all MSAL behavior is gated behind `productionAuthEnabled`.
The Vite dev server (`import.meta.env.DEV`) renders exactly as before, so the
existing e2e `setRole()` (which asserts the RoleSwitcher is visible) still
locks the dev path.

---

## Acceptance Criteria

| Criterion | Status | Evidence |
|---|---|---|
| Real Entra login works | Operator-verified (not CI) | Requires a live Entra app registration + assigned app roles; verified in a production-like env (feeds Slice 6 UAT). |
| Protected routes reject unauthenticated users | ✅ (backend) | `_extract_claims` requires a valid Bearer in production (401); `test_me_endpoint.py` covers 401/403; frontend `LoginGate` blocks the UI until signed in. |
| Role claims map to the 9 canonical roles | ✅ | Model A: `roles[0]` → `Role` enum; `GET /me` returns the canonical role; per-role test parametrized over all 9 roles. |
| Production does not rely on dev bypass headers | ✅ | `APP_ENV=production` → `X-User-Role`/`X-User-Id` rejected (400); frontend sends Bearer, not dev headers, in production. |
| Admin remains metadata-only | ✅ | `GET /me` returns only `{user_id_hash, role}`; admin still 403 on business endpoints (unchanged). |

---

## Local Validation Evidence

Run on the host venv, mirroring CI (`gh` CLI is unavailable here).

| Check | Result |
|---|---|
| `ruff check apps scripts` | clean (exit 0) |
| `python -m compileall apps scripts` | clean (exit 0) |
| smoke (`apps/edr/tests/smoke`) | 2 passed |
| integration (`apps/edr/tests/integration`) | **479 passed** (incl. 20 new), 0 failed |
| `test_me_endpoint.py` | 20 passed |
| evaluation suite (`--min-pass-rate 0.95 --min-precision 0.90`) | passed (exit 0) |
| frontend `npm run lint` | clean |
| frontend `npm run build` | success — JS 90.59 kB gzip / 120 budget, CSS 5.92 kB / 15 budget |
| frontend `npm run check-bundle` | pass |
| frontend `npm run test:ui` (Playwright) | **54 passed** — Chromium, Firefox, WebKit |
| `scripts/check_doc_drift.py` | clean |
| `scripts/check_ai_context.py` | clean |
| `git diff --check` | clean |
| CI on pushed `e1bd284` | run `26384373013` (smoke + frontend) |

---

## Out of Scope / Deferred

- Real Entra tenant login + app-role assignment + end-to-end token acceptance
  (audience == `ENTRA_CLIENT_ID`) — operator-verified in a production-like env,
  with sanitized evidence (feeds Slice 6 UAT).
- Group→role mapping (Model B), `pip-audit` hard gate (G11), Langfuse live (G9).

---

## Governance (Slice 1 precedent)

Per the approved plan, this slice follows the Slice 1 precedent: the
`agent-state.json.status` stays `PHASE_2C_COMPLETE_NOT_LIVE` and `latest_report`
stays `PHASE_2C_REPORT.md`; slice progress is tracked in a separate
`phase_2d_slice_2_status` field. No edits to `check_ai_context.py`
`ALLOWED_STATUSES` or `check_doc_drift.py` constants are required (verified:
both checks remain clean). The governance anchor refresh — `current_commit`,
`latest_verified_ci`, `AGENT_HANDOFF.md`, `SHARED_CONTEXT.md`, and the
`PHASE_2D_EXECUTION_PLAN.md` Slice 2 status — is committed alongside the code.
The five frozen audit truth docs (CONTROL_PLANE_LOCK, CURRENT_PROJECT_STATE,
IMPLEMENTATION_PHASES, FEATURE_MATRIX, README) are intentionally left at the
2026-05-24 audit snapshot until a re-audit/closeout, matching the Slice 1
precedent.

Committed as `4693d6c` (feature) + `e1bd284` (governance) and pushed to `main`. Production remains `NOT_LIVE`.
