# Phase 2D Execution Plan — Production Readiness and Go-Live Hardening

## Current Verified Baseline

- **HEAD:** `538dd2e04ad1f12fa3ccaf9b8e04952727628042`
- **CI run:** `26359168106` — success
- **Current status:** `PHASE_2C_COMPLETE_NOT_LIVE_AUDIT_RECONCILED_CI_GREEN`
- **Production status:** `NOT_LIVE`
- **Go-live status:** `NOT READY`
- **Phase 2D approval gate:** Phase 2D is the next allowed phase, but implementation is blocked until explicit user approval in the current session.

This plan is a planning artifact only. It does not authorize implementation,
deployment, production cutover, or go-live.

## Objective

Phase 2D exists to move DecisionCenter from healthy-not-live to
production-ready. The phase must close the known go-live blockers, prove the
real production integration path, collect operator/security evidence, and
define the final go-live gate.

Completing Phase 2D must not automatically make the service live. Production
remains `NOT_LIVE` until a separate explicit go-live approval is given and an
authorized operator performs the deployment/cutover steps.

## Out Of Scope

- No deployment without explicit approval.
- No go-live without explicit approval.
- No business behavior redesign.
- No Phase 3 work.
- No speculative features.
- No weakening RBAC, admin isolation, evidence rules, human review, or quality-gate rules.
- No production secret edits in git.

## Main Blockers To Resolve

- Missing production frontend delivery path.
- Missing Entra/MSAL frontend auth and Bearer-token API calls.
- Live integrations not proven.
- Backup/restore rehearsal missing.
- Production hardening evidence missing.

## Slice Breakdown

### Slice 1 — Production frontend delivery path

**Status:** ✅ Implemented

**Decision**

- **Path:** Caddy static-file serving (SPA) + explicit reverse-proxy for backend routes.
- **Rationale:** The backend does not use an `/api` prefix, so we cannot use a simple
  `/api → backend` rule without changing backend business logic (forbidden in Slice 1).
  Hash-based routing means `try_files {path} /index.html` is safe — every frontend
  route sends `GET /` to the server.
- **Build:** `make build-frontend` (or `cd frontend && npm ci && npm run build`).
- **Serve:** `make up` mounts `./frontend/dist` into the Caddy container at
  `/usr/share/caddy` and serves it as a static SPA.
- **Rollback:** Re-build the previous commit's frontend and restart Caddy
  (`docker compose restart caddy`) or revert to the previous `frontend/dist`
  snapshot.
- **Smoke-check:** `curl -f http://localhost/healthz` (backend proxy) and
  `curl -f http://localhost/` (should return HTML with `<div id="root">`).

**Changes**

- `Caddyfile` — added explicit `handle` blocks for `/healthz*`, `/reports*`,
  `/workspace*`, `/upload*`, `/admin*` proxying to `app:8000`; added static
  `file_server` with SPA fallback and immutable-asset cache headers.
- `docker-compose.yml` — mounted `./frontend/dist:/usr/share/caddy:ro` into the
  Caddy service.
- `frontend/vite.config.ts` — added explicit `base: '/'` with production comment.
- `Makefile` — added `build-frontend` target.

**Acceptance**

- [x] Frontend build is served correctly through the selected production path.
- [x] Routing works on refresh and direct URL entry.
- [x] No dev-only assumptions are required for production frontend delivery.
- [x] The production delivery decision and verification evidence are recorded in repo docs.

### Slice 2 — Production auth

**Status:** ✅ Implemented (2026-05-25) — Entra/MSAL frontend login, Bearer-token
API calls, `GET /me` canonical-role source, and production rejection of dev bypass
headers. Local/CI keep the RoleSwitcher bypass. Real Entra login is operator-verified.
Production remains `NOT_LIVE`. See `docs/execution/PHASE_2D_SLICE_2_REPORT.md`.

**Scope**

- Implement Entra/MSAL frontend login.
- Send `Authorization: Bearer <token>` on API calls in production.
- Remove production dependency on dev bypass headers (`x-user-role`, `x-user-id`).
- Preserve local/CI bypass behavior only where explicitly allowed and blocked from production.
- Verify backend claim extraction, canonical role mapping, and protected-route behavior against real Entra tokens.

**Acceptance**

- Real Entra login works.
- Protected routes reject unauthenticated users.
- Role claims map correctly to the nine canonical roles.
- Production does not rely on dev bypass headers.
- Admin remains metadata-only and cannot access business report content.

