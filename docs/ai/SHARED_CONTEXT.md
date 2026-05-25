# Shared AI Operating Context

## Current State

- Project name: DecisionCenter
- Current verified commit (anchor): `69e230479d7cee2cd3b3531b0b740d8481f1de1a` (Slice 4 — backup/restore readiness)
- Current status: `PHASE_2C_COMPLETE_NOT_LIVE`
- Production status: `NOT_LIVE`
- Phase 2C closed: 2026-05-24
- Active implementation phase: none. Phase 2D is blocked until explicit user approval.
- Next allowed: Phase 2D — requires explicit user approval before implementation starts.
- Latest report: `docs/execution/PHASE_2C_REPORT.md`
- Latest full-phase report: `docs/execution/PHASE_2C_REPORT.md`
- Phase 2D Slice 1 (production frontend delivery path): implemented and committed
- Phase 2D Slice 2 (production Entra/MSAL auth + GET /me): implemented; production NOT_LIVE
- Phase 2D Slice 3 (live integration validation): implemented; production NOT_LIVE
- Phase 2D Slice 4 (backup and restore): implemented; production NOT_LIVE; Phase 2D remains approval-gated

Phases 0, 1A, 1B, 1B.5, 1C, 1D, the Phase 1D-fixup, 1E, 1F, 1G, 1H, and 1I
are complete. Phase 1I established the frontend foundation: Vite + React +
TypeScript + Tailwind project in `frontend/`; design tokens; layout shell;
reusable components; role-guarded hash-based routing with 9 canonical roles;
static scaffolds for Admin System Health, Permissions & Roles (Role Matrix
only), Source Mapping (read-only), and the initial Query Composer shell.
Frontend lint and build are wired into CI.

Phase 2A is complete and not live. Implementation slices 1–9, backend
read/status/content/cancel/upload additions, deterministic local E2E, and
U-01..U-16 manual QA are complete. The current workspace uses live backend
state for the Query Composer project list, Reports List, Processing View,
Report View, Evidence Panel, review actions, quality-gate banners, final
immutable display, and cancellation path.

Phase 2B is complete and not live. All ten slices are closed and CI-green:
admin RBAC base, Connectors, Health, Audit Log, Permissions, Source Mapping,
Approval Queue, Dashboard, Routing + Nav, and Closeout. The admin control
plane has seven live backend-integrated screens and preserves the C-1/C-6
boundaries: no business report content, query text, evidence excerpts, or
credential values in admin responses. `docs/execution/PHASE_2B_REPORT.md`
records the A-01..A-23 QA matrix, cross-screen invariants, audit event
catalog, and validation evidence.

Phase 2C is complete and not live. All four slices are closed:

- **Slice 1** — Playwright test harness: accessibility (5 tests), responsive
  behavior (5 tests), security-DOM (4 tests).
- **Slice 2** — Performance + bundle-budget validation: JS ≤ 120 kB gzip,
  CSS ≤ 15 kB gzip; Processing View and Report View render within budget.
- **Slice 3** — Golden-path acceptance: submit → processing → report →
  approve → download, fully mocked with `page.route()`.
- **Slice 4** — Cross-browser matrix: 54/54 tests pass on Chromium, Firefox,
  and WebKit. CI updated to install all three browser engines.

`docs/execution/PHASE_2C_REPORT.md` records the full closeout evidence
including U-01..U-16 and A-01/C-6 automated coverage, bundle evidence,
performance timings, cross-browser notes, and CI run references.

The 2026-05-24 read-only project audit at
`c3ab71d9864e17c3d99da847e5f673fabe2f1dba` rated the repo **7/10** with
final recommendation `NOT_GO_LIVE_READY_BUT_HEALTHY`. The project is healthy
but not go-live ready. Main blockers are: ~~production frontend delivery path missing~~ (Slice 1 ✅);
~~production Entra/MSAL frontend auth missing~~ (Slice 2 ✅);
~~live integrations not proven~~ (Slice 3 ✅ — infrastructure proven in CI;
workflow operator-run documented);
~~backup/restore evidence missing~~ (Slice 4 ✅ — scripts, docs, rehearsal evidence);
production hardening evidence missing → Slice 5.

Latest CI verification: run 26387937091 (commit `5368a9f`) — smoke job success
(22m20s), frontend job success (2m26s). Live probes excluded from CI via
`live_probe` marker; they pass locally against the Docker stack.

Pre-2C cleanup is complete at anchor `32b039c`: accidental Phase 2C
Playwright/UI-test wiring was removed, and Node 15 now reports degraded audit
persistence with sanitized operation names when MinIO/PostgreSQL writes fail.
Phase 2C was then explicitly authorized on 2026-05-21 after push/CI success at
`14c3154`.

The machine-readable checkpoint is `docs/ai/agent-state.json`.

## Required Validation Commands

