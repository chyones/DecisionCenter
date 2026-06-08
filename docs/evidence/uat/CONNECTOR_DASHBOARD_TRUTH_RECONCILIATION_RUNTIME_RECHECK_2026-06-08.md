# Connector Dashboard Truth Reconciliation — Runtime Recheck

**Date:** 2026-06-08
**Verdict:** `CONNECTOR_DASHBOARD_TRUTH_RECONCILED_PENDING_ENTRA_TOKEN_NOT_LIVE`
**Production status:** NOT_LIVE
**HEAD:** `029de7c1a63c7f1b4e47abe5cf91c892743d46db`
**Branch:** `main`

---

## 1. Dirty Worktree Summary

Commands run:

```bash
git status --short --branch
git diff --name-only
git log --oneline -5
```

Recent commits:

```text
029de7c feat: add exact Odoo SharePoint source mapping sync
fc54c64 fix: reconcile Phase 2D blockers before UAT
450ecc8 Merge pull request #2 from chyones/fix/entra-auth-version-agnostic
d49e51b fix(auth): accept Entra v1.0 and v2.0 tokens; add live validation
b361b40 feat(health): mirror connector truth in System Health (no false green)
```

Connector-dashboard task-owned changes:

- `apps/edr/admin/connector_status.py`
- `apps/edr/app.py` (connector-health enum mapping only for this task)
- `apps/edr/tests/integration/test_connector_truth.py`
- `frontend/src/api/types.ts`
- `frontend/src/screens/ConnectorTruthPanel.tsx`
- `docs/evidence/uat/CONNECTOR_DASHBOARD_TRUTH_RECONCILIATION_2026-06-08.md`
- `docs/evidence/uat/CONNECTOR_DASHBOARD_TRUTH_RECONCILIATION_RUNTIME_RECHECK_2026-06-08.md`

Pre-existing dirty changes present before this closeout:

