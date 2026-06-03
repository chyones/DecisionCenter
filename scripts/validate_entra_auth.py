#!/usr/bin/env python3
"""Entra Auth — live end-to-end validation (operator script).

Proves the production Entra login chain works against the real tenant:

    1. OIDC discovery + JWKS for ENTRA_TENANT_ID are reachable.
    2. A real access token is decoded (claims printed; the token is never logged).
    3. The production EntraJWTValidator validates the token (RS256 via JWKS,
       tenant-scoped issuer, app-scoped audience) and resolves the canonical role.
    4. (optional) GET /me on a target base URL returns that same role — the full
       chain through Caddy's ``/me*`` proxy.

Reuses the production validator (apps.edr.auth.validator) — no copy of the auth
logic — so a PASS here is evidence the deployed backend accepts the token.

Usage (inside the app container or any env with the .env loaded):
    python scripts/validate_entra_auth.py --token "<access token>"
    ENTRA_TEST_TOKEN="<token>" python scripts/validate_entra_auth.py
    python scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token "<token>"
    # token may also be piped on stdin:
    pbpaste | python scripts/validate_entra_auth.py

Exit codes:
    0 — every executed step PASSed
    1 — a step FAILed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.edr.auth.validator import EntraJWTValidator
from apps.edr.config import settings
from apps.edr.persistence.hash import hash_user_id

_TIMEOUT = 10


def _decode_unverified(token: str) -> dict[str, object]:
    """Decode JWT claims WITHOUT verifying the signature (for diagnostics only)."""
    import jwt

    return jwt.decode(token, options={"verify_signature": False})


def _check_discovery(tenant: str) -> tuple[bool, str]:
    url = f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"
    try:
        with urlopen(url, timeout=_TIMEOUT) as resp:  # noqa: S310 (fixed Microsoft host)
            doc = json.loads(resp.read())
        issuer = doc.get("issuer", "?")
        jwks_uri = doc.get("jwks_uri")
    except (HTTPError, URLError, OSError) as exc:
        return False, f"FAIL — OIDC discovery unreachable: {type(exc).__name__}: {exc}"
    if not jwks_uri:
        return False, "FAIL — discovery doc has no jwks_uri"
    try:
        with urlopen(jwks_uri, timeout=_TIMEOUT) as resp:  # noqa: S310
            keys = json.loads(resp.read()).get("keys", [])
    except (HTTPError, URLError, OSError) as exc:
        return False, f"FAIL — JWKS unreachable: {type(exc).__name__}: {exc}"
    return True, f"OK — issuer={issuer} ; {len(keys)} signing key(s)"


def _read_token(arg_token: str | None) -> str | None:
    if arg_token:
        return arg_token.strip()
    env_token = os.environ.get("ENTRA_TEST_TOKEN")
    if env_token:
        return env_token.strip()
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            return piped
    return None


def _check_me(base_url: str, token: str, expected_role: str) -> tuple[bool, str]:
    url = f"{base_url.rstrip('/')}/me"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})  # noqa: S310
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            body = json.loads(resp.read())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        return False, f"FAIL — GET /me {exc.code}: {detail}"
    except (URLError, OSError) as exc:
        return False, f"FAIL — GET /me unreachable: {type(exc).__name__}: {exc}"
    role = body.get("role")
    if role != expected_role:
        return False, f"FAIL — /me role={role!r} != validator role={expected_role!r}"
    return True, f"OK — /me role={role}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Entra Auth live validation")
    parser.add_argument("--token", help="access token (else $ENTRA_TEST_TOKEN or stdin)")
    parser.add_argument("--base-url", help="also call GET /me on this base URL")
    args = parser.parse_args()

    tenant = (settings.entra_tenant_id or "").strip()
    client_id = (settings.entra_client_id or "").strip()

    print("Entra Auth — Live Validation")
    print("-" * 60)
    if not tenant or not client_id:
        print("FAIL — ENTRA_TENANT_ID and ENTRA_CLIENT_ID must be set")
        return 1
    print(f"{'Tenant':16s} {tenant}")
    print(f"{'Client (API app)':16s} {client_id}")
    print("-" * 60)

    any_fail = False

    ok, detail = _check_discovery(tenant)
    print(f"{'OIDC + JWKS':16s} {detail}")
    any_fail |= not ok

    token = _read_token(args.token)
    if not token:
        print(f"{'Token':16s} SKIP — no token (--token / $ENTRA_TEST_TOKEN / stdin)")
        print("-" * 60)
        # Infra reachable but no token to validate end-to-end.
        return 1 if any_fail else 0

    try:
        claims = _decode_unverified(token)
        roles = claims.get("roles")
        roles_str = ",".join(roles) if isinstance(roles, list) else "(none)"
        print(
            f"{'Token claims':16s} iss={claims.get('iss')} ; ver={claims.get('ver')} ; "
            f"aud={claims.get('aud')} ; roles={roles_str}"
        )
    except Exception as exc:  # noqa: BLE001 — diagnostic only
        print(f"{'Token claims':16s} FAIL — could not decode: {type(exc).__name__}: {exc}")
        print("-" * 60)
        return 1

    validator = EntraJWTValidator(tenant, client_id)
    try:
        validated = validator.validate(token)
        print(
            f"{'Validate':16s} PASS — role={validated.role} ; "
            f"roles={','.join(validated.roles) or '(none)'} ; "
            f"oid_hash={hash_user_id(validated.user_id)[:12]}…"
        )
    except Exception as exc:  # noqa: BLE001 — surface the validator's diagnostic
        print(f"{'Validate':16s} FAIL — {type(exc).__name__}: {exc}")
        print("-" * 60)
        print("Result: FAIL — token did not validate against the production validator")
        return 1

    if args.base_url:
        ok, detail = _check_me(args.base_url, token, validated.role or "")
        print(f"{'GET /me':16s} {detail}")
        any_fail |= not ok

    print("-" * 60)
    if any_fail:
        print("Result: FAIL — at least one step did not pass")
        return 1
    print("Result: PASS — Entra auth validated end-to-end")
    return 0


if __name__ == "__main__":
    sys.exit(main())
