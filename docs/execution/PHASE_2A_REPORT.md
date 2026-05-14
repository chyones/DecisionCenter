# Phase 2A Report — User Chat Workspace Implementation

> **Date:** 2026-05-14
> **Closeout base commit:** `0a19bae781b78cceb57a4cca99197cb9af8eed6c`
> **Status:** `PHASE_2A_COMPLETE_NOT_LIVE`
> **Previous phase:** Phase 1I (Frontend Foundation & Static Admin Scaffolds)
> **Production:** `NOT_LIVE`
> **Next safe phase:** Phase 2B — Admin Visual Control Plane Implementation,
> only after explicit user authorization.

---

## Summary

Phase 2A is complete and not live. The user workspace implementation, backend
read/status/content/cancel/upload contracts, deterministic local E2E harness,
and U-01 through U-16 manual QA blockers have all been validated against the
current repository state.

The validated E2E path is:

`submit -> processing -> quality_gate passed -> approve -> final -> download MD`

No deployment was performed. Phase 2B was not started. The quality gate,
approval rules, and RBAC rules were not weakened.

## Closeout Fixes

The final Phase 2A QA blocker pass made these scoped corrections:

- Added a live workspace context endpoint so the Query Composer uses backend
  role/project state instead of static project fixtures.
- Added a live report content endpoint for Report View, Evidence Panel,
  reviewer draft preview, quality-gate flags, immutable final state, and
  role-aware financial visibility.
- Wired Reports List, Processing View, Report View, and Evidence Panel to live
  backend state.
- Preserved `report-draft.json` as an internal staged artifact so authorized
  reviewers can inspect needs-review drafts while exports remain blocked.
- Tightened admin denial on user-workspace APIs and downloads.
- Changed cancellation audit recording to the locked lifecycle event
  `report.cancelled`.
- Removed obsolete static/unavailable UI states from Phase 2A workspace screens.

## U-01 Through U-16 Manual QA Results

| Criterion | Result | Evidence |
|---|---|---|
| U-01 | PASSED | `GET /workspace/context` returns role-scoped `allowed_projects`; Query Composer renders only those options. |
| U-02 | PASSED | Empty/no-generate roles receive "No authorized projects for your role. Contact your administrator."; submit is unavailable. |
| U-03 | PASSED | Client guards route `auditor` to My Reports and block Query Composer / processing submit routes. |
| U-04 | PASSED | Client guards redirect `admin` to Admin CP; user-workspace backend routes return 403 for admin. |
| U-05 | PASSED | Processing View renders the 18 user-facing node labels in order and does not render internal node IDs as UI text. |
| U-06 | PASSED | Failed quality gate renders a non-dismissable error banner, suppresses Export Panel, and download APIs return 403. |
| U-07 | PASSED | Needs-review requester gets flags only; authorized reviewer gets watermarked draft; exports remain absent. |
| U-08 | PASSED | Export Panel renders only for `approved` or `final` reports with non-failed quality gate. |
| U-09 | PASSED | Roles without budget access see `[Financial data is not available for your role]`; financial markdown is not rendered. |
| U-10 | PASSED | Superscript citations are focusable/clickable and open/highlight the corresponding Evidence Panel entry. |
| U-11 | PASSED | Evidence Panel shows source type, confidence, and truncated hash; raw `evidence_id` values are not shown as display text. |
| U-12 | PASSED | Upload Zone blocks files over 10 MB before upload; backend `POST /upload` rejects oversized files. |
| U-13 | PASSED | CAD uploads show the exact release message required by the UI contract. |
| U-14 | PASSED | Staging reports show "Awaiting review"; review actions render only when backend `can_review` is true. |
| U-15 | PASSED | Final reports show a locked immutable indicator; review actions are absent; content is read-only. |
| U-16 | PASSED | Cancel uses confirmation, calls `DELETE /reports/{id}`, sets `review_state=cancelled`, and writes `report.cancelled`. |

## Validation Evidence

| Gate | Result |
|---|---|
| `python3 scripts/agent_preflight.py` | clean before edits; dirty-tree rerun correctly failed while fixes were uncommitted |
| `make phase2a-e2e` | PASS; 18 nodes visited; `quality_gate=passed`; pre-approval download 403; final MD 1443 bytes |
| `make smoke` | 2 passed |
| `make test` | 184 passed, 1 warning |
| `make eval` | 64/64 passed; pass rate 100.00%; precision 92.19% |
| `ruff check .` | clean |
| `python3 -m compileall apps scripts` | clean |
| `python3 scripts/check_doc_drift.py` | clean before closeout truth-doc update |
| `python3 scripts/check_ai_context.py` | clean before closeout truth-doc update |
| `cd frontend && npm run lint` | clean |
| `cd frontend && npm run build` | success; JS 280.74 kB / 81.49 kB gzip, CSS 26.82 kB / 5.72 kB gzip |
| `python3 scripts/agent_postflight.py --allow-no-evidence` | to be run after closeout truth docs are updated |

## Remaining Deferred Items

| Item | Status |
|---|---|
| Production deployment | Deferred; production remains `NOT_LIVE`. |
| Phase 2B implementation | Not started; may only begin after explicit user authorization. |
| Frontend UI automation (`make test:ui`) | Deferred to Phase 2C. Manual U-01 through U-16 QA passed for Phase 2A closeout. |
| Pip-audit hard gate | Deferred per Phase 1H triage. |
| Arabic PDF bidi/reshaping beyond current disclaimer | Deferred beyond Phase 2A. |
| Live Langfuse dashboard verification | Deferred beyond Phase 2A. |

## Final Phase 2A Decision

**PHASE_2A_COMPLETE_NOT_LIVE**

Phase 2A is closed locally with validation evidence. Phase 2B remains unstarted
and requires explicit user authorization before any work begins.
