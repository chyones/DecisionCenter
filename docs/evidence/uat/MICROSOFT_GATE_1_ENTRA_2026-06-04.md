# Microsoft Gate 1 — Entra Auth Live Validation

> **Verdict:** `MICROSOFT_GATE_1_ENTRA_PASSED_NOT_LIVE`
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T11:59:23Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** origin-main
> **Phase:** 2D Slice 6 in progress
> **Service status:** NOT_LIVE — Gate 1 passed; full UAT not yet run; production not yet declared live

---

## 1. Purpose

Officially close Microsoft Gate 1 by recording a live, non-expired end-to-end
Entra authentication validation against the running stack at `https://vantage.elrace.com`.
This supersedes all prior "BLOCKED" readiness recheck documents for Gate 1.

---

## 2. Git State

| Item | Value |
|------|-------|
| HEAD | `fc54c64cd37adb234c01296bf34dd89274196602` |
| Working-tree staged | none |
| Working-tree unstaged | `apps/edr/connectors/email.py`, `apps/edr/connectors/sharepoint.py`, `apps/edr/graph/node_05_sharepoint.py`, `apps/edr/graph/node_07_email.py`, `frontend/src/auth/LoginGate.tsx`, `frontend/src/auth/msalConfig.ts`, `frontend/src/main.tsx`, and related tests |
| Untracked | several `docs/evidence/uat/` files, `scripts/bind_n8n_webhook_auth.py`, `apps/edr/connectors/graph_token.py` |

---

## 3. Token Freshness

| Claim | Value |
|-------|-------|
| Expiry (`exp`) | `1780577622` (Unix epoch) |
| Checked at (Unix) | `1780574329` |
| Remaining at check | **3293 s (~54 min)** |
| Expired? | **No** |

Token value: **not recorded** — presence and expiry checked only.

---

## 4. Validation Command

```
python3 scripts/validate_entra_auth.py --base-url https://vantage.elrace.com < /root/dc_token.txt
```

Script: `scripts/validate_entra_auth.py` — reuses the production `EntraJWTValidator`
(no copy of auth logic); a PASS here is evidence the deployed backend accepts the token.

---

## 5. Validation Output (sanitised — no token value)

```
Entra Auth — Live Validation
------------------------------------------------------------
Tenant           14a72467-3f25-4572-a535-3d5eddb00cc5
Client (API app) a2160d26-acc0-4d8c-b815-3a377f1fb5bd
------------------------------------------------------------
OIDC + JWKS      OK — issuer=https://login.microsoftonline.com/14a72467-3f25-4572-a535-3d5eddb00cc5/v2.0 ; 5 signing key(s)
Token claims     iss=https://login.microsoftonline.com/14a72467-3f25-4572-a535-3d5eddb00cc5/v2.0 ; ver=2.0 ; aud=a2160d26-acc0-4d8c-b815-3a377f1fb5bd ; roles=admin
Validate         PASS — role=admin ; roles=admin ; oid_hash=45568e746071…
GET /me          OK — /me role=admin
------------------------------------------------------------
Result: PASS — Entra auth validated end-to-end
```

---

## 6. Claim Summary

| Claim | Value | Expected | Match? |
|-------|-------|----------|--------|
| `iss` | `https://login.microsoftonline.com/14a72467-3f25-4572-a535-3d5eddb00cc5/v2.0` | `…/14a72467…/v2.0` or `https://sts.windows.net/14a72467…/` | ✅ |
| `aud` | `a2160d26-acc0-4d8c-b815-3a377f1fb5bd` | `a2160d26…` or `api://a2160d26…` | ✅ |
| `ver` | `2.0` | 1.0 or 2.0 (both accepted) | ✅ |
| `roles` | `["admin"]` | any canonical role | ✅ |
| Resolved role | `admin` | — | ✅ |

---

## 7. Step Results

| Step | Result | Detail |
|------|--------|--------|
| OIDC discovery + JWKS reachable | **PASS** | Issuer matches tenant; 5 signing keys returned |
| Token decoded (no signature check) | **PASS** | iss / ver / aud / roles all present |
| `EntraJWTValidator.validate()` | **PASS** | RS256 via JWKS; role=admin; oid_hash=45568e746071… |
| `GET /me` on `https://vantage.elrace.com` | **PASS** | role=admin matches validator role |

---

## 8. What This Proves

- The Entra tenant OIDC/JWKS endpoints are reachable from the validation environment.
- A real v2.0 access token issued for the API app (`a2160d26…`) with role `admin` is
  accepted by the production `EntraJWTValidator` (RS256, tenant-scoped issuer, app-scoped audience).
- The full chain — browser → Cloudflare edge → Caddy `/me*` proxy → FastAPI backend — correctly
  validates the token and returns `role=admin` from `GET /me`.

---

## 9. What This Does NOT Prove

- Full UAT (report generation, approval, publish) — not run in this task.
- Connector live probes (SharePoint, email, ownCloud) — not tested.
- Production go-live — `production_status` remains `NOT_LIVE`.

---

## 10. Final Verdict

**`MICROSOFT_GATE_1_ENTRA_PASSED_NOT_LIVE`**

Gate 1 is officially closed. The live Entra authentication chain validated end-to-end
against the running stack with a non-expired real access token. Production remains
`NOT_LIVE` pending full UAT (Gate 2 and beyond).
