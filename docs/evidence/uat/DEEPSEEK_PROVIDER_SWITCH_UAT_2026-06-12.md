# DeepSeek Generation-Provider Switch — UAT Evidence

**Date:** 2026-06-12
**Scope:** Disable Anthropic at runtime (kept in code), add DeepSeek as the active
generation LLM via the `LLM_PROVIDER` runtime switch. Voyage (embeddings) and
Cohere (rerank) untouched.
**System status:** NOT_LIVE (unchanged — see `docs/GO_LIVE_PLAN.md`).

## What changed

| File | Change |
|---|---|
| `apps/edr/config.py` | Added `llm_provider` (default `anthropic`), `deepseek_api_key`, `deepseek_base_url`. No existing setting touched. |
| `apps/edr/llm.py` | Provider routing in `call_llm` via `active_provider()`; new `_call_deepseek` (OpenAI-compatible `/chat/completions` over the existing `httpx` dependency); locked DeepSeek model IDs (`deepseek-chat` both tiers) and DeepSeek-specific token caps (56K in / 8K–4K out, inside the 64K context) and cost rates. The Anthropic call path was extracted to `_call_anthropic` unchanged; all guardrails (injection sanitizer, cost cap, token cap, Langfuse tracing, deterministic fallback) apply identically to both providers. Unknown `LLM_PROVIDER` values fall back to `anthropic`. |
| `apps/edr/admin/connector_status.py` | New `deepseek` ai_provider connector spec (key-presence only, like the others). The generation provider NOT selected by `LLM_PROVIDER` is classified `DISABLED` (kept, never blocks go-live). `_report_generation_status` now follows the active provider; runtime-disabled providers are not counted as "missing secondary providers". Voyage/Cohere classification unchanged. |
| `.env.example` | Added `LLM_PROVIDER=anthropic` (documented default), `DEEPSEEK_API_KEY=`, `DEEPSEEK_BASE_URL=https://api.deepseek.com` (40 → 43 keys). |
| `.env` (runtime, not committed) | `LLM_PROVIDER=deepseek` set; `DEEPSEEK_API_KEY=` added **empty** — the real key is pending. Backup taken before edit. No existing value modified. |
| `.github/workflows/ci.yml` | Config-coverage key count 40 → 43. |
| `docs/admin/CONTROL_PLANE_LOCK.md` | Authoritative env baseline updated 40 → 43 keys (doc-drift gate requires doc/CI/file agreement). No control was unlocked. |
| `apps/edr/tests/conftest.py` (new) | Pins `llm_provider=anthropic` for suite determinism; provider-switch tests opt in to deepseek explicitly. |
| `apps/edr/tests/integration/test_llm_provider_switch.py` (new) | 11 tests (see below). |
| `scripts/validate_deepseek_provider.py` (new) | Runtime validation harness (see below). |

Explicitly NOT changed: the Anthropic code path and dependency (`anthropic==0.42.0`
stays in `pyproject.toml`), Voyage, Cohere, Microsoft Graph/Entra, n8n, Odoo,
RBAC, governance/approval logic, frontend (the connector-truth panel renders the
new provider generically).

## Tests run

- `apps/edr/tests/integration/test_llm_provider_switch.py` — 11 passed:
  - provider resolution: default anthropic, deepseek, unknown-value fallback;
  - `call_llm` with `LLM_PROVIDER=deepseek` + key → HTTP `/chat/completions`
    request observed via mock transport (bearer auth present, `deepseek-chat`
    requested), response returned verbatim with exact usage tokens (42/7) —
    impossible for the deterministic fallback;
  - deepseek without key → deterministic fallback preserved;
  - anthropic default path byte-identical behavior (fallback model
    `claude-haiku-4-5`);
  - connector truth: inactive provider `DISABLED`/never blocks; active deepseek
    without key → `report_generation=BLOCKED` naming `DEEPSEEK_API_KEY`; with
    key → `READY` (capped at `CONFIGURED_NOT_TESTED`, no false liveness);
    Voyage/Cohere never disabled by the switch.
