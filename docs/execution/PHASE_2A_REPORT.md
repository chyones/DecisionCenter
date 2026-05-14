# Phase 2A Report — User Chat Workspace Implementation

> **Date:** 2026-05-14
> **Closeout anchor commit:** `e37b0c12c2ecfa86c2f0727338f238d988f923ee`
> **Status:** `PHASE_2A_SLICE_9_COMPLETE_NOT_LIVE`
> **Previous phase:** Phase 1I (Frontend Foundation & Static Admin Scaffolds)
> **Phase 2A implementation slices:** 9 of 9 authored
> **Phase 2A validation gate (E2E + U-01..U-16 manual QA):** PARTIAL — the
> deterministic local E2E path passed after the E2E unblock slice; U-01..U-16
> manual QA remains pending.
> **Next safe phase:** Phase 2A manual QA + closeout; Phase 2B may not start
> until that gate closes. Both require explicit user approval.

---

## Summary

Phase 2A authored the nine implementation slices defined in
`docs/execution/PHASE_2A_PLAN.md` §I between commits `840e954` (Slice 1) and
`e37b0c1` (Slice 9), all landing on `main`. Each slice was verified by a green
GitHub Actions CI run on push. Phase 2A is **not** marked fully complete. The
deterministic local E2E path (submit → processing → quality_gate passed →
approve → final → download MD) now passes through the existing workflow,
quality gate, approval, publish, and download path without real external
credentials. U-01..U-16 manual QA against `docs/design/UI_CONTRACT_v1.md` §9.1
remains pending under explicit approval.

This report also reconciles repository truth with the live `main` branch. The
prior governance anchor at `35f561d` had become six commits stale because
Slices 6–9 landed without a corresponding update to `docs/ai/agent-state.json`
and the truth docs. No application code, configuration, schema, or contract
was changed by this reconciliation. The two governance detectors were extended
to recognize the post-Slice-5 states and to flag anchor staleness in future.

---

## Phase 2A implementation slices

| Slice | Scope | Commit | CI run |
|---|---|---|---|
| 1 | API client foundation and auth wiring (`frontend/src/api/*`) | `840e954` | success (`25728391860`) |
| 2 | Query Composer submit wired to `POST /reports/staging` | `38f7b58` | success (`25729483203`) |
| 3 | Reports List read-only shell (no `GET /reports`) | `89a4e49` | success (`25730625701` series) |
| 4 | Processing View status shell (no status/cancel endpoint) | `5674581` | success (`25730625701`) |
| 5 | Report View + Evidence Panel shell (no `GET /reports/{id}`) | `35f561d` | success (`25788830982`) |
| 6 | Export Panel (wired to existing `GET /reports/{staging,final}/{id}/download/{fmt}`) | `96ec4b9` | success (`25795083507`) |
| 7 | Upload Zone (client-side validation; `POST /upload` absent, submission disabled) | `52b8a02` | success (`25796533185`) |
| 8 | Routing integration + role guards update | `a5aedfc` | success (`25798446018`) |
| 9 | Error handling polish (`ToastProvider`, retry surfaces, network-error paths) | `e37b0c1` | success (`25799899473`) |

All slices passed CI. Run URLs:
`https://github.com/chyones/DecisionCenter/actions/runs/<run_id>`.

---

## Live backend integration vs unavailable shells (historical e37b0c1 snapshot)

At the original Slice 9 closeout anchor, the Phase 2A workspace screens
distinguished between routes wired to live backend endpoints and routes that
render contract-correct "unavailable" shells because the required backend
read/status endpoints were not present in `apps/edr/app.py` at `e37b0c1`.
This was documented as a scope decision in
`docs/execution/PHASE_2A_PLAN.md` §F.2.

