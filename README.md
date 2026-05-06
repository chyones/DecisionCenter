# Decision Center

> An internal AI Decision Center for senior management. One business question in, one structured executive report out — grounded only in verified company evidence.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/deploy-Docker%20Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![Status](https://img.shields.io/badge/status-phase1a_infra_ready-blue.svg)](#)

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

Decision Center uses an **agentic workflow** — Plan → Retrieve → Normalize → Verify → Self-correct → Compose → Quality-gate → Approve — bounded by tool budgets, RBAC, and a claim checker.

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

## Documentation

The single source of truth is the workflow specification:

- **[docs/workflows/EDR-AGENTIC-RAG-v2.1.md](docs/workflows/EDR-AGENTIC-RAG-v2.1.md)** — full specification (35 sections, ~1,700 lines)

Supporting documents:

| Topic | Location |
|---|---|
| RBAC matrix | [docs/security/rbac_matrix.md](docs/security/rbac_matrix.md) |
| API contracts | [docs/contracts/](docs/contracts/) |
| Policies | [docs/policies/](docs/policies/) |
| Operations (hosting, cost, runbook) | [docs/operations/](docs/operations/) |
| Evaluation (test cases, metrics) | [docs/evaluation/](docs/evaluation/) |
| JSON schemas | [docs/schemas/](docs/schemas/) |
| Phase execution order | [docs/execution/IMPLEMENTATION_PHASES.md](docs/execution/IMPLEMENTATION_PHASES.md) |
| Control-plane lock | [docs/admin/CONTROL_PLANE_LOCK.md](docs/admin/CONTROL_PLANE_LOCK.md) |

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
# Edit .env with your credentials and domain
make up
make smoke
```

See [docs/operations/runbook.md](docs/operations/runbook.md) for the full deployment runbook.

## Implementation status

The repo is structured for **vibe coding** with Claude Code: each session implements one phase from Section 31 of the spec, with a clear exit test.

| Phase | Status |
|---|---|
| 0 — Control and documentation lock | Locked |
| 1A — Infrastructure Foundation | Implemented locally |
| 1B — RBAC and Identity | Not started |
| 1C — n8n Connector Workflows | Placeholders only |
| 1D — Embedding and Vector Retrieval | Not started |
| 1E — LLM Nodes | Not started |
| 1F — Persistence and Audit | Not started |
| 1G — Human Review Gate | Not started |
| 1H — Evaluation and Hardening | Not started |

Every node in `apps/edr/graph/` carries a docstring referencing the relevant spec section so Claude Code can implement it directly from the contract.

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
