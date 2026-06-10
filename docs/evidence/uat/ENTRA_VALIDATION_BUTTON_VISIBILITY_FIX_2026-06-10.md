# Entra Validation Button Visibility Fix

**Date:** 2026-06-10
**Production status:** `NOT_LIVE`
**Scope:** Entra connector card action visibility and current MSAL browser-session validation

## Problem

The Entra validation action was rendered only for
`PREVIOUSLY_VALIDATED_TOKEN_EXPIRED`. If first-time validation failed or no
current evidence existed, connector truth returned `CONFIGURED_NOT_TESTED` and
the action disappeared even though the card still required user-token
validation.

The backend also attempted to call Microsoft Graph `/me` with the
DecisionCenter API access token. That token is intentionally issued for the
DecisionCenter API audience, so it is not a valid Graph-audience token.

## Implemented Behavior

- Configured Entra states without current passing evidence always show
  `Validate with current Microsoft session` or
  `Revalidate with current Microsoft session`.
- This includes configured-not-tested, no fresh evidence, expired, failed, and
  other configured action-required states.
- A validated/current card retains a secondary Revalidate action.
- The click requests the API token from the existing MSAL browser session with
  forced silent refresh.
- The validation action does not redirect away when silent acquisition fails.
  It keeps the action visible and shows:
  `Sign in with Microsoft again, then retry validation`.
- OIDC discovery and JWKS reachability do not count as user-token validation.

## Backend Validation

The current-token endpoint validates:

- cryptographic signature and issuer;
- DecisionCenter API audience;
- configured tenant through the tenant-bound issuer;
- token expiry;
- canonical role membership and authenticated role consistency;
- `oid` user identity and authenticated identity consistency.

The DecisionCenter API token is not sent to Microsoft Graph. Successful
evidence contains only validation/expiry timestamps, the canonical role, and
boolean check results. Raw tokens and raw user identity are not logged,
printed, persisted, or returned. Legacy evidence without the identity check is
not accepted as current proof.

## Targeted Test Evidence

| Check | Result |
|---|---|
| Backend connector truth + Entra validator tests | PASS — 55 passed |
| Entra card/MSAL Playwright tests | PASS — 24 passed across Chromium, Firefox, and WebKit |
| Targeted Ruff | PASS |
| Frontend lint | PASS |

The browser tests cover:

1. Button visible for `CONFIGURED_NOT_TESTED`.
2. Button visible when fresh user-token evidence is absent.
3. Button visible for expired and failed/action-required states.
4. Button remains visible after backend validation failure.
5. Button remains visible after MSAL acquisition failure.
6. Click requests forced MSAL acquisition without interactive fallback.
7. Success updates the card to validated/current evidence.
8. Raw credential values and internal endpoint instructions are absent from UI.

## Full Validation

| Command | Result |
|---|---|
| `ruff check apps scripts` | PASS |
| `python3 -m compileall apps scripts` | PASS |
| `cd frontend && npm run lint` | PASS |
| `cd frontend && npm run build` | PASS — existing Vite large-chunk warning only |
| `python3 scripts/check_doc_drift.py` | PASS — clean |
| `python3 scripts/check_ai_context.py` | PASS — clean |
| `python3 scripts/agent_postflight.py --allow-no-evidence` | PASS — clean |

## Guardrails

- `/root/dc_token.txt` was not used.
- No fake token was used as validation proof.
- No token, secret, password, or raw identity was printed or persisted.
- Microsoft Gate 4 was not started.
- No deployment or live-UAT operation was performed.
- Phase 2D Slice 7 remains blocked and production remains `NOT_LIVE`.
