# Entra Expired-State UI Badge Fix

**Date:** 2026-06-09
**Verdict:** `ENTRA_EXPIRED_STATE_UI_BADGE_FIXED_NOT_LIVE`
**Production status:** `NOT_LIVE`

## Scope

Fix only the Microsoft Entra connector card classification/rendering and the
current-browser-session revalidation flow. No Microsoft Gate, permission,
deployment, UAT, Slice 7, or LIVE work was started. `/root/dc_token.txt` was not
used. No token, secret, or Authorization header was printed or persisted.

## Root Cause

The frontend treated every Entra `data_source="evidence"` response as current
positive validation. Its generic evidence chip rendered
`validation evidence · validated once`, and its generic timestamp row used
`last_success_at ?? last_probe_at` under the label `Last verified`.

For `PREVIOUSLY_VALIDATED_TOKEN_EXPIRED`, the backend also omitted the previous
successful validation timestamp and token-expiry timestamp from the response,
while its safe evidence text exposed an internal POST route instruction.

A failed Graph `/me` check could write a failing marker over the previous
passing marker, erasing the historical state instead of leaving the connector
expired/action-required.

## Changes

### Backend

- Added `token_expires_at` to Entra connector truth.
- Preserved `last_success_at` for expired historical validation.
- Replaced internal API instructions with safe user-neutral evidence text.
- Preserved the previous redacted passing marker when token validation or
  Graph `/me` revalidation fails.
- Kept existing cryptographic issuer, audience, tenant, expiry, and role
  validation unchanged.

### Frontend

- Expired state badge is `Expired` with warning styling.
- Removed positive/current evidence wording from the expired state.
- Split timestamp labels into:
  - `Last successful validation`
  - `Token expired at`
  - `Last checked`
- Added `Revalidate with current browser session`.
- The action requests a force-refreshed token through the existing MSAL silent
  flow, retains the existing interactive redirect fallback, and sends the
  acquired token only to the existing backend revalidation endpoint.
- Successful revalidation refreshes connector truth and renders `Validated`
  with `Current validation evidence`.
- Failure keeps `Expired` and shows sign-in/retry guidance.

## Before And After

| Before | After |
|---|---|
| `Previously validated — token expired` plus positive evidence chip | `Expired` warning badge |
| `validation evidence · validated once` | No current-evidence chip while expired |
| `Last verified` using a probe fallback | Separate success, expiry, and check timestamps |
| Internal `Use POST ... current-token` instruction | User action: `Revalidate with current browser session` |
| Failed `/me` could replace prior passing evidence | Prior redacted passing evidence remains intact |

## Tests

| Check | Result |
|---|---|
| Targeted Entra backend tests | PASS — 8 passed, 37 deselected |
| Full connector-truth integration file | PASS — 45 passed, 1 dependency warning |
| Isolated expired-state closeout candidate | PASS — 41 passed, 1 dependency warning; 4 unrelated AI-readiness tests excluded from the commit |
| Targeted Entra card tests | PASS — 9 passed across Chromium, Firefox, and WebKit |
| Ruff | PASS |
| Python compileall | PASS |
| Frontend lint | PASS |
| Frontend build | PASS — existing Vite large-chunk warning only |
| Documentation drift | PASS — clean |
| AI context | PASS — clean |
| Agent postflight | PASS — clean with `--allow-no-evidence` |

The targeted browser tests prove:

1. Expired state does not render as current validation.
2. Successful revalidation replaces expired UI with valid UI.
3. Internal API wording is absent.
4. Failed revalidation preserves expired status and shows login guidance.

## Production Status

Production remains `NOT_LIVE`. This fix does not authorize a Microsoft Gate,
deployment, UAT, Slice 7, or LIVE operation.

## Final Verdict

`ENTRA_EXPIRED_STATE_UI_BADGE_FIXED_NOT_LIVE`
