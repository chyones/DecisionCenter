# Go-Live Blocker Resolution — Entra, Graph, upload_ids, Full Graph

**Date:** 2026-06-12 (continues from `DEEPSEEK_FULL_GRAPH_AND_BLOCKER_MATRIX_2026-06-12.md`)
**System status:** NOT_LIVE (unchanged; no operator go-live approval exists).
No secrets printed (tokens/keys reported by presence/length only). DeepSeek
untouched (no new defect). ownCloud untouched (stays disabled).

## A. Entra authentication / token version — RESOLVED (config + code coherent)

My prior session recorded an `AADSTS501051` "worse than recorded" finding.
**That was a wrong test method, now corrected:** I was requesting a
*client-credentials* token for the API audience. The API app exposes only
`User`-assignable app roles (`admin`, `executive`), so by design no service
principal can mint an API token — only an interactive **user** can. This is
correct, intended behaviour, not a blocker.

Both sides of the v1/v2 issuer question are now verified consistent:

- **API app manifest** (read live via Microsoft Graph `applications` API):
  `requestedAccessTokenVersion = 2` → the API issues **v2.0** access tokens
  (issuer `…/v2.0`, audience == client id). The historical "Invalid issuer"
  cause (v1.0 tokens) is removed at the source.
- **Validator** (`apps/edr/auth/validator.py`): accepts **both** issuer/aud
  forms — `…/v2.0` + aud==client_id (v2) and `sts.windows.net/{tenant}/` +
  aud==`api://{client_id}` (v1). A v2 token now validates cleanly.
- **OIDC discovery + JWKS** for the tenant are reachable; discovery `issuer`
  is the v2.0 form and the JWKS endpoint serves 6 signing keys.
- App-only Graph token (client-credentials, audience graph) mints
  successfully — proves the client secret is valid (length 40, not printed).
- Tests: `apps/edr/tests/integration/test_entra_validator_versions.py` passes
  (v1 and v2 acceptance, issuer/aud matrix).

**Remaining (operator/interactive, not a defect):** a real end-to-end smoke
of `/reports/staging` through the deployed auth surface needs a genuine
**user** bearer token, which is obtained by interactive Entra login (device
code / SPA). It cannot be minted head-lessly and was not available to this
session. Operator step:
`python scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token "<user access token>"`.

## B. Microsoft Graph evidence flow — root-caused, fix designed and VALIDATED against live Graph; live import is an operator step

### Root cause (from the live n8n execution log, read-only)

The deployed n8n SharePoint/Mail workflow executions (ids 356/357 and every
prior pair) fail with **`NodeOperationError: Credentials not found`** at the
Graph HTTP node — so the webhook returns an empty body, which the app's
payload validator cannot parse, so zero Graph evidence reaches reports. The
HTTP nodes are set to `authentication: genericCredentialType`
(`genericAuthType: httpHeaderAuth`) but have **no credential object attached**
— while the Authorization header is *already* built manually from the
app-supplied per-request token (`Bearer {{ $json.body.access_token }}`). The
static-credential reference is both redundant and broken; the correct setting
for a per-request dynamic token is "no n8n-managed credential, use the
explicit header".

A second SharePoint defect: the search URL builds `search(q=<term>)` without
the OData-required quotes, so even past the credential error Graph returns
`400 BadRequest: Syntax error … in 'q=guard room'`.

### Validation that the corrected logic works (live Graph, app's own token)

Using the real app client-credentials Graph token (roles include
`Sites.Read.All`, `Files.Read.All`, `Mail.Read`):

| Query (corrected URL) | Result |
|---|---|
| `…/sites/{site}/drives/{drive}/root/search(q='guard room')` | **HTTP 200, 200 items** (e.g. "AM CD STN-SDS-EL-0005 … CCTV System …") |
| `…/root/search(q='maintenance')` | **HTTP 200, 200 items** |

Both literal-quote (`'guard%20room'`, what `encodeURIComponent` yields) and
fully-encoded (`%27…%27`) forms return 200 — confirming the fix is correct
and the upstream SharePoint credentials/permissions are fully working.

### Prepared fix (repo source of truth `n8n/*.json`) — ready to apply

`n8n/sharepoint_search.json` → `Graph Search` node:
1. `"authentication": "genericCredentialType"` → `"none"`; delete
   `"genericAuthType": "httpHeaderAuth"`. (Manual `Authorization` /`Accept`
   headers are retained — the real Bearer token still flows.)
2. URL query term wrapped in OData quotes:
   `… '/root/search(q=' + encodeURIComponent("'" + ($json.body.query || '') + "'") + ')'`.

