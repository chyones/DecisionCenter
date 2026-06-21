# Agent Handoff — DecisionCenter

## Current State

- **Status:** `PHASE_2D_IN_PROGRESS_NOT_LIVE`
- **Current anchor:** `3822aabfbefdf47a5702e9cebe43fa4a75535495` (GitHub `main` PR #6 merge; repo state checked 2026-06-18)
- **Closed date:** 2026-05-25
- **Latest report:** `docs/execution/PHASE_2D_SLICE_6_REPORT.md`
- **Latest full closeout report:** `docs/execution/PHASE_2C_REPORT.md`
- **Last completed phase:** Phase 2C — UI Hardening & Acceptance Validation
- **Production:** `NOT_LIVE`
- **Active phase:** Phase 2D — Slice 7 approval-gated
- **Phase 2D Slice 1:** Production frontend delivery path — implemented
- **Phase 2D Slice 2:** Production Entra/MSAL auth + GET /me — implemented (NOT_LIVE)
- **Phase 2D Slice 3:** Live Integration Validation — implemented (NOT_LIVE)
- **Phase 2D Slice 4:** Backup and Restore — implemented (NOT_LIVE)
- **Phase 2D Slice 5:** Production Hardening — implemented (NOT_LIVE)
- **Phase 2D Slice 6:** Real UAT Flow — readiness implemented and CI-green (NOT_LIVE); live UAT evidence exists but remains partial/not go-live proof, operator-pending
- **Phase 2D Slice 7:** Go-Live Gate — not started; approval-gated, follows successful Slice 6

## 2026-06-21 Report Pipeline Policy Parity Branch

Branch `fix/report-pipeline-slice-0-1` is anchored at
`468d54862d8835076416537602ec6dd23c262a46` and is ready for review/merge
verification. It remains `NOT_LIVE`; Slice 7 is still approval-gated.

Branch scope completed:

- Intent SSOT routes Quality Gate checks through `report_type` / classifier.
- Odoo `f_*` cost extraction was corrected without starting extended Odoo
  source work.
- Markdown section numbering is dynamic and policy-driven.
- Professional fallback floor prevents filename-only fallback analysis from
  becoming report content.
- Salary reports populate sources.
- `ReportPolicy` registry now drives section policy and Quality Gate profiles.
- DOCX, PDF, PPTX, and Excel exports now honor `ReportPolicy.sections`, so
  salary/data reports omit irrelevant Financial Snapshot, Root Causes, Delay,
  and Contractual output.

Explicitly not changed: JSON behavior, LIVE state, production status, ownCloud,
new financial/risk/delay/document report types, and extended Odoo source work.
`must_not_deploy` remains `true` except for an explicitly requested
NOT_LIVE-only deploy operation.

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

Repo state was inspected on `main` at
`3822aabfbefdf47a5702e9cebe43fa4a75535495`, tracking `origin/main` with
divergence `0 0`. `git fetch --prune origin` completed cleanly and
`git pull --ff-only` reported "Already up to date." No merge commit was
created. No stashes or visible untracked files were present. Ignored local
runtime/tooling artifacts were left in place and not committed.

The only required repair was governance context: docs/ai still described PR #6
(`fix/report-sync-timeout-guard`) as active after it had already merged to
`main`. This session refreshed docs/ai context and added
`docs/evidence/uat/GIT_REPO_STATE_FIX_2026-06-18.md`. No code, `.env`,
deployment, runtime, n8n, or production-state change occurred. Production
remains `NOT_LIVE`; Slice 7 remains approval-gated.

## 2026-06-17 (Later) — Odoo Source Map Batched Scan + PR #5/#6 Merged

This supersedes the git-hygiene note below. The Odoo Source Map **automatic
batched deep scan** was completed and **merged to `main` via PR #3** (merge commit
`6f3d310`); pre-merge review fixes were applied (strong reference to the background
scan `asyncio.Task`; UI progress poll window widened 5m -> 15m). The repo later
advanced through PR #5 and PR #6 to merge HEAD `3822aab`.

- What the feature does: per-source isolated scan; `search_count` for exact
  totals; bounded offset-paged sample (never a full-table read); strict
  per-batch/per-source timeouts; retry/resume; DB-persisted progress polled by the
  UI — so the scan can no longer hit the 120s reverse-proxy timeout.
- Not changed: report generation, AI providers, SharePoint, Email, the generic
  Odoo source registry.
