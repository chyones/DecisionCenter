"""Canonical 9-role RBAC model. Source: docs/security/rbac_matrix.md."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    EXECUTIVE = "executive"
    PROJECT_MANAGER = "project_manager"
    FINANCE = "finance"
    COMMERCIAL = "commercial"
    DOCUMENT_CONTROL = "document_control"
    PROCUREMENT = "procurement"
    LEGAL = "legal"
    AUDITOR = "auditor"
    ADMIN = "admin"


@dataclass(frozen=True)
class RolePermissions:
    can_access_sharepoint: bool
    can_access_owncloud: bool
    can_access_own_mailbox: bool
    can_access_shared_mailboxes: bool
    can_access_odoo_budget: bool
    can_access_odoo_actual_cost: bool
    can_approve: bool
    can_access_audit_logs: bool
    # Admin role cannot generate business reports (spec Section 9)
    can_generate_report: bool = True


ROLE_PERMISSIONS: dict[Role, RolePermissions] = {
    Role.EXECUTIVE: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=False,
        can_access_shared_mailboxes=True,
        can_access_odoo_budget=True,
        can_access_odoo_actual_cost=True,
        can_approve=True,
        can_access_audit_logs=True,
    ),
    Role.PROJECT_MANAGER: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=True,
        can_access_shared_mailboxes=True,
        can_access_odoo_budget=True,
        can_access_odoo_actual_cost=True,
        can_approve=True,
        can_access_audit_logs=True,
    ),
    Role.FINANCE: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=True,
        can_access_shared_mailboxes=True,
        can_access_odoo_budget=True,
        can_access_odoo_actual_cost=True,
        can_approve=True,
        can_access_audit_logs=True,
    ),
    Role.COMMERCIAL: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=True,
        can_access_shared_mailboxes=True,
        can_access_odoo_budget=True,
        can_access_odoo_actual_cost=True,
        can_approve=True,
        can_access_audit_logs=True,
    ),
    Role.DOCUMENT_CONTROL: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=True,
        can_access_shared_mailboxes=True,
        can_access_odoo_budget=False,
        can_access_odoo_actual_cost=False,
        can_approve=True,
        can_access_audit_logs=True,
    ),
    Role.PROCUREMENT: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=True,
        can_access_shared_mailboxes=True,
        can_access_odoo_budget=True,
        can_access_odoo_actual_cost=True,
        can_approve=True,
        can_access_audit_logs=True,
    ),
    Role.LEGAL: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=True,
        can_access_shared_mailboxes=True,
        can_access_odoo_budget=True,
        can_access_odoo_actual_cost=True,
        can_approve=True,
        can_access_audit_logs=True,
    ),
    Role.AUDITOR: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=False,
        can_access_shared_mailboxes=False,
        can_access_odoo_budget=True,
        can_access_odoo_actual_cost=True,
        can_approve=False,
        can_access_audit_logs=True,
        can_generate_report=False,
    ),
    Role.ADMIN: RolePermissions(
        can_access_sharepoint=False,
        can_access_owncloud=False,
        can_access_own_mailbox=False,
        can_access_shared_mailboxes=False,
        can_access_odoo_budget=False,
        can_access_odoo_actual_cost=False,
        can_approve=False,
        can_access_audit_logs=True,
        can_generate_report=False,
    ),
}

VALID_ROLES: frozenset[str] = frozenset(r.value for r in Role)
