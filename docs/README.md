# DecisionCenter Documentation Index

This index is navigation only. It does not replace the locked workflow specification or the
control-plane decisions.

## Authority Chain

| Level | Document | Purpose |
|---|---|---|
| 1 | [workflows/EDR-AGENTIC-RAG-v2.1.md](workflows/EDR-AGENTIC-RAG-v2.1.md) | Behavioral source of truth for the EDR system |
| 2 | [admin/CONTROL_PLANE_LOCK.md](admin/CONTROL_PLANE_LOCK.md) | Phase 0 and Phase 1A control decisions, readiness, and boundaries |
| 3 | [design/UI_CONTRACT_v1.md](design/UI_CONTRACT_v1.md) | Locked UI contract; specification only, no frontend implementation |
| 4 | [execution/IMPLEMENTATION_PHASES.md](execution/IMPLEMENTATION_PHASES.md) | Authoritative implementation phase order |
| 5 | [PRE_START_IMPLEMENTATION_PLAN.md](PRE_START_IMPLEMENTATION_PLAN.md) | Audit-backed pre-start plan, current gaps, risks, and validation gates |
| 6 | [admin/FEATURE_MATRIX.md](admin/FEATURE_MATRIX.md) | Current feature coverage and known gaps by component |

## Current Control State

| Area | Current authority |
|---|---|
| Environment baseline | `.env.example` has 36 keys; `apps/edr/config.py` loads all 36 |
| Phase 1A status | Infrastructure Foundation is implemented locally and rated 10/10 ready |
| Next safe phase | Phase 1B: RBAC and Identity only |
| n8n workflows | Present as placeholders with empty `nodes` arrays |
| Evaluation baseline | One executable golden example exists; more cases are required before go-live |
| Admin UI | Not specified; any Admin UI is a future spec change |

## Directory Guide

| Directory | Purpose |
|---|---|
| [admin/](admin/) | Control-plane lock, feature matrix, and implementation coverage audit |
| [approvals/](approvals/) | Human review and approval policy documents |
| [config/](config/) | Example project/source mapping inputs |
| [contracts/](contracts/) | External API contracts for Graph, Odoo, and ownCloud |
| [design/](design/) | Locked UI contract and design-source navigation |
| [evaluation/](evaluation/) | Golden-set format, required cases, and metrics definitions |
| [execution/](execution/) | Phase sequence and phase-specific implementation scopes |
| [operations/](operations/) | Hosting, runbook, cost, observability, backup, restore, and connector connection guide |
| [policies/](policies/) | Evidence, RBAC, email, Odoo, data minimization, and security policies |
| [schemas/](schemas/) | JSON Schemas for report, evidence, audit, and quality-gate artifacts |
| [security/](security/) | Canonical RBAC matrix |
| [templates/](templates/) | Report output templates |
| [workflows/](workflows/) | Locked end-to-end EDR workflow specification |

## Reading Order For A New Engineer

1. Read [admin/CONTROL_PLANE_LOCK.md](admin/CONTROL_PLANE_LOCK.md) to understand what is locked.
2. Read [execution/IMPLEMENTATION_PHASES.md](execution/IMPLEMENTATION_PHASES.md) to understand phase boundaries.
3. Read [admin/FEATURE_MATRIX.md](admin/FEATURE_MATRIX.md) to see current implementation coverage.
4. Read the relevant policy, schema, and contract files for the phase being implemented.
5. Read the relevant sections of [workflows/EDR-AGENTIC-RAG-v2.1.md](workflows/EDR-AGENTIC-RAG-v2.1.md) before changing behavior.
