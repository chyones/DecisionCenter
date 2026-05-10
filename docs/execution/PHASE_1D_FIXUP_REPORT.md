# Phase 1D-Fixup Verification Report

## Scope

- Branch: `main`
- Starting commit: `c9ed521`
- Ending commit: `cda49987c8f728f8586d8025f421cf7dc7ca30b5`
- Production status: `NOT_LIVE`
- Final readiness decision: `READY_FOR_PHASE_1E_NOT_LIVE`

This report verifies the Phase 1D-fixup audit closure only. It does not start
Phase 1E and does not make the service live.

## Fixed Audit Issues

- `C-1`: Qdrant collection naming aligned between runtime `EvidenceStore` and `scripts/init_qdrant.py`.
- `C-2`: Odoo search domains are built with `json.dumps` to prevent project-code injection.
- `C-3`: All n8n webhook nodes require Header Auth.
- `C-4`: Email mailbox allowlist enforced in Python before external calls and again inside n8n.
- `C-6`: ownCloud and Odoo service-account credentials removed from webhook payloads and read by n8n from environment variables.
- `C-7`: JWT and cryptography dependencies upgraded to close known advisories.
- `C-8`: Node 14 exports only when `quality_gate == "passed"` and a report payload exists.
- `L-5`: Evidence metadata accepts scalar lists for fields such as email recipients.
- `R-4`: Entra JWT validator caches JWKS client state and surfaces all role claims.
- `O-1`: `POST /reports/staging` no longer returns misleading `stubbed` status and now uses UUID request IDs.
- `O-2`: Caddy configuration supports `PUBLIC_HOSTNAME`, TLS, HSTS, and local `:80` fallback.
- `O-3`: Internal service exposure tightened; Qdrant and n8n are internal-only, while app and MinIO bind to localhost.
- `O-4`: Evaluation messaging corrected from Phase 1G to Phase 1H.

## Files Changed Summary

Phase 1D-fixup changed 29 tracked files between `c9ed521` and `cda4998`:

- Environment and CI: `.env.example`, `.github/workflows/ci.yml`, `pyproject.toml`.
- Runtime configuration and edge: `docker-compose.yml`, `Caddyfile`, `apps/edr/config.py`, `apps/edr/app.py`.
- Auth and graph nodes: `apps/edr/auth/validator.py`, `apps/edr/graph/node_06_owncloud.py`, `apps/edr/graph/node_07_email.py`, `apps/edr/graph/node_08_odoo.py`, `apps/edr/graph/node_14_compose_md.py`.
- Schemas and retrieval support: `apps/edr/schemas/evidence.py`, `scripts/init_qdrant.py`.
- n8n workflows and operator docs: `n8n/sharepoint_search.json`, `n8n/email_search.json`, `n8n/owncloud_list.json`, `n8n/odoo_read.json`, `n8n/README.md`.
- Tests and drift guard: `apps/edr/tests/integration/test_phase1d_fixes.py`, `apps/edr/tests/integration/test_phase1d_security.py`, `apps/edr/tests/integration/test_doc_drift.py`, `scripts/check_doc_drift.py`.
- Project state docs: `README.md`, `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/admin/FEATURE_MATRIX.md`, `docs/execution/CURRENT_PROJECT_STATE.md`, `docs/execution/IMPLEMENTATION_PHASES.md`.

## Tests Executed

- `git status --short --branch`
- `git rev-parse HEAD`
- `make smoke`
- `make test`
- `python3 -m pytest -q`
- `ruff check .`
- `python3 -m compileall apps scripts`
- `python3 scripts/check_doc_drift.py`

Local Docker verification used an ignored `.env` copied from `.env.example`
with placeholder values only. No secrets were committed. Because
`vt360_minio` already owns localhost ports `9000` and `9001` on this shared
host, the local verification stack used a temporary Compose override to bind
DecisionCenter MinIO to localhost ports `9002` and `9003`. The application
still used the internal Compose endpoint `minio:9000`.

## Test Results

- `make smoke`: 2 passed.
- `make test`: 62 passed.
- `python3 -m pytest -q`: 62 passed.
- `ruff check .`: clean.
- `python3 -m compileall apps scripts`: clean.
- `python3 scripts/check_doc_drift.py`: clean.
- Config coverage: 40/40.
- GitHub Actions: CI for `cda49987c8f728f8586d8025f421cf7dc7ca30b5` passed.

## Security Checks Executed

- `apps/edr/tests/integration/test_phase1d_security.py`
- CI `pip-audit (advisory only)` step
- n8n workflow Header Auth checks
- ownCloud and Odoo credential-leakage regression checks
- mailbox allowlist regression checks
- Odoo domain injection regression check

## Documentation Files Updated

- `README.md`
- `docs/admin/CONTROL_PLANE_LOCK.md`
- `docs/admin/FEATURE_MATRIX.md`
- `docs/execution/CURRENT_PROJECT_STATE.md`
- `docs/execution/IMPLEMENTATION_PHASES.md`
- `n8n/README.md`
- `docs/execution/PHASE_1D_FIXUP_REPORT.md`

## Remaining Known Issues

- Production is `NOT_LIVE`; pushing to `origin/main` does not deploy the service.
- The production server still requires operator SSH, `git pull origin main`,
  `make up`, and `make smoke`.
- The server `.env` must provide `PUBLIC_HOSTNAME`, `OWNCLOUD_USERNAME`,
  `OWNCLOUD_PASSWORD`, `N8N_WEBHOOK_TOKEN`, and existing Odoo, Qdrant, Redis,
  Postgres, and Entra settings before `make up`.
- n8n must have a Webhook Header Auth credential configured as
  `Authorization: Bearer <N8N_WEBHOOK_TOKEN>`.
- On this local host, `python3` is available and `python` is not. Local
  verification used `python3` commands.

## Readiness

`READY_FOR_PHASE_1E_NOT_LIVE`