| Screen | Backend integration |
|---|---|
| Query Composer (`/workspace/new`) | Live: `POST /reports/staging`. Project dropdown is fixture-backed because no project-list endpoint exists. |
| Reports List (`/workspace/reports`) | Unavailable shell: `GET /reports` is absent. |
| Processing View (`/workspace/report/{request_id}/processing`) | Unavailable shell: `GET /reports/{id}/status` and `DELETE /reports/{id}` are absent. |
| Report View (`/workspace/report/{request_id}`) | Unavailable shell: `GET /reports/{id}` is absent. |
| Evidence Panel | Driven by Report View; renders contract-correct empty state. |
| Export Panel | Live for report-format downloads via existing `GET /reports/{staging,final}/{id}/download/{fmt}`. `evidence-pack.json` and `audit-log.json` rows are disabled because no artifact-fetch endpoint exists. |
| Upload Zone | Client-side validation and preview list operate; submission is disabled because `POST /upload` is absent. |

Backend endpoints required to light up the remaining shells are listed in
`docs/execution/PHASE_2A_PLAN.md` §F.2. Adding them is out of scope for this
closeout.

---

## Validation evidence (HEAD `e37b0c1` reconciled)

| Gate | Result |
|---|---|
| `ruff check apps scripts` | clean |
| `python3 -m compileall apps scripts` | clean |
| `python3 scripts/check_doc_drift.py` | clean |
| `python3 scripts/check_ai_context.py` | clean |
| `python3 scripts/agent_preflight.py` | clean |
| Smoke (`pytest -q apps/edr/tests/smoke`) | 2 passed |
| Integration (`pytest -q apps/edr/tests/integration`) | 141 passed |
| Evaluation (`python3 -m apps.edr.evaluation.run --suite goldenset --min-pass-rate 0.95 --min-precision 0.90`) | 65/65 passed, thresholds met |
| `npm run lint` (`frontend/`) | clean |
| `npm run build` (`frontend/`) | success (273.88 kB JS / 78.87 kB gzip; 26.85 kB CSS) |
| HEAD CI (`e37b0c1`, run `25799899473`) | completed / success |

The closeout commit itself runs the same gates in CI on push; see the run
linked from `docs/ai/agent-state.json.latest_verified_ci`.

---

## What was explicitly NOT done

- U-01..U-16 manual QA per `docs/design/UI_CONTRACT_v1.md` §9.1 remains
  pending. The deterministic local E2E path was exercised later by
  `make phase2a-e2e` and passed, but this report does not close Phase 2A.
- Backend endpoints required by remaining workspace shells were not added by
  the original `e37b0c1` closeout; they were added later in the controlled G12
  backend additions recorded below.
- No production deployment; production stays `NOT_LIVE`.
- No code, configuration, schema, contract, or workflow JSON was changed by
  the closeout reconciliation.
- No promotion of `pip-audit` to a hard CI gate (tracked as gap G11).
- No bidirectional Arabic shaping in PDF export (tracked as gap G10b).
- No live Langfuse dashboard validation (tracked as gap G9).
- No frontend test runner; UI acceptance automation (`make test:ui`) remains
  Phase 2C scope.

---

## Governance detector updates

The two detectors that were structurally incapable of catching the six-commit
staleness uncovered during the audit were extended in this closeout:

- `scripts/check_ai_context.py` — `ALLOWED_STATUSES` extended to include
  `PHASE_2A_SLICE_6_COMPLETE_NOT_LIVE`,
  `PHASE_2A_SLICE_7_COMPLETE_NOT_LIVE`,
  `PHASE_2A_SLICE_8_COMPLETE_NOT_LIVE`,
  `PHASE_2A_SLICE_9_COMPLETE_NOT_LIVE`, and `PHASE_2A_COMPLETE_NOT_LIVE`. The
  status now accepted at this closeout is `PHASE_2A_SLICE_9_COMPLETE_NOT_LIVE`.
