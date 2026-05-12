# Phase 2A Planning Report — User Chat Workspace Implementation

> **Status:** Planning only. Phase 2A is **not** started and **requires explicit user approval** before any implementation.
> **Date:** 2026-05-12
> **Prepared against:** HEAD `8378079` (Phase 1I closeout); Phases 0, 1A–1I + 1D-fixup complete; production `NOT_LIVE`.
> **Sources of truth:** `docs/design/UI_CONTRACT_v1.md` §2, `docs/execution/IMPLEMENTATION_PHASES.md` §Phase 2A, `docs/admin/CONTROL_PLANE_LOCK.md`, `apps/edr/app.py`, `frontend/src/`.

---

## A. Verified starting state

- **Phase 1I complete.** `docs/ai/agent-state.json` → `status: PHASE_1I_COMPLETE_NOT_LIVE`, `last_completed_phase: Phase 1I`, `next_allowed_phase: Phase 2A`; CI Run 44 green; `frontend/` lint and build gated in CI.
- **Frontend foundation live.** Vite + React + TS + Tailwind in `frontend/`; tokens, layout shell, 6 reusable components, 9-role hash routing, 4 static scaffolds.
- **Backend phases complete.** Phases 1A–1H + 1D-fixup are closed and locked. The execution pipeline runs end-to-end.
- **Production NOT_LIVE.** `agent-state.json.production_status: NOT_LIVE`, `must_not_deploy: true`.
- **Phase 2A not started.** No live backend integration in frontend. No API client exists.
- **Phase 2A gate visible.** Restated in `AGENTS.md`, `docs/ai/SHARED_CONTEXT.md`, `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/execution/IMPLEMENTATION_PHASES.md`.

---

## B. Phase 2A objective

Implement all **six user-facing workspace screens** with live backend integration:

1. **Query Composer** (`/workspace/new`) — live project dropdown, submit handler.
2. **Processing View** (`/workspace/report/{request_id}/processing`) — status polling / streaming.
3. **Report View** (`/workspace/report/{request_id}`) — content rendering with citations.
4. **Evidence Panel** (slide-in from Report View) — evidence entries with filtering.
5. **Export Panel** (slide-in from Report View) — format downloads, RBAC-gated artifacts.
6. **My Reports List** (`/workspace/reports`) — role-scoped listing with filters.

Backend dependency: Phases 1F (persistence) and 1G (review gate) are complete. The
frontend depends on HTTP endpoints that exist or must be added to `apps/edr/app.py`.

---

## C. Allowed scope (Phase 2A — IN scope)

Per `IMPLEMENTATION_PHASES.md` §Phase 2A and `UI_CONTRACT_v1.md` §2:

### C.1 Query Composer (`/workspace/new`)

- Populate Project dropdown from `POST /reports/staging` pre-flight or JWT claims
  (`allowed_projects`).
- Contract No. auto-suggest from `project_source_mapping.json` (baked or fetched).
- Output format toggles: MD (default), DOCX, PDF, XLSX, PPTX — all enabled.
- Submit button disabled until Project + Query are both set.
- All screen states: `idle`, `draft`, `submitting`, `queued`, `error`, `no_projects`.
- POST to `/reports/staging` on submit; handle 202 → redirect to Processing View.
- Upload zone: functional file picker, validation, preview list (no backend upload
  endpoint may exist; if not, upload stays disabled with a placeholder).

### C.2 Processing View (`/workspace/report/{request_id}/processing`)

- Poll backend for report status (endpoint TBD — see §G).
- Map 18 internal nodes to user-facing labels per `UI_CONTRACT_v1.md` §2.2.
- Progress bar and elapsed timer.
- Cancel action with `ConfirmDialog` → `DELETE` request (endpoint TBD).
- Handle all screen states: `running`, `self_correct_retry`, `quality_gate_passed`,
  `quality_gate_needs_review`, `quality_gate_failed`, `awaiting_reviewer`,
  `timed_out`, `rbac_denied`, `cancelled`.

### C.3 Report View (`/workspace/report/{request_id}`)

- Fetch report JSON and metadata (endpoint TBD — see §G).
- Render report content with superscript citations linking to Evidence Panel.
- Financial Position conditional rendering per role (`can_access_odoo_budget`).
- Conflicts Detected and Missing Data sections always rendered if non-empty.
- Report state handling: `staging`, `needs_review`, `approved`, `rejected`, `final`.
- `needs_review` requester view: QG flags only, no report content.
- `needs_review` reviewer view: watermarked draft + Approve/Reject/Request revision.

### C.4 Evidence Panel (slide-in)

- Render evidence entries from report JSON.
- Source label, source type, confidence score, truncated hash (last 8 hex chars).
- Email excerpts read-only; document excerpts copyable.
- Filter by source type and confidence.

