"""Canonical 9-role RBAC model. Source: docs/security/rbac_matrix.md.

Owner-operator model (docs/execution/SPEC_CHANGE_2026-05-31_owner_operator_model.md):
DecisionCenter is used by ~5 equal company owners plus an owner who is also the
system operator. ``admin`` is therefore a full owner (generate/approve/read +
system settings), report visibility is shared among owner roles, and two-person
approval is removed. Email scope stays project-scoped (own-mailbox off; the
per-project mailbox allowlist remains the authority).
"""
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
    # Owner-operator model: admin is a full owner and may generate business
    # reports. Default True; only auditor opts out.
    can_generate_report: bool = True
    # Owner roles (executive, admin) may view ALL owners' reports — shared
    # decision-support for equal owners. Auditor also reads all (read-only),
    # handled explicitly in the API layer.
    can_view_all_reports: bool = False


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
        can_view_all_reports=True,
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
    # Owner-operator: admin is a full owner (business powers) PLUS system
    # settings. Email stays project-scoped: own-mailbox off, shared mailboxes
    # on (governed by the per-project Source Mapping allowlist).
    Role.ADMIN: RolePermissions(
        can_access_sharepoint=True,
        can_access_owncloud=True,
        can_access_own_mailbox=False,
        can_access_shared_mailboxes=True,
        can_access_odoo_budget=True,
        can_access_odoo_actual_cost=True,
        can_approve=True,
        can_access_audit_logs=True,
        can_generate_report=True,
        can_view_all_reports=True,
    ),
}

VALID_ROLES: frozenset[str] = frozenset(r.value for r in Role)
