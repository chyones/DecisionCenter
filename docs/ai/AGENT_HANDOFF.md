# Agent Handoff — DecisionCenter

## Current State

- **Status:** `PHASE_2C_COMPLETE_NOT_LIVE`
- **Current anchor:** `69e230479d7cee2cd3b3531b0b740d8481f1de1a` (Slice 4 — backup/restore readiness)
- **Closed date:** 2026-05-24
- **Latest report:** `docs/execution/PHASE_2C_REPORT.md`
- **Latest full closeout report:** `docs/execution/PHASE_2C_REPORT.md`
- **Last completed phase:** Phase 2C — UI Hardening & Acceptance Validation
- **Production:** `NOT_LIVE`
- **Active phase:** None — Phase 2D is approval-gated
- **Phase 2D Slice 1:** Production frontend delivery path — implemented
- **Phase 2D Slice 2:** Production Entra/MSAL auth + GET /me — implemented (NOT_LIVE)
- **Phase 2D Slice 3:** Live Integration Validation — implemented (NOT_LIVE)
- **Phase 2D Slice 4:** Backup and Restore — implemented (NOT_LIVE); Phase 2D remains approval-gated

Phase 2C is closed. All four slices are complete:

1. **Slice 1** — Playwright test harness (accessibility, responsive, security-DOM)
2. **Slice 2** — Performance + bundle-budget validation (JS ≤ 120 kB gzip, CSS ≤ 15 kB gzip)
3. **Slice 3** — Golden-path acceptance test (submit → processing → report → approve → download, fully mocked)
4. **Slice 4** — Cross-browser expansion: 54/54 tests pass on Chromium, Firefox, and WebKit

The UI hardening and acceptance validation phase is complete. All U-01..U-16
workspace checks and the A-01/C-6 admin DOM checks are automated and green.

## Latest Audit Verdict

The 2026-05-24 read-only project audit at
`c3ab71d9864e17c3d99da847e5f673fabe2f1dba` rated the repo **7/10** and
returned final recommendation `NOT_GO_LIVE_READY_BUT_HEALTHY`.

Production remains **not go-live ready**. Main blockers:

- ~~Production frontend delivery path missing~~ (Slice 1 ✅)
- ~~Production Entra/MSAL frontend auth missing~~ (Slice 2 ✅)
- ~~Live integrations not proven~~ (Slice 3 ✅ — infrastructure proven in CI; workflow operator-run documented)
- ~~Backup/restore evidence missing~~ (Slice 4 ✅ — scripts, docs, rehearsal evidence complete)
- Production hardening evidence missing → Slice 5

## Phase 2D Progress

Phase 2D was explicitly approved and is proceeding slice by slice. Each new
slice still requires explicit user approval before implementation; production
stays `NOT_LIVE` until a separate go-live approval.

- **Slice 1 — Production frontend delivery path:** implemented (Caddy SPA +
  reverse proxy).
- **Slice 2 — Production auth:** implemented — Microsoft Entra/MSAL login,
  `Authorization: Bearer` API calls, a `GET /me` canonical-role source, and
  production rejection of the dev bypass headers (`x-user-role`/`x-user-id`).
  Local dev and CI keep the RoleSwitcher bypass. Real Entra login is
  operator-verified (no live tenant in CI). See
  `docs/execution/PHASE_2D_SLICE_2_REPORT.md`.
- **Slice 4 — Backup and Restore:** implemented — PostgreSQL + MinIO backup/restore
  scripts, operator runbook, DR policy, and rehearsal evidence. See
  `docs/execution/PHASE_2D_SLICE_4_REPORT.md`.
- **Next — Slice 5 (Production Hardening):** approval-gated; not started.

`docs/ai/agent-state.json.requires_explicit_user_approval_for_phase_2d` is
`true`: no agent may start the next slice without explicit user approval in the
current session.

## Current Guardrails

- Do not deploy; production remains `NOT_LIVE`.
- Do not start Phase 2D without explicit user approval in the current session.
- Do not weaken `_require_admin`; non-admin roles must continue to receive
  HTTP 403 from every `/admin/*` endpoint.
- Do not expose business report content, query text, evidence excerpts, or
  credential values in admin responses.
- Do not commit `.env`, `.env.*`, credentials, tokens, generated caches, local
  logs, or staging/final artifacts.

## Governance Drift Incident (Slice 4)

The Slice 4 CI run (`26357255473`) had the `smoke` job fail on the
documentation drift check. Root cause: `agent-state.json.current_commit` was
4 commits behind HEAD after Slices 2–4 landed without a governance refresh.
The frontend CI job was fully green (54/54 Playwright tests). This closeout
commit fixes the anchor drift. Corrective rules have been added to `AGENTS.md`.

**Rule for future AI agents:** Refresh `agent-state.json`, `AGENT_HANDOFF.md`,
and `SHARED_CONTEXT.md` after every pushed commit, before the final session
report. Run `python3 scripts/check_doc_drift.py` before starting any new slice.
If anchor drift exceeds 3 commits, stop and fix governance before coding.

## Latest Validation Evidence

| Check | Result |
|---|---|
| Playwright 54 tests (3 browsers) | 54/54 passed |
| Frontend lint | clean |
| Frontend build | JS 92.77 kB gzip, CSS 6.06 kB gzip |
| Bundle budget | JS ≤ 120 kB ✅, CSS ≤ 15 kB ✅ |
| Live integration probes | 15/15 passed (infra + webhook failure-mode) |
| CI smoke job | success (22m20s) |
| CI frontend job | success (2m26s) |
| doc_drift | clean |
| ai_context | clean |
| postflight | clean |

## Required Validation

For repo-level changes, use the authoritative list in
`docs/ai/agent-state.json`. For pure truth-doc work, run at minimum:

- `python3 scripts/check_doc_drift.py`
- `python3 scripts/check_ai_context.py`
- `python3 scripts/agent_postflight.py --allow-no-evidence`

For any future Phase 2D implementation, run the full gate:

- `make smoke`
- `make test`
- `make test-ui`
- `make eval`
- `ruff check .`
- `python3 -m compileall apps scripts`
- `cd frontend && npm run lint`
- `cd frontend && npm run test:ui`
- `cd frontend && npm run build`
- `python3 scripts/check_doc_drift.py`
- `python3 scripts/check_ai_context.py`
- `python3 scripts/agent_postflight.py --allow-no-evidence`