- Evidence: `docs/evidence/uat/ODOO_SCAN_BATCHED_2026-06-17.md` and
  `docs/evidence/uat/ODOO_SCAN_BATCHED_PHASE_CLOSE_2026-06-17.md`.
- **Production: NOT_LIVE.** No deployment occurred in the 2026-06-18
  repo-state repair. Any future operator deploy still requires explicit
  approval and must rebuild `app` + frontend `dist` together, then redeploy the
  n8n `odoo_read` workflow to unlock exact `search_count` totals.
- Recovery SHAs (deleted branches): odoo `136522d`, connector-truth `ba27557`,
  owner-operator `24f32c4`, entra `d49e51b`, pre-cleanup main `6f3d310`.
- PR #5 (`fix/ci-odoo-config-coverage`) corrected the CI config-coverage gap and
  a goldenset scope issue uncovered by CI: mailbox allowlist cases now use
  synthetic `PRJ-MAILBOX-ONLY` so they verify explicit allowlist/RBAC behavior,
  not PRJ-001's real group-mailbox mapping path. Local validation: config
  coverage `51/51`, goldenset `64/64`, and the exact previously failing pytest
  `test_runner_threshold_exit_non_zero` passed. PR #5 merged to `main` as
  `41e01b6`; no deployment occurred.
- PR #6 (`fix/report-sync-timeout-guard`) wraps synchronous
  `/reports/staging` workflow execution with `asyncio.wait_for` and returns a
  controlled HTTP 504 at 90 seconds, below the typical 100-second edge/proxy
  read-timeout budget. Local validation: timeout guard pytest `2 passed`, smoke
  `2 passed`, config coverage `51/51`, Ruff, compileall, doc drift, AI context,
  and `git diff --check` clean. PR #6 merged to `main` as `3822aab`; production
  remains `NOT_LIVE`.

## 2026-06-17 Git Hygiene And Governance Anchor Refresh

This session cleaned repo state without deploying and without touching `main`.
On branch `feat/odoo-source-map-batched-scan`, `git pull --ff-only` was already
up to date and the branch was even with
`origin/feat/odoo-source-map-batched-scan` at starting HEAD
`744b98e5993739fb63ac1c9cdbd62c4ae4d4e507`. `origin/main` was one commit ahead
and was intentionally not merged or rebased.

The root-level untracked files `Audit.md`, `FULL_SYSTEM_AUDIT_REPORT.md`, and
`executive-decision-report.md` were inspected and moved intact to
`/root/DecisionCenter-untracked-archive/2026-06-17/`; nothing was deleted.
Only docs/ai governance context was refreshed. No code, `.env`, deployment,
runtime, n8n, or production-state change occurred. Production remains
`NOT_LIVE`; Slice 7 remains approval-gated.

## 2026-06-11 Entra Revalidation Non-Root Runtime Fix

The post-`b7a4140` app rebuild exposed a runtime-only Entra revalidation
regression. Browser requests carried a valid admin bearer token: `/me` returned
HTTP 200 and `POST /admin/connectors/entra/revalidate-current-token` passed the
JWT and admin checks, then returned HTTP 500 while writing the redacted evidence
marker. The rebuilt app runs as uid 10001, while the marker file copied into the
image remained root-owned and read-only to `appuser`.

`Dockerfile` now grants `appuser` ownership of only
`docs/evidence/uat/ENTRA_CONNECTOR_TRUTH_REVALIDATION_2026-06-08.md`. The app
image was rebuilt and recreated; the marker is writable by uid 10001 and
`/healthz` is green. The frontend was rebuilt from current `b7a4140` source and
the public edge serves the refreshed artifact. The embedded production scope
has the required `api://<backend-api-client-id>/access_as_user` shape and its
audience and tenant match backend configuration.

Validation: connector truth tests 49 passed; Ruff, compileall, doc drift, and AI
context checks passed. The operator's post-fix browser revalidation returned
HTTP 200, wrote a fresh redacted PASS marker, and moved runtime Entra connector
truth to `VALIDATED` with evidence as its data source. No post-fix HTTP 500 or
permission error remains. Production remains `NOT_LIVE`; no go-live work was
performed.

## 2026-06-11 Audit Remediation (read-write session)

Targeted fixes from the 2026-06-10 full read-only audit
(`FULL_SYSTEM_AUDIT_REPORT.md`, audited at HEAD `2c5a6d1`):