- `scripts/check_doc_drift.py` — added an anchor-currency invariant: the
  `current_commit` in `docs/ai/agent-state.json` must be HEAD itself or no
  more than three commits behind HEAD on the current branch. Drift beyond
  that fails the detector.

Both invariants are exercised by the existing CI step that already runs the
detectors on every push.

---

## Doc updates made at closeout

- `docs/execution/PHASE_2A_REPORT.md` — this report.
- `docs/ai/agent-state.json` — `current_commit` advanced to `e37b0c1`,
  `status` set to `PHASE_2A_SLICE_9_COMPLETE_NOT_LIVE`,
  `completed_phase_2a_slices` extended to Slices 1–9,
  `latest_report` set to this report,
  `latest_verified_ci` set to HEAD CI run `25799899473`,
  approval flags cleaned up to reflect the validation gate as the new gated
  next step.
- `docs/ai/SHARED_CONTEXT.md` — current state, no-go rules, and next-work
  language updated.
- `docs/ai/AGENT_HANDOFF.md` — handoff updated to reflect Slices 1–9 complete
  and the validation gate deferred.
- `README.md` — phase table and status badge updated.
- `docs/admin/CONTROL_PLANE_LOCK.md` — Phase 2A progress lock updated; final
  readiness decision restated.
- `docs/admin/FEATURE_MATRIX.md` — Phase 2A frontend table updated to mark
  Export Panel and Upload Zone implemented; Reports List, Processing View,
  Report View, and Evidence Panel remain partial pending backend reads.
- `docs/execution/CURRENT_PROJECT_STATE.md` — audit date, phase progress
  table, and readiness ratings refreshed.
- `docs/execution/IMPLEMENTATION_PHASES.md` — Phase 2A live progress note
  updated to anchor `e37b0c1` and Slices 1–9 complete.
- `scripts/check_ai_context.py`, `scripts/check_doc_drift.py` — see
  "Governance detector updates" above.

---

## Deferred items

| Item | Tracking | Required action to close |
|---|---|---|
| Phase 2A validation gate (manual QA + closeout) | This report | Execute U-01..U-16 manual QA, capture evidence, then a follow-up closeout pass may upgrade status to `PHASE_2A_COMPLETE_NOT_LIVE`. Requires explicit user approval. |
| Pip-audit hard CI gate (gap G11) | `docs/admin/CONTROL_PLANE_LOCK.md` | Promote `pip-audit` from advisory to gating after major-version dependency bumps regress-test clean. |
| Arabic bidi/reshaping in PDF (gap G10b) | `docs/admin/FEATURE_MATRIX.md` | Integrate a bidi/reshaper library and remove the RTL disclaimer. |
| Langfuse live dashboard validation (gap G9) | `docs/admin/FEATURE_MATRIX.md` | Exercise the tracer against a Langfuse project. |
| Frontend acceptance automation (`make test:ui`) | `IMPLEMENTATION_PHASES.md` §Phase 2C | Add Playwright or Cypress headless suite and CI gate. |

---

## Phase 2A backend additions (gap G12 closed)

After this closeout was filed, the five backend endpoints flagged as missing in
`docs/execution/PHASE_2A_PLAN.md` §F.2 — `GET /reports`, `GET /reports/{id}`,
`GET /reports/{id}/status`, `DELETE /reports/{id}`, and `POST /upload` — were
added to `apps/edr/app.py` in a controlled backend slice with explicit user
approval. The change is scoped to the backend and the API client's TypeScript
contract types; no Phase 2A screen wiring was changed and no new phase was
started.

Endpoints (all under JWT in production, X-User-Role bypass in dev):