Run these before claiming readiness or success for repo-level changes (the
authoritative list is `required_validation` in `docs/ai/agent-state.json`):

```bash
make smoke
make test
make test-ui
make eval
ruff check .
python3 -m compileall apps scripts
python3 scripts/check_doc_drift.py
python3 scripts/check_ai_context.py
cd frontend && npm run lint
cd frontend && npm run test:ui
cd frontend && npm run build
```

For pure documentation / truth work, `python3 scripts/check_doc_drift.py` and
`python3 scripts/check_ai_context.py` are the gate (see
`docs/ai/skills/README.md`). For fast local sanity checks, `python3 -m pytest -q`
is acceptable supporting evidence, but it does not replace `make smoke`,
`make test`, and `make eval` when the user requests the full gate.

`scripts/check_doc_drift.py` enforces an anchor-currency invariant: the
`current_commit` in `docs/ai/agent-state.json` must be HEAD itself or no more
than three commits behind HEAD on the current branch. When feature commits
land, refresh the anchor and the truth docs **in the same session, before
the final report**. Failure to do so will cause CI to fail on the
documentation drift check.

## Current No-Go Rules

- Do not start Phase 2D. It requires explicit user approval in the current session.
- Do not weaken `_require_admin`; non-admin roles must continue to receive
  HTTP 403 from every `/admin/*` endpoint.
- Do not deploy.
- Do not claim production is live.
- Do not commit `.env`, `.env.*`, credentials, tokens, local session files, or
  generated caches.
- Do not rely on previous chat memory over current repo files.
- Do not claim a check passed unless it was run and produced passing output.

## Production Deployment Requirements

Production is `NOT_LIVE`. A push to `origin/main` does not deploy the service.
Production requires an operator to run:

```bash
ssh <user>@<your-hetzner-host>
cd DecisionCenter
git pull origin main
make up
make smoke
```

Before `make up`, the server `.env` must provide:

- `PUBLIC_HOSTNAME`
- `OWNCLOUD_USERNAME`
- `OWNCLOUD_PASSWORD`
- `N8N_WEBHOOK_TOKEN`
- Existing Odoo settings
- Existing Qdrant settings
- Existing Redis settings
- Existing Postgres settings
- Existing Entra settings

## n8n Credential Requirement

n8n must have a Webhook Header Auth credential configured as:

```text
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

The ownCloud and Odoo service-account credentials are read from n8n container
environment variables and must not be sent in webhook bodies.

## Protected And Ignored Files

Protected source-of-truth files:

- `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
- `docs/execution/IMPLEMENTATION_PHASES.md`
- `docs/execution/CURRENT_PROJECT_STATE.md`
- `docs/execution/PHASE_1D_FIXUP_REPORT.md`
- `docs/execution/PHASE_1E_REPORT.md`
- `docs/execution/PHASE_1F_REPORT.md`
- `docs/execution/PHASE_1G_REPORT.md`
- `docs/execution/PHASE_1H_REPORT.md`
- `docs/execution/PHASE_1I_REPORT.md`
- `docs/execution/PHASE_2A_PLAN.md`
- `docs/execution/PHASE_2A_REPORT.md`
- `docs/execution/PHASE_2B_PLAN.md`
- `docs/execution/PHASE_2B_REPORT.md`
- `docs/admin/CONTROL_PLANE_LOCK.md`
- `docs/admin/FEATURE_MATRIX.md`
- `docs/ai/SHARED_CONTEXT.md`
- `docs/ai/AGENT_HANDOFF.md`
- `docs/ai/agent-state.json`

Ignored or local-only files must not be committed (see `.gitignore` and
`.git/info/exclude`):

- `.env`
- `.env.*` except `.env.example`
- `.claude/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`
- `staging/`
- `final/`
- `logs/`
- Docker volume data directories (`minio-data/`, `postgres-data/`, `qdrant-data/`, `redis-data/`, `n8n-data/`)

## Agent Coordination Rules

- Read `AGENTS.md` and this shared context before editing.
- Verify branch, commit, status, and phase before work.
- Treat `docs/ai/agent-state.json` as the machine-readable checkpoint.
- Update `docs/ai/AGENT_HANDOFF.md` before ending a repo-changing session.
- Keep each commit scoped and explain what was verified.
- If checks fail, leave the status as not ready or document the exact blocker.
- **Governance drift rule:** After every pushed commit (not just at closeout),
  refresh `agent-state.json`, `AGENT_HANDOFF.md`, and `SHARED_CONTEXT.md`
  before ending the session. Run `python3 scripts/check_doc_drift.py` before
  starting any new slice. If anchor drift exceeds 3 commits, stop and fix
  governance before writing any more code.
- If a future user explicitly authorizes Phase 2D, update this shared context,
  the handoff, and `docs/ai/agent-state.json` only as part of that approved
  session.
