# DeepSeek Full-Graph Proof + Current Blocker Matrix

**Date:** 2026-06-12 (continues from commit `4ef1e8a`; follows
`DEEPSEEK_MODEL_NAME_FIX_2026-06-12.md`)
**System status:** NOT_LIVE (unchanged). No code changed in this validation.
No secrets printed (keys reported by presence/length only).

## 1. Full report-generation graph (not a `call_llm` probe)

### Deployed API surface: auth-blocked

`POST /reports/staging` on the deployed container requires a valid Entra
bearer token (production mode; dev-bypass headers rejected). A live
client-credentials token request against the real tenant failed with
**AADSTS501051** — the API app (`DecisionCenter-API`) has no app role
assigned for itself, so no service token can be minted, and no interactive
user token was available to this session. Entra modification was out of
scope, so the HTTP surface could not be exercised.

**DeepSeek full-graph verdict: `DEEPSEEK_FULL_REPORT_BLOCKED_NOT_LIVE`**
(blocked at the API door by Entra auth — not by anything in the
generation path; see compensating proof below).

### Compensating proof: full graph in-process on commit 4ef1e8a + runtime .env

`run_workflow()` — the exact function `POST /reports/staging` calls — was
driven end-to-end (all 18 nodes) with the runtime `.env`, role `executive`,
project `PRJ-001`, with every outbound LLM HTTP call captured:

```text
visited_nodes: node_00_begin … node_17_publish   (all 18, in order)
deepseek http calls: 5  statuses=[200, 200, 200, 200, 200]
token usage recorded: {'input': 1281, 'output': 2014}
cost_accumulated_usd: 0.003944
draft_report_status: generated
  [PASS] provider_is_deepseek
  [PASS] full_graph_completed
  [PASS] deepseek_http_calls_observed
  [PASS] all_deepseek_calls_http_200
  [PASS] usage_tokens_recorded
  [PASS] cost_recorded
  [PASS] fallback_shell_absent
  [PASS] report_json_produced
RESULT: PASS
```

- **DeepSeek used:** 5 real calls to `api.deepseek.com/chat/completions`,
  all HTTP 200 — one per LLM node (intent, scope, plan, draft, compose).
- **Fallback used: no** — fallback opens no network connection; report JSON
  contains no fallback shell markers.
- **Usage/cost recorded: yes** — 1 281 input / 2 014 output tokens,
  USD 0.003944 accumulated on the request.
- `quality_gate: failed` is the gate being honest: retrieval webhooks use
  container-internal hostnames unreachable from the host runner, so evidence
  was scarce. Generation itself is fully DeepSeek-served.
- **Langfuse trace: not configured** — `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY` are both empty in the runtime `.env` (length 0);
  per task rule, trace confirmation is N/A.

## 2. Current blocker matrix (verified live this session, not from old reports)

| # | Item | Current status | Evidence (this session) |
|---|---|---|---|
| 1 | Entra invalid issuer / token version | **BLOCKED — worse than recorded** | Client-credentials mint fails with `AADSTS501051` (no app role on `DecisionCenter-API` for itself), so the v1/v2 issuer question cannot even be exercised by a service principal; `requestedAccessTokenVersion=2` manifest fix remains externally unverifiable. Deployed report/admin API unusable without a user token. |
| 2 | n8n Graph HTTP credential | **n8n healthy; webhook auth OK** | n8n `/healthz` → 200 (via container bridge IP); `Authorization: Bearer <N8N_WEBHOOK_TOKEN>` (len 43) accepted — 403 without it, 200 with it. Per the 2026-06-04 reconciliation, a dedicated n8n Graph OAuth credential is architecturally not required. |
| 3 | Microsoft Graph connector path | **BLOCKED — empty responses** | `sharepoint-search` and `email-search` webhooks return HTTP 200 with **zero-byte bodies** even with production payload shapes (site_id/drive_id and allowed_mailboxes from the real PRJ-001 mapping). The evidence contract (`{"evidence":[…]}`) is not fulfilled — the app's payload validation cannot parse an empty body, so no Graph evidence reaches reports. Contrast: Odoo returns the full contract. |
| 4 | Odoo credential / upstream | **WORKING** | `odoo-read` webhook with production payload → HTTP 200 with real evidence (`project.project` id 14435, "Maintenance of Guard Room Entrance at Traffic Department", source_uri on erp.elrace.com). Full chain app→n8n→Odoo proven live. |
| 5 | ownCloud | **DISABLED (by design, consistent)** | `OWNCLOUD_USERNAME`/`PASSWORD` empty (len 0); connector spec marks it intentionally disabled; n8n webhook `owncloud-list` → 404 (workflow not active). Current config does not require it; not re-enabled. |
| 6 | `app.py` upload_ids one-liner | **STILL OPEN** | `upload_ids` accepted in the request model (`app.py:50`) but `grep` over `apps/edr/graph/` shows no node consumes it — audit risk R5 (uploads accepted, never ingested) unchanged. |
| 7 | UAT_RUN evidence | **ABSENT** | No `docs/evidence/uat/UAT_RUN_<date>.md` exists (Slice 6 closeout requirement). |
| 8 | Phase 2D Slice 7 approval artifact | **ABSENT — Slice 7 not started** | `CURRENT_PROJECT_STATE.md` confirms: BLOCKED, requires Slice 6 live-UAT evidence plus a separate explicit user approval (`requires_explicit_user_approval_for_phase_2d = true`); no approval artifact found anywhere under `docs/evidence/`. |

### Dependency note

Items 1, 3, 7, 8 form the critical chain to go-live: a real UAT run (7)
needs the deployed API usable (1) and Graph evidence flowing (3); Slice 7
(8) needs 7 plus explicit owner approval. Item 6 is a known MEDIUM_RISK
audit item independent of that chain.

## Final verdict

**`CURRENT_BLOCKERS_VERIFIED_NOT_LIVE`** — DeepSeek generation is proven
through the full graph (5/5 HTTP 200, fallback never used, usage and cost
recorded); the deployed HTTP surface remains gated by Entra (verdict
`DEEPSEEK_FULL_REPORT_BLOCKED_NOT_LIVE`), and the blocker matrix above is
current as of this session. System remains NOT_LIVE.
