"""Entra validator — v1.0 / v2.0 token-version acceptance (defense in depth).

The API app may emit either v2.0 tokens (issuer ``…/v2.0``, audience == client id)
or v1.0 tokens (issuer ``https://sts.windows.net/{tenant}/``, audience
``api://{client id}``) depending on ``accessTokenAcceptedVersion``. The validator
must accept both for the same tenant/app, and reject a wrong tenant/audience with a
diagnostic that names the offending claim.

These tests sign *real* RS256 tokens with an in-test RSA key and mock only the JWKS
lookup, so the issuer/audience lists are exercised through the real ``jwt.decode``.
No network, no live tenant — CI-safe, mirroring test_phase1d_security.py.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.edr.auth.validator import EntraJWTValidator

_TENANT = "11111111-2222-3333-4444-555555555555"
_CLIENT = "a2160d26-acc0-4d8c-b815-3a377f1fb5bd"
_V2_ISS = f"https://login.microsoftonline.com/{_TENANT}/v2.0"
_V1_ISS = f"https://sts.windows.net/{_TENANT}/"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()


def _sign(claims: dict[str, object]) -> str:
    now = int(time.time())
    payload = {"iat": now - 10, "nbf": now - 10, "exp": now + 3600, **claims}
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256", headers={"kid": "test-kid"})


def _validator() -> EntraJWTValidator:
    """Validator whose JWKS lookup returns the in-test public key (no network)."""
    validator = EntraJWTValidator(tenant_id=_TENANT, client_id=_CLIENT)
    fake_client = MagicMock()
    fake_key = MagicMock()
    fake_key.key = _PUBLIC_KEY
    fake_client.get_signing_key_from_jwt.return_value = fake_key
    validator._jwks_client = fake_client
    return validator


def test_accepts_v2_token() -> None:
    token = _sign(
        {"oid": "user-v2", "ver": "2.0", "iss": _V2_ISS, "aud": _CLIENT, "roles": ["executive"]}
    )
    claims = _validator().validate(token)
    assert claims.user_id == "user-v2"
    assert claims.role == "executive"


def test_accepts_v1_token() -> None:
    token = _sign(
        {
            "oid": "user-v1",
            "ver": "1.0",
            "iss": _V1_ISS,
            "aud": f"api://{_CLIENT}",
            "roles": ["executive"],
        }
    )
    claims = _validator().validate(token)
    assert claims.user_id == "user-v1"
    assert claims.role == "executive"


def test_v1_token_resolves_role_by_precedence() -> None:
    # Unordered multi-role array — admin must win regardless of position.
    token = _sign(
        {
            "oid": "owner",
            "ver": "1.0",
            "iss": _V1_ISS,
            "aud": f"api://{_CLIENT}",
            "roles": ["executive", "admin"],
        }
    )
    claims = _validator().validate(token)
    assert claims.role == "admin"
    assert claims.roles == ("executive", "admin")


def test_rejects_wrong_tenant_issuer_with_diagnostic() -> None:
    bad_iss = "https://sts.windows.net/99999999-0000-0000-0000-000000000000/"
    token = _sign({"oid": "x", "ver": "1.0", "iss": bad_iss, "aud": _CLIENT})
    with pytest.raises(ValueError) as exc:
        _validator().validate(token)
    msg = str(exc.value)
    assert "iss=" in msg and bad_iss in msg
    assert "ver=" in msg


def test_rejects_wrong_audience_with_diagnostic() -> None:
    token = _sign({"oid": "x", "ver": "2.0", "iss": _V2_ISS, "aud": "some-other-app"})
    with pytest.raises(ValueError) as exc:
        _validator().validate(token)
    assert "aud=" in str(exc.value)


def test_rejects_expired_token() -> None:
    now = int(time.time())
    token = jwt.encode(
        {
            "iat": now - 120,
            "nbf": now - 120,
            "exp": now - 60,
            "oid": "expired-user",
            "ver": "2.0",
            "iss": _V2_ISS,
            "aud": _CLIENT,
            "roles": ["admin"],
        },
        _PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        _validator().validate(token)


def test_falls_back_to_v1_keys_when_kid_missing() -> None:
    """A v1 token whose kid is absent from the v2 keyset uses the v1 endpoint."""
    from jwt.exceptions import PyJWKClientError

    token = _sign(
        {"oid": "user-fb", "ver": "1.0", "iss": _V1_ISS, "aud": f"api://{_CLIENT}", "roles": ["finance"]}
    )
    validator = EntraJWTValidator(tenant_id=_TENANT, client_id=_CLIENT)

    v2_client = MagicMock()
    v2_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("kid not found")
    validator._jwks_client = v2_client

    v1_key = MagicMock()
    v1_key.key = _PUBLIC_KEY
    v1_client = MagicMock()
    v1_client.get_signing_key_from_jwt.return_value = v1_key
    validator._jwks_client_v1 = v1_client

    claims = validator.validate(token)
    assert claims.role == "finance"
    v1_client.get_signing_key_from_jwt.assert_called_once()
