# Entra Token-Expiry Dashboard Behavior

**Implemented:** 2026-06-09
**Runtime verification (UTC):** 2026-06-09T05:32:51Z
**Verdict:** `ENTRA_TOKEN_EXPIRY_DASHBOARD_BEHAVIOR_FIXED_NOT_LIVE`
**Production status:** `NOT_LIVE`

## Scope

Correct the Entra connector dashboard state when prior validation evidence
exists but its token-expiry timestamp is in the past.

No Gate 4, Gate 5, UAT, Phase 2D Slice 7, or LIVE work was started. AI
providers were not configured. ownCloud remains disabled. No write was made to
Odoo, SharePoint, Microsoft Graph, or any mailbox.

## Files Changed

- `apps/edr/admin/connector_status.py`
  - Added `PREVIOUSLY_VALIDATED_TOKEN_EXPIRED`.
  - Preserved expired validation evidence as evidence instead of treating it as
    no validation history.
  - Added redacted current-token evidence writing; raw tokens are never written
    or returned.
- `apps/edr/app.py`
  - Added the admin-only current-browser-token revalidation endpoint.
  - Added the expired state to System Health as `unknown`.
- `frontend/src/api/types.ts`
  - Added the expired state to the `ConnectorState` API contract.
- `frontend/src/screens/ConnectorTruthPanel.tsx`
  - Added the label `Previously validated — token expired` with non-green
    warning styling.
- `apps/edr/tests/integration/test_connector_truth.py`
  - Added expiry, no-evidence, missing-config, token-redaction, endpoint
    redaction, and unchanged connector-state regression coverage.
- `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
  - Added the normative Entra dashboard-state and token-redaction contract.
- `docs/execution/CURRENT_PROJECT_STATE.md`
  - Reconciled the connector truth-state list and Entra expiry behavior.
- `docs/ai/AGENT_HANDOFF.md`
  - Recorded the implementation, validation, runtime rebuild, and `NOT_LIVE`
    status for the next agent.
- `docs/ai/agent-state.json`
  - Advanced the governance anchor to the pre-closeout `main` HEAD.
- `docs/evidence/uat/ENTRA_TOKEN_EXPIRY_DASHBOARD_BEHAVIOR_2026-06-08.md`
  - This evidence record.

## Behavior Before And After

| Condition | Before | After |
|---|---|---|
| Fresh valid Entra evidence | `VALIDATED` | `VALIDATED` |
| Previous validation exists, token expired | `CONFIGURED_NOT_TESTED` | `PREVIOUSLY_VALIDATED_TOKEN_EXPIRED` |
| Config exists, no validation evidence ever | `CONFIGURED_NOT_TESTED` | `CONFIGURED_NOT_TESTED` |
| Required Entra config missing | `NOT_CONFIGURED` | `NOT_CONFIGURED` |

The expired state blocks go-live and maps to System Health `unknown`; it is
never green and is not misrepresented as first-time untested configuration.

## Token Handling

The dashboard does not read `/root/dc_token.txt`; that path remains CLI-only
operator input.

The browser revalidation endpoint:

1. Uses FastAPI authentication to validate the caller's bearer token.
2. Requires the canonical `admin` role.
3. Calls Microsoft Graph `/me`.
4. Persists and returns only redacted evidence: validation timestamp, expiry
   timestamp, role, `/me` result, and issuer/audience/tenant/expiry check
   booleans.

The raw bearer token is held only in request-local memory, deleted after use,
and is never logged, printed, persisted, or returned. Automated tests assert
that a sentinel token is absent from both the evidence file and endpoint/helper
responses.

## Connector-State Regression

The focused integration suite confirms these states remain unchanged:

| Connector | State |
|---|---|
| Odoo | `LIVE_OK` |
| SharePoint | `VERIFIED_FROM_EVIDENCE` |
| Microsoft Graph / Email | `VERIFIED_FROM_EVIDENCE` |
| ownCloud | `DISABLED` |
| Anthropic | `NOT_CONFIGURED` |
| Voyage | `NOT_CONFIGURED` |
| Cohere | `NOT_CONFIGURED` |

## Validation Results

| Command | Result |
|---|---|
| `ruff check .` | PASS |
| `python3 -m compileall apps scripts` | PASS |
| `.venv/bin/python -m pytest apps/edr/tests/integration/test_connector_truth.py -q` | PASS — 44 passed, 1 dependency warning |
| `npm --prefix frontend run lint` | PASS |
| `npm --prefix frontend run build` | PASS — existing Vite large-chunk warning only |
| `python3 scripts/check_doc_drift.py` | PASS — clean |
| `python3 scripts/check_ai_context.py` | PASS — clean |
| `python3 scripts/agent_postflight.py --allow-no-evidence` | PASS — clean |

## Runtime Rebuild

| Command | Result |
|---|---|
| `docker compose build app` | PASS — `decisioncenter-app:latest` rebuilt |
| `docker compose up -d app` | PASS — app container recreated and started |
| `curl -s http://127.0.0.1:8000/healthz \| jq` | PASS |
| Runtime Entra classification inside rebuilt app | PASS — `PREVIOUSLY_VALIDATED_TOKEN_EXPIRED`, configured, evidence-backed, non-green, blocks go-live |

Health response:

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

Sanitized runtime Entra truth:

```json
{
  "blocks_go_live": true,
  "configured": true,
  "data_source": "evidence",
  "live_data_ok": false,
  "state": "PREVIOUSLY_VALIDATED_TOKEN_EXPIRED"
}
```

## Production Status

Production remains `NOT_LIVE`. This change does not authorize or start UAT,
Slice 7, any go-live gate, or LIVE operation.

## Final Verdict

`ENTRA_TOKEN_EXPIRY_DASHBOARD_BEHAVIOR_FIXED_NOT_LIVE`
