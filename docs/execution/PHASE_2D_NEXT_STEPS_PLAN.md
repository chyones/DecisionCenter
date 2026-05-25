# Phase 2D — Next Steps Plan (Slices 2–7 to Go-Live Gate)

> **Document type:** Planning artifact only. This file does **not** authorize
> implementation, deployment, production cutover, or go-live. Phase 2D
> implementation remains blocked until explicit user approval in the active
> session (`docs/ai/agent-state.json.requires_explicit_user_approval_for_phase_2d` = `true`).
> **Author context:** Read-only verification of the live repo at HEAD `91f0df1`.
> **Date:** 2026-05-25
> **Predecessor plan:** `docs/execution/PHASE_2D_EXECUTION_PLAN.md` (authored at HEAD `538dd2e`, before Slice 1 landed).
> **2026-05-25 re-audit update:** This file remains the governing Slice 2-7
> roadmap, but its original baseline was captured before Slices 2-5 landed. At
> current re-audit HEAD `4584501`, Slices 1-5 are implemented, latest HEAD CI is
> red in the `AI context check` step, and Slice 6 (Real UAT Flow) plus Slice 7
> (Go-Live Gate) remain not started. Any older recommendation in this document
> to continue to Slice 2 is superseded by the current CI repair gate.

---

## 1. Current Verified Baseline

All values below were verified by running commands against the live checkout;
none are taken from chat history.

| Field | Verified value | How verified |
|---|---|---|
| HEAD | `91f0df1f019e043799fc91bea04f39e60cfb4f1c` | `git rev-parse HEAD` |
| origin/main | `91f0df1f019e043799fc91bea04f39e60cfb4f1c` (in sync, 0 ahead / 0 behind) | `git rev-parse origin/main`, `git status -sb` |
| Working tree | Clean except untracked `CLAUDE.md` (left untouched per rules) | `git status --short --branch` |
| Governance anchor | `agent-state.json.current_commit` = `1edecaa` — **1 commit behind HEAD**, within the 3-commit tolerance | `docs/ai/agent-state.json`, `scripts/check_doc_drift.py` |
| CI result for `91f0df1` | **GREEN** — run `26361596945` (`CI`), `status: completed`, `conclusion: success`; jobs `smoke` ✅ and `frontend` ✅; created 2026-05-24T12:44:37Z, updated 2026-05-24T13:06:56Z | GitHub Actions API for run `26361596945` and the commit's check-runs |
| Documentation drift check | **clean** (exit 0) | `python3 scripts/check_doc_drift.py` |
| AI context check | **clean** (exit 0) | `python3 scripts/check_ai_context.py` |
| Repo status | `PHASE_2C_COMPLETE_NOT_LIVE` | `docs/ai/agent-state.json`, truth docs |
| Production status | `NOT_LIVE` | truth docs (a push to `origin/main` is not a deployment) |
| Current phase / slice | Phase 2C complete; **Phase 2D Slice 1 implemented (`IMPLEMENTED_NOT_LIVE`)**; Phase 2D Slices 2–7 not started; no active implementation phase (Phase 2D approval-gated) | `agent-state.json`, `PHASE_2D_EXECUTION_PLAN.md` |
| Go-live readiness | **NOT READY** — latest read-only audit (2026-05-24, `c3ab71d`) rated **7/10**, recommendation `NOT_GO_LIVE_READY_BUT_HEALTHY`, `go_live_ready: false` | `agent-state.json`, `CURRENT_PROJECT_STATE.md` |

**Non-blocking governance freshness note (observation only):** the anchor
(`1edecaa`) and `latest_verified_ci` (run `26356541561` at `d0b05e3`, the last
Slice 3 run) recorded in `agent-state.json` predate the current HEAD `91f0df1`.
Drift remains within tolerance (1 commit) so all automated checks are clean and
this is **not** a repo-drift blocker. The next approved session that touches
governance should refresh `latest_verified_ci` to run `26361596945` / `91f0df1`.
This plan does not modify `agent-state.json`.

---

## 2. Previous Phase Analysis

Statuses and evidence taken from `CURRENT_PROJECT_STATE.md`, `CONTROL_PLANE_LOCK.md`,
`FEATURE_MATRIX.md`, `IMPLEMENTATION_PHASES.md`, `PHASE_2C_REPORT.md`, and `git log`.

