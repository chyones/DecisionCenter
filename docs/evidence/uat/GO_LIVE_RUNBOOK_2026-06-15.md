# DecisionCenter — Go-Live Runbook (2026-06-15)

**System status: NOT_LIVE.** This runbook lists the exact remaining steps to take
DecisionCenter live. It does **not** flip LIVE — the final gate is an explicit signed
approval (Step 5). No secrets in this file.

## State at time of writing (live-verified 2026-06-15)

Already done — no action needed:

| Area | State |
|---|---|
| App deployed | Healthy. `APP_ENV=production`; `/healthz` → postgres/redis/qdrant/minio all `ok`, 18 nodes |
| Public HTTPS edge | LIVE — `https://vantage.elrace.com/healthz` → 200 (cloudflared tunnel up) |
| Secret rotation | `POSTGRES_PASSWORD` + `MINIO_SECRET_KEY` rotated off `change-me`; app boots under fail-fast |
| Generation | DeepSeek, `LLM_PROVIDER=deepseek`, 5/5 HTTP 200, no fallback, ~$0.003/report |
| Entra v2 token | Resolved at source (`requestedAccessTokenVersion=2`) + validator accepts v1/v2 |

Descoped / not gates: email/mail (group-mailbox design), Odoo financial/cost (deferred),
ownCloud (disabled), Langfuse (optional), empty `ANTHROPIC_API_KEY` (DeepSeek in use).

---

## Step 1 — Rebuild the app to bake the Odoo evidence fix

**Why:** `apps/edr/graph/node_08_odoo.py` (and `node_11_self_correct.py`) queried Odoo with a
nonexistent field (`project_external_id`) and nonexistent columns (`budget`, `actual_cost`),
so reports got **zero Odoo evidence**. Fixed in commit on `main` (this session): query by the
real `id` column with a name fallback, and request only valid columns
(`name, date_start, date, user_id, partner_id`). Helper: `build_project_query()` in
`apps/edr/connectors/odoo.py`.

```bash
cd /root/DecisionCenter
docker compose up -d --build app
```

Verify after rebuild (Odoo must be responsive — see note):
```bash
curl -s http://127.0.0.1:8000/healthz   # expect status ok, 18 nodes
```

> **Odoo latency note:** during this session the Odoo upstream (`erp.elrace.com`) became
> intermittently slow — `/webhook/odoo-read` calls that returned in <1s earlier began timing
> out, while n8n `/healthz` stayed 200. The corrected domain `[["id","=",14602]]` was
> live-proven to return 1 item earlier the same day; the wrong domain returned 0. If the
> Odoo probe in Step 4 times out, retry when the ERP is responsive — it is an upstream
> condition, not a code defect.

---

## Step 2 — Fix the n8n SharePoint/email webhook credential + routing

**Why:** the n8n `import:workflow` CLI strips the `Receive Request` `httpHeaderAuth` credential
every time, and a stale `pathLength=NULL` webhook row corrupts in-memory routing — so
`/webhook/sharepoint-search` returns HTTP 500. The Graph node fix (`authentication:none` +
OData quoting) is already live in the n8n DB; only the webhook credential is missing. Full
diagnosis: `N8N_WEBHOOK_HTTP500_DIAGNOSIS_2026-06-15.md`.

```bash
cd /root/DecisionCenter
python scripts/bind_n8n_webhook_auth.py     # re-attaches the header-auth credential in the n8n DB
docker compose restart n8n                  # reload workflows + clear the routing corruption
```

`bind_n8n_webhook_auth.py` is idempotent and writes only the credential reference for the
`Receive Request` nodes (same pattern as the working `odoo_read` workflow). It prints a
verification line per workflow (`BOUND` / `already bound`).

Verify (with a real Graph Bearer token in the body):
```
POST http://172.22.0.5:5678/webhook/sharepoint-search
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
Body: { site_id, drive_id, query:"guard room", project_code:"PRJ-001", access_token:<graph token> }
→ expect HTTP 200, non-empty {"evidence":[...]}   (currently HTTP 500)
```

---

## Step 3 — Entra user-token smoke through the deployed auth surface

**Why:** `/reports/staging` requires a real **user** bearer token; it cannot be minted
head-lessly (the API app exposes only User-assignable roles). Obtain one via interactive
Entra login (device-code / SPA), then:

```bash
cd /root/DecisionCenter
python scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token "<user access token>"
```

Expect: token validates (issuer/aud accepted), role resolves to `admin` or `executive`.

---

## Step 4 — One clean end-to-end UAT (PRJ-001)

Depends on Steps 1–3. Generate a single report for PRJ-001 through the deployed API with the
user token, and confirm:
- the report's evidence array contains **both** `sharepoint` and `odoo` source types;
- generation is DeepSeek-served (no `FALLBACK_DETERMINISTIC`);
- the quality gate passes;
- approve → publish → download all succeed.

Capture the redacted run as `docs/evidence/uat/UAT_RUN_2026-06-15.md` (I can help write this
once the run output is available).

---

## Step 5 — Explicit go-live approval (final gate)

Sign the approval block in `docs/evidence/uat/SLICE7_GO_LIVE_READINESS_2026-06-15.md`:
```
Phase 2D Go-Live Approval
  Approved by: ____________  Role: ________  Date: ________
  UAT_RUN reference: UAT_RUN_2026-06-15.md   Commit: ________
  I authorise production go-live.   Signature: ________________
```

Until Steps 1–4 are closed **and** this block is signed by an authorised operator, the system
remains **NOT_LIVE**. Approval is never inferred from any other action.

---

## Quick checklist

- [ ] Step 1 — `docker compose up -d --build app` (Odoo evidence fix live)
- [ ] Step 2 — `bind_n8n_webhook_auth.py` + `docker compose restart n8n`; SharePoint webhook → 200
- [ ] Step 3 — `validate_entra_auth.py` with a real user token → valid
- [ ] Step 4 — clean PRJ-001 report with SharePoint + Odoo evidence → `UAT_RUN_2026-06-15.md`
- [ ] Step 5 — sign the approval block → flip to LIVE
