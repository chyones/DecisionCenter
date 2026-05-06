# Phase 1A — Infrastructure Foundation (Detailed Scope)

> **Phase:** 1A
> **Goal:** Every service starts, config is complete, CI catches regressions.
> **Rule:** No node logic. No LLM calls. No n8n changes. No schema changes. No auth logic.
> **Date:** 2026-05-06
> **Derived from:** `docs/PRE_START_IMPLEMENTATION_PLAN.md` Section 8

---

## Task 1 — Expand `config.py` to load all `.env.example` keys

**Current state:**
- File: `apps/edr/config.py` (15 lines)
- Loads 6 fields: `app_env`, `public_base_url`, `n8n_base_url`, `n8n_webhook_token`, `daily_cost_cap_usd`, `monthly_cost_target_usd`
- Template: `.env.example` (36 keys; authoritative Phase 0 env baseline)

**Required changes:**
1. Add Pydantic `Field()` declarations for all 36 keys with correct types:
   - `str` for URLs, tokens, IDs, database names
   - `int` for ports
   - `float` for cost caps
   - `str | None` for optional API keys and secrets
2. Group fields logically:
   - Application (APP_*)
   - Database / Cache / Vector (POSTGRES_*, REDIS_URL, QDRANT_URL)
   - Object Storage (MINIO_*)
   - External APIs (ANTHROPIC_*, VOYAGE_*, COHERE_*)
   - Identity (ENTRA_*)
   - Observability (LANGFUSE_*)
   - Orchestration (N8N_*)
   - Connectors (ODOO_*, *_WEBHOOK)
   - Cost Control (DAILY_*, MONTHLY_*)
3. Add `env_file_encoding="utf-8"` to `SettingsConfigDict`.
4. Add validation: `POSTGRES_PORT` must be 1–65535; `DAILY_COST_CAP_USD` must be > 0.

**Acceptance:** `python -c "from apps.edr.config import settings; print(len(settings.model_fields))"` returns 36.

---

## Task 2 — Rewrite `GET /healthz` with real dependency pings

**Current state:**
- File: `apps/edr/app.py`, lines 30–32
- Returns static JSON: `{"status": "ok", "workflow_nodes": 18}`

**Required changes:**
1. Import clients for PostgreSQL (`psycopg` or `asyncpg`), Redis (`redis`), Qdrant (`qdrant_client`), MinIO (`minio`).
2. Ping each service with a lightweight operation:
   - PostgreSQL: `SELECT 1`
   - Redis: `PING`
   - Qdrant: `client.get_collections()`
   - MinIO: `client.list_buckets()`
3. Return structured response:
   ```json
   {
     "status": "ok",
     "workflow_nodes": 18,
     "postgres": "ok",
     "redis": "ok",
     "qdrant": "ok",
     "minio": "ok"
   }
   ```
4. If any service fails, return HTTP 503 with the failing service marked `"error"` and exception message.

**Acceptance:** `curl http://localhost:8000/healthz` returns all four services as `"ok"` when stack is running.

---

## Task 3 — Pin all dependencies in `pyproject.toml`

**Current state:**
- File: `pyproject.toml`
- All dependencies use `>=` (e.g., `fastapi>=0.115.0`, `langgraph>=0.2.0`)
- No lock file (`requirements.lock` or `uv.lock`) present

**Required changes:**
1. Run `pip freeze` inside the running Docker container or local venv to capture exact installed versions.
2. Replace all `>=` with `==` for runtime dependencies.
3. Keep `>=` for build-system deps (`setuptools`) and optional test deps if CI depends on latest.
4. Add a lock artifact if selected during Phase 1A; no lock artifact exists yet.

**Acceptance:** `pip install -e .` installs exactly the same tree on a fresh environment.

---

## Task 4 — Create `.github/workflows/ci.yml`

**Current state:**
- Directory `.github/workflows/` does not exist and must be created in Phase 1A.
- `Makefile` has `smoke`, `test`, `eval`, `format` targets.
- `pyproject.toml` has `[tool.ruff]` and `[tool.pytest.ini_options]` configured.

**Required changes:**
1. Create `.github/workflows/ci.yml`.
2. Trigger: `push` to `main`, `pull_request` to `main`.
3. Job steps:
   - Checkout code.
   - Set up Python 3.11.
   - Install dependencies: `pip install -e ".[dev]"`.
   - Run `ruff check apps` (must exit 0).
   - Run `ruff format --check apps`.
   - Run `make smoke` (inside Docker Compose or via `pytest -q apps/edr/tests/smoke`).
4. Do NOT run `make eval` in CI (requires API keys and costs money).
5. Cache `pip` dependencies between runs.

**Acceptance:** Pushing to `main` triggers the workflow; all steps pass.

---

## Task 5 — Write Qdrant collection initialization script

**Current state:**
- No collection-creation code exists.
- Qdrant service starts empty in `docker-compose.yml`.
- `apps/edr/retrieval/embeddings.py` raises `NotImplementedError`.

**Required changes:**
1. Create `scripts/init_qdrant.py` (currently missing; `scripts/` does not exist yet) or `apps/edr/scripts/init_qdrant.py`.
2. Accept `project_code` as CLI argument or from a future real `project_source_mapping.json`; only `docs/config/project_source_mapping.example.json` exists today.
3. For each project:
   - Check if collection exists; skip if yes (idempotent).
   - Create collection with vector size matching Voyage-3-large (1024).
   - Use `distance: Cosine`.
   - Set `on_disk_payload: True` for cost efficiency.
4. Add `make init-qdrant` target to `Makefile`.
5. Document in `docs/operations/runbook.md`.

**Acceptance:** Running the script twice produces no errors and no duplicate collections.

---

## Task 6 — Fix `Caddyfile` ACME email

**Current state:**
- File: `Caddyfile`, line 2: `email admin@example.com`

**Required change:**
1. Replace `admin@example.com` with a real organization email (e.g., `admin@elrace.com` or infrastructure team email).

**Acceptance:** `caddy validate Caddyfile` passes.

---

## Task 7 — Verify `.dockerignore` exclusions

**Current state:**
- File: `.dockerignore` exists with 15 entries.
- Already excludes: `.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.env`.

**Required changes:**
1. Verify `node_modules` is excluded (if frontend added later).
2. Verify `n8n-data` and local data dirs (`postgres-data`, `redis-data`, etc.) are excluded.
3. Verify `.git` is excluded (yes).
4. Add `*.egg-info` and `dist/` if not present.

**Acceptance:** `docker build` context size is < 50 MB.

---

## Critical Risks to Address During 1A

| Risk | Location | Mitigation |
|------|----------|------------|
| `config.py` AttributeError on missing env var | `apps/edr/config.py` | Load all 36 keys with defaults or strict validation |
| No CI → regressions undetected | `.github/workflows/` missing | Create `ci.yml` before any node logic changes |
| No version pins → broken installs | `pyproject.toml` | Convert `>=` to `==` |
| Qdrant empty → first embedding fails | No init script | Create idempotent `init_qdrant.py` |
| Caddy ACME rejected | `Caddyfile` line 2 | Replace placeholder email |

---

## What 1A Does NOT Touch

- `apps/edr/graph/node_*.py` (all 18 nodes)
- `apps/edr/retrieval/embeddings.py` (implementation in 1D)
- `apps/edr/retrieval/rerank.py` (implementation in 1D)
- `n8n/*.json` workflows (implementation in 1C)
- `apps/edr/graph/node_01_auth.py` (implementation in 1B)
- Any prompt files
- Any schema files