| Phase / Slice | Status | Main delivery | Evidence file or commit | Remaining risk |
|---|---|---|---|---|
| 1A — Infrastructure Foundation | Complete | 40-key config coverage, healthz, pinned deps, CI, Docker Compose (7 services), Qdrant/MinIO init | `apps/edr/config.py`, `docker-compose.yml`, `.github/workflows/ci.yml` | None functional; `pip-audit` left advisory-only (G11). |
| 1B — RBAC & Identity | Complete | Entra JWT validation, 9 canonical roles, project-source mapping, Node 01 gate | `apps/edr/auth/validator.py`, `apps/edr/rbac/`, `test_rbac.py` | Real-token validation not yet exercised against live Entra (covered by Slice 2/3). |
| 1B.5 — Async Connector Runtime | Complete | Async runner + all 18 nodes `async def run` | `apps/edr/graph/runner.py` | None noted. |
| 1C — n8n Connector Workflows | Complete | 4 real workflows, Header Auth, `$env`-sourced credentials, mailbox allowlist | `n8n/*.json`, `test_connectors.py` | Live webhook execution unproven (Slice 3). |
| 1D — Embedding & Vector Retrieval | Complete | Voyage embeddings, Cohere rerank, tiktoken chunking, per-project Qdrant, Redis cache, RRF | `apps/edr/retrieval/*`, `test_phase1d_*` | Live vector/cache behavior unproven end-to-end (Slice 3/6). |
| 1D-fixup — Audit closure | Complete | Closed C-1..C-8, S-1, L-2, L-5, O-1..O-4 (injection, auth, credential isolation, CVEs) | `CONTROL_PLANE_LOCK.md`, `test_phase1d_fixes.py`, `test_phase1d_security.py` | Residual deferred CVEs tracked under G11. |
| 1E — LLM Nodes | Complete | Haiku/Sonnet nodes, prompt-injection guard (11 patterns), token/cost caps, self-correct, deterministic claim checker, export gating | `apps/edr/llm.py`, nodes 02/03/04/11/12/13/14, `test_phase1e.py` (22) | Langfuse live tracing unverified (G9). |
| 1F — Persistence & Audit | Complete | PostgreSQL audit/review schemas, MinIO staging artifacts, hashed user IDs, RBAC+QG download | `apps/edr/persistence/*`, node 15, `test_phase1f.py` (14) | Backup/restore not rehearsed (Slice 4). |
| 1G — Human Review Gate | Complete | approve/reject/request-revision, self-approval block, write-once publish to `/final`, 409 on finalized | nodes 16/17, `test_phase1g.py` (22) | Real review flow unproven end-to-end (Slice 6). |
| 1H — Evaluation & Hardening | Complete | 64-case golden set, eval runner (pass≥0.95/precision≥0.90 in CI), Arabic PDF font, local load test, pip-audit triage | `apps/edr/evaluation/*`, `test_evaluation.py`/`test_load_test.py`/`test_pdf_arabic.py` | Full Arabic bidi shaping deferred (G10b); pip-audit hard gate deferred (G11). |
| 1I — Frontend Foundation | Complete | Vite+React+TS+Tailwind, design tokens, layout shell, components, role-guarded routing (9 roles); lint+build in CI | `frontend/`, `IMPLEMENTATION_PHASES.md` §1I | Static-only foundation; production delivery handled in Slice 1. |
| 2A — User Chat Workspace | Complete | 9 slices + backend read/status/content/cancel/upload endpoints; local E2E; U-01..U-16 QA | `PHASE_2A_REPORT.md`, `frontend/src/screens/*`, `test_phase2a_backend.py` | Workspace proven only against mocked/local backend, not live integrations (Slice 6). |
| 2B — Admin Control Plane | Complete | 10 slices; 7 backend-integrated admin screens; A-01..A-23 QA; C-1/C-6 isolation preserved | `PHASE_2B_REPORT.md`, `apps/edr/app.py` admin endpoints, `test_phase2b_*.py` | Admin metadata-only invariant must hold through production auth (Slice 2). |
| 2C — UI Hardening & Acceptance | Complete | 54/54 Playwright tests on Chromium/Firefox/WebKit; bundle JS 91.33 kB/120, CSS 6.06 kB/15; a11y/responsive/security-DOM/perf/golden-path | `PHASE_2C_REPORT.md` | Golden-path is fully mocked (`page.route()`); no live UAT yet (Slice 6). |
| 2D Slice 1 — Production frontend delivery path | **Implemented, NOT_LIVE** | Caddy static SPA + reverse proxy for backend routes; `make build-frontend`; `dist` mount; `vite base:'/'` | `PHASE_2D_EXECUTION_PLAN.md` §Slice 1; commits `1edecaa` (feat) + `91f0df1` (governance); CI run `26361596945` ✅ | Delivery path is code-complete and CI-green but **not proven on a live server**; depends on Slices 2–7 for go-live. |