### Slice 3 — Live integration validation

**Scope**

- Validate n8n.
- Validate Microsoft Graph.
- Validate SharePoint.
- Validate Odoo.
- Validate ownCloud.
- Validate Qdrant.
- Validate MinIO.
- Validate PostgreSQL.
- Validate Langfuse.
- Confirm connector failures return explicit degraded/error states rather than silent success.

**Acceptance**

- Each integration has a probe/test.
- Failures are logged clearly with sanitized details.
- No fake success is possible.
- Validation evidence is recorded in repo docs.
- Service-account credentials remain outside webhook bodies and outside git.

### Slice 4 — Backup, restore, and data safety

**Scope**

- Define and test PostgreSQL backup.
- Define and test MinIO backup.
- Run a restore rehearsal.
- Capture audit evidence for backup and restore operations.
- Document recovery point expectations, recovery steps, and operator ownership.

**Acceptance**

- Restore is tested.
- Recovery steps are documented.
- Evidence is stored in repo docs.
- Backup artifacts are not committed to git.
- Restored system evidence proves audit/report data can be recovered.

### Slice 5 — Production hardening

**Scope**

- Rotate or confirm rotation of production secrets.
- Review environment variables against `.env.example` and production requirements.
- Verify TLS/domain configuration.
- Verify firewall rules.
- Verify SSH hardening.
- Review Redis, Qdrant, MinIO, PostgreSQL, and n8n exposure.
- Confirm no internal service is publicly reachable unless explicitly intended.

**Acceptance**

- No public internal services.
- Secrets are out of git.
- Production environment checklist is completed.
- TLS/domain checks pass.
- Firewall and SSH hardening evidence is documented.

### Slice 6 — Real UAT flow

**Scope**

- Use real login.
- Submit a real report request.
- Retrieve evidence from live integrations.
- Run quality gate.
- Approve through the human review path.
- Publish final artifacts.
- Download final output.
- Capture evidence without using mocked backend responses.

**Acceptance**

- One real integrated flow passes.
- Evidence is captured.
- No mocked backend is used.
- Quality gate, approval, publish, and download behavior are verified end to end.
- Business-sensitive screenshots/logs are redacted before being committed to docs.

### Slice 7 — Go-live gate

**Scope**

- Prepare final approval docs.
- Prepare rollback plan.
- Prepare operator runbook.
- Perform monitoring check.
- Verify CI, UAT, security, backup/restore, and integration evidence are complete.
- Define the explicit production cutover approval record.

**Acceptance**

- Go-live approval passes.
- Rollback is verified.
- Monitoring checks pass.
- Operator runbook is complete.
- Production remains `NOT_LIVE` until explicit go-live approval.

## Required Validation Commands

Run these before claiming Phase 2D readiness or go-live readiness:

```bash
python3 scripts/check_doc_drift.py
python3 scripts/check_ai_context.py
python3 scripts/agent_postflight.py --allow-no-evidence
make smoke
make test
make eval
cd frontend && npm run lint
cd frontend && npm run build
cd frontend && npm run test:ui
```

Additional validation may be required by individual slices, especially for live
integration probes, production auth, backup/restore rehearsal, and UAT.

## Evidence Required Before Go-Live

- CI green.
- Frontend production URL proof.
- Entra login proof.
- Connector test logs.
- Backup/restore logs.
- UAT screenshots/logs.
- Security hardening checklist.
- Rollback rehearsal.
- Approval record.

All evidence committed to the repository must be sanitized. Do not commit
credentials, raw tokens, private mailbox content, report content that is not
approved for documentation, sensitive evidence excerpts, `.env`, generated
artifacts, backups, or local runtime state.

## Rules For The Next AI

- Read this file first.
- Read `AGENTS.md` and `docs/ai/agent-state.json` before edits.
- Run preflight before work.
- Update governance docs after every slice.
- Do not rely on chat history.
- Stop if drift checks fail.
- Do not go live without explicit approval.
- Do not start Phase 2D implementation unless the user explicitly approves it in the current session.
- Keep each slice narrow and auditable.
- Prefer docs/scripts/tests for validation evidence unless a slice explicitly requires application changes.
- Never touch untracked local files such as `CLAUDE.md` unless the user explicitly instructs it.

PHASE_2D_PLAN_CREATED_IMPLEMENTATION_NOT_STARTED
