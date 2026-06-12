# DeepSeek Model-Name Routing Fix (tier string sent as API model)

**Date:** 2026-06-12 (follows `DEEPSEEK_LIVE_GENERATION_VALIDATION_2026-06-12.md`)
**Trigger:** A real deployed DeepSeek call failed with **HTTP 400**:
*"The supported API model names are deepseek-v4-pro or deepseek-v4-flash,
but you passed standard."*
**System status:** NOT_LIVE (unchanged).

## Defect

Two compounding problems in `apps/edr/llm.py`:

1. `_resolve_model_and_caps` used `_DEEPSEEK_TIER_MODELS.get(tier, tier)` —
   any tier string not in the map (`"standard"` in the failing call; the
   repo's own nodes only use `light`/`heavy`) was forwarded **verbatim as the
   API model name**.
2. The locked DeepSeek model IDs were `deepseek-chat` (both tiers), which the
   API no longer accepts; the supported names are `deepseek-v4-flash` and
   `deepseek-v4-pro`.

## Fix (provider routing only)

`apps/edr/llm.py`:

- Locked model IDs updated: light tier → `deepseek-v4-flash` (also the
  default), heavy (report) tier → `deepseek-v4-pro`.
- `_resolve_model_and_caps` for deepseek now resolves unknown tiers to the
  default model (`deepseek-v4-flash`) — a tier string can never reach the API
  as a model name again. Caps behavior unchanged (unknown tier keeps the
  conservative heavy caps).
- `_COST_RATES` keyed to the new model constants.

`scripts/validate_deepseek_provider.py`: mock + assertion updated to expect
`deepseek-v4-pro` for the report node (tier=heavy). RESULT: PASS.

Explicitly NOT touched: Anthropic path (preserved, runtime-inactive), Voyage,
Cohere, Graph/Entra, n8n, Odoo, RBAC, governance, fence stripping.

## Live validation (real api.deepseek.com, app's own `call_llm`)

`tier="standard"` call (the exact failing case), runtime `.env`, key reported
by length only (35):

```text
tier 'standard' resolves to: deepseek-v4-flash
model returned: deepseek-v4-flash
usage tokens: input=30 output=65
content: '{"marker": "DSSTD-117D42CB"}'
http observed: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
  [PASS] provider_is_deepseek
  [PASS] standard_tier_not_sent_as_model
  [PASS] resolved_model_is_v4_flash
  [PASS] http_status_200
  [PASS] usage_tokens_returned
  [PASS] fallback_not_used          (one-time random marker echoed; fallback opens no network connection)
  [PASS] model_used_is_v4_flash
  [PASS] json_parseable_fence_stripping_ok
RESULT: PASS
```

Heavy tier live check: `tier="heavy"` → `deepseek-v4-pro`, HTTP 200,
tokens 11/33, content as instructed — the report tier model is accepted.

**Observation (no code change):** the v4 models are reasoning models —
`completion_tokens` includes `reasoning_tokens` (seen in
`completion_tokens_details`), and the answer still arrives in
`message.content`, which `_call_deepseek` already reads. Consequence: very
small `max_tokens` budgets (≤32) can be consumed entirely by reasoning,
yielding HTTP 200 with empty content. Production nodes use 4 000–8 000 caps
and are unaffected; validation harnesses must use ≥256.

## Tests

- `apps/edr/tests/integration/test_llm_provider_switch.py` — **17 passed**,
  including 3 new regressions: tier→model table (flash/pro), unknown tiers
  (`standard`, `advanced`, `report`, empty, garbage) never forwarded as model
  names, and an end-to-end mock-transport call with `tier="standard"`
  observing `deepseek-v4-flash` in the request payload.
- Mock harness `scripts/validate_deepseek_provider.py`: RESULT: PASS.
- LLM/provider/connector test subset + ruff: see commit-time record in the
  final session report.

## Deployment closeout (operator rebuild on 4ef1e8a, later 2026-06-12)

Operator rebuilt the app container on commit `4ef1e8a`. Independent read-only
verification from the host (no docker access needed):

- New app process started **Fri Jun 12 14:03:28 2026**; container filesystem
  contains both fixes (`deepseek-v4-flash` and `strip_code_fences` present in
  the deployed `apps/edr/llm.py`); `LLM_PROVIDER=deepseek` in the live process
  environment; `/healthz` → HTTP 200. **App container healthy.**

Operator-reported in-container `call_llm` with `tier="standard"`:

| Check | Result |
|---|---|
| Model resolved | `deepseek-v4-flash` |
| input_tokens | 32 |
| output_tokens | 76 |
| cost_usd | recorded |
| Deterministic fallback used | **no** |
| JSON parsed (fence stripping) | **yes** |

Both prior blockers from this document are **cleared**: the running container
no longer predates the fixes, and the in-container `tier="standard"` call
succeeded through DeepSeek.

## Final DeepSeek verdict

**`DEEPSEEK_DEPLOYED_RUNTIME_ACTIVE_NOT_LIVE`** — DeepSeek is the active
generation provider in the deployed runtime; system go-live status is
unchanged (NOT_LIVE per `docs/GO_LIVE_PLAN.md`).
