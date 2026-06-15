"""Phase 1D-fixup security regression tests (Session 2).

Cover:
- C-4 mailbox allowlist enforced in Node 07 before any external call.
- C-3 every n8n workflow webhook requires header-auth.
- C-6/S-1 service-account credentials no longer flow through the webhook body.
- L-2 JWT validator surfaces the full ``roles`` list from the Entra claim.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.edr.auth.validator import EntraJWTValidator
from apps.edr.graph import node_06_owncloud, node_07_email, node_08_odoo
from apps.edr.graph.state import DecisionState

WORKFLOW_PATHS = [
    Path("n8n/sharepoint_search.json"),
    Path("n8n/email_search.json"),
    Path("n8n/owncloud_list.json"),
    Path("n8n/odoo_read.json"),
]


# ---------------------------------------------------------------------------
# C-4 — Mailbox allowlist enforcement (Node 07)
# ---------------------------------------------------------------------------


def _email_state(user_id: str, allowed: list[str]) -> DecisionState:
    state = DecisionState(
        request_id="r-1",
        user_id=user_id,
        role=None,
        project_code="PRJ-001",
        query="status",
    )
    state.allowed_mailboxes = allowed
    return state


def _patch_no_group_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force node_07 down the user/shared-mailbox allowlist path (no group)."""
    class _M:
        @staticmethod
        def load() -> "_M":
            return _M()

        def get(self, project_code: str) -> dict:
            return {"enabled_sources": ["email"]}

    monkeypatch.setattr(node_07_email, "ProjectMapping", _M)


def test_email_node_denies_when_allowlist_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def boom(_payload: dict) -> list:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(node_07_email, "search_email", boom)
    _patch_no_group_mapping(monkeypatch)

    state = _email_state("alice@example.com", [])
    result = asyncio.run(node_07_email.run(state))

    assert result.outputs["email_status"] == "denied_no_allowlist"
    assert called is False


def test_email_node_denies_when_user_mailbox_not_in_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def boom(_payload: dict) -> list:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(node_07_email, "search_email", boom)
    _patch_no_group_mapping(monkeypatch)

    state = _email_state(
        "alice@example.com",
        ["project-prj-001@example.com", "doc-control@example.com"],
    )
    result = asyncio.run(node_07_email.run(state))

    assert result.outputs["email_status"] == "denied_mailbox_not_in_allowlist"
    assert called is False


def test_email_node_proceeds_when_user_mailbox_in_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    async def fake_search(payload: dict) -> list:
        captured.update(payload)
        return []

    monkeypatch.setattr(node_07_email, "search_email", fake_search)
    _patch_no_group_mapping(monkeypatch)

    state = _email_state(
        "project-prj-001@example.com",
        ["project-prj-001@example.com"],
    )
    result = asyncio.run(node_07_email.run(state))

    assert result.outputs["email_status"].startswith("ok")
    assert captured["user_mailbox"] == "project-prj-001@example.com"


# ---------------------------------------------------------------------------
# C-3 — Every n8n webhook node enforces header authentication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", WORKFLOW_PATHS, ids=lambda p: p.name)
def test_n8n_webhook_requires_header_auth(path: Path) -> None:
    workflow = json.loads(path.read_text(encoding="utf-8"))
    webhooks = [
        node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.webhook"
    ]
    assert webhooks, f"{path} has no webhook node"
    for node in webhooks:
        assert node["parameters"].get("authentication") == "headerAuth", (
            f"{path}::{node['name']} must declare authentication=headerAuth"
        )


# ---------------------------------------------------------------------------
# C-6 / S-1 — Service-account credentials are not in webhook bodies
# ---------------------------------------------------------------------------


