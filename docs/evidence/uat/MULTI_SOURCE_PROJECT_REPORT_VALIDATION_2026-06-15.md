# Multi-Source Project Report Validation — 2026-06-15

**Status: NOT_LIVE (unchanged).** Implements and verifies mandatory multi-source evidence
coverage (Odoo + SharePoint + Email) for project reports. No secrets printed. No evidence faked.
No Odoo financial data invented. LIVE not marked.

## Problem

The PRJ-001 report `b7b8f847` contained only a single Odoo source. Two root causes:
1. SharePoint received the raw natural-language query ("give me small sumary…") which matched
   zero documents in Graph drive search.
2. Email was effectively skipped (the per-user `/users/{mailbox}/messages` webhook 404s for the
   project's Microsoft 365 *group* mailbox), and a project report had no coverage section to
   surface attempted-but-zero sources.

## Verified facts (live, before coding)

- **Odoo `project.project`** (id 14602) exposes `name, date_start, date, user_id, partner_id,
  task_count` — and **no** `budget`/`actual_cost` columns. Requesting those returns nothing.
- **Odoo cost lives in `account.analytic.line`** keyed by analytic account `21963`: real posted
  lines (e.g. "Gross Staff" −6500/−9250/−2000 on 2026-05-31). Actual cost is real evidence here.
- **Email mailbox is a Unified M365 group** (`groupTypes: ['Unified']`, `mailEnabled: true`).
  `/groups/{id}/conversations` → **HTTP 200, real conversations** with the app's application
  token (no tenant change). `/users/{groupmail}/messages` → **404 ErrorInvalidUser** (proves the
  old per-user path is wrong for a group).

## Changes

| Area | Change |
|---|---|
| `apps/edr/graph/coverage.py` (new) | Per-source coverage model (enabled/attempted/status/count/reason) + completeness summary. |
| `apps/edr/connectors/odoo.py` | `build_cost_query()` for `account.analytic.line`; `COST_FIELDS`. `build_project_query` already uses real `id` + valid fields. |
| `apps/edr/graph/node_08_odoo.py` | Retrieves project record **and** real cost lines; records coverage; sets `odoo_financial_available`; never requests budget/actual_cost. |
| `apps/edr/connectors/email.py` | `search_group_conversations()` — direct Graph `/groups/{id}/conversations` for group mailboxes. |
| `apps/edr/graph/node_07_email.py` | Group-conversations path (gated like SharePoint), legacy user/shared-mailbox fallback (gated by own-mailbox); always records coverage. |
| `apps/edr/graph/node_05_sharepoint.py` | `derive_search_terms()` (query keywords → project name → aliases → code); tries terms until documents match; records coverage. |
| `apps/edr/graph/node_12_draft_json.py` | Embeds `connector_coverage` into the report; adds financial "not available" note when no verified cost. |
| `apps/edr/graph/node_13_quality_gate.py` | Adds `evidence_completeness` (full/partial); downgrades to `needs_review` on connector error or silent non-attempt. |
| `apps/edr/exporters/markdown.py` | Renders a **Connector Coverage** section + completeness + financial note. |

## Live verification (in-process full 18-node graph, real connectors)

Query deliberately reused the generic one that previously failed:
**"give me small sumary for this project"**, role executive, PRJ-001.

```
evidence by source: {sharepoint: 199, email: 2, odoo: 101}
source_coverage:
  odoo:       enabled=yes attempted=yes status=ok  count=101
  sharepoint: enabled=yes attempted=yes status=ok  count=199  (term used: project name)
  email:      enabled=yes attempted=yes status=ok  count=2    (path: group_conversations)
evidence_completeness: full
quality_gate: passed
DeepSeek calls: 4, all HTTP 200, fallback_used: False
```

- Odoo: 1 project record + 100 real analytic cost lines (`odoo_financial_available=true`).
- SharePoint: keyword fallback used the project name when the raw query matched nothing.
- Email: project group mailbox conversations via `/groups/{id}/conversations`.
- `publish_status: blocked_until_approval` — expected for the host runner (cannot resolve the
  `postgres` container hostname; gracefully caught). All 18 nodes ran.

## Behaviour guarantees (tests)

`apps/edr/tests/integration/test_multi_source_coverage.py` (14 tests) proves:
- every enabled source is attempted (`test_all_enabled_sources_attempted`);
- zero-evidence is visible in coverage, not hidden (`test_zero_evidence_is_visible`);
- SharePoint keyword fallback for generic summaries (`test_sharepoint_keyword_fallback_terms`,
  `test_sharepoint_uses_fallback_when_query_matches_nothing`);
- email cannot be silently skipped — always records coverage, surfaces errors, documents blockers
  (`test_email_*`, `test_summary_always_includes_email_entry`);
- Odoo financial fields are never invented (`test_odoo_project_query_never_requests_invented_fields`,
  `test_odoo_cost_query_uses_analytic_model_or_none`, `test_financial_note_when_no_verified_cost`);
- quality gate distinguishes partial vs full and does not silently pass on connector error
  (`test_quality_gate_*`).

Existing email allowlist security tests updated to exercise the user-mailbox fallback path
(no group), preserving the allowlist enforcement guarantee.

## Email design decision (re-opened; previously "descoped")

Email is **no longer descoped**. The correct Graph path for the project's Unified group mailbox
is `/groups/{id}/conversations`, proven to return real data with the app's existing application
permissions — no operator/tenant change required. Because the n8n `email_search` workflow is
per-user (`/users/{mailbox}/messages`) and workflow redesign/import is out of scope here, the app
reads group conversations directly via Graph (it already holds the Graph token). The per-user
n8n path remains as a fallback for projects that map an explicit user/shared mailbox.

## Verdict

`MULTI_SOURCE_COVERAGE_IMPLEMENTED_AND_VERIFIED; NOT_LIVE` — Odoo, SharePoint, and Email all
attempted and returning real evidence for a generic project query; coverage is visible; financial
data is real or explicitly "not available"; quality gate distinguishes partial vs full. System
remains NOT_LIVE pending the deployed-API run with an interactive Entra user token and signed
go-live approval.