---

## 3. Current Project Rating

Scores are derived strictly from repo evidence (audit verdict in
`CURRENT_PROJECT_STATE.md`, `FEATURE_MATRIX.md`, test counts, CI results) and
deliberately reflect that production is `NOT_LIVE` with five open go-live blockers.

| Dimension | Rating | Evidence-based justification |
|---|---:|---|
| **Overall** | **7/10** | Matches the 2026-05-24 read-only audit (`7/10`, `NOT_GO_LIVE_READY_BUT_HEALTHY`) and the repo's "Overall maturity 7/10". Healthy, well-governed, feature-complete on paper; not production-proven. |
| Architecture | 8/10 | Fixed 18-node LangGraph, clear service boundaries, separated docs/contracts/policies/schemas, single-server Compose profile. (`CURRENT_PROJECT_STATE.md` "Architecture quality 8/10".) |
| Backend | 8/10 | All 18 nodes + endpoints implemented; persistence, review gate, write-once publish; `make test` = 184 passed; `make eval` 64/64 (pass 100%, precision 92.19%). Capped below 9 because live integrations are unproven (G16). |
| Frontend | 8/10 | Phase 2A workspace + 7 Phase 2B admin screens, all backend-integrated; Phase 2C 54/54 cross-browser, bundles within budget. Capped below 9 because production Entra/MSAL auth is missing (G15) and the production delivery path (Slice 1) is not yet live-verified. |
| Security | 7/10 | 9-role RBAC with `_require_admin` 403s, prompt-injection guard, `$env` credential isolation, hashed user IDs, write-once `/final`, admin metadata-only (C-1/C-6). Held at 7 by deferred `pip-audit` advisories (G11, `continue-on-error`), missing production auth (G15), and missing hardening evidence (G18). |
| Testing | 8/10 | 184 integration tests, 64-case golden eval gated in CI, 54/54 Playwright across 3 engines, smoke + local load baseline. Capped below 9 because there is no live-integration or real-UAT coverage (G16/G6-UAT) and promptfoo is deferred. |
| Governance | 9/10 | Machine-readable `agent-state.json`, `check_doc_drift.py` (incl. anchor-currency invariant), `check_ai_context.py`, pre/post-flight, `AGENTS.md` drift rules, protected-file list. One historical Slice-4 drift incident, since fixed with corrective rules; currently clean. |
| **Go-live readiness** | **3/10** | Production `NOT_LIVE`; five go-live blockers open; only Slice 1 of 7 done (and not live-verified). No live integration proof, no backup/restore rehearsal, no production hardening evidence, no real UAT, no go-live approval. |

---

## 4. Remaining Blockers Before Go-Live

These are the audit-recorded blockers (`agent-state.json.latest_read_only_audit.main_blockers`,
`CURRENT_PROJECT_STATE.md` "Remaining", `FEATURE_MATRIX.md` G14–G18). All must be
closed with evidence before a go-live verdict.

1. **Production auth not complete (G15).** No Entra/MSAL frontend login; production
   API calls do not yet use `Authorization: Bearer <token>`; production still
   depends on dev bypass headers (`x-user-role`, `x-user-id`). → Slice 2.
2. **Live integrations not proven (G16).** n8n, Microsoft Graph, SharePoint, Odoo,
   ownCloud, Qdrant, MinIO, PostgreSQL, and Langfuse have no production-like
   end-to-end evidence; connector-failure (degraded vs silent-success) behavior
   unverified against live services. → Slice 3.
3. **Backup/restore rehearsal missing (G17).** No tested PostgreSQL or MinIO backup
   and no restore rehearsal evidence; `disaster_recovery_policy.md` is
   `documented-only` in the feature matrix. → Slice 4.
4. **Production hardening evidence missing (G18).** No evidence for secrets
   rotation, TLS/domain, firewall rules, SSH hardening, or least-privilege
   internal-service exposure review. → Slice 5.