def test_owncloud_node_omits_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    async def fake_list(payload: dict) -> list:
        captured.update(payload)
        return []

    class _FakeMapping:
        @staticmethod
        def load() -> "_FakeMapping":
            return _FakeMapping()

        def get(self, project_code: str) -> dict:
            return {"owncloud": {"base_path": "Projects/PRJ-001"}}

    monkeypatch.setattr(node_06_owncloud, "list_owncloud", fake_list)
    monkeypatch.setattr(node_06_owncloud, "ProjectMapping", _FakeMapping)

    state = DecisionState(
        request_id="r-1",
        user_id="u",
        role=None,
        project_code="PRJ-001",
        query="status",
    )
    asyncio.run(node_06_owncloud.run(state))

    assert "username" not in captured
    assert "password" not in captured


def test_odoo_node_omits_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    async def fake_read(payload: dict) -> list:
        captured.update(payload)
        return []

    class _FakeMapping:
        @staticmethod
        def load() -> "_FakeMapping":
            return _FakeMapping()

        def get(self, project_code: str) -> dict:
            return {"odoo": {"project_model": "project.project"}}

    monkeypatch.setattr(node_08_odoo, "read_odoo", fake_read)
    monkeypatch.setattr(node_08_odoo, "ProjectMapping", _FakeMapping)

    state = DecisionState(
        request_id="r-1",
        user_id="u",
        role=None,
        project_code="PRJ-001",
        query="status",
    )
    asyncio.run(node_08_odoo.run(state))

    forbidden = {"odoo_url", "database", "username", "api_key"}
    leaked = forbidden & captured.keys()
    assert not leaked, f"odoo payload leaks {leaked}"


# ---------------------------------------------------------------------------
# C-3 — Service-account credentials referenced via $env in workflow JSON
# ---------------------------------------------------------------------------


def test_owncloud_workflow_reads_credentials_from_env() -> None:
    raw = Path("n8n/owncloud_list.json").read_text(encoding="utf-8")
    assert "$env.OWNCLOUD_USERNAME" in raw
    assert "$env.OWNCLOUD_PASSWORD" in raw
    # Body-driven credentials must be gone.
    assert "$json.body.username" not in raw
    assert "$json.body.password" not in raw


def test_odoo_workflow_reads_credentials_from_env() -> None:
    raw = Path("n8n/odoo_read.json").read_text(encoding="utf-8")
    for needle in ("$env.ODOO_DATABASE", "$env.ODOO_USERNAME", "$env.ODOO_API_KEY", "$env.ODOO_URL"):
        assert needle in raw, f"odoo workflow missing {needle}"
    for needle in ("$json.body.database", "$json.body.username", "$json.body.api_key"):
        assert needle not in raw, f"odoo workflow still uses {needle}"


def test_odoo_workflow_honors_bounded_request_limit() -> None:
    workflow = json.loads(Path("n8n/odoo_read.json").read_text(encoding="utf-8"))
    query_node = next(node for node in workflow["nodes"] if node["name"] == "Odoo Query")
    code = query_node["parameters"]["jsCode"]

    assert "const requestedLimit = Number(raw.limit ?? 100);" in code
    assert "limit must be an integer between 1 and 100" in code
    assert "limit:requestedLimit" in code
    assert "limit:100" not in code


# ---------------------------------------------------------------------------
# L-2 — Validator surfaces all roles from the Entra claim
# ---------------------------------------------------------------------------


def test_validator_surfaces_all_roles() -> None:
    validator = EntraJWTValidator(tenant_id="t", client_id="c")

    fake_jwks_client = MagicMock()
    fake_signing_key = MagicMock()
    fake_signing_key.key = "fake-key"
    fake_jwks_client.get_signing_key_from_jwt.return_value = fake_signing_key
    validator._jwks_client = fake_jwks_client

    fake_payload = {"oid": "user-42", "roles": ["finance", "auditor"]}
    with patch("jwt.decode", return_value=fake_payload):
        claims = validator.validate("dummy-token")

    assert claims.user_id == "user-42"
    assert claims.role == "finance"
    assert claims.roles == ("finance", "auditor")


def test_validator_jwks_client_cached() -> None:
    validator = EntraJWTValidator(tenant_id="t", client_id="c")
    first = validator._get_jwks_client()
    second = validator._get_jwks_client()
    assert first is second
