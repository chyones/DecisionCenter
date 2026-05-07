"""Node 01 — Auth and RBAC Gate. Spec: Sections 8, 9, and 16."""
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import ProjectMapping, ProjectNotFoundError, RbacDeniedError
from apps.edr.rbac.roles import ROLE_PERMISSIONS, VALID_ROLES, Role


async def run(state: DecisionState) -> DecisionState:
    role = state.role
    project_code = state.project_code

    if not role or role not in VALID_ROLES:
        raise RbacDeniedError(f"Missing or invalid role: {role!r}")

    permissions = ROLE_PERMISSIONS[Role(role)]
    if not permissions.can_generate_report:
        raise RbacDeniedError(f"Role {role!r} cannot generate business reports")

    if not project_code:
        raise RbacDeniedError("project_code is required")

    try:
        mapping = ProjectMapping.load()
        mapping.get(project_code)
    except ProjectNotFoundError:
        raise RbacDeniedError(f"Unknown project_code: {project_code!r}")

    state.allowed_projects = [project_code]
    state.allowed_mailboxes = mapping.allowed_mailboxes(project_code)
    state.allowed_odoo_ids = mapping.allowed_odoo_ids(project_code)
    state.outputs["rbac_status"] = "authorized"
    state.outputs["rbac_role"] = role

    return state.mark("node_01_auth")