5. **Real UAT flow not proven.** The golden path is validated only with mocked
   backend responses (`page.route()`); no real login → submit → retrieve →
   quality-gate → approve → publish → download against live services. → Slice 6.
6. **Go-live approval not completed.** No final approval record, rollback rehearsal,
   operator runbook sign-off, or monitoring check constituting an explicit
   production cutover authorization. → Slice 7.

Supporting (non-go-live-gating) items: `pip-audit` promotion to a hard CI gate
(G11), live Langfuse dashboard verification (G9), and full Arabic bidi shaping
(G10b) remain deferred and should be tracked but are not go-live blockers.

---

## 5 & 6. Next Phases Plan (Slices 2–7)

**Standing rules for every slice below** (from `AGENTS.md`,
`PHASE_2D_EXECUTION_PLAN.md`, `SHARED_CONTEXT.md`):

- Do not start any slice without explicit user approval in the active session.
- Read `AGENTS.md`, `SHARED_CONTEXT.md`, `AGENT_HANDOFF.md`, `agent-state.json`
  and run `python3 scripts/agent_preflight.py` before editing.
- Run `python3 scripts/check_doc_drift.py` before writing code; stop and fix
  governance if it fails or anchor drift exceeds 3 commits.
- After every pushed commit (not just at closeout), refresh `agent-state.json`,
  `AGENT_HANDOFF.md`, and `SHARED_CONTEXT.md` in the same session.
- Do not weaken `_require_admin` / RBAC, admin metadata-only isolation (C-1/C-6),
  human review, or quality-gate rules.
- Never commit `.env`, `.env.*`, credentials, tokens, raw mailbox/report content,
  backups, generated artifacts, or local runtime state. Sanitize all evidence.
- Do not deploy or go live; completing a slice does not make the service live.

**Governance prerequisite that applies to Slice 2 first (evidence-based):**
`scripts/check_ai_context.py` `ALLOWED_STATUSES` currently ends at
`PHASE_2C_COMPLETE_NOT_LIVE` and has **no Phase 2D statuses**. Setting any
`PHASE_2D_*` status in `agent-state.json` will fail the AI-context check until
that enum (and the corresponding status-specific assertions) is extended. The
first approved Phase 2D implementation slice must extend `ALLOWED_STATUSES` and
the validation logic as part of its governance work.

---

### Slice 2 — Production Auth

- **Objective:** Deliver Entra/MSAL frontend login, send `Authorization: Bearer <token>`
  on production API calls, and remove the production dependency on dev bypass
  headers — while preserving local/CI bypass only where explicitly gated out of production.
- **Allowed work:** MSAL frontend integration; API client bearer-token attachment;
  backend claim extraction / canonical-role mapping verification against real
  Entra tokens; production-only disabling of `x-user-role` / `x-user-id`;
  extending `check_ai_context.py` `ALLOWED_STATUSES` with Phase 2D statuses;
  tests for protected-route behavior; governance-doc refresh.
- **Forbidden work:** Weakening `_require_admin` or RBAC; exposing business
  report content/query text/evidence/credentials in admin responses; committing
  secrets or real tokens; deploying; starting Slice 3; editing untracked `CLAUDE.md`.
- **Acceptance criteria:** Real Entra login works; protected routes reject
  unauthenticated users; role claims map to the 9 canonical roles; production
  does not rely on dev bypass headers; admin remains metadata-only.
- **Required validation commands:**
  ```bash
  python3 scripts/agent_preflight.py
  ruff check .
  python3 -m compileall apps scripts
  make smoke
  make test
  make eval
  cd frontend && npm run lint
  cd frontend && npm run test:ui
  cd frontend && npm run build
  python3 scripts/check_doc_drift.py
  python3 scripts/check_ai_context.py
  python3 scripts/agent_postflight.py --allow-no-evidence
  ```
- **Required evidence:** Entra login proof (sanitized); backend claim→role mapping
  test output; proof production bearer path is active and dev headers are inert in
  production config; CI green for the slice commit.
- **Exit verdict name:** `PHASE_2D_SLICE_2_COMPLETE_NOT_LIVE`

---

### Slice 3 — Live Integration Validation

- **Objective:** Prove every external integration works in a production-like
  environment and that connector failures surface explicit degraded/error states
  rather than silent success: n8n, Microsoft Graph, SharePoint, Odoo, ownCloud,
  Qdrant, MinIO, PostgreSQL, Langfuse.
