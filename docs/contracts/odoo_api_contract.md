# Odoo API Contract

Odoo is the only source of truth for financial and operational numbers.

## Access

- Use a read-only API user.
- Scope records by project and RBAC.
- Do not write, approve, or modify any Odoo record in Phase 1.

## Required Response Fields

- record model and ID
- project code
- financial or operational value
- currency when applicable
- record timestamp
- source hash or immutable reference

## Failure Handling

Missing values must be returned as unavailable. The workflow must not infer
financial values from documents or email.
