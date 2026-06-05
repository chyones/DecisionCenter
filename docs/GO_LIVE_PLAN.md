# DecisionCenter — Go-Live Reminder Plan
**Updated:** 2026-06-04  
**Status:** NOT_LIVE — code ready, operator actions pending  
**URL:** https://vantage.elrace.com

---

## What's Already Done (Don't Redo)

| # | Item | Evidence |
|---|------|----------|
| ✅ | Entra auth v1/v2 fix — live validated | PR #2 merged → `450ecc8`, `/me` returns `role=admin` |
| ✅ | Owner-operator governance model | Merged to `main`, admin+executive = full owners |
| ✅ | Role resolution fallback (`/me` → `/workspace/context`) | Deployed via frontend dist, no docker needed |
| ✅ | Connector truth model | Frontend live; backend staged (needs rebuild) |
| ✅ | n8n workflows imported + active | sharepoint-search, email-search, owncloud-list |
| ✅ | Cloudflare tunnel created | ID `f39448f2-...`, DNS resolves — HTTP 530 only (no connector running) |
| ✅ | `APP_ENV=production` set | Entra JWT auth enforced, no dev bypass |

---

## Step-by-Step Go-Live Plan

### Step 1 — Fill in `.env` secrets
> `N8N_WEBHOOK_TOKEN` and `ENTRA_CLIENT_SECRET` are already present. Add these remaining empty values:

```
ANTHROPIC_API_KEY=...          # report generation — get from console.anthropic.com
VOYAGE_API_KEY=...             # embeddings — get from dash.voyageai.com
COHERE_API_KEY=...             # reranking — get from dashboard.cohere.com
OWNCLOUD_USERNAME=...          # ownCloud connector
OWNCLOUD_PASSWORD=...          # ownCloud connector
CLOUDFLARED_TUNNEL_TOKEN=...   # get from Cloudflare Zero Trust dashboard → tunnel f39448f2
```

**How to get the tunnel token:**
Cloudflare Zero Trust → Networks → Tunnels → `decisioncenter` → Configure → copy the token value.

---

### Step 2 — Azure Portal (Entra) — COMPLETED (2026-06-04)

- [x] **2a. SPA redirect URI** — confirmed `https://vantage.elrace.com`
- [x] **2b. App Roles** — `admin` + `executive` defined and users assigned
- [x] **2c. Users assigned** — ch.yones = admin; other owners = executive
- [x] **2d. Admin consent** — granted for `Files.Read.All`, `Mail.Read`

---

### Step 3 — n8n credential binding — COMPLETED (2026-06-04)

> Applied by AI via `scripts/bind_n8n_webhook_auth.py`. No n8n UI required.
> Architecture finding: Graph credentials are NOT stored in n8n — the app backend
> acquires a Graph token via client credentials and passes it in the request body.

- [x] **3a. Microsoft Graph OAuth2 credential in n8n**: NOT NEEDED — pass-through architecture
- [x] **3b. Header Auth bound to Receive Request** in `sharepoint_search`, `email_search`, `owncloud_list`
- [x] **3c. Graph access token acquisition**: implemented in `apps/edr/connectors/graph_token.py`
- [x] **3d. Token injected into n8n payloads**: `sharepoint.py` and `email.py` updated

---

### Step 4 — Rebuild and Start Containers
> Run from `/root/DecisionCenter`:

```bash
# Rebuild app (bakes new .env values + backend connector truth code)
docker compose up -d --build app

# Start the Cloudflare tunnel (was staged but never started)
docker compose up -d cloudflared

# Verify all containers running
docker compose ps
```

> ⚠️ Never run `docker compose up` on the base file alone without the override — Caddy would bind to host ports 80/443 which are owned by vt360_caddy. The override (`docker-compose.override.yml`) resets Caddy to no host ports. Always use `docker compose up -d <service>`.

---

### Step 5 — Validate Authentication End-to-End
> Get a fresh token (sign in via the app at https://vantage.elrace.com) and save to `/root/dc_token.txt` (chmod 600), then:

```bash
python scripts/validate_entra_auth.py --base-url https://vantage.elrace.com < /root/dc_token.txt
```

Expected output: `PASS — role=admin`.

---

### Step 6 — Slice 6 UAT
```bash
python3 scripts/uat_check.py
```
Then do a manual end-to-end test:
1. Sign in at https://vantage.elrace.com → should show `admin` role
2. Admin panel accessible at `/admin`
3. Connector truth panel shows real states (not all NOT_CONFIGURED)
4. Generate a test report → should call Anthropic API and return a result
5. Approve/publish the report (self-approval OK under owner-operator model)

---

### Step 7 — Go-Live Approval (Slice 7)
When UAT passes:
- [ ] Confirm no open critical issues
- [ ] Write explicit go-live approval note (can be a commit message or a file in `docs/approvals/`)
- [ ] Announce to team: `vantage.elrace.com` is LIVE

---

## Quick Reference — Key Values

| Item | Value |
|------|-------|
| Production URL | https://vantage.elrace.com |
| Cloudflare tunnel name | `decisioncenter` |
| Cloudflare tunnel ID | `f39448f2-1898-41af-a055-fc98439088e1` |
| Entra tenant | `14a72467-3f25-4572-a535-3d5eddb00cc5` |
| Entra SPA client | `97519dfa-650b-4c77-8895-f34a8169871b` |
| Entra API app (audience) | `a2160d26-acc0-4d8c-b815-3a377f1fb5bd` |
| Entra scope | `api://a2160d26-acc0-4d8c-b815-3a377f1fb5bd/access_as_user` |
| Git HEAD (current) | `fc54c64` on `main` |

---

## Blockers Summary (updated 2026-06-04)

| # | Blocker | Who | Step | Status |
|---|---------|-----|------|--------|
| 1 | `ANTHROPIC_API_KEY` empty | You | Step 1 | OPEN |
| 2 | `VOYAGE_API_KEY` empty | You | Step 1 | OPEN |
| 3 | `COHERE_API_KEY` empty | You | Step 1 | OPEN |
| 4 | `OWNCLOUD_USERNAME/PASSWORD` empty | You | Step 1 | OPEN |
| 5 | `CLOUDFLARED_TUNNEL_TOKEN` absent | You | Step 1 | OPEN |
| 6 | App container not rebuilt with new code | Docker (`docker compose up -d --build app`) | Step 4 | OPEN |
| 7 | Cloudflared container not running | Docker (`docker compose up -d cloudflared`) | Step 4 | OPEN |
| 8 | Fresh Entra token needed for validation | You (sign in at vantage.elrace.com) | Step 5 | OPEN |
| — | ~~Microsoft Entra steps~~ | DONE | Step 2 | ✅ CLOSED 2026-06-04 |
| — | ~~n8n credential bindings~~ | DONE | Step 3 | ✅ CLOSED 2026-06-04 |
| — | ~~Graph token acquisition code~~ | DONE | Step 3 | ✅ CLOSED 2026-06-04 |
| — | ~~N8N_WEBHOOK_TOKEN empty~~ | Already present | Step 1 | ✅ CLOSED |
