# DeepSeek Live Generation Validation (post top-up + rebuild)

**Date:** 2026-06-12 (afternoon; follows `DEEPSEEK_PROVIDER_SWITCH_UAT_2026-06-12.md`)
**Scope:** Verify the first successful live DeepSeek generation after the
operator topped up the account (previous live call: HTTP 402 insufficient
balance) and rebuilt the app container.
**System status:** NOT_LIVE (unchanged).

## 1. Container runtime verification

Docker CLI is not permitted for the validation session, so the container was
inspected via the host `/proc` filesystem (the app runs as host-visible PID
2940256, `uvicorn apps.edr.app:app`):

- `LLM_PROVIDER=deepseek` present in the live process environment.
- `DEEPSEEK_API_KEY` present — verified **by length only (35 chars)**; value
  never printed.
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`, `APP_ENV=production`.
- Process start: **Fri Jun 12 09:13:10 2026** — the rebuild/restart happened
  (the previous UAT noted the then-running container predated the switch).
- The container filesystem (`/proc/<pid>/root/app/apps/edr/llm.py`) contains
  `_call_deepseek` — the provider-switch code is in the running image.

## 2. Live generation call (real API, app's own `call_llm` path)

One minimal call (tier=light, max 16 output tokens) through
`apps.edr.llm.call_llm` with the runtime `.env`, asking the model to echo a
random one-time marker (`DSLIVE-6EF3CE77`) that no deterministic path could
produce. HTTP traffic observed via the `httpx` logger:

```text
runtime provider (settings): deepseek
DEEPSEEK_API_KEY length: 35
model returned: deepseek-chat
usage tokens: input=21 output=9
cost_usd: 0.000016
content: 'DSLIVE-6EF3CE77'
http observed: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
  [PASS] provider_is_deepseek
  [PASS] key_present
  [PASS] http_request_to_deepseek_observed
  [PASS] http_status_200
  [PASS] usage_tokens_returned
  [PASS] marker_echoed_not_fallback
  [PASS] deepseek_model_used
RESULT: PASS
```

- **HTTP 200** (the 402 balance blocker is cleared).
- **Usage tokens returned by the API** (21 in / 9 out) and cost recorded.
- **Deterministic fallback NOT used**: the fallback never opens a network
  connection and could not echo the one-time marker.

## 3. Report generation — defect found and fixed

`scripts/validate_deepseek_provider.py` (mock endpoint): RESULT: PASS — the
report-draft node `node_12_draft_json` routes through DeepSeek.

A live run of the same node against the real API then exposed a defect the
mock could not: **live DeepSeek wraps its JSON answer in markdown code fences**
(` ```json … ``` `) even when the prompt asks for raw JSON. `json.loads`
failed in `node_12_draft_json.run()`, which silently substituted the
deterministic evidence-builder report — generation "succeeded" (HTTP 200,
tokens billed) but the delivered report content was not the model's.
All five JSON-consuming graph nodes (02 intent, 03 scope, 04 plan,
11 self-correct, 12 draft) were affected.

**Fix (single point, provider-agnostic):** `apps/edr/llm.py` — new
`strip_code_fences()`; `call_llm` strips one outer markdown fence from
provider content when `expect_json=True`. Unfenced content and
`expect_json=False` calls (markdown composer node 14) are untouched; the
deterministic fallback path is unchanged.

Live re-run of `node_12_draft_json.run()` after the fix:

```text
http observed: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
node_12_cost_usd: 0.00099095
executive_summary: [{"claim": "The project budget is AED 1000 and the actual
  cost is AED 900, resulting in a favorable variance of AED 100.",
  "evidence_ids": ["ev-1"], "confidence": "high"}]
  [PASS] provider_is_deepseek
  [PASS] http_status_200_on_api_deepseek_com
  [PASS] report_json_produced
  [PASS] fallback_shell_absent
  [PASS] usage_cost_recorded
RESULT: PASS
```

The report content is now demonstrably model-generated (evidence-cited claims
derived from the supplied snippet), parsed from DeepSeek's fenced JSON.

## 4. Tests

- 3 new tests in `apps/edr/tests/integration/test_llm_provider_switch.py`:
  fence-stripping variants (incl. unfenced/empty/inner-fence pass-through),
  `expect_json=True` strips fences end-to-end via mock transport,
  `expect_json=False` leaves fences intact. File total: **14 passed**.
- `ruff check` on changed files: clean.
- Full backend suite: see commit message / final report for the run result
  recorded at commit time.

## 5. Remaining blockers

1. **Running container predates the fence fix** — the 09:13 image has the
   provider switch but NOT `strip_code_fences`; live in-container report
   generation will still silently fall back to the evidence-builder until the
   operator rebuilds/restarts the app (`docker compose up -d --build app`).
2. First in-container end-to-end report (via the API surface, with Langfuse
   trace visible) still to be observed after that rebuild.
3. System remains **NOT_LIVE** per `docs/GO_LIVE_PLAN.md`; this validation
   does not change that.

## Verdict

DeepSeek is live and serving generation through the app code path: runtime
provider `deepseek`, HTTP 200, real usage tokens, fallback not used, report
content model-generated after the fence fix. One rebuild is required to ship
the fence fix into the running container.