### C.5 Export Panel (slide-in)

- Render only when report state is `approved` or `final`.
- Block all downloads when `quality_gate = "failed"`.
- RBAC-gated `evidence-pack.json` and `audit-log.json` downloads.
- Report format downloads: MD, DOCX, PDF, XLSX, PPTX via existing
  `GET /reports/staging/{request_id}/download/{fmt}` and
  `GET /reports/final/{request_id}/download/{fmt}`.

### C.6 My Reports List (`/workspace/reports`)

- Group by state: In progress, Awaiting review, Approved / Final.
- Role-scoped: own requests only (except `auditor`, who sees project-scoped reports).
- Filters by project, state, date range.
- Click row → Report View.

### C.7 API client foundation

- Minimal, typed API client in `frontend/src/api/` (or equivalent).
- Base URL from `VITE_API_BASE_URL` or similar env var; fallback to `/api`.
- JSON-only; no form-data unless required for upload.
- Error handling: network errors → toast; 4xx/5xx → inline or toast per contract.

### C.8 Auth integration

- Microsoft Entra SSO per `UI_CONTRACT_v1.md` §8.1.
- JWT stored securely (httpOnly cookie preferred; if not possible, memory-only
  with refresh logic).
- Token attached to all API requests via `Authorization: Bearer` header.
- 401/403 from backend → redirect to login or Forbidden screen.

---

## D. Non-scope items (Phase 2A — explicitly OUT)

- **No Admin Visual Control Plane screens.** Dashboard, Approval Queue, Audit Log,
  Connectors, Cost Monitor, editable Source Mapping, editable Permissions — all Phase 2B.
- **No report template editor.**
- **No mobile-native layout or responsive redesign.** Minimum width stays 768px.
- **No real-time collaboration or WebSocket beyond status polling.**
- **No notification email system.**
- **No Arabic bidirectional shaping in PDF export.** Deferred to later phase.
- **No promptfoo CLI integration.**
- **No permanent load-test p95 thresholds.**
- **No `pip-audit` promotion to hard gate.**
- **No deployment.** Production stays `NOT_LIVE`.

---

## E. UX contract dependencies

Single source of truth: `docs/design/UI_CONTRACT_v1.md` §2 (User Chat Workspace).

| Screen | Contract section | Critical rules |
|---|---|---|
| Query Composer | §2.1 | Submit disabled until Project + Query set; 6 screen states; noProjects message |
| Processing View | §2.2 | 18 node labels never expose internal identifiers; cancel confirms; audit on cancel |
| Report View | §2.3 | Superscript citations anchor to Evidence Panel; Financial Position role-gated; needs_review requester sees flags only |
| Evidence Panel | §2.3 (anatomy) | Raw `evidence_id` never shown; email excerpts read-only; document excerpts copyable |
| Export Panel | §2.4 | Only `approved`/`final`; block when QG failed; RBAC-gated artifacts |
| My Reports List | §2.6 | Own requests only; auditor project-scoped; no full-text search |

Design-token discipline from Phase 1I continues unchanged:
- All spacing on 4px grid.
- No gradients, no decorative artwork.
- Focus rings using `focus-ring` token.
- `processing` spin is the only continuous animation.

---

## F. Backend/API dependencies

### F.1 Existing endpoints (verified in `apps/edr/app.py`)

| Method | Path | Purpose | Phase 2A usage |
|---|---|---|---|
| POST | `/reports/staging` | Create report | Query Composer submit |
| POST | `/reports/staging/{id}/approve` | Approve report | Report View (reviewer) |
| POST | `/reports/staging/{id}/reject` | Reject report | Report View (reviewer) |
| POST | `/reports/staging/{id}/request-revision` | Request revision | Report View (reviewer) |
| GET | `/reports/staging/{id}/download/{fmt}` | Download staging artifact | Export Panel |
| GET | `/reports/final/{id}/download/{fmt}` | Download final artifact | Export Panel |
| GET | `/healthz` | Service health | Optional (Admin only in 2B) |

### F.2 Missing endpoints (required for Phase 2A)

| Need | Suggested endpoint | Used by |
|---|---|---|
| List user's reports | `GET /reports` | My Reports List |
| Get report metadata/state | `GET /reports/staging/{id}` or `GET /reports/{id}` | Report View, Processing View |
| Poll processing status | `GET /reports/staging/{id}/status` or SSE | Processing View |
| Cancel in-flight report | `DELETE /reports/staging/{id}` | Processing View cancel |
| Get evidence pack | `GET /reports/staging/{id}/evidence-pack` | Evidence Panel |
| Upload files | `POST /upload` | Query Composer upload zone |

**Decision:** These endpoints are not present in `apps/edr/app.py` at HEAD `8378079`.
Phase 2A implementation must either:
1. Add the minimal required endpoints to `apps/edr/app.py` (backend scope creep, but
   necessary), OR
