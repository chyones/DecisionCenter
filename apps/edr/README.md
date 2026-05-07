# EDR Application Package

`apps/edr/` contains the Python FastAPI app and the current EDR workflow skeleton.

## Package Map

| Path | Purpose |
|---|---|
| `app.py` | FastAPI routes, health checks, Entra/bypass claim extraction, and the staged-report entry point |
| `config.py` | Pydantic settings for the 36-key `.env.example` baseline |
| `connectors/` | n8n webhook client wrappers; real workflow logic lives outside Python in Phase 1C |
| `evaluation/` | Stub evaluation runner, promptfoo placeholder, and one executable golden example |
| `exporters/` | Export helpers for Markdown, Word, Excel, PDF, and PowerPoint |
| `graph/` | Fixed 18-node workflow skeleton and state/runner helpers |
| `prompts/` | Prompt source files to be wired in later LLM phases |
| `retrieval/` | Retrieval helper skeletons, RRF implementation, cache, embedding, and rerank placeholders |
| `schemas/` | Pydantic models corresponding to the JSON Schemas in `docs/schemas/` |
| `tests/` | Smoke and RBAC integration tests that validate the fixed workflow skeleton, node 01 authorization, and approval gate boundary |

## Current Boundary

Phase 1A infrastructure, Phase 1B RBAC/identity, and Phase 1B.5 async runtime readiness
are complete. Node 01 performs role/project authorization from JWT or local bypass claims
and `docs/config/project_source_mapping.json`. All 18 graph nodes are async.

Product logic remains intentionally limited: retrieval nodes 05-08 are stubbed, n8n
workflows are empty placeholders, embeddings and reranking raise `NotImplementedError`,
persistence/audit is not implemented, approval APIs do not exist, and no LLM calls are wired.

Safe next phase: Phase 1C, limited to real n8n connector workflows plus schema/curl
validation. Do not add Python node logic, LLM calls, embeddings, persistence, approval APIs,
frontend work, or unrelated product behavior during Phase 1C.

Before changing behavior, read `docs/admin/CONTROL_PLANE_LOCK.md`,
`docs/execution/IMPLEMENTATION_PHASES.md`, and the relevant spec sections in
`docs/workflows/EDR-AGENTIC-RAG-v2.1.md`.
