# Shared AI Operating Context

## Current State

- Project name: DecisionCenter
- Current verified commit (anchor): `0a17c39482821bc551ca60c7d476c28548c7fd23` (PR #11 financial cost-breakdown merge; main checked 2026-07-08)
- Current status: `PHASE_2D_IN_PROGRESS_NOT_LIVE`
- Production status: `NOT_LIVE`
- Phase 2C closed: 2026-05-24
- Active implementation phase: Phase 2D, with Slice 7 blocked until explicit user approval.
- Next real action: run the operator live UAT on the target environment and save redacted evidence — this is an operator action, not coding. Phase 2D Slice 7 — Go-Live Gate remains blocked: it requires that Slice 6 live-UAT evidence plus explicit user approval, and does not start automatically.
- Latest report: `docs/execution/PHASE_2D_SLICE_6_REPORT.md`
- Latest full-phase report: `docs/execution/PHASE_2C_REPORT.md`
- Phase 2D Slice 1 (production frontend delivery path): implemented and committed
- Phase 2D Slice 2 (production Entra/MSAL auth + GET /me): implemented; production NOT_LIVE
- Phase 2D Slice 3 (live integration validation): implemented; production NOT_LIVE
- Phase 2D Slice 4 (backup and restore): implemented; production NOT_LIVE
- Phase 2D Slice 5 (production hardening): implemented; production NOT_LIVE
- Phase 2D Slice 6 (real UAT flow): readiness implemented and CI-green; live UAT evidence exists but remains partial/not go-live proof; operator-pending; production NOT_LIVE
- Phase 2D Slice 7 (go-live gate): not started; approval-gated, follows successful Slice 6

## 2026-07-08 Main Cleanup And Governance Anchor Refresh

Local `main` is fast-forwarded to `origin/main` at merge commit
`0a17c39482821bc551ca60c7d476c28548c7fd23` (PR #11,
`fix/financial-cost-breakdown`). The working tree is clean and production
remains `NOT_LIVE`.

Cleanup performed:

- Local generated report captures `docs/output report` and
  `docs/output report 1` were moved out of the repo to
  `/root/DecisionCenter-untracked-archive/2026-07-08-clean/`.
- Local branches already merged into `main` were deleted.
- Temporary clean worktrees `/tmp/decisioncenter-ci-b` and
  `/tmp/decisioncenter-ci-main` were removed, then the stale local branch
  `fix/ci-odoo-config-coverage` was deleted.
- The unmerged draft PR branch `fix/financial-cost-breakdown-reset` remains
  locally and on GitHub as PR #12. It was intentionally not deleted.
- Ignored local secrets, backups, virtualenvs, node modules, runtime data,
  logs, and private operator files remain untouched.

Validation for the cleanup: `git fetch --prune origin`, `git pull --ff-only`,
`git status -sb`, `git branch -vv`, and `git worktree list` were checked.
Preflight initially failed only because `agent-state.json.current_commit` was
4 commits behind `main`; this governance refresh updates the anchor.

## 2026-06-22 Financial Arabic UAT Defect Fix

Branch `fix/financial-uat-evidence-filter` fixes only the current UAT defect for
Arabic query `تقرير عن مصاريف المشروع` at local fix commit
`d6111d0c08b69da10de5fc0c01565e3ca828f728`.

The fix keeps production `NOT_LIVE`, keeps `must_not_deploy=true`, does not
enable `ODOO_EXTENDED_SOURCES_ENABLED`, does not change Al Marfa / Al Mirfa
project naming, and does not add new features.

Implemented scope:

- Arabic financial query expansion now searches controlled financial evidence
  terms.
- Financial SharePoint/email retrieval filters to BOQ, payment certificate,
  invoice, purchase order/LPO, cost report, variation, budget, procurement, and
  payment context; schedules, drawings, QAQC, MIR, method statements, technical
  submittals, and test reports are excluded unless explicitly requested.
- node_12 forces clean Odoo-led financial synthesis when only Odoo financial
  data is usable.
- Quality Gate fails visible report-body raw filenames as unsupported; filenames
  and URLs remain allowed only in Sources appendix.

Validation: targeted tests `46 passed`; smoke `2 passed`; backend `make test`
`930 passed, 3 skipped, 2 deselected`; goldenset `68/68 passed`, `0 failed`,
`100.00%` pass rate, `94.12%` precision; frontend lint/build passed; frontend UI
`78 passed`; ruff, compileall, doc drift, and AI context checks passed.
`make phase2a-e2e` remains blocked by production `APP_ENV` guard in the running
NOT_LIVE container and is not part of this defect's acceptance proof.

## 2026-06-21 Report Pipeline Policy Parity Branch

Branch `fix/report-pipeline-slice-0-1` is anchored at
`c0f27b845403b1aa2d81833aaf9b89b9091e7680` after exporter parity and a
frontend accessibility fixture correction. This branch is for review/merge only
and does not start new feature work.

Completed branch scope:

- Intent SSOT: report type comes from `report_type` / classifier, not a second
  regex path in Quality Gate.
- Odoo `f_*` cost extraction fixed without adding extended Odoo source work.
- Markdown section numbering is dynamic and honors `ReportPolicy.sections`.
- Professional fallback floor added so filename-only fallback analysis is not
  emitted as report content.
- Salary report sources are populated.
- `ReportPolicy` registry is the section/check-profile source for Markdown and
  Quality Gate.
- DOCX, PDF, PPTX, and Excel exports now honor the same
  `ReportPolicy.sections` as Markdown. Salary/data exports omit irrelevant
  Financial Snapshot, Root Causes, Delay, and Contractual sections.
- Frontend accessibility coverage now mocks a cancelable running report status
  before opening the Cancel confirmation dialog, so the focus-trap test verifies
  the dialog instead of clicking a disabled control.

Not changed: JSON schema behavior, Quality Gate semantics beyond policy-profile
selection, production status, LIVE state, ownCloud, extended Odoo source work,
and new financial/risk/delay/document report types. Production remains
`NOT_LIVE`; `must_not_deploy` remains `true` unless an explicitly requested
NOT_LIVE-only deployment step is being performed.

## 2026-06-18 Query Composer Timeout Deploy Verification

Current `origin/main` commit `513314df977fa7d7acd3f8501313c22b5a6fcd4f`
was deployed to the NOT_LIVE app environment with
`docker compose up -d --build app`. n8n workflows, connector settings, secrets,
and production status were not changed. The app container was recreated from
image digest `sha256:c6571d0f23051eb7129507c475c7e18c2dfe3a79cc1ad002c0dcc363e5051695`
and is healthy. Local and public `/healthz` returned HTTP 200.

The running container contains the `/reports/staging` timeout guard
(`REPORT_SYNC_TIMEOUT_S` plus `asyncio.wait_for`), and the in-container timeout
guard test passed (`2 passed`). Query Composer/API attempts for
`Construction of Civil Defense building in Al Marfa` (`PRJ-001`) with the
requested question returned fast JSON HTTP 401 responses because no real bearer
token was available and production mode correctly rejects dev-bypass headers.
Therefore the authenticated long-running workflow path was not verified in this
run. Evidence:
`docs/evidence/uat/QUERY_COMPOSER_TIMEOUT_DEPLOY_VERIFY_2026-06-18.md`.
Production remains `NOT_LIVE`; `must_not_deploy` remains `true`.

## 2026-06-18 Git/GitHub Repo State Repair

The repo was inspected on `main` at
`3822aabfbefdf47a5702e9cebe43fa4a75535495`, tracking `origin/main` with
divergence `0 0`. `git fetch --prune origin` completed cleanly and
`git pull --ff-only` reported "Already up to date." No merge commit was
created. No stashes or visible untracked files were present. Ignored local
runtime/tooling artifacts were left in place and not committed.

The only required repair was governance context: the AI files still described
PR #6 (`fix/report-sync-timeout-guard`) as active after it had already merged
to `main`. This session refreshed docs/ai context and added evidence at
`docs/evidence/uat/GIT_REPO_STATE_FIX_2026-06-18.md`. No code, `.env`,
deployment, runtime, n8n, or production-state change occurred. Production
remains `NOT_LIVE`; Slice 7 remains approval-gated.

## 2026-06-17 (Later) — Odoo Source Map Batched Scan, PR #5, And PR #6 Merged

Supersedes the git-hygiene note below. The Odoo Source Map automatic batched deep
scan was merged to `main` via PR #3 (merge `6f3d310`) with pre-merge review fixes
(strong ref to the background scan task; UI poll window 5m -> 15m). The repo is now
on `main` at PR #6 merge HEAD `3822aab`. Read
generation / AI providers / SharePoint / Email / the generic Odoo registry were
NOT changed by the batched scan or timeout guard. Production remains
`NOT_LIVE`; no deployment was performed in the 2026-06-18 repo-state repair.
Any future operator deploy still requires explicit approval. Recovery SHAs:
odoo `136522d`, connector-truth `ba27557`, owner-operator
`24f32c4`, entra `d49e51b`, pre-cleanup main `6f3d310`.

PR #5 (`fix/ci-odoo-config-coverage`) also corrected goldenset scope for three
mailbox allowlist cases. They now use synthetic project code
`PRJ-MAILBOX-ONLY`, so node_07_email exercises the explicit mailbox allowlist /
RBAC path instead of PRJ-001's real group-mailbox mapping path. Validation:
config coverage `51/51`, goldenset `64/64`, and the exact previously failing
pytest `test_runner_threshold_exit_non_zero` passed. PR #5 merged to `main` as
`41e01b6`; no deployment occurred.

PR #6 (`fix/report-sync-timeout-guard`) wraps synchronous
`/reports/staging` workflow execution with `asyncio.wait_for` and returns a
controlled HTTP 504 at 90 seconds, below the typical 100-second edge/proxy
read-timeout budget. Local validation: timeout guard pytest `2 passed`, smoke
`2 passed`, config coverage `51/51`, Ruff, compileall, doc drift, AI context,
and `git diff --check` clean. PR #6 merged to `main` as `3822aab`; production
remains `NOT_LIVE`.

## 2026-06-17 Git Hygiene Context

Repo hygiene was performed on branch `feat/odoo-source-map-batched-scan`.
The branch was clean after `git pull --ff-only` and even with
`origin/feat/odoo-source-map-batched-scan` at starting HEAD
`744b98e5993739fb63ac1c9cdbd62c4ae4d4e507`; `origin/main` was one commit
ahead and was not merged, rebased, or touched.

Root-level untracked artifacts were inspected and moved intact, not deleted, to
`/root/DecisionCenter-untracked-archive/2026-06-17/`:
`Audit.md`, `FULL_SYSTEM_AUDIT_REPORT.md`, and
`executive-decision-report.md`. No `.env`, code, deployment, runtime, or
production-state changes were made. Production remains `NOT_LIVE`, and Phase
2D Slice 7 remains blocked pending explicit user approval.

## 2026-06-11 Audit Remediation Context

The 2026-06-10 full read-only audit (`FULL_SYSTEM_AUDIT_REPORT.md`, verdict
`GOVERNANCE_BLOCKED_NOT_LIVE`) was remediated in source:

- Upload Zone is wired end-to-end: Query Composer uploads files via
  `POST /upload` (`ApiClient.postForm`) and attaches `upload_ids` to
  `POST /reports/staging`; `ReportRequest` now carries `upload_ids`.
- Admin "Enrich Email Groups" sends an empty `project_codes` list; the backend
  pilot scope (PRJ-001/PRJ-002, a deliberate tested invariant) is the single
  source of truth.
- `node_17_publish.py` surfaces previously swallowed exceptions via logging and
  `state.outputs["publish_errors"]`.
- Caddyfile production block sends `Content-Security-Policy` and
  `Permissions-Policy` (MSAL flows allowed). Dockerfile runs as non-root
  `appuser` (the `/staging`, `/final`, `/logs` bind mounts are not written by
  the app).
- `config.py` fails fast when `APP_ENV=production` still uses `change-me`
  secrets. **Operator warning:** the live `.env` is exactly in that state, so
  rotate `POSTGRES_PASSWORD` and `MINIO_SECRET_KEY` before the next app image
  rebuild.
- `docker-compose.override.example.yml` + `docs/operations/deployment_overrides.md`
  document the git-ignored mandatory deployment override.

Audit corrections: `microsoft_rescan.py` `_PLACEHOLDER_*` constants are
placeholder-detection sets (audit false positive; unchanged); the Odoo probe
timeout fix already landed in `74c944b` — remaining work is the operator n8n
re-import and app rebuild. No deployment, n8n import, restart, or credential
change occurred. Production remains `NOT_LIVE`.

## 2026-06-10 Entra Validation Action Context

The Entra connector card keeps a current-session Validate/Revalidate action
visible whenever Entra is configured but fresh passing user-token evidence is
absent, expired, or failed. The click force-refreshes the existing MSAL API
token and leaves the button visible with sign-in guidance if acquisition fails.

The backend validates the DecisionCenter API token's issuer, audience, tenant,
expiry, canonical roles, and `oid` identity consistency. It does not send that
API-audience token to Graph `/me`. Only redacted evidence is stored. Production
remains `NOT_LIVE`; Microsoft Gate 4, deployment, live UAT, and Slice 7 remain
untouched.

## 2026-06-10 Odoo Dashboard Timeout Reliability Context

The Odoo connector truth probe now uses the greater of its existing 10-second
minimum or configured `N8N_TIMEOUT`. The n8n Odoo workflow validates and honors
an optional caller limit from 1–100 instead of always fetching 100 records; the
dashboard probe requests 5.

Redacted runtime diagnosis found healthy app-to-n8n connectivity and successful
quiet-state Odoo reads around 4.4–4.9 seconds, but the deployed 100-record
workflow timed out under concurrent validation load. No app deployment, n8n
workflow import, service restart, or credential change was performed. The
source fix is CI-green in run `27261573729` and awaits an explicitly approved
future rollout. Production remains `NOT_LIVE`.

## 2026-06-03 Reconciliation Context

This session reconciled owner-operator expectations and Odoo webhook security
without deploying the app and without changing production `NOT_LIVE`.

- Owner-operator expectations now align across active docs, goldenset, and
  Playwright security-DOM tests: `admin` is a full owner plus system operator
  and can use workspace/report flows.
- Frontend source affordances now expose workspace Reports/New Query to admin
  where appropriate, and Report View treats admin as budget-capable.
- `n8n/odoo_read.json` now declares `authentication: headerAuth`, validates
  required Odoo request fields, and returns explicit non-200 response codes for
  invalid/downstream-failure paths.
- The deployed active n8n `odoo_read` workflow was intentionally updated and
  restarted. Export verification shows `headerAuth`, a `httpHeaderAuth`
  credential reference, dynamic response code, and invalid-request guard.
- Runtime bad-call verification: unauthenticated invalid Odoo POST returns
  HTTP 403; authenticated invalid Odoo POST returns HTTP 400 with an explicit
  `Invalid Odoo request` error.
- Source-level connector truth probe: Odoo `LIVE_OK` with 100 evidence items;
  SharePoint and Microsoft Graph `CONFIGURED_NOT_TESTED`; ownCloud
  `NOT_CONFIGURED`; report generation `BLOCKED`; readiness `PARTIAL_READY`.
- Validation: full backend pytest 582 passed / 3 skipped; goldenset 64/64;
  Playwright security-DOM 12/12 across Chromium, Firefox, WebKit; full
  Playwright UI passed in CI mode with one WebKit Processing View timing retry
  (`53 passed, 1 flaky`); default local parallel UI mode still has two
  Processing View timing failures; frontend lint/build passed; bundle budget
  passed under the repo/CI blank-Entra env; ruff, doc_drift, and ai_context
  clean.

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
plane has seven live backend-integrated screens. The 2026-05-31 owner-operator
override supersedes C-1 admin content-blindness for workspace/report content;
C-6 remains in force, so credential values are never exposed in admin
responses. `docs/execution/PHASE_2B_REPORT.md`
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
~~production hardening evidence missing~~ (Slice 5 ✅ — checklist, secrets policy, automated checks).
Remaining go-live blockers are: real UAT flow not proven (Slice 6 readiness
is implemented; the live UAT run is operator-pending) and go-live approval
not completed (Slice 7). Production remains `NOT_LIVE`.

Latest verified GitHub CI for `origin/main`/HEAD `450ecc8`: run `26876872322`
is completed with conclusion `failure`; jobs `frontend` and `smoke` failed.
The reconciliation fix set still requires commit, push, and CI verification in
the current operator task. Historical Slice 6 readiness was CI-green, but
the **real live UAT evidence does not exist**: `docs/evidence/uat/` holds only
`README.md` (no `UAT_RUN_<YYYY-MM-DD>.md`). Current verdict:
`PHASE_2D_SLICE_6_LIVE_UAT_PENDING`. The next real action is an operator live
UAT run on the target environment (real Entra tenant, real report-capable plus
separate reviewer tokens, live connectors, a mapped project) with redacted
evidence saved — an operator action, not coding. Local dev-bypass is not
acceptable as real UAT proof. Slice 6 stays `IMPLEMENTED_NOT_LIVE` (not
complete) and Slice 7 stays blocked until that evidence exists.

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

- Do not start Slice 7. It requires explicit user approval in the current session.
- Do not weaken `_require_admin`; non-admin roles must continue to receive
  HTTP 403 from every `/admin/*` endpoint.
- Do not deploy the app; production remains `NOT_LIVE`. Runtime n8n workflow
  changes require explicit operator/user direction.
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
  starting any new slice.  If anchor drift exceeds 3 commits, stop and fix
  governance before writing any more code.
- If a future user explicitly authorizes Slice 7, update this shared context,
  the handoff, and `docs/ai/agent-state.json` only as part of that approved
  session.
