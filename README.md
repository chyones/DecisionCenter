# Decision Center

> An internal AI Decision Center for senior management. One business question in, one structured executive report out — grounded only in verified company evidence.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/deploy-Docker%20Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![Status](https://img.shields.io/badge/status-phase2d_in_progress_not_live-blue.svg)](#)

---

## What this is

Decision Center is an **agentic RAG** system designed for one job: take a complex business question from a senior manager and produce a single, structured, evidence-backed executive report.

The system reads from:

- **SharePoint** — contracts, BOQ, invoices, letters, RFIs, meeting minutes
- **ownCloud** — secondary document storage
- **Email** (Microsoft Graph) — user mailbox and project shared mailboxes
- **Odoo** — the single source of truth for financial and operational numbers

It produces:

- `executive-decision-report.md` — the report, with source citations
- `evidence-pack.json` — every piece of evidence used
- `audit-log.json` — full trace of what was searched, blocked, and decided
- `quality-gate-result.json` — claim-by-claim validation result

The system **never** invents financial numbers, **never** acts without human approval, and **never** retrieves data the user is not authorized to see.

## Why it exists

Generic RAG fails for executive decision questions because they:

- Require multiple sources (documents + email + ERP).
- Require reconciling conflicts (invoice vs Odoo, draft vs signed).
- Require disclosing missing data instead of guessing.
- Require an audit trail because the answers feed real decisions.

Decision Center uses an **agentic workflow** — Plan → Retrieve → Normalize → Verify → Self-correct → Compose → Quality-gate → Approve → Publish — bounded by tool budgets, RBAC, a deterministic claim checker, and a human review gate.

## Architecture at a glance

```
                       ┌────────────────────────────────────────┐
   Senior Manager ───► │   FastAPI app (Microsoft Entra SSO)    │
                       └───────────────────┬────────────────────┘
                                           │
                                ┌──────────▼──────────┐
                                │  LangGraph workflow  │
                                │   18 fixed nodes     │
                                └──┬────────────────┬──┘
                                   │                │
              ┌────────────────────┼────────────────┼────────────────────┐
              ▼                    ▼                ▼                    ▼
      ┌──────────────┐     ┌──────────────┐  ┌──────────────┐    ┌──────────────┐
      │ Claude Haiku │     │Claude Sonnet │  │   Qdrant     │    │   n8n        │
      │  (Light)     │     │   (Heavy)    │  │ (vectors)    │    │ (connectors) │
      │ classify,    │     │ analyze,     │  │ hybrid search│    │ SharePoint,  │
      │ normalize    │     │ compose      │  │ + RRF        │    │ ownCloud,    │
      └──────────────┘     └──────────────┘  └──────────────┘    │ Email, Odoo  │
                                                                  └──────────────┘
                                   │
                       ┌───────────▼───────────┐
                       │  Postgres + MinIO     │
                       │  audit + reports      │
                       └───────────────────────┘
                                   │
                                   ▼
                            ┌─────────────┐
                            │  Langfuse   │
                            │  (tracing)  │
                            └─────────────┘
```

Single Hetzner CCX23 server. Everything runs in Docker Compose.

## Quick orientation

| Need | Start here |
|---|---|
| Understand AI agent operating rules | [AGENTS.md](AGENTS.md) and [docs/ai/SHARED_CONTEXT.md](docs/ai/SHARED_CONTEXT.md) |
| Understand the locked behavior | [docs/workflows/EDR-AGENTIC-RAG-v2.1.md](docs/workflows/EDR-AGENTIC-RAG-v2.1.md) |
| Understand what is safe to implement next | [docs/admin/CONTROL_PLANE_LOCK.md](docs/admin/CONTROL_PLANE_LOCK.md) and [docs/execution/IMPLEMENTATION_PHASES.md](docs/execution/IMPLEMENTATION_PHASES.md) |
| Understand the live audited state | [docs/execution/CURRENT_PROJECT_STATE.md](docs/execution/CURRENT_PROJECT_STATE.md) |
| Audit current feature coverage | [docs/admin/FEATURE_MATRIX.md](docs/admin/FEATURE_MATRIX.md) |
| Understand the locked UI contract | [docs/design/UI_CONTRACT_v1.md](docs/design/UI_CONTRACT_v1.md) |
| Find documentation by purpose | [docs/README.md](docs/README.md) |
| Understand the Python app package | [apps/edr/README.md](apps/edr/README.md) |
| Understand n8n workflow status | [n8n/README.md](n8n/README.md) |
| Understand utility scripts | [scripts/README.md](scripts/README.md) |

Phase 0, Phase 1A, Phase 1B, Phase 1B.5, Phase 1C, Phase 1D, the
Phase 1D-fixup, Phase 1E, Phase 1F, Phase 1G, Phase 1H, Phase 1I, and
Phases 2A-2C are complete and production is `NOT_LIVE`. Phase 2D is
approval-gated and in progress: Slices 1-6 are implemented, Slice 6 live-UAT
evidence is operator-pending, and Slice 7 (Go-Live Gate) remains blocked until
that evidence exists plus a separate explicit user approval is given.
The phase-status table below is the authoritative marker for the current
project state. Treat the files above as the current authority before changing
code, workflows, schemas, or operational assumptions.

Latest read-only audit verdict: **7/10** and
`NOT_GO_LIVE_READY_BUT_HEALTHY`. Original audit blockers were: production
frontend delivery path missing; production Entra/MSAL frontend auth missing;
live integrations not proven; backup/restore evidence missing; production
hardening evidence missing. Current governance/audit posture is
`GOVERNANCE_BLOCKED_NOT_LIVE`: those original Phase-2C-era blockers have
implementation coverage in Phase 2D Slices 1-5, but production still must
remain `NOT_LIVE`. Remaining go-live blockers are real live UAT evidence,
explicit Slice 7 approval, production credential rotation, and operator-side
connector import/verification.

## AI Agent Operating Context

All AI coding agents must read the shared operating context before editing.
Read these files in order:

1. [AGENTS.md](AGENTS.md)
2. [docs/ai/SHARED_CONTEXT.md](docs/ai/SHARED_CONTEXT.md)
3. [docs/ai/AGENT_HANDOFF.md](docs/ai/AGENT_HANDOFF.md)
4. [docs/ai/agent-state.json](docs/ai/agent-state.json)
5. The latest report named by [docs/ai/agent-state.json](docs/ai/agent-state.json)

The AI context is checked by `python3 scripts/check_ai_context.py` and
`python3 scripts/check_doc_drift.py`, plus the read-only
`python3 scripts/agent_preflight.py` / `python3 scripts/agent_postflight.py`
helpers. These are guardrails against stale assumptions, duplicated work, and
accidental phase or deployment drift. `check_doc_drift.py` enforces an
anchor-currency invariant: the `current_commit` in `docs/ai/agent-state.json`
must be HEAD itself or no more than three commits behind HEAD on the current
branch.

## Repository map

| Path | Purpose |
|---|---|
| `apps/edr/` | FastAPI app, workflow nodes, schemas, retrieval pipeline, exporters, prompts, persistence, and tests |
| `docs/` | Locked workflow spec, control docs, execution plans, policies, contracts, schemas, operations, evaluation docs |
| `docs/ai/` | AI agent shared context, handoff, machine-readable state, skill selection, failure modes, and task template |
| `n8n/` | Real Phase 1C connector workflows (Header Auth, `$env`-sourced credentials) |
| `scripts/` | Infrastructure/operations utilities: Qdrant + MinIO init, doc-drift and AI-context checks, agent pre/post-flight |
| `.github/workflows/` | CI validation: lint, syntax, config coverage, doc/AI-context checks, smoke + integration tests, evaluation suite, pip-audit |
| Root config files | Docker Compose, Caddy, Python packaging, Makefile, env template, and ignore rules |

## Documentation

The single source of truth is the workflow specification:

- **[docs/workflows/EDR-AGENTIC-RAG-v2.1.md](docs/workflows/EDR-AGENTIC-RAG-v2.1.md)** — full specification (35 sections, ~1,700 lines)

Use [docs/README.md](docs/README.md) as the full documentation index. Key supporting documents:

| Topic | Location |
|---|---|
| Control-plane lock | [docs/admin/CONTROL_PLANE_LOCK.md](docs/admin/CONTROL_PLANE_LOCK.md) |
| Phase execution order | [docs/execution/IMPLEMENTATION_PHASES.md](docs/execution/IMPLEMENTATION_PHASES.md) |
| Phase 1A scope | [docs/execution/PHASE_1A_SCOPE.md](docs/execution/PHASE_1A_SCOPE.md) |
| Phase 2A plan | [docs/execution/PHASE_2A_PLAN.md](docs/execution/PHASE_2A_PLAN.md) |
| Phase 2B plan | [docs/execution/PHASE_2B_PLAN.md](docs/execution/PHASE_2B_PLAN.md) |
| Latest full-phase report | [docs/execution/PHASE_2C_REPORT.md](docs/execution/PHASE_2C_REPORT.md) |
| Feature matrix | [docs/admin/FEATURE_MATRIX.md](docs/admin/FEATURE_MATRIX.md) |
| RBAC matrix | [docs/security/rbac_matrix.md](docs/security/rbac_matrix.md) |
| API contracts | [docs/contracts/](docs/contracts/) |
| Policies | [docs/policies/](docs/policies/) |
| Operations (hosting, cost, runbook) | [docs/operations/](docs/operations/) |
| Evaluation (test cases, metrics) | [docs/evaluation/](docs/evaluation/) |
| UI contract | [docs/design/UI_CONTRACT_v1.md](docs/design/UI_CONTRACT_v1.md) |
| JSON schemas | [docs/schemas/](docs/schemas/) |

## Deployment profile (locked)

This repo is sized and configured for one specific deployment:

| Parameter | Value |
|---|---|
| Users | 5 senior management |
| Throughput | ≤ 25 requests/day, ≤ 5 concurrent |
| Languages | Arabic + English |
| Hosting | Single Hetzner Cloud CCX23 server |
| Heavy LLM | Claude Sonnet 4.6 |
| Light LLM | Claude Haiku 4.5 |
| Embeddings | Voyage-3-large |
| Reranker | Cohere Rerank 3.5 |
| Vector store | Qdrant (self-hosted) |
| Orchestration | LangGraph |
| Connectors | n8n |
| Observability | Langfuse Cloud |
| Identity | Microsoft Entra ID |
| **Monthly cost target** | **≤ USD 300** |

## Quick start

Prerequisites: a Hetzner CCX23 server (or equivalent), a domain pointing to it, and API keys for Anthropic, Voyage, and Cohere.

```bash
# On the server
git clone https://github.com/chyones/DecisionCenter.git
cd DecisionCenter
cp .env.example .env
# Edit .env with your credentials and PUBLIC_HOSTNAME
make up
make smoke
```

See [docs/operations/runbook.md](docs/operations/runbook.md) for the full deployment runbook.

## Implementation status

The repo is structured for **vibe coding** with Claude Code: each session implements one phase from Section 31 of the spec, with a clear exit test.

| Phase | Status |
|---|---|
| 0 — Control and documentation lock | Locked |
| 1A — Infrastructure Foundation | Complete |
| 1B — RBAC and Identity | Complete |
| 1B.5 — Async Connector Runtime Readiness | Complete |
| 1C — n8n Connector Workflows | Complete (Header Auth + `$env` credentials) |
| 1D — Embedding and Vector Retrieval | Complete |
| 1D-fixup — Audit closure | Complete |
| 1E — LLM Nodes | Complete |
| 1F — Persistence and Audit | Complete |
| 1G — Human Review Gate | Complete |
| 1H — Evaluation and Hardening | Complete |
| 1I — Frontend Foundation | Complete (static scaffolds, no API wiring) |
| 2A — User Chat Workspace Implementation | Complete; E2E and U-01..U-16 manual QA passed; production `NOT_LIVE` |
| 2B — Admin Visual Control Plane Implementation | Complete; A-01..A-23 manual QA passed; production `NOT_LIVE` |
| 2C — UI Hardening and Acceptance Validation | Complete; 54/54 Playwright tests passed across Chromium, Firefox, and WebKit; production `NOT_LIVE` |
| 2D — Production Integration and Go-Live Hardening | In progress; Slices 1-6 implemented (production `NOT_LIVE`), Slice 6 live UAT operator-pending, Slice 7 Go-Live Gate blocked pending explicit user approval |

Every node in `apps/edr/graph/` carries a docstring referencing the relevant spec section so Claude Code can implement it directly from the contract.

Current audited state is tracked in [docs/execution/CURRENT_PROJECT_STATE.md](docs/execution/CURRENT_PROJECT_STATE.md).

## Cost estimate

| Item | USD/month |
|---|---|
| Anthropic API (with prompt caching) | 220 |
| Voyage embeddings | 5 |
| Cohere reranker | 10 |
| Hetzner CCX23 | 35 |
| Hetzner Storage Box (backups) | 5 |
| Domain + TLS | 1 |
| Langfuse Cloud (free tier) | 0 |
| **Total** | **~276** |

Detailed in [docs/operations/cost_model.md](docs/operations/cost_model.md).

## License

[MIT](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All changes to behaviour MUST be reflected in the spec at `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`. Code without spec coverage is not merged.
