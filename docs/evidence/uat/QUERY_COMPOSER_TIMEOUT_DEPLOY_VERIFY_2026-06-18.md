# Query Composer Timeout Deploy Verification - 2026-06-18

## Scope

Deploy current `origin/main` to the NOT_LIVE DecisionCenter environment and
verify `/reports/staging` timeout behavior. No secrets were printed. No
production status flag was changed. n8n workflows and connector configuration
were not modified.

## Baseline

- Branch: `main`
- Local HEAD before deploy: `513314df977fa7d7acd3f8501313c22b5a6fcd4f`
- `origin/main`: `513314df977fa7d7acd3f8501313c22b5a6fcd4f`
- `git pull --ff-only`: already up to date
- `HEAD == origin/main`: yes
- Expected baseline commit: matched `513314df977fa7d7acd3f8501313c22b5a6fcd4f`
- `production_status`: `NOT_LIVE`
- `must_not_deploy`: `true`

## Pre-Deploy Checks

```bash
ruff check apps scripts
python3 -m compileall -q apps scripts
python3 scripts/check_doc_drift.py
python3 scripts/check_ai_context.py
.venv/bin/python -m pytest -q apps/edr/tests/integration/test_report_timeout_guard.py
```

Results:

- Ruff: passed
- Compileall: passed
- Documentation drift: clean
- AI context: clean
- Timeout guard test: `2 passed, 1 warning`

## Deploy

Command:

```bash
docker compose up -d --build app
```

Outcome:

- App image rebuilt from current checkout.
- `decisioncenter-app-1` was recreated and started.
- n8n workflow files and connector settings were not modified.
- Supporting services were not recreated by this command; Compose only waited
  on their existing health/state.

Runtime app image/container:

- Image digest: `sha256:c6571d0f23051eb7129507c475c7e18c2dfe3a79cc1ad002c0dcc363e5051695`
- Container created: `2026-06-18T05:34:22.948712721Z`
- Container started: `2026-06-18T05:34:31.185260761Z`
- Container status: running, healthy
- Exposed app version: `0.1.0`
- Exposed git commit endpoint: not found

Runtime source check inside the running container:

- `/app/apps/edr/app.py` contains `REPORT_SYNC_TIMEOUT_S`
- `/app/apps/edr/app.py` contains `asyncio.wait_for`

## Health

Local health:

```text
GET http://127.0.0.1:8000/healthz -> HTTP 200 in 0.031392s
{"status":"ok","workflow_nodes":18,"postgres":"ok","redis":"ok","qdrant":"ok","minio":"ok"}
```

Public health:

```text
GET https://vantage.elrace.com/healthz -> HTTP 200 in 0.094811s
{"status":"ok","workflow_nodes":18,"postgres":"ok","redis":"ok","qdrant":"ok","minio":"ok"}
```

## Timeout Guard Runtime Verification

In-container runtime test:

```bash
docker compose exec -T app pytest -q apps/edr/tests/integration/test_report_timeout_guard.py
```

Result: `2 passed, 3 warnings`.

This verifies the deployed container's `/reports/staging` timeout guard behavior
with the running app code: slow workflow returns controlled HTTP 504 and fast
workflow returns normally.

## Query Composer / API Verification

Requested project:

- Display name: `Construction of Civil Defense building in Al Marfa`
- Resolved project code: `PRJ-001`

Question:

```text
give me big problem for this project only one big
```

Files: none.

Authentication state:

- Production-mode app rejects dev-bypass headers.
- No bearer token was present in host or app environment variables checked for
  this run.
- Real authenticated Query Composer workflow execution was therefore blocked
  before entering the report workflow.

### Test A - MD Only

Local API attempt:

- Payload output formats: `["md"]`
- Result: HTTP 401 in `0.089s`
- Response JSON prefix: `{"detail":"Authorization: Bearer <token> required"}`

Public API attempt:

- Payload output formats: `["md"]`
- Result: HTTP 401 in `0.072s`
- Response JSON prefix: `{"detail":"Authorization: Bearer <token> required"}`

### Test B - All Formats

Local API attempt:

- Payload output formats: `["md", "docx", "xlsx", "pdf", "pptx"]`
- Result: HTTP 401 in `0.050s`
- Response JSON prefix: `{"detail":"Authorization: Bearer <token> required"}`

Public API attempt:

- Payload output formats: `["md", "docx", "xlsx", "pdf", "pptx"]`
- Result: HTTP 401 in `0.058s`
- Response JSON prefix: `{"detail":"Authorization: Bearer <token> required"}`

## Verdict

- Deploy performed: yes, app service only.
- Deployed commit: `513314df977fa7d7acd3f8501313c22b5a6fcd4f`.
- Runtime timeout guard present: yes.
- Runtime timeout guard behavior verified in container: yes.
- Public proxy path health: OK.
- Query Composer authenticated workflow for the requested prompt: not verified,
  because no real bearer token was available and production mode correctly
  rejected unauthenticated requests.
- Proxy 120-second timeout disappeared for the attempted requests: yes for the
  attempted unauthenticated POSTs; they reached the app and returned JSON 401
  immediately. Not verified for an authenticated long-running workflow.
- New error/blocker: `Authorization: Bearer <token> required` for both Test A
  and Test B.
- Production status: `NOT_LIVE`.
- `must_not_deploy`: `true`.

