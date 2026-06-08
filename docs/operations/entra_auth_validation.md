# Entra Auth — Live Validation & Token-Version Fix

Operator runbook for validating the production Microsoft Entra login chain and
resolving the **v1.0-vs-v2.0 access-token mismatch** that returns
`401 "Invalid token: Invalid issuer"` at login.

## Topology — two app registrations

| Role | App (client) ID | Purpose |
|---|---|---|
| **API app** (token *audience*) | `a2160d26-acc0-4d8c-b815-3a377f1fb5bd` | Backend `ENTRA_CLIENT_ID`. The access token must be validated against this app. Exposes scope `access_as_user`. |
| **SPA** (token *requestor*) | `97519dfa-650b-4c77-8895-f34a8169871b` | Frontend `VITE_ENTRA_CLIENT_ID`. Requests scope `api://a2160d26…/access_as_user`. |

Tenant: `14a72467-3f25-4572-a535-3d5eddb00cc5`.

## Root cause

The API app emits tokens in one of two formats depending on its
`accessTokenAcceptedVersion` setting:

| Token version | `iss` | `aud` |
|---|---|---|
| **v1.0** | `https://sts.windows.net/{tenant}/` | `api://a2160d26…` |
| **v2.0** | `https://login.microsoftonline.com/{tenant}/v2.0` | `a2160d26…` (client id) |

The backend previously hard-required the **v2.0** issuer and the client-id
audience. When the API app emitted **v1.0** tokens, neither claim matched → 401.

## Fix — defense in depth

### A. Backend accepts both versions (shipped)

`apps/edr/auth/validator.py` now validates against **both** issuers and **both**
audiences for the same tenant + client id. This is not a trust-boundary change —
the tokens are signed by the same tenant keys for the same app; only the
`iss`/`aud` *format* differs. RS256-via-JWKS signature verification is unchanged.
A claim mismatch now raises a diagnostic naming the actual `iss`/`aud`/`ver` vs
expected, instead of an opaque "Invalid issuer".

### B. Make the API app emit v2.0 tokens (operator action — recommended)

So that steady-state tokens are v2.0:

- **Portal:** App registrations → `a2160d26…` → **Manifest** → set
  `"accessTokenAcceptedVersion": 2` → **Save**.
- **CLI:** `az ad app update --id a2160d26-acc0-4d8c-b815-3a377f1fb5bd --set api.requestedAccessTokenVersion=2`
  (Microsoft Graph names this field `api.requestedAccessTokenVersion`).

Then sign out / clear the SPA's MSAL `sessionStorage` so the next login mints a
fresh v2.0 token. Cached v1.0 tokens keep working until they expire because of (A).

Also confirm on the SPA app: redirect URI `https://vantage.elrace.com` (SPA
platform, no trailing slash) and admin-consented delegated permission to the API
app's `access_as_user` scope.

## Validate (live, end-to-end)

`scripts/validate_entra_auth.py` reuses the production validator — a PASS is
evidence the deployed backend accepts the token.

```bash
# 1. Validator only (infra + token claims + role resolution):
python scripts/validate_entra_auth.py --token "<access token>"
ENTRA_TEST_TOKEN="<token>" python scripts/validate_entra_auth.py   # or via env

# 2. Full chain through Caddy /me*:
python scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token "<token>"
```

Expected PASS output (token never printed — only non-secret claims):

```
OIDC + JWKS      OK — issuer=https://login.microsoftonline.com/<tenant>/v2.0 ; N signing key(s)
Token claims     iss=… ; ver=2.0 ; aud=a2160d26… ; roles=executive
Validate         PASS — role=executive ; roles=executive ; oid_hash=…
GET /me          OK — /me role=executive
Result: PASS — Entra auth validated end-to-end
```

Exit code `0` = PASS, `1` = FAIL (the failing step prints the exact mismatch).

## Connector-truth state

Microsoft Entra stays `CONFIGURED_NOT_TESTED` in
`GET /admin/connectors/truth` until an operator records a passing run of the
script above against the live tenant. A current redacted PASS marker in the UAT
evidence file moves Entra to `VALIDATED` only while the recorded token expiry is
still in the future. The dashboard never reads or stores the token value.

## Browser smoke

After (B) + a frontend rebuild, sign in at the SPA: no "Sign-in problem" screen,
and `LoginGate`'s 401 diagnostic (if shown) reports `ver=2.0` with matching
`iss`/`aud`.