2. Stub the frontend with realistic error states until backend endpoints are added
   in a separate backend phase.

The Phase 2A plan treats backend endpoint additions as **in-scope only if they are
minimal read/query endpoints** that do not modify the core graph logic. Write endpoints
(`POST /reports/staging` and review actions) already exist.

### F.3 Data sources

- **Project list:** `DecisionState.allowed_projects` from Node 01 auth, or
  `docs/config/project_source_mapping.json`.
- **Report JSON:** MinIO staging path (`report.json`, `evidence-pack.json`, etc.).
- **Audit/review state:** PostgreSQL `audit_log` and `review_decisions` tables.
- **Cost data:** PostgreSQL audit log (daily/monthly aggregates).

---

## G. RBAC and security constraints

Phase 2A RBAC behavior is **server-enforced**; the frontend UX guards from Phase 1I
remain as cosmetic fallbacks only.

### G.1 Role boundaries

| Role | Query Composer | Processing View | Report View | Evidence Panel | Export Panel | My Reports List |
|---|---|---|---|---|---|---|
| `executive` | ✅ | ✅ | ✅ (financial if permitted) | ✅ | ✅ | Own only |
| `project_manager` | ✅ | ✅ | ✅ (financial if permitted) | ✅ | ✅ | Own only |
| `finance` | ✅ | ✅ | ✅ (financial always) | ✅ | ✅ | Own only |
| `commercial` | ✅ | ✅ | ✅ (financial if permitted) | ✅ | ✅ | Own only |
| `document_control` | ✅ | ✅ | ✅ (no financial by default) | ✅ | ✅ | Own only |
| `procurement` | ✅ | ✅ | ✅ (PO-related financial) | ✅ | ✅ | Own only |
| `legal` | ✅ | ✅ | ✅ (financial if permitted) | ✅ | ✅ | Own only |
| `auditor` | ❌ redirected | ❌ | Read-only, project-scoped | Read-only | ❌ | Project-scoped read-only |
| `admin` | ❌ redirected | ❌ | ❌ | ❌ | ❌ | ❌ |

### G.2 Security rules

- Admin never sees report content, evidence, query text, or business artifacts.
- Financial section is absent with explicit message for unauthorized roles, not hidden.
- `needs_review` requester sees QG flags only; reviewer sees watermarked draft.
- Quality gate `failed` blocks Export Panel and all downloads.
- Evidence pack and audit log downloads are RBAC-gated.
- JWT must be validated on every request; 401/403 handled gracefully.

---

## H. Data/network behavior

### H.1 Network layer requirements

- **API client:** Typed wrapper around `fetch` (native browser API) or `axios`. If
  `axios` is chosen, it must be pinned and its use limited to the API client module.
- **Base URL:** Configurable at build time (`VITE_API_BASE_URL`); defaults to `/api`.
- **Auth header:** `Authorization: Bearer <token>` on every request.
- **Content-Type:** `application/json` for all requests except file upload
  (`multipart/form-data`).
- **Error handling:**
  - Network error → Toast with retry option.
  - 401 → Redirect to login.
  - 403 → Forbidden screen.
  - 404 → Report not found message.
  - 422 → Inline validation errors.
  - 5xx → Toast with "Please try again later."

### H.2 Polling strategy (Processing View)

- Interval: `2000ms` initial, backoff to `5000ms` after 30s.
- Stop polling when terminal state reached (`final`, `failed`, `cancelled`, `rejected`).
- Cleanup interval on unmount.
- Optional: SSE or WebSocket if backend supports it; polling is the fallback.

### H.3 Caching strategy

- Report list: cache for `30s`, invalidate on mutation (submit, approve, reject).
- Report detail: cache for `60s`, invalidate on status change.
- Evidence pack: cache for `5min`, rarely changes.
- No global state store (Redux/Zustand) unless complexity demands it; React Context
  + `useState`/`useReducer` preferred for Phase 2A.

---

## I. Implementation slices (proposed)

Each slice = small, auditable commit. Run the Phase 2A validation gate at the end.

1. **API client foundation + auth wiring**
   - Create `frontend/src/api/client.ts` with typed `fetch` wrapper.
   - Add env-based base URL.
   - Add request/response interceptors for auth header and error handling.
   - Add minimal API types matching backend Pydantic schemas.
   - No UI changes yet.

2. **Query Composer — live project dropdown + submit**
   - Replace disabled project selector with live dropdown.
   - Wire submit to `POST /reports/staging`.
   - Handle all 6 screen states.
   - Redirect to Processing View on 202.
   - Keep filters and upload zone disabled if backend support is missing.

3. **My Reports List — read-only listing**
   - Create `ReportsListScreen` at `/workspace/reports`.
   - Fetch from `GET /reports` (or stub with empty state if endpoint missing).
   - Group by state, role-scoped.
   - Click row → Report View.

