# Entra Connector Truth Revalidation

<!-- connector_truth_entra_validation: {"checks":{"audience_ok":true,"expiry_valid":true,"issuer_ok":true,"jwks_ok":true,"me_role_ok":true,"oidc_discovery_ok":true,"role_present":true,"tenant_ok":true},"me_role":"admin","result":"PASS","role":"admin","token_expires_at":"2026-06-08T12:45:40Z","validated_at":"2026-06-08T11:45:43Z"} -->

**Date:** 2026-06-08
**Timestamp (UTC):** 2026-06-08T11:45:43Z
**Verdict:** `ENTRA_CONNECTOR_TRUTH_REVALIDATED_NOT_LIVE`
**Production status:** NOT_LIVE
**HEAD:** `029de7c1a63c7f1b4e47abe5cf91c892743d46db`
**Branch:** `main`

---

## Scope

Close out Entra fresh-token validation and update connector dashboard truth.

No Gate 4, Gate 5, UAT, Slice 7, or LIVE work was started. AI providers were
not configured. ownCloud remained disabled. No Odoo, SharePoint, Microsoft
Graph, or mailbox write was performed. The token value was not printed.

---

## Token File Check

Required token path:

```text
/root/dc_token.txt
```

| Check | Result |
|---|---|
| File exists | yes |
| Mode | `0600` |
| Token value printed | no |
| JWT parts | 3 |
| Issuer present | yes |
| Audience present | yes |
| Tenant present | yes |
| Roles present | yes |
| Token expires at UTC | `2026-06-08T12:45:40Z` |
| Fresh at validation | yes |

---

## Validation Command

The exact requested host `python3` invocation was attempted first without
printing the token:

```bash
TOKEN="$(tr -d '\n\r' < /root/dc_token.txt)"
python3 scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token "$TOKEN"
unset TOKEN
```

Host `python3` could not import `asyncpg`; this was an interpreter dependency
gap, not an Entra validation failure. The project virtualenv has the required
runtime dependencies, so the same validator was run with `.venv/bin/python`.

```bash
TOKEN="$(tr -d '\n\r' < /root/dc_token.txt)"
.venv/bin/python scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token "$TOKEN"
unset TOKEN
```

Sanitised output:

```text
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

Confirmed:

- OIDC discovery OK.
- JWKS OK.
- issuer OK.
- audience OK.
- tenant OK.
- token not expired.
- role present.
- `/me` returns expected role.
- Result PASS.

---

## Connector Truth Before

Runtime connector truth was checked from the running app container before the
truth-model update.

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

Readiness before: `PARTIAL_READY`.

Blocking list before:

```text
entra_auth, anthropic, voyage, cohere
```

---

## Truth Model Update

`apps/edr/admin/connector_status.py` now accepts a current redacted Entra
validation marker only when:

- validation result is PASS;
- OIDC discovery, JWKS, issuer, audience, tenant, expiry, role, and `/me` role
  checks are all true;
- the recorded token expiry is still in the future.

When those conditions hold, Entra reports `VALIDATED`. The dashboard never
reads `/root/dc_token.txt`, never stores the token, and automatically falls
back to unvalidated status once the recorded token-expiry window closes.

---

## Connector Truth After

Runtime connector truth was checked from the rebuilt app container after the
truth-model update and app refresh.

Runtime refresh:

- `docker compose build app`: passed; image rebuilt with the updated truth model
  and redacted evidence marker.
- `docker compose up -d app`: passed; app container recreated.

Health check:

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

| Connector | State | Data source | Sample count | Blocks |
|---|---|---|---:|---|
| PostgreSQL | `LIVE_OK` | live | — | no |
| Redis | `LIVE_OK` | live | — | no |
| Qdrant | `LIVE_OK` | live | — | no |
| MinIO | `LIVE_OK` | live | — | no |
| Cloudflare Tunnel / public edge | `LIVE_OK` | live | — | no |
| Caddy routing | `LIVE_OK` | live | — | no |
| Microsoft Entra authentication | `VALIDATED` | evidence | 1 | no |
| n8n webhook | `LIVE_OK` | live | — | no |
| SharePoint | `VERIFIED_FROM_EVIDENCE` | evidence | 2 | no |
| Email / Microsoft Graph | `VERIFIED_FROM_EVIDENCE` | evidence | 35 | no |
| ownCloud | `DISABLED` | none | — | no |
| Odoo | `LIVE_OK` | live | 100 | no |
| Anthropic | `NOT_CONFIGURED` | none | — | yes |
| Voyage | `NOT_CONFIGURED` | none | — | yes |
| Cohere | `NOT_CONFIGURED` | none | — | yes |

Readiness after: `PARTIAL_READY`.

Blocking list after:

```text
anthropic, voyage, cohere
```

The Entra connector no longer appears in the blocking list. Report generation
remains `BLOCKED` because AI providers are intentionally not configured.

---

## Validation Commands

| Command | Result |
|---|---|
| `ruff check .` | PASS |
| `python3 -m compileall apps scripts` | PASS |
| `pytest apps/edr/tests/integration/test_connector_truth.py -q` | Host Python environment failed during collection because the bare `pytest` binary resolves to an inconsistent global FastAPI/Pydantic install. |
| `.venv/bin/python -m pytest apps/edr/tests/integration/test_connector_truth.py -q` | PASS — 33 passed, 1 warning |
| `python3 scripts/check_doc_drift.py` | PASS — clean |
| `python3 scripts/check_ai_context.py` | PASS — clean |
| `python3 scripts/agent_postflight.py --allow-no-evidence` | PASS — clean |

The host `pytest` failure is an interpreter/environment issue, not an Entra or
connector-truth test failure. The project virtualenv is the valid local test
environment and the connector truth suite passed there.

---

## Production Status

Production remains `NOT_LIVE`. This Entra connector truth closeout does not
start Gate 4, Gate 5, UAT, Slice 7, or LIVE.

---

## Next Allowed Step

The next allowed step remains the explicitly operator-controlled real live UAT
run with redacted evidence. Slice 7 Go-Live Gate remains blocked until real UAT
evidence exists and the user explicitly approves Slice 7/go-live work.

---

## Final Verdict

```text
ENTRA_CONNECTOR_TRUTH_REVALIDATED_NOT_LIVE
```