- Upload Zone is wired end-to-end: Query Composer uploads ready files via
  `POST /upload` (new `ApiClient.postForm`) and attaches the returned
  `upload_ids` to the `POST /reports/staging` payload. `ReportRequest` in
  `apps/edr/app.py` now carries `upload_ids: list[str] = []`, recorded in the
  workflow inputs/audit trail (node-level ingestion remains a later phase).
  Regression tests: `apps/edr/tests/integration/test_upload_ids_field.py`.
- Admin "Enrich Email Groups" no longer hardcodes `['PRJ-001','PRJ-002']` in
  the frontend; it sends an empty `project_codes` list and defers to the
  backend's pilot scope so the scope is defined in one place. The backend
  pilot guard (PRJ-001/PRJ-002 only) is unchanged — it is a deliberate,
  tested invariant.
- Publish node (`apps/edr/graph/node_17_publish.py`) no longer silently
  swallows exceptions; artifact-copy, approval-log, and review-state failures
  are logged and surfaced in `state.outputs["publish_errors"]`. Existing
  `publish_status` values are unchanged.
- Caddyfile production block now sends `Content-Security-Policy` and
  `Permissions-Policy` headers (MSAL redirect/silent-iframe flows allowed via
  `login.microsoftonline.com` in connect-src/frame-src/form-action).
- Dockerfile now runs the app as non-root `appuser` (uid 10001). Verified
  safe: the app persists artifacts to MinIO/Postgres only; the legacy
  `/staging`, `/final`, `/logs` bind mounts are not written by the app.
- `apps/edr/config.py` fails fast at startup when `APP_ENV=production` is set
  while `POSTGRES_PASSWORD` or `MINIO_SECRET_KEY` still hold the `change-me`
  placeholder. The check is deliberately a plain post-construction check, not
  a pydantic validator, because a `ValidationError` would echo the full
  settings input — secrets included — into startup logs.
  **Operator warning:** the live `.env` sets `APP_ENV=production` with both
  placeholders still in place, so rotate both secrets before the next app
  image rebuild or the container will refuse to boot (with a clear message).
- `docker-compose.override.example.yml` and
  `docs/operations/deployment_overrides.md` now document the previously
  git-ignored mandatory deployment override (MinIO port remap, Caddy port
  reset, cloudflared tunnel). No secret values are tracked.

Audit corrections recorded for future agents:

- `microsoft_rescan.py` `_PLACEHOLDER_*` constants are placeholder-**detection**
  sets used to flag mappings that still contain seeded example values — not
  stub data. The audit's "replace placeholder constants" finding is a false
  positive; no change was made.
- The Odoo probe-timeout fix already landed in `74c944b`
  (probe timeout `max(50s, N8N_TIMEOUT)`, probe `limit: 5`, workflow honors
  limits). Remaining work is operator-side: re-import `n8n/odoo_read.json`
  into the runtime n8n and rebuild the app image.

Validation (host venv, `APP_ENV=local`): integration suite 721 passed with 14
live probes deselected (run twice: before and after the `app.py` change);
smoke 2/2; targeted upload_ids/publish/smoke 28 passed; Ruff, compileall,
frontend lint and build, doc_drift, and ai_context all clean. The audit's
in-container pytest timeouts were environmental, not failing tests.

Production remains `NOT_LIVE`; Slice 7 not started; no deployment, n8n import,
restart, or credential change occurred in this session.

## 2026-06-10 Entra Validation Button And Browser Session Fix

The Entra connector card now keeps a Validate/Revalidate action visible for
every configured state that lacks current passing user-token evidence,
including `CONFIGURED_NOT_TESTED`, expired evidence, failed validation, and
other action-required states. A current `VALIDATED` card retains a secondary
Revalidate action.

The validation click requests the current DecisionCenter API token through the
existing MSAL session with `forceRefresh: true`. This action disables the
interactive redirect fallback so acquisition failure leaves the card and
button visible with `Sign in with Microsoft again, then retry validation`.

The backend no longer sends the DecisionCenter API-audience token to Graph
`/me`. It validates issuer, audience, tenant, expiry, canonical role membership,
and `oid` identity consistency against the authenticated request. Only redacted
timestamps, role, and boolean checks are persisted; raw tokens and raw user
identity are never stored or returned. Legacy evidence without the identity
check is not accepted as current proof.

Targeted validation: connector/validator backend tests `55 passed`; Entra card
Playwright tests `24 passed` across Chromium, Firefox, and WebKit; targeted Ruff
and frontend lint passed. Full required validation and CI are recorded in
`docs/evidence/uat/ENTRA_VALIDATION_BUTTON_VISIBILITY_FIX_2026-06-10.md`.
Production remains `NOT_LIVE`; Microsoft Gate 4, deployment, live UAT, and
Slice 7 were not started.