- Full backend suite (`apps/edr/tests`): **738 passed, 12 skipped, 1 failed**
  (first run) — the single failure was the doc-drift gate flagging the env-key
  count (40 → 43), fixed in ci.yml + CONTROL_PLANE_LOCK.md; targeted rerun of
  `test_doc_drift.py`, `test_phase1e.py`, `test_connector_truth.py`,
  `test_llm_provider_switch.py` → **85 passed**; full-suite rerun after the
  fix: **739 passed, 12 skipped, 0 failed**. Baseline before any change:
  71 passed (same files).
- `ruff check` on all changed files: clean.
- CI config-coverage assertion replicated locally: `config coverage: 43/43`.

## Runtime validation (DeepSeek used, not deterministic fallback)

`scripts/validate_deepseek_provider.py` starts a local HTTP server emulating
DeepSeek `/chat/completions`, points `DEEPSEEK_BASE_URL` at it, and drives the
real report-draft node `node_12_draft_json.run()` end-to-end. The deterministic
fallback never opens a network connection, so an observed HTTP request is proof
of provider routing. No real credentials used; none printed.

```text
DeepSeek provider runtime validation
  request observed: {"path": "/chat/completions", "authorization_header_present": true,
                     "model": "deepseek-chat", "max_tokens": 4000, "prompt_chars": 2206}
  [PASS] llm_provider_resolved_deepseek
  [PASS] anthropic_key_not_required
  [PASS] http_request_reached_mock_endpoint
  [PASS] endpoint_is_chat_completions
  [PASS] authorization_header_present
  [PASS] deepseek_model_requested
  [PASS] report_content_from_deepseek_not_fallback
  [PASS] fallback_shell_absent
  [PASS] usage_tokens_recorded
RESULT: PASS
```

## Current provider state

- Runtime `.env`: `LLM_PROVIDER=deepseek` — DeepSeek is the active generation
  provider; Anthropic is runtime-disabled (code and dependency retained,
  switch back by setting `LLM_PROVIDER=anthropic`).
- `ANTHROPIC_API_KEY` was already empty in `.env`; `DEEPSEEK_API_KEY` is empty.
  Until the key is provisioned, generation runs the deterministic fallback and
  `/admin/connectors/truth` reports `report_generation=BLOCKED` naming
  `DEEPSEEK_API_KEY` — honest by design.
- Voyage and Cohere keys: present, untouched.

## Live key validation (added later on 2026-06-12)

After the operator provisioned `DEEPSEEK_API_KEY` in `.env`, one minimal live
call was made through the app's own `call_llm` path (tier=light, max 16
output tokens):

- The request reached `https://api.deepseek.com/chat/completions` and
  **authenticated** (no 401), proving key validity and end-to-end wiring
  against the real endpoint.
- The API returned **HTTP 402 Payment Required** — DeepSeek's "insufficient
  balance" error. The account has no credit, so generation cannot complete
  until the operator tops up.

Local app probe at the same time: `/healthz` returns the full green core JSON
and `/admin/connectors/truth` correctly returns 401 unauthenticated — the
running container is up but predates the provider switch.

## Remaining blockers

1. ~~`DEEPSEEK_API_KEY` not provisioned~~ — **cleared**: key present in `.env`
   and authenticates against the live API.
2. **DeepSeek account has insufficient balance** (HTTP 402) — operator must add
   credit at platform.deepseek.com before any generation can succeed.
3. **Running app container predates this change** — operator must rebuild and
   restart the backend (e.g. `docker compose up -d --build app`) for the
   switch to take effect in the live process. The 2026-06-11 audit
   prerequisite (placeholder passwords) is already cleared: `.env` no longer
   contains `change-me` values.
4. **First successful live generation not yet observed** — after top-up and
   restart, rerun the minimal live call and confirm the trace in the
   Langfuse/cost dashboard.

## Verdict

Provider switch implemented, guarded, verified end-to-end against a mock
DeepSeek endpoint, and the real key verified to authenticate against the live
API (blocked only by account balance). Anthropic preserved for future use.
System remains NOT_LIVE.
