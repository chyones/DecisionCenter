# EDR Application Package

`apps/edr/` contains the FastAPI application, the fixed 18-node LangGraph
workflow, retrieval/connectors, exporters, persistence, RBAC, evaluation, and
tests for DecisionCenter.

## Package Map

| Path | Purpose |
|---|---|
| `app.py` | FastAPI routes, health checks, Entra/local-bypass claim extraction, report staging, review, download, Phase 2A workspace APIs, Phase 2B admin APIs, and upload handling |
| `config.py` | Pydantic settings for the locked `.env.example` baseline |
| `auth/` | Microsoft Entra JWT validation |
| `rbac/` | Canonical 9-role permissions and project-source mapping loader |
| `connectors/` | n8n webhook client wrappers and response validation |
| `retrieval/` | Chunking, embeddings, Qdrant, rerank, hybrid search, and cache helpers |
| `graph/` | Fixed 18-node async workflow and state/runner helpers |
| `exporters/` | Markdown, Word, Excel, PDF, and PowerPoint exports |
| `persistence/` | PostgreSQL audit/review state and MinIO artifact/upload storage |
| `evaluation/` | Executable golden-set runner and local load-test helpers |
| `schemas/` | Pydantic models corresponding to the JSON Schemas in `docs/schemas/` |
| `tests/` | Smoke and integration tests for RBAC, connectors, retrieval, LLM nodes, persistence, review/publish, evaluation, Phase 2A workspace APIs, and Phase 2B admin APIs |

## Current Boundary

Phases 1A through 1I, the Phase 1D-fixup, Phase 2A, and Phase 2B are complete.
Phase 2C is in progress for UI hardening and acceptance validation.
Production is `NOT_LIVE`. Phase 2B closeout evidence is recorded in
`docs/execution/PHASE_2B_REPORT.md`; the active Phase 2C plan is
`docs/execution/PHASE_2C_PLAN.md`.

Current active phase: Phase 2C — UI Hardening & Acceptance Validation. Do not
deploy, do not expand Phase 2C beyond UI validation/hardening, and do not add
unrelated product behavior.

Before changing behavior, read `docs/admin/CONTROL_PLANE_LOCK.md`,
`docs/execution/IMPLEMENTATION_PHASES.md`, `docs/ai/SHARED_CONTEXT.md`, and
the relevant spec sections in `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`.