## 2026-06-10 Odoo Dashboard Timeout Reliability Fix

The Odoo connector card's intermittent `TimeoutError` was traced without
printing credentials or response records. App-to-n8n connectivity was healthy,
and quiet-state live Odoo probes succeeded in 4.4–4.9 seconds. The dashboard
requested 5 records, but the deployed n8n workflow ignored that request and
returned 100; the dashboard also used a fixed 10-second timeout instead of the
configured 60-second connector timeout.

Source now makes the probe timeout `max(10 seconds, N8N_TIMEOUT)` and makes
`n8n/odoo_read.json` validate and honor request limits from 1–100. Focused tests
passed 63/63; CI-equivalent integration tests passed 720 with 1 skipped and 14
live probes deselected; smoke 2/2, goldenset 64/64, and Playwright 78/78 passed.
Ruff, compileall, frontend lint/build, JSON parsing, and wrapped n8n Code-node
syntax checks passed.

GitHub Actions run `27261573729` passed both `frontend` and `smoke`. No app
deployment, n8n import, restart, or credential change occurred. The currently
deployed workflow still returns 100 records; a quiet-state deployed probe was
green in 4.604 seconds after validation load ended. Production remains
`NOT_LIVE`.

## 2026-06-09 Entra Expired-State UI Badge Fix

The Entra card now treats `PREVIOUSLY_VALIDATED_TOKEN_EXPIRED` as action
required rather than current positive validation:

- Status is `Expired`, with warning styling.
- Current-validation wording and internal endpoint instructions are absent.
- Timestamps are split into `Last successful validation`, `Token expired at`,
  and `Last checked`.
- `Revalidate with current browser session` force-refreshes the API token
  through the existing MSAL browser flow before calling the redacted backend
  revalidation endpoint.
- Successful revalidation returns the card to `Validated`; failed acquisition,
  token validation, or Graph `/me` keeps the expired state and displays
  sign-in/retry guidance.
- Failed Graph `/me` validation no longer overwrites the previous successful
  redacted evidence marker.

JWT issuer, audience, tenant, expiry, and role validation rules were not
changed. No token file, fake token, Microsoft permission, Gate, deployment, or
LIVE work was used.

Evidence:
`docs/evidence/uat/ENTRA_EXPIRED_STATE_UI_BADGE_FIX_2026-06-09.md`.
Production remains `NOT_LIVE`.

## 2026-06-09 Entra Token-Expiry Dashboard Fix

The Entra connector truth now preserves prior validation history after the
validated token expires:

- Fresh passing evidence -> `VALIDATED`.
- Passing evidence with an expired token -> `PREVIOUSLY_VALIDATED_TOKEN_EXPIRED`.
- Config with no validation evidence -> `CONFIGURED_NOT_TESTED`.
- Missing config -> `NOT_CONFIGURED`.

The frontend displays `Previously validated — token expired` with non-green
warning styling. System Health maps the state to `unknown`. An admin-only
current-browser-token revalidation endpoint validates the bearer token, calls
Graph `/me`, and writes/returns only redacted evidence; `/root/dc_token.txt`
remains CLI-only input.

Validation: connector-truth integration tests `44 passed`; Ruff, compileall,
frontend lint/build, doc drift, and AI context passed. The app image was rebuilt,
the `app` service recreated, and `/healthz` returned `status=ok` with PostgreSQL,
Redis, Qdrant, and MinIO all `ok`.

Evidence:
`docs/evidence/uat/ENTRA_TOKEN_EXPIRY_DASHBOARD_BEHAVIOR_2026-06-08.md`.
Production remains `NOT_LIVE`; Gate 4, Gate 5, UAT, Slice 7, and LIVE were not
started.

## 2026-06-03 Reconciliation Update

This reconciliation does not change production app deployment. The deployed n8n
`odoo_read` workflow was intentionally updated and restarted because the
operator request explicitly required restoring deployed Odoo webhook auth.

Changes made:

- Owner-operator expectations reconciled in active docs, goldenset, and
  Playwright security-DOM tests: `admin` is a full owner plus system operator,
  may use `/workspace/*`, may generate/read report content, and may self-approve.
- Frontend owner-operator affordances reconciled: admin sees workspace Reports
  and New Query nav; Report View budget visibility includes admin.
