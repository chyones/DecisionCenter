# DecisionCenter Documentation Index

This index is navigation only. It does not replace the locked workflow specification or the
control-plane decisions.

## Authority Chain

| Level | Document | Purpose |
|---|---|---|
| 1 | [workflows/EDR-AGENTIC-RAG-v2.1.md](workflows/EDR-AGENTIC-RAG-v2.1.md) | Behavioral source of truth for the EDR system |
| 2 | [admin/CONTROL_PLANE_LOCK.md](admin/CONTROL_PLANE_LOCK.md) | Locked control decisions, readiness, and boundaries |
| 3 | [design/UI_CONTRACT_v1.md](design/UI_CONTRACT_v1.md) | Locked UI contract; specification only, no frontend implementation |
| 4 | [execution/IMPLEMENTATION_PHASES.md](execution/IMPLEMENTATION_PHASES.md) | Authoritative implementation phase order |
| 5 | [execution/CURRENT_PROJECT_STATE.md](execution/CURRENT_PROJECT_STATE.md) | Live audited project state and readiness ratings |
| 6 | [admin/FEATURE_MATRIX.md](admin/FEATURE_MATRIX.md) | Current feature coverage and known gaps by component |
| 7 | [PRE_START_IMPLEMENTATION_PLAN.md](PRE_START_IMPLEMENTATION_PLAN.md) | Historical audit-backed pre-start plan (superseded by the docs above for current state) |

## Current Control State

The authoritative, kept-current control state lives in:

- [admin/CONTROL_PLANE_LOCK.md](admin/CONTROL_PLANE_LOCK.md) — locked decisions, environment baseline, readiness decision.
- [execution/CURRENT_PROJECT_STATE.md](execution/CURRENT_PROJECT_STATE.md) — live audited stage, completed phases, blockers, safe next phase.
- [admin/FEATURE_MATRIX.md](admin/FEATURE_MATRIX.md) — per-component coverage and open gaps.
- [ai/agent-state.json](ai/agent-state.json) — machine-readable phase/production status.

This index intentionally does not duplicate those numbers, so it cannot drift from them.

## Directory Guide

| Directory | Purpose |
|---|---|
| [admin/](admin/) | Control-plane lock and feature matrix |
| [ai/](ai/) | AI agent shared context, handoff, machine-readable state, skill selection, failure modes, task template |
| [approvals/](approvals/) | Human review and approval policy documents |
| [config/](config/) | Example project/source mapping inputs |
| [contracts/](contracts/) | External API contracts for Graph, Odoo, and ownCloud |
| [design/](design/) | Locked UI contract and design-source navigation |
| [evaluation/](evaluation/) | Golden-set format, required cases, and metrics definitions |
| [execution/](execution/) | Phase sequence, phase-specific scopes, and phase reports |
| [operations/](operations/) | Hosting, runbook, cost, observability, backup, restore, and connector connection guide |
| [policies/](policies/) | Evidence, RBAC, email, Odoo, data minimization, and security policies |
| [schemas/](schemas/) | JSON Schemas for report, evidence, audit, and quality-gate artifacts |
| [security/](security/) | Canonical RBAC matrix |
| [templates/](templates/) | Report output templates |
| [workflows/](workflows/) | Locked end-to-end EDR workflow specification |

## Reading Order For A New Engineer

1. Read [admin/CONTROL_PLANE_LOCK.md](admin/CONTROL_PLANE_LOCK.md) to understand what is locked.
2. Read [execution/CURRENT_PROJECT_STATE.md](execution/CURRENT_PROJECT_STATE.md) to understand the live state and safe next phase.
3. Read [execution/IMPLEMENTATION_PHASES.md](execution/IMPLEMENTATION_PHASES.md) to understand phase boundaries.
4. Read [admin/FEATURE_MATRIX.md](admin/FEATURE_MATRIX.md) to see current implementation coverage.
5. Read the relevant policy, schema, and contract files for the phase being implemented.
6. Read the relevant sections of [workflows/EDR-AGENTIC-RAG-v2.1.md](workflows/EDR-AGENTIC-RAG-v2.1.md) before changing behavior.
