# EDR Application Package

`apps/edr/` contains the Python FastAPI app and the current EDR workflow skeleton.

## Package Map

| Path | Purpose |
|---|---|
| `app.py` | FastAPI routes, health checks, and the staged-report entry point |
| `config.py` | Pydantic settings for the 36-key `.env.example` baseline |
| `connectors/` | n8n webhook client wrappers; real workflow logic lives outside Python in Phase 1C |
| `evaluation/` | Stub evaluation runner, promptfoo placeholder, and one executable golden example |
| `exporters/` | Export helpers for Markdown, Word, Excel, PDF, and PowerPoint |
| `graph/` | Fixed 18-node workflow skeleton and state/runner helpers |
| `prompts/` | Prompt source files to be wired in later LLM phases |
| `retrieval/` | Retrieval helper skeletons, RRF implementation, cache, embedding, and rerank placeholders |
| `schemas/` | Pydantic models corresponding to the JSON Schemas in `docs/schemas/` |
| `tests/` | Smoke tests that validate the fixed workflow skeleton and approval gate boundary |

## Current Boundary

Phase 1A infrastructure is complete. Product logic is intentionally not implemented here yet:
graph nodes remain stubbed, embeddings and reranking raise `NotImplementedError`, n8n workflows
are placeholders, and no LLM calls are wired.

Before changing behavior, read `docs/admin/CONTROL_PLANE_LOCK.md`,
`docs/execution/IMPLEMENTATION_PHASES.md`, and the relevant spec sections in
`docs/workflows/EDR-AGENTIC-RAG-v2.1.md`.