- `n8n/odoo_read.json` restored to `authentication: headerAuth`, with explicit
  request validation and dynamic non-200 response codes for workflow errors.
- Deployed n8n `odoo_read` workflow verified active with `headerAuth`, a
  `httpHeaderAuth` credential reference, dynamic response code, and invalid
  request guard.
- Unauthenticated invalid Odoo webhook POST returns HTTP 403; authenticated
  invalid Odoo webhook POST returns HTTP 400 with an explicit
  `Invalid Odoo request` error.
- Connector-truth tests now call the sync `admin_connectors_truth` endpoint
  without `await`.

Validation evidence:

| Check | Result |
|---|---|
| Full backend pytest (bind-mounted current source) | 582 passed, 3 skipped |
| Golden-set eval | 64/64 passed |
| Playwright security-DOM | 12/12 passed across Chromium, Firefox, WebKit |
| Odoo live integration subset | 2 passed |
| Connector truth tests | 22 passed |
| n8n headerAuth workflow tests | 4 passed |
| Connector truth live probe | Odoo `LIVE_OK` (100 evidence items); SharePoint/Graph `CONFIGURED_NOT_TESTED`; ownCloud `NOT_CONFIGURED`; report generation `BLOCKED` |
| Frontend build | passed with existing Vite large-chunk warning |
| Frontend bundle budget | passed under repo/CI blank-Entra env: JS 91.19 kB gzip / 120.00 kB; CSS 6.08 kB gzip / 15.00 kB |
| Full Playwright UI, CI mode | exit 0; 53 passed, 1 flaky WebKit Processing View timing retry |
| Full Playwright UI, default local parallel mode | 52 passed, 2 Processing View timing failures in Firefox/WebKit |
| Frontend lint | clean |
| Ruff | clean |
| doc_drift / ai_context | clean |

## Live UAT Evidence Status (Slice 6)

- **Current verdict:** `PHASE_2D_SLICE_6_LIVE_UAT_PENDING`
- **Slice 6 implementation:** complete and **CI-green** (run `26395931904`, HEAD `e1992b1`).
- **Live UAT evidence:** **MISSING.** `docs/evidence/uat/` contains only `README.md`; there is no `UAT_RUN_<YYYY-MM-DD>.md` file.
- **Why it cannot be generated here:** no real target environment, no real Entra tokens, no live connectors. `scripts/uat_flow.py` correctly SKIPs (exit 0) without a target — it never fakes success. Local dev-bypass (`X-User-Role`) is **not** acceptable as real UAT proof.
- **Slice 6 is NOT complete.** Status stays `IMPLEMENTED_NOT_LIVE`; it does not advance to `COMPLETE_NOT_LIVE` until a real, redacted live-UAT run exists.
- **The next real action is the operator live UAT run — not coding.**
- **Slice 7 (Go-Live Gate):** BLOCKED — requires Slice 6 live-UAT evidence and a separate explicit user approval.
- **Production:** `NOT_LIVE`. **Go Live:** `NOT READY`.

### Operator prerequisites for the live UAT run

- Real Entra tenant configured (`ENTRA_CLIENT_ID` + `ENTRA_TENANT_ID`; real-token mode).
- Report-capable user real Entra access token (`UAT_BEARER_TOKEN`).
- Separate reviewer real Entra access token (`UAT_REVIEWER_TOKEN`).
- Live connectors configured (n8n -> SharePoint/ownCloud/Email/Odoo; Qdrant/Redis/PostgreSQL/MinIO).
- A project with a complete source mapping (`UAT_PROJECT_CODE`).

See `docs/operations/uat_runbook.md` and `docs/evidence/uat/README.md` for steps and redaction rules.

Phase 2C is closed. All four slices are complete:

1. **Slice 1** — Playwright test harness (accessibility, responsive, security-DOM)
2. **Slice 2** — Performance + bundle-budget validation (JS ≤ 120 kB gzip, CSS ≤ 15 kB gzip)
3. **Slice 3** — Golden-path acceptance test (submit → processing → report → approve → download, fully mocked)
4. **Slice 4** — Cross-browser expansion: 54/54 tests pass on Chromium, Firefox, and WebKit

The UI hardening and acceptance validation phase is complete. All U-01..U-16
workspace checks and the A-01/C-6 admin DOM checks are automated and green.

## Latest Audit Verdict