- `apps/edr/graph/node_08_odoo.py`
- `apps/edr/graph/node_11_self_correct.py`
- `apps/edr/persistence/postgres_store.py`
- `apps/edr/rbac/project_mapping.py`
- `apps/edr/tests/integration/test_odoo_sharepoint_sync.py`
- `apps/edr/tests/integration/test_phase1d_fixes.py`
- `apps/edr/tests/integration/test_phase2b_source_mapping.py`
- `apps/edr/tests/integration/test_rbac.py`
- `docs/config/project_source_mapping.json`
- `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
- `frontend/src/api/index.ts`
- `frontend/src/screens/AdminSourceMappingScreen.tsx`
- `apps/edr/admin/email_group_enrichment.py`
- `apps/edr/tests/integration/test_email_group_enrichment.py`
- Existing source-mapping / email-group evidence files under `docs/evidence/uat/`.

No unrelated dirty changes were reverted.

---

## 2. Validation

| Command | Result |
|---|---|
| `ruff check .` | PASS |
| `python3 -m compileall apps scripts` | PASS |
| `.venv/bin/python -m pytest apps/edr/tests/integration/test_connector_truth.py -q` | PASS — 31 passed |
| `.venv/bin/python -m pytest apps/edr/tests/integration/test_email_group_enrichment.py -q` | PASS — 30 passed |
| `.venv/bin/python -m pytest apps/edr/tests/integration/test_phase2b_source_mapping.py -q` | PASS — 68 passed |
| `npm --prefix frontend run lint` | PASS |
| `npm --prefix frontend run build` | PASS — existing Vite large-chunk warning |
| `python3 scripts/check_doc_drift.py` | PASS — clean |
| `python3 scripts/check_ai_context.py` | PASS — clean |
| `python3 scripts/agent_postflight.py --allow-no-evidence` | PASS — clean |

The frontend production bundle contains the `Verified from evidence` label, so
no Caddy image rebuild was required. Caddy serves `frontend/dist` by bind mount.

---

## 3. Runtime Rebuild

Commands run:

```bash
docker compose build app
docker compose up -d app
docker compose ps
curl -s http://127.0.0.1:8000/healthz | jq
```

Result:

- `docker compose build app`: PASS, image `decisioncenter-app:latest` built.
- `docker compose up -d app`: PASS, app container recreated.
- `decisioncenter-app-1`: healthy.
- Rebuilt app image digest: `sha256:64012a6e2890f2ce51dc05df7171cba38470c47b55fb1b15bd9c359268e2ecae`.

`/healthz` after rebuild:

```json
{
  "status": "ok",
  "workflow_nodes": 18,
  "postgres": "ok",
  "redis": "ok",
  "qdrant": "ok",
  "minio": "ok"
}
```

Production remains NOT_LIVE. No Gate 4, Gate 5, UAT, Slice 7, or LIVE work was
started.

---

## 4. Connector Truth After Rebuild

Connector truth was checked from the rebuilt app runtime using the same
`apps.edr.admin.connector_status.build_report(run_probes=True)` service that
backs the admin connector truth endpoint.

| Connector | State | Data source | Sample count | Blocks |
|---|---|---|---:|---|
| PostgreSQL | `LIVE_OK` | live | — | no |
| Redis | `LIVE_OK` | live | — | no |
| Qdrant | `LIVE_OK` | live | — | no |
| MinIO | `LIVE_OK` | live | — | no |
| Cloudflare Tunnel / public edge | `LIVE_OK` | live | — | no |
| Caddy routing | `LIVE_OK` | live | — | no |
| Microsoft Entra authentication | `CONFIGURED_NOT_TESTED` | none | — | yes |
| n8n webhook | `LIVE_OK` | live | — | no |
| SharePoint | `VERIFIED_FROM_EVIDENCE` | evidence | 2 | no |
| Email / Microsoft Graph | `VERIFIED_FROM_EVIDENCE` | evidence | 35 | no |
| ownCloud | `DISABLED` | none | — | no |
| Odoo | `LIVE_OK` | live | 100 | no |
| Anthropic | `NOT_CONFIGURED` | none | — | yes |
| Voyage | `NOT_CONFIGURED` | none | — | yes |
| Cohere | `NOT_CONFIGURED` | none | — | yes |

Readiness:

```text
PARTIAL_READY
core platform, edge and login are up; pending live validation:
entra_auth, anthropic, voyage, cohere
```

Report generation:

```text
BLOCKED
provider keys missing — ANTHROPIC_API_KEY not set
```

Blocking list:

```text
entra_auth, anthropic, voyage, cohere
```

---

## 5. Required Proof Points

### Odoo

Odoo read-only probe after rebuild:

- `LIVE_OK`
- `sample_count=100`
- Evidence summary: Odoo webhook returned 100 Odoo evidence items.
- No HTTP 404.
- No Odoo writes performed.

### SharePoint

SharePoint is no longer `CONFIGURED_NOT_TESTED`.

- State: `VERIFIED_FROM_EVIDENCE`
- Evidence: current `source_mappings` verify SharePoint site/drive coordinates
  for PRJ-001 and PRJ-002.
- Sample count: 2 projects.
- No SharePoint writes performed.

### Microsoft Graph / Email

Email / Microsoft Graph is no longer `CONFIGURED_NOT_TESTED`.

- State: `VERIFIED_FROM_EVIDENCE`
- Evidence: current `source_mappings` verify Microsoft group mailbox/member
  enrichment for PRJ-001 and PRJ-002.
- Sample count: 35 members total.
- PRJ-001: 17 members.
- PRJ-002: 18 members.
- No Microsoft Graph writes performed.

### ownCloud

ownCloud remains intentionally disabled.

- State: `DISABLED`
- `configured=False`
- `blocks_go_live=False`
- Evidence: ownCloud is disabled and not part of any project's enabled sources.

### AI Providers

AI providers remain intentionally not configured.

- Anthropic: `NOT_CONFIGURED`
- Voyage: `NOT_CONFIGURED`
- Cohere: `NOT_CONFIGURED`
- Report generation remains `BLOCKED`.

### Entra

Entra remains configured but not freshly validated.

- State: `CONFIGURED_NOT_TESTED`
- Evidence: OIDC discovery reachable; no live user token validated yet.
- Candidate token file `/root/dc_token.txt` exists but is expired.
- The token was not printed.
- No fresh token validation was run.

---

## Final Verdict

```text
CONNECTOR_DASHBOARD_TRUTH_RECONCILED_PENDING_ENTRA_TOKEN_NOT_LIVE
```

The rebuilt runtime now reflects the connector dashboard truth reconciliation.
Odoo is live through the restored read-only n8n webhook, SharePoint and Email /
Microsoft Graph are verified from current persisted evidence without fake
`LIVE_OK`, ownCloud remains disabled, AI providers remain not configured, and
Entra is the remaining connector-truth blocker pending a fresh user-token
validation. Production remains NOT_LIVE.
