# Contributing

Decision Center is specification-first. Any behavior change must update
`docs/workflows/EDR-AGENTIC-RAG-v2.1.md` in the same change.

## Workflow

1. Pick one implementation phase from Section 31 of the spec.
2. Keep the change scoped to that phase.
3. Add or update tests for the changed behavior.
4. Run `make test` before opening a pull request.

## Rules

- Do not commit secrets, production exports, customer data, or `.env` files.
- Phase 1 must remain read-only.
- Financial numbers must come from Odoo or be reported as unavailable.
- Every generated report must include evidence, audit, and quality gate outputs.