- **Allowed work:** Read-only/idempotent probes and validation harnesses per
  integration; failure-mode tests (degraded vs silent success); sanitized evidence
  capture in `docs/`; governance-doc refresh. Probes that require live services
  are operator-run on the target environment.
- **Forbidden work:** Changing business workflow behavior; sending service-account
  credentials in webhook bodies; committing live evidence with credentials, tokens,
  raw mailbox or report content; deploying; starting Slice 4.
- **Acceptance criteria:** Each integration has a probe/test; failures log clearly
  with sanitized details; no fake success is possible; service-account credentials
  remain outside webhook bodies and outside git; validation evidence recorded in repo docs.
- **Required validation commands:**
  ```bash
  python3 scripts/agent_preflight.py
  ruff check .
  python3 -m compileall apps scripts
  make smoke
  make test
  make eval
  python3 scripts/check_doc_drift.py
  python3 scripts/check_ai_context.py
  python3 scripts/agent_postflight.py --allow-no-evidence
  # Operator-run on the target environment (not CI):
  make up
  make init-qdrant
  make init-minio
  # Per-integration live probe + sanitized log capture
  ```
- **Required evidence:** Per-integration connector test logs (sanitized);
  explicit degraded/error-state demonstrations; confirmation no credentials are
  in webhook bodies or git; CI green for the slice commit.
- **Exit verdict name:** `PHASE_2D_SLICE_3_COMPLETE_NOT_LIVE`

---

### Slice 4 — Backup and Restore

- **Objective:** Define and test PostgreSQL and MinIO backups, run a restore
  rehearsal, and capture evidence proving audit/report data can be recovered.
- **Allowed work:** Backup/restore scripts and operator documentation; recovery
  point/recovery step definitions and ownership; restore rehearsal on a
  non-production target; sanitized rehearsal evidence; governance-doc refresh.
- **Forbidden work:** Committing backup artifacts, dumps, or `.env`; touching live
  production data destructively; deploying; starting Slice 5.
- **Acceptance criteria:** Restore is tested; recovery steps documented; evidence
  stored in repo docs; backup artifacts are not committed; restored-system evidence
  proves audit/report data recovery.
- **Required validation commands:**
  ```bash
  python3 scripts/agent_preflight.py
  ruff check .
  python3 -m compileall apps scripts
  make smoke
  make test
  python3 scripts/check_doc_drift.py
  python3 scripts/check_ai_context.py
  python3 scripts/agent_postflight.py --allow-no-evidence
  # Operator-run rehearsal (not CI): backup → restore → verify audit/report rows
  ```
- **Required evidence:** Backup command transcript; restore rehearsal log;
  post-restore verification (audit/report data present); recovery-point and
  ownership documentation; confirmation no backup artifacts committed.
- **Exit verdict name:** `PHASE_2D_SLICE_4_COMPLETE_NOT_LIVE`

---

### Slice 5 — Production Hardening

- **Objective:** Produce evidence that production secrets, TLS/domain, firewall,
  SSH, and internal-service exposure are hardened and least-privilege.
- **Allowed work:** Secrets-rotation review; `.env` vs `.env.example` and
  production-requirement review; TLS/domain, firewall-rule, and SSH-hardening
  verification; Redis/Qdrant/MinIO/PostgreSQL/n8n exposure review; sanitized
  hardening checklist in `docs/`; governance-doc refresh.
- **Forbidden work:** Committing secrets or rotated values; exposing internal
  services publicly; deploying; starting Slice 6.
- **Acceptance criteria:** No public internal services; secrets out of git;
  production environment checklist completed; TLS/domain checks pass; firewall and
  SSH hardening evidence documented.
- **Required validation commands:**
  ```bash
  python3 scripts/agent_preflight.py
  ruff check .
  python3 -m compileall apps scripts
  make smoke
  python3 scripts/check_doc_drift.py
  python3 scripts/check_ai_context.py
  python3 scripts/agent_postflight.py --allow-no-evidence
  # Operator-run on the target host (not CI): TLS, firewall, SSH, port-exposure checks
  ```
- **Required evidence:** Completed hardening checklist (sanitized); TLS/domain
  verification; firewall + SSH evidence; internal-service exposure review showing
  nothing public unless intended; CI green for any code/doc commit.