`n8n/email_search.json` → `Graph Mail Search` node: same credential fix
(item 1 only).

> NOTE: editing these two files in place was blocked by the harness change
> classifier (it read the n8n HTTP node's outbound `authentication: "none"`
> as touching the app's auth boundary — it does not; the node still sends the
> real Graph Bearer token, and no app/user auth or RBAC is affected). The
> change is therefore staged here for **explicit operator approval** rather
> than forced through. It is config, not code, and does not weaken any
> authentication.

### Live import (operator step — n8n CLI/REST not available to this session)

After approving the repo change, import into the running n8n and re-activate:
`docker compose exec n8n n8n import:workflow --input=/data/sharepoint_search.json --separate`
(and `email_search.json`), or import via the n8n editor. Then re-run the
app→n8n probe; SharePoint evidence will populate.

### Remaining Graph sub-blocker — Mail from a Microsoft 365 **group** mailbox

Even with the credential fix, `email_search` will not yet return evidence:
the PRJ-001/PRJ-002 allowlist mailbox is a **group** mailbox
(`…@elrace.com`, `mail_enabled: true`), but the node queries
`/users/{mailbox}/messages`, which returns `404 ErrorInvalidUser` because a
group mailbox is not a user principal. Additionally the allowlist model
checks the *caller's* `user_mailbox` against the group address, which won't
match a normal user. This is a genuine design question (query
`/groups/{id}/…` or a shared-mailbox model + revised allowlist semantics)
and is **left for a product decision — not changed speculatively** here.
SharePoint + Odoo remain the substantive, working evidence sources.

## C. upload_ids — PROVEN HARMLESS (deferred ingestion is not a go-live blocker)

`ReportRequest.upload_ids` is validated/stored at `POST /upload` (per-user
MinIO prefix, type+size checked) and recorded in `state.inputs` for the audit
trail, but **no graph node consumes it** (audit item R5, MEDIUM_RISK,
intentional deferral). Harmlessness is now locked by a structural regression
test, `apps/edr/tests/integration/test_upload_ids_inert.py`:

- `test_no_graph_node_consumes_upload_ids` scans every module under
  `apps.edr.graph` and asserts none references `upload_ids` — so a caller
  supplying them cannot influence retrieval, the LLM prompt, or report
  content. (Fails loudly if ingestion is ever wired in.)
- `test_upload_ids_recorded_in_inputs_but_not_in_state_fields` confirms it is
  carried only in the free-form audit `inputs` dict, not promoted to a typed
  state field the graph acts on.

Plus the existing `test_upload_ids_field.py` (field present, defaults empty,
flows into the inputs dump). Uploaded files are isolated and never reach a
report, so the deferral is safe; full ingestion remains future work, not a
go-live gate.

## D. Full report workflow + DeepSeek — re-verified this session

`run_workflow()` (the exact function `POST /reports/staging` calls) driven
end-to-end on commit `4ef1e8a` + runtime `.env` (role executive, PRJ-001):

```text
visited_nodes: node_00_begin … node_17_publish   (all 18)
deepseek http calls: 5  statuses=[200,200,200,200,200]
token usage recorded: {'input': 1281, 'output': 2220}
cost_accumulated_usd: 0.004203
draft_report_status: generated
RESULT: PASS  (provider_is_deepseek, all 200, usage+cost recorded,
               fallback_shell_absent, report_json_produced)
```

- **DeepSeek used: yes** (5 real api.deepseek.com calls, all 200).
- **Deterministic fallback used: no.**
- **Tokens/cost recorded: yes.**
- `quality_gate: failed` is honest — this in-process runner cannot resolve
  the `n8n:5678` container hostname, so retrieval evidence is empty
  (compounding the live n8n credential defect in §B). Generation is fully
  DeepSeek-served regardless.

**The literal "full report end-to-end through the deployed HTTP API"** needs
two operator-gated inputs that no autonomous session can supply: (1) the §B
n8n fix imported into live n8n, and (2) an interactive Entra **user** token
for the auth surface (§A). Both are documented above as exact operator steps.

## Verdict

`CURRENT_BLOCKERS_VERIFIED_NOT_LIVE` — Entra token-version blocker resolved
(config+code coherent for v2); Graph evidence flow root-caused with a fix
validated against live Graph (200 items) and staged for operator approval +
live import; upload_ids proven harmless and locked by tests; DeepSeek
full-graph generation re-verified (no fallback, tokens/cost). System remains
**NOT_LIVE**.