| Endpoint | Purpose | RBAC |
|---|---|---|
| `GET /reports` | Paginated report list with optional `state`, `project_code`, `date_from`, `date_to` filters | Own `user_id_hash` for normal roles; auditor sees all; admin denied (403) |
| `GET /reports/{id}` | Report metadata + review-decision history (no evidence content) | Owner or auditor; admin denied |
| `GET /reports/{id}/status` | Processing-state snapshot for the Phase 2A Processing View polling loop | Owner or auditor; admin denied |
| `DELETE /reports/{id}` | Soft-cancel a non-terminal report (writes a `cancelled` review decision and flips `review_state`) | Requester only; 409 on `final`/`rejected`/`cancelled` |
| `POST /upload` | Persist a single attachment under `uploads/{user_id_hash}/{upload_id}/{filename}` in MinIO | Authenticated; type allowlist (PDF/DOCX/XLSX/TXT/MSG/EML); per-file ≤10 MB |

Supporting changes:

- `apps/edr/persistence/postgres_store.py` — added `list_audits` (role-scoped, paginated, with `state`/`project_code`/`date_from`/`date_to` filters; safe parameterised SQL).
- `apps/edr/persistence/minio_store.py` — added `put_upload` for the `uploads/` prefix.
- `apps/edr/app.py` — new Pydantic response models (`ReportSummary`, `ReportListResponse`, `ReportDetail`, `ReviewDecisionView`, `ReportStatusResponse`, `CancelReportResponse`, `UploadResponse`), helper functions (`_validated_role`, `_derive_external_state`, `_query_excerpt`, `_exported_formats`, `_check_can_read_own_report`, `_safe_filename`, `_validate_upload_type`), and the five endpoint handlers.
- `pyproject.toml` — `python-multipart==0.0.20` added (required by FastAPI to parse `multipart/form-data` for `POST /upload`).
- `frontend/src/api/types.ts` and `frontend/src/api/index.ts` — added `ReportState`, `ReportSummary`, `ReportListResponse`, `ReviewDecisionView`, `ReportDetail`, `ReportStatusResponse`, `CancelReportResponse`, `UploadResponse`, `ListReportsParams` types and re-exports. **No screen wiring changed**; the existing 'unavailable shell' UI is unchanged because the Phase 2A validation gate slice will wire and exercise the screens together.
- `apps/edr/tests/integration/test_phase2a_backend.py` — 31 mocked integration cases covering RBAC scoping, state derivation, filter pass-through, terminal-state blocking, owner-only cancellation, MIME/size validation on uploads, and safe filename handling.

Validation evidence is captured in the closeout commit that lands this work. No production deployment; production stays `NOT_LIVE`. Phase 2A status remains `PHASE_2A_SLICE_9_COMPLETE_NOT_LIVE` per the user's instruction (no claim of Phase 2A completion until the validation gate runs).

## Phase 2A E2E unblock validation

After the backend additions and focused blocker fixes, a deterministic local
validation harness was added to unblock the Phase 2A E2E path without real
external credentials. The harness patches only the external connector boundary
inside a local TestClient run and supplies a controlled SharePoint
`EvidenceObject`; it does not change `node_13_quality_gate.py` or any
quality-gate thresholds.

Validated path:

`submit → processing → quality_gate passed → approve → final → download MD`

Latest local evidence:

| Gate | Result |
|---|---|
| `make phase2a-e2e` | PASS |
| Workflow nodes visited | 18 |
| Quality gate | `passed` |
| Pre-approval staging download | 403 (approval/security gate preserved) |
| Approval state | `approved` |
| Publish status | `published` |
| Final state | `final` |
| Final markdown download | 200, 1443 bytes |
| Fixture evidence id | `ev_phase2a_local_sharepoint_001` |

The E2E blocker is removed. Phase 2A is still not closed by this update because
U-01..U-16 manual QA and explicit closeout approval remain pending.

## Next phase

Phase 2A manual QA + closeout requires explicit user approval and a running
stack. Until that gate closes, Phase 2A is not marked fully complete and Phase
2B may not start. Phase 2B itself requires explicit user approval and is gated
on Phase 2A closure.

This closeout authorizes nothing beyond the truth-reconciliation it performs.
