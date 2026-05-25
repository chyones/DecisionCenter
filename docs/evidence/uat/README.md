# UAT Evidence — Phase 2D Slice 6

This directory holds **redacted** evidence from real UAT runs executed against a
live DecisionCenter stack, as defined by `docs/operations/uat_runbook.md`.

## What goes here

One markdown file per UAT run, named `UAT_RUN_<YYYY-MM-DD>.md`, containing the
sanitized result of each step:

1. Real Entra login — `/me` returned role (no token, no raw user id)
2. Report submission — `request_id`, status, `visited_nodes` count
3. Evidence retrieval — count and source types of evidence items (no content)
4. Quality gate — verdict only
5. Approval — reviewer role, action, self-approval block confirmed
6. Publish — write-once `/final` confirmed, re-approval returned 409
7. Download — formats retrieved, byte sizes, validity

A run is conveniently produced with:

```bash
python scripts/uat_flow.py --json > /tmp/uat_summary.json   # operator host only
```

Paste the **already-sanitized** summary into the dated evidence file and add a
short Go/No-Go conclusion.

## Redaction rules (mandatory)

Never commit any of the following to this directory or anywhere in git:

- Bearer tokens, passwords, client secrets, or connector credentials.
- Raw business report content, query text, or evidence excerpts.
- Unredacted screenshots or logs containing business data.
- Real user identifiers (use the hashed `user_id_hash` only).

Raw, unredacted captures must stay in a gitignored local path (e.g. `logs/`) or
an operator-controlled secure store — see `docs/policies/secrets_policy.md` and
`docs/policies` for data-minimization rules.

## Status

Producing this evidence proves the Slice 6 real UAT flow. It does **not** make
the service live. Production remains `NOT_LIVE` until the Slice 7 Go-Live Gate
and a separate explicit go-live approval are completed.