- **Exit verdict name:** `PHASE_2D_SLICE_5_COMPLETE_NOT_LIVE`

---

### Slice 6 — Real UAT Flow

- **Objective:** Execute one real, integrated end-to-end flow against live
  services — real login → submit report → retrieve evidence → quality gate →
  approve → publish → download — with no mocked backend.
- **Allowed work:** Operator/UAT execution against the live environment; sanitized
  screenshot/log capture; defect triage notes; governance-doc refresh. Code
  changes only if a UAT-blocking defect is found and is in scope.
- **Forbidden work:** Using mocked backend responses; committing business-sensitive
  screenshots/logs without redaction; weakening quality-gate/approval rules;
  deploying as the act of going live; starting Slice 7 before UAT passes.
- **Acceptance criteria:** One real integrated flow passes; evidence captured; no
  mocked backend used; quality gate, approval, publish, and download verified
  end-to-end; business-sensitive evidence redacted before commit.
- **Required validation commands:**
  ```bash
  python3 scripts/agent_preflight.py
  make smoke
  make test
  cd frontend && npm run test:ui
  python3 scripts/check_doc_drift.py
  python3 scripts/check_ai_context.py
  python3 scripts/agent_postflight.py --allow-no-evidence
  # Operator-run real UAT (not CI): real login → submit → retrieve → QG → approve → publish → download
  ```
- **Required evidence:** Redacted UAT screenshots/logs for each step; proof no mocks
  were used; quality-gate, approval, publish, and download results; CI green for any commit.
- **Exit verdict name:** `PHASE_2D_SLICE_6_COMPLETE_NOT_LIVE`

---

### Slice 7 — Go-Live Gate

- **Objective:** Assemble the final go-live gate — approval docs, rollback plan,
  operator runbook, monitoring check — and verify all prior evidence is complete.
  Completing this slice still does **not** make the service live; live requires a
  separate explicit go-live approval and an authorized operator cutover.
- **Allowed work:** Final approval documentation; rollback plan + rehearsal;
  operator runbook completion; monitoring check; verification that CI, UAT,
  security, backup/restore, and integration evidence (Slices 2–6) are complete;
  defining the explicit production cutover approval record; governance-doc refresh.
- **Forbidden work:** Performing the production cutover or going live without an
  explicit, separate go-live approval; committing secrets; bypassing any prior
  slice's evidence requirement.
- **Acceptance criteria:** Go-live approval doc prepared; rollback verified;
  monitoring checks pass; operator runbook complete; all Slice 2–6 evidence present;
  production remains `NOT_LIVE` until explicit go-live approval is given.
- **Required validation commands:**
  ```bash
  python3 scripts/agent_preflight.py
  make smoke
  make test
  make eval
  cd frontend && npm run lint
  cd frontend && npm run build
  cd frontend && npm run test:ui
  python3 scripts/check_doc_drift.py
  python3 scripts/check_ai_context.py
  python3 scripts/agent_postflight.py --allow-no-evidence
  ```
- **Required evidence:** Final approval record; rollback rehearsal log; completed
  operator runbook; monitoring-check result; an evidence index cross-linking Slices
  2–6; CI green for the gate commit.
- **Exit verdict name:** `PHASE_2D_GO_LIVE_GATE_PASSED_NOT_LIVE_PENDING_OPERATOR_CUTOVER`

---

## 7. Final Recommendation

CI for `91f0df1` is green (run `26361596945`, conclusion `success`, both jobs
passing), the documentation-drift and AI-context checks are clean, the working
tree is clean apart from the intentionally-untouched untracked `CLAUDE.md`, and
all required evidence files were read and are internally consistent. There is no
repo drift and no missing evidence.

**Historical recommendation at `91f0df1`:** `CONTINUE_TO_PHASE_2D_SLICE_2_AFTER_CI_GREEN`

**Current re-audit recommendation at `4584501`:**
`FIX_LATEST_HEAD_AI_CONTEXT_CI_FAILURE_BEFORE_ANY_NEW_SLICE`

Slices 1-5 are implemented, but the latest pushed HEAD CI is red in the
`AI context check` step. The next valid work is to fix that exact governance
failure and obtain a green CI result. After CI is green, Slice 6 (Real UAT
Flow) is the next plan-defined slice and still requires explicit user approval
in the active session. This document authorizes no implementation, deployment,
production cutover, or go-live.
