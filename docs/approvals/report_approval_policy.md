> **⚠ SUPERSEDED FOR THE OWNER-OPERATOR DEPLOYMENT (2026-05-31).**
> The separation-of-duties controls described below — admin content-blindness,
> two-person approval, and own-report-only visibility — were intentionally
> relaxed per the owner-approved
> [`SPEC_CHANGE_2026-05-31_owner_operator_model`](../execution/SPEC_CHANGE_2026-05-31_owner_operator_model.md).
> Admin is now a full owner; owners share report visibility; self-approval is
> allowed. The automated quality gate, audit logging, and the project-scoped
> email allowlist remain in force. Production remains `NOT_LIVE`.

# Report Approval Policy

Phase 1 reports are saved to staging first. A final report may be published
only after human approval, and the final path must include an approval log.

Approval roles are governed by `docs/security/rbac_matrix.md`. No approval or
rejection API endpoint exists in the current skeleton.
