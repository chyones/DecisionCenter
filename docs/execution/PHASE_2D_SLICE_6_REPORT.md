# Phase 2D Slice 6 — Real UAT Flow Readiness

## Status

**IMPLEMENTED_NOT_LIVE**

Slice 6 was explicitly approved in the current session and the real-UAT
readiness path is now implemented. Executing the live UAT run remains an
operator action on the target environment (a live Entra tenant and live
connectors are required and are not available in CI). Production remains
`NOT_LIVE`. Slice 7 (Go-Live Gate) remains approval-gated.

## Live UAT Evidence Status

- **Evidence file:** missing — `docs/evidence/uat/` contains only `README.md`; no `UAT_RUN_<YYYY-MM-DD>.md` exists.
- **Completion status:** not complete. Slice 6 stays `IMPLEMENTED_NOT_LIVE`; it does **not** advance to `COMPLETE_NOT_LIVE`.
- **Reason:** target environment credentials not available (no real Entra tenant, no real tokens, no live connectors in this session). `scripts/uat_flow.py` correctly SKIPs without a target and never fakes success; local dev-bypass is not acceptable as real UAT proof.
- **Required next action:** an authorized operator must run the live UAT on the target environment (see "Operator Run" above) and commit the redacted evidence file.
- **Final verdict:** `PHASE_2D_SLICE_6_LIVE_UAT_PENDING`

## Scope

Create a real, non-mocked UAT readiness and evidence path covering:

- Real Entra login
- Report submission
- Evidence retrieval
- Quality gate
- Approval
- Publish
- Download

No mocked backend may be used for final UAT proof.

## Deliverables

| Deliverable | Location | Status |
|---|---|---|
| Operator UAT runbook | `docs/operations/uat_runbook.md` | ✅ |
| CI-safe UAT readiness checker | `scripts/uat_check.py` | ✅ |
| Operator live UAT driver (real backend, no mocks) | `scripts/uat_flow.py` | ✅ |
| Integration tests | `apps/edr/tests/integration/test_phase2d_slice6_uat.py` | ✅ |
| Redacted evidence location | `docs/evidence/uat/README.md` | ✅ |

## Real Flow Coverage

Each stage maps to a real backend endpoint exercised by `scripts/uat_flow.py`
over live HTTP (no mocks):

| Stage | Real endpoint / behavior |
|---|---|
| Real login | `GET /me` with a real Entra `Authorization: Bearer` token → canonical role |
| Submission | `POST /reports/staging` runs the 18-node LangGraph workflow |
| Evidence retrieval | `GET /reports/{id}/content` + `GET /reports/{id}` (live connectors) |
| Quality gate | `quality_gate` verdict from the deterministic claim checker |
| Approval | `POST /reports/staging/{id}/approve` (self-approval blocked; RBAC enforced) |
| Publish | node 17 write-once `/final`; re-approval returns HTTP 409 |
| Download | `GET /reports/final/{id}/download/{fmt}` returns the real artifact |

## No-Mock Guarantee

- `scripts/uat_flow.py` imports **no** mocking library. `scripts/uat_check.py`
  and `test_phase2d_slice6_uat.py` both assert the driver contains none of
  `unittest.mock`, `MagicMock`, `AsyncMock`, `monkeypatch`, `page.route`, or
  `responses.add`.
- The mocked Playwright golden path (`frontend/e2e/golden-path.spec.ts`,
  `page.route()`) is explicitly **not** accepted as UAT proof; the runbook
  records why.

## Safe Handling of Missing Credentials

- `scripts/uat_flow.py` prints `SKIP` and exits `0` when `UAT_BASE_URL` is
  unset, the target is unreachable, or no auth (token or dev role) is available
  — it never fakes success.
- `scripts/uat_check.py` is static and runs in CI; it never contacts a live
  service.
- The live test `test_uat_flow_live` is marked `@pytest.mark.live_probe` and is
  excluded from CI via `-m "not live_probe"`.
- Tokens/credentials are read from environment variables only and are never
  written to git.

## Automated Check Evidence

```bash
$ python3 scripts/uat_check.py
[PASS] UAT runbook exists: docs/operations/uat_runbook.md
[PASS] UAT runbook covers full flow: 10 stages documented
[PASS] UAT runbook keeps NOT_LIVE: production stays NOT_LIVE
[PASS] UAT driver exists: scripts/uat_flow.py
[PASS] UAT driver has no mocks: no mocking library used
[PASS] Evidence path documented: docs/evidence/uat/README.md

Total: 6 passed, 0 failed
```

## Evidence Path

- Redacted, per-run evidence: `docs/evidence/uat/UAT_RUN_<YYYY-MM-DD>.md`
  (template and redaction rules in `docs/evidence/uat/README.md`).
- Raw/unredacted captures must never be committed (gitignored local path or a
  secure operator store).

## Operator Run (target environment)

```bash
make up
export UAT_BASE_URL=https://<target-host>     # or http://127.0.0.1:8000
export UAT_BEARER_TOKEN=<real Entra token>     # production-equivalent path
export UAT_REVIEWER_TOKEN=<second user token>
export UAT_PROJECT_CODE=<project with complete source mapping>
python scripts/uat_flow.py --json
```

## Remaining Work

| Item | Owner | Gate |
|---|---|---|
| Execute the live UAT run and capture redacted evidence | Operator | Slice 6 sign-off |
| Slice 7 — Go-Live Gate (approval docs, rollback, runbook, monitoring) | Next session | Explicit user approval |

## Governance

Phase 2D is **not** complete. The execution plan defines Slice 7 (Go-Live Gate)
after Slice 6. This slice keeps `production_status = NOT_LIVE`,
`last_completed_phase = Phase 2C`, and `requires_explicit_user_approval_for_phase_2d = true`.
The remaining go-live blockers (real UAT execution evidence and go-live
approval) stay open until an operator runs the live UAT and Slice 7 is approved.

## Related Documents

- `docs/operations/uat_runbook.md` — Full operator UAT runbook
- `docs/evidence/uat/README.md` — Redacted evidence location and rules
- `scripts/uat_check.py` — CI-safe readiness checker
- `scripts/uat_flow.py` — Operator live UAT driver
- `docs/execution/PHASE_2D_EXECUTION_PLAN.md` — Original execution plan
- `docs/execution/PHASE_2D_NEXT_STEPS_PLAN.md` — Next steps plan
- `docs/execution/PHASE_2D_SLICE_5_REPORT.md` — Previous slice