The 2026-06-10 full read-only audit at `2c5a6d11eb34106b392e283df9e40d5e67cf2694`
(`FULL_SYSTEM_AUDIT_REPORT.md`) returned primary verdict
**`GOVERNANCE_BLOCKED_NOT_LIVE`** — structurally sound and well-architected,
but not ready for live operation and correctly locked by its own governance
controls. Key technical blockers: empty AI provider keys (100% LLM fallback),
2 of 4 n8n workflows not imported into the runtime, expired Entra token, and
default Postgres/MinIO passwords. The 2026-06-11 remediation session closed
the safe code fixes (see above); credentials, n8n imports, and password
rotation remain operator actions.

The earlier 2026-05-24 read-only audit at
`c3ab71d9864e17c3d99da847e5f673fabe2f1dba` rated the repo **7/10** and
returned final recommendation `NOT_GO_LIVE_READY_BUT_HEALTHY`.

Production remains **not go-live ready**. Main blockers:

- ~~Production frontend delivery path missing~~ (Slice 1 ✅)
- ~~Production Entra/MSAL frontend auth missing~~ (Slice 2 ✅)
- ~~Live integrations not proven~~ (Slice 3 ✅ — infrastructure proven in CI; workflow operator-run documented)
- ~~Backup/restore evidence missing~~ (Slice 4 ✅ — scripts, docs, rehearsal evidence complete)
- ~~Production hardening evidence missing~~ (Slice 5 ✅ — checklist, secrets policy, automated checks, operator evidence)
- Real UAT flow not proven — Slice 6 readiness implemented; live UAT run is operator-pending
- Go-live approval not completed (Slice 7)

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
- **Slice 5 — Production Hardening:** implemented — hardening checklist, secrets policy,
  automated `check_hardening.py` script, and operator-run SSH/firewall evidence.
  See `docs/execution/PHASE_2D_SLICE_5_REPORT.md`.
- **Slice 6 — Real UAT Flow:** readiness implemented — operator UAT runbook
  (`docs/operations/uat_runbook.md`), CI-safe readiness checker
  (`scripts/uat_check.py`), real-backend live driver with no mocks
  (`scripts/uat_flow.py`), and a redacted evidence path
  (`docs/evidence/uat/`). The live UAT run (real login -> submit -> evidence
  retrieval -> quality gate -> approval -> publish -> download, no mocked
  backend) is operator-pending on the target environment. See
  `docs/execution/PHASE_2D_SLICE_6_REPORT.md`.
- **Next — Slice 7 Go-Live Gate:** not started; approval-gated. A separate
  explicit go-live approval is required before production can be declared live.

`docs/ai/agent-state.json.requires_explicit_user_approval_for_phase_2d` is
`true`: no agent may start the next slice without explicit user approval in the
current session.

## Current Guardrails

- Do not deploy the app; production remains `NOT_LIVE`. Runtime n8n workflow
  changes require explicit operator/user direction.
- Do not start Slice 7 without explicit user approval in the current session.
- Do not weaken `_require_admin`; non-admin roles must continue to receive
  HTTP 403 from every `/admin/*` endpoint.
- Do not expose credential values in admin responses. Do not expose report
  content, query text, or evidence excerpts outside the owner-operator RBAC
  rules.
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
| Integration suite (host venv, APP_ENV=local, 2026-06-11) | 721 passed, 14 live probes deselected (run before and after the app.py change) |
| Smoke (host venv, 2026-06-11) | 2 passed |
| Targeted upload_ids / publish / smoke (2026-06-11) | 28 passed |
| Frontend lint | clean |
| Frontend build | passed; existing Vite large-chunk warning remains |
| Ruff / compileall | clean |
| doc_drift / ai_context | clean |
| Latest verified GitHub CI | run `27261573729` green on `74c944b`; the 2026-06-11 remediation commit requires a new CI run |

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


## Connector status truth (2026-06-03)

Dashboard/Connectors now show honest connector states — see
`apps/edr/admin/connector_status.py` and `GET /admin/connectors/truth`. A
connector is green only on a real `LIVE_OK` live probe; fixture/mock data is
capped at `MOCK_ONLY`. Current source-level live probe reality after the Odoo
headerAuth restoration: Odoo is `LIVE_OK` with 100 evidence items; SharePoint
and Microsoft Graph are `CONFIGURED_NOT_TESTED`; ownCloud is `NOT_CONFIGURED`;
AI providers remain not configured, so report generation is `BLOCKED`.
Readiness is `PARTIAL_READY` and production stays `NOT_LIVE`.
