"""Phase 1B integration tests: RBAC enforcement in node_01_auth.

Owner-operator model (SPEC_CHANGE 2026-05-31): admin is a full owner and is
report-capable; only auditor is denied report generation.

Required cases (spec Phase 1B validation gate):
  1. Authorized user  — valid role + known project → rbac_status = "authorized"
  2. Unknown project  — valid role + unknown project_code → RbacDeniedError
  3. Auditor          — read-only role → RbacDeniedError (cannot generate)

Additional coverage:
  4. Missing role → RbacDeniedError
  5. All 9 roles enumerated (8 report-capable incl. admin + auditor read-only)
"""
import asyncio

import pytest

from apps.edr.graph import node_01_auth
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import RbacDeniedError
from apps.edr.rbac.roles import Role


def _state(role: str | None, project_code: str | None = "PRJ-001") -> DecisionState:
    return DecisionState(
        request_id="test",
        user_id="test-user",
        role=role,
        project_code=project_code,
        query="What is the project status?",
    )


# --- Required 3 cases ---

def test_authorized_user() -> None:
    result = asyncio.run(node_01_auth.run(_state("executive")))
    assert result.outputs["rbac_status"] == "authorized"
    assert result.outputs["rbac_role"] == "executive"
    assert "PRJ-001" in result.allowed_projects
    assert "node_01_auth" in result.visited_nodes


def test_admin_role_is_report_capable() -> None:
    # Owner-operator model: admin is a full owner and may generate reports.
    result = asyncio.run(node_01_auth.run(_state("admin")))
    assert result.outputs["rbac_status"] == "authorized"
    assert result.outputs["rbac_role"] == "admin"


def test_unknown_project_code() -> None:
    with pytest.raises(RbacDeniedError, match="Unknown project_code"):
        asyncio.run(node_01_auth.run(_state("executive", project_code="UNKNOWN-999")))


# --- Additional coverage ---

def test_missing_role_raises() -> None:
    with pytest.raises(RbacDeniedError, match="Missing or invalid role"):
        asyncio.run(node_01_auth.run(_state(None)))


def test_invalid_role_string_raises() -> None:
    with pytest.raises(RbacDeniedError, match="Missing or invalid role"):
        asyncio.run(node_01_auth.run(_state("superuser")))


def test_missing_project_code_raises() -> None:
    with pytest.raises(RbacDeniedError, match="project_code is required"):
        asyncio.run(node_01_auth.run(_state("executive", project_code=None)))


# --- 9-role coverage ---

REPORT_CAPABLE_ROLES = [
    Role.EXECUTIVE,
    Role.PROJECT_MANAGER,
    Role.FINANCE,
    Role.COMMERCIAL,
    Role.DOCUMENT_CONTROL,
    Role.PROCUREMENT,
    Role.LEGAL,
]

READ_ONLY_ROLES = [Role.AUDITOR]


@pytest.mark.parametrize("role", REPORT_CAPABLE_ROLES)
def test_all_report_capable_roles_authorized(role: Role) -> None:
    result = asyncio.run(node_01_auth.run(_state(role.value)))
    assert result.outputs["rbac_status"] == "authorized"
    assert result.outputs["rbac_role"] == role.value


def test_auditor_role_denied_for_report_generation() -> None:
    with pytest.raises(RbacDeniedError, match="cannot generate business reports"):
        asyncio.run(node_01_auth.run(_state(Role.AUDITOR.value)))


def test_admin_role_authorized_with_known_project() -> None:
    # Owner-operator model: admin is report-capable (was denied pre-2026-05-31).
    result = asyncio.run(node_01_auth.run(_state(Role.ADMIN.value)))
    assert result.outputs["rbac_status"] == "authorized"


def test_9_roles_total() -> None:
    assert len(Role) == 9


# --- Populated state fields ---

def test_allowed_mailboxes_includes_group_mail_when_email_source_enabled() -> None:
    # PRJ-001 email source verified: GROUP_MEMBERS_READ, mail_enabled=True.
    # The Microsoft Group mailbox is included in allowed_mailboxes when
    # "email" is in enabled_sources and the group mailbox is mail-enabled.
    result = asyncio.run(node_01_auth.run(_state("executive")))
    assert "ConstructionofCivilDefenseCenterinAlMirfaAlDhafraRegion@elrace.com" in result.allowed_mailboxes


def test_allowed_odoo_ids_use_verified_odoo_project_id() -> None:
    result = asyncio.run(node_01_auth.run(_state("executive")))
    assert result.allowed_odoo_ids == ["14602"]
