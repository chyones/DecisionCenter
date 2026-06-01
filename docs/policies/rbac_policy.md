> **⚠ SUPERSEDED FOR THE OWNER-OPERATOR DEPLOYMENT (2026-05-31).**
> The separation-of-duties controls described below — admin content-blindness,
> two-person approval, and own-report-only visibility — were intentionally
> relaxed per the owner-approved
> [`SPEC_CHANGE_2026-05-31_owner_operator_model`](../execution/SPEC_CHANGE_2026-05-31_owner_operator_model.md).
> Admin is now a full owner; owners share report visibility; self-approval is
> allowed. The automated quality gate, audit logging, and the project-scoped
> email allowlist remain in force. Production remains `NOT_LIVE`.

# RBAC Policy

Decision Center must enforce RBAC before retrieval and inside each connector
call. A user may only retrieve evidence for projects, mailboxes, and Odoo
records explicitly mapped to that user or role.

The canonical role model is the 9-role matrix in `docs/security/rbac_matrix.md`.