4. **Processing View — status polling**
   - Create `ProcessingScreen` at `/workspace/report/{request_id}/processing`.
   - Poll backend for status.
   - Render node labels, progress bar, elapsed timer.
   - Cancel action with ConfirmDialog.
   - Handle all 9 screen states.

5. **Report View + Evidence Panel — content rendering**
   - Create `ReportViewScreen` at `/workspace/report/{request_id}`.
   - Fetch report JSON.
   - Render Markdown content with citation links.
   - Conditional Financial Position.
   - Conflicts and Missing Data sections.
   - Evidence Panel slide-in with filtering.
   - needs_review requester vs reviewer views.

6. **Export Panel — downloads**
   - Add Export slide-in to Report View.
   - RBAC-gated artifact downloads.
   - Block when QG failed or state not approved/final.
   - Wire to existing download endpoints.

7. **Upload Zone — functional file handling**
   - Enable drag-and-drop, file picker, validation.
   - Preview list with remove action.
   - Wire to `POST /upload` if endpoint exists; otherwise keep disabled.

8. **Routing integration + role guards update**
   - Add new routes to Router.
   - Update guards for new screens.
   - Ensure default landings are correct.

9. **Error handling + polish**
   - Toast notifications for all API errors.
   - Loading skeletons.
   - Empty states.
   - Final validation gate.

---

## J. Validation plan

Per `IMPLEMENTATION_PHASES.md` §Phase 2A validation gate before 2B:

- **End-to-end test:** submit query → processing → staging → approve → final → download MD.
- **U-01 through U-16 acceptance criteria** from `UI_CONTRACT_v1.md` §9.1 pass in manual QA.
- **`quality_gate = "failed"` blocks Export Panel and all downloads.**
- **`needs_review` requester sees flags only; reviewer sees watermarked draft.**
- **Financial section hidden with explicit message for unauthorized roles.**
- **No console errors.**
- **No unhandled promise rejections.**

Plus existing gates:
- `npm run build` exits 0.
- `npm run lint` exits 0.
- All Python gates remain green: `make smoke`, `make test`, `make eval`, `ruff check .`,
  `python3 -m compileall apps scripts`, `check_doc_drift.py`, `check_ai_context.py`.

---

## K. CI and approval gates

- Frontend lint and build already gated in CI (added in Phase 1I Slice 10).
- No new CI steps required for Phase 2A unless backend endpoints are added.
- If backend endpoints are added, backend tests must cover them.
- Closeout: update `docs/admin/FEATURE_MATRIX.md`, `docs/execution/CURRENT_PROJECT_STATE.md`,
  `docs/execution/IMPLEMENTATION_PHASES.md`, `docs/admin/CONTROL_PLANE_LOCK.md`,
  `README.md`, `docs/ai/*`, and `docs/ai/agent-state.json` for Phase 2A closeout;
  create `docs/execution/PHASE_2A_REPORT.md`.

---

## L. Risks and blockers

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Missing backend endpoints** (list reports, get report, status poll, cancel) | High | Blocks My Reports List, Processing View, Report View | Add minimal read/query endpoints to `apps/edr/app.py` as part of Phase 2A, or stub frontend with realistic error states |
| **No auth/token implementation in frontend** | High | Blocks all API calls | Implement Entra SSO or dev-only JWT bypass (with production gate) in Slice 1 |
| **SSE/WebSocket not supported by backend** | Medium | Forces polling for Processing View | Polling is the fallback; document the limitation |
| **Report JSON schema mismatch between backend and frontend** | Medium | Rendering errors | Share Pydantic schemas as TypeScript types; validate at runtime |
| **Upload endpoint missing** | Medium | Upload zone stays disabled | Defer to later slice; keep placeholder |
| **Scope creep into Phase 2B Admin screens** | Medium | Delayed delivery | Strict route boundary: `/workspace/*` only in 2A |

No blockers requiring a repo fix were found: every backend phase Phase 2A depends on
(1F persistence, 1G review gate) is complete; the locked UI contract exists and is
detailed; the frontend foundation is ready.

---

## M. Final verdict

**PHASE_2A_PLAN_READY_FOR_USER_APPROVAL**

Phase 2A scope, non-scope, screen contracts, backend dependencies, RBAC posture,
implementation slices, and validation are fully derivable from the live repo. All
prerequisite phases (0, 1A–1I + 1D-fixup) are complete; production remains `NOT_LIVE`;
Phase 2A is not started and stays gated behind explicit user approval. The primary
risk is missing backend read/query endpoints for reports, which must be addressed
either by minimal backend additions or by frontend stubs.

> This document is a plan, not an authorization. Do not start Phase 2A implementation
> without explicit user approval in the working session.
