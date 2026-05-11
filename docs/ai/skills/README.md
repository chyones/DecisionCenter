# AI Agent Skill Selection

> This file is read-only guidance for agents. It does not change product behavior.

Use this table to classify a task before editing any source file. If a task
spans multiple skill types, run the validation for every type touched.

---

## 1. Docs / Truth Work

| | |
|---|---|
| **When to use** | Updating phase reports, agent state, feature matrix, implementation phases, control plane lock, or README after a phase closes or a fixup lands. |
| **Files usually inspected** | `docs/ai/agent-state.json`, `docs/execution/*.md`, `docs/admin/*.md`, `README.md`, `scripts/check_doc_drift.py`, `scripts/check_ai_context.py` |
| **Files usually edited** | `docs/execution/PHASE_*_REPORT.md`, `docs/execution/CURRENT_PROJECT_STATE.md`, `docs/execution/IMPLEMENTATION_PHASES.md`, `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/admin/FEATURE_MATRIX.md`, `docs/ai/agent-state.json`, `README.md` |
| **Forbidden changes** | Do not change `.env.example` keys without updating `apps/edr/config.py` and CI. Do not change truth files to match chat memory; match live repo state only. Do not declare a phase complete without CI evidence. |
| **Required validation** | `python3 scripts/check_doc_drift.py`, `python3 scripts/check_ai_context.py` |
| **Final report requirements** | List every truth file edited, the old claim, the new claim, and the evidence (commit hash or CI run). |

## 2. Backend Work

| | |
|---|---|
| **When to use** | Changing FastAPI routes, request/response schemas, graph node logic, exporters, or the LLM client. |
| **Files usually inspected** | `apps/edr/app.py`, `apps/edr/schemas/*.py`, `apps/edr/graph/*.py`, `apps/edr/exporters/*.py`, `apps/edr/llm.py`, `apps/edr/config.py` |
| **Files usually edited** | `apps/edr/app.py`, `apps/edr/graph/node_*.py`, `apps/edr/schemas/*.py`, `apps/edr/exporters/*.py`, `apps/edr/llm.py` |
| **Forbidden changes** | Do not change locked spec behavior without updating `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`. Do not add new env keys without adding them to `.env.example` and `config.py`. Do not bypass RBAC or auth. |
| **Required validation** | `ruff check apps scripts`, `python3 -m compileall -q apps scripts`, `pytest apps/edr/tests/smoke`, `pytest apps/edr/tests/integration` |
| **Final report requirements** | List routes/nodes changed, schema changes, test count before/after, and any spec section updated. |

## 3. Retrieval / Evaluation Work

| | |
|---|---|
| **When to use** | Changing embeddings, chunking, reranking, Qdrant store, evidence cache, golden set, evaluation runner, or load test. |
| **Files usually inspected** | `apps/edr/retrieval/*.py`, `apps/edr/evaluation/*.py`, `apps/edr/evaluation/goldenset/*.jsonl`, `docs/evaluation/*.md` |
| **Files usually edited** | `apps/edr/retrieval/*.py`, `apps/edr/evaluation/run.py`, `apps/edr/evaluation/load_test.py`, `apps/edr/evaluation/goldenset/*.jsonl`, `apps/edr/evaluation/promptfoo.config.yaml` |
| **Forbidden changes** | Do not reduce golden-set case count. Do not relax pass-rate or precision thresholds. Do not add external service dependencies to the evaluation runner. |
| **Required validation** | `python -m apps.edr.evaluation.run --suite goldenset --min-pass-rate 0.95 --min-precision 0.90`, `pytest apps/edr/tests/integration/test_evaluation.py`, `pytest apps/edr/tests/integration/test_load_test.py` |
| **Final report requirements** | Report golden-set count, pass rate, precision, and any new categories added. |

## 4. Security / RBAC Work

| | |
|---|---|
| **When to use** | Changing roles, permissions, JWT validation, project mapping, mailbox allowlists, or audit logging of auth events. |
| **Files usually inspected** | `apps/edr/rbac/*.py`, `apps/edr/auth/*.py`, `apps/edr/graph/node_01_auth.py`, `docs/security/rbac_matrix.md`, `docs/config/project_source_mapping.json` |
| **Files usually edited** | `apps/edr/rbac/*.py`, `apps/edr/auth/*.py`, `apps/edr/graph/node_01_auth.py`, `docs/security/rbac_matrix.md` |
| **Forbidden changes** | Do not add new roles without updating the spec and migration plan. Do not remove audit logging of auth failures. Do not weaken password hashing or JWT validation. Do not hard-code credentials. |
| **Required validation** | `pytest apps/edr/tests/integration/test_rbac.py`, `pytest apps/edr/tests/integration/test_phase1d_security.py`, `ruff check apps scripts` |
| **Final report requirements** | List role/permission changes, new test cases, and any spec or matrix updates. |

## 5. Persistence / Audit Work

| | |
|---|---|
| **When to use** | Changing PostgreSQL schema, MinIO store, audit log format, review decisions, or initialization scripts. |
| **Files usually inspected** | `apps/edr/persistence/*.py`, `scripts/init_qdrant.py`, `scripts/init_minio.py`, `docker-compose.yml` |
| **Files usually edited** | `apps/edr/persistence/*.py`, `apps/edr/graph/node_15_save_audit.py`, `apps/edr/graph/node_16_review.py`, `apps/edr/graph/node_17_publish.py` |
| **Forbidden changes** | Do not drop existing columns/tables without a migration plan. Do not log sensitive data (query text, evidence excerpts, user IDs in plain text). Do not bypass write-once final artifact rules. |
| **Required validation** | `pytest apps/edr/tests/integration/test_phase1f.py`, `pytest apps/edr/tests/integration/test_phase1g.py`, `python3 -m compileall -q apps scripts` |
| **Final report requirements** | List schema changes, migration steps, and evidence that hashed IDs and write-once rules are preserved. |

## 6. Release / Closeout Work

| | |
|---|---|
| **When to use** | Closing a phase, updating truth files, creating phase reports, or reconciling agent state after CI passes. |
| **Files usually inspected** | All truth files, CI logs, `.github/workflows/ci.yml`, `docs/ai/agent-state.json` |
| **Files usually edited** | `docs/execution/PHASE_*_REPORT.md`, `docs/ai/agent-state.json`, `docs/execution/CURRENT_PROJECT_STATE.md`, `docs/execution/IMPLEMENTATION_PHASES.md`, `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/admin/FEATURE_MATRIX.md`, `README.md` |
| **Forbidden changes** | Do not change `current_commit` to a moving HEAD; it must be a verified anchor. Do not advance `status` until CI passes. Do not set `production_status` to LIVE. Do not start the next phase without explicit user approval. |
| **Required validation** | `python3 scripts/check_doc_drift.py`, `python3 scripts/check_ai_context.py`, CI success on the closeout commit, `ruff check .`, `python3 -m compileall -q apps scripts` |
| **Final report requirements** | Phase commits, CI run IDs, test counts, evaluation results, remaining accepted risks, and explicit next-phase authorization status. |
