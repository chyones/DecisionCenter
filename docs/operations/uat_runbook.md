# DecisionCenter — Phase 2D Slice 6 Real UAT Runbook

> **Status:** Phase 2D Slice 6 readiness — `IMPLEMENTED_NOT_LIVE`.
> Completing a UAT run does **not** deploy the service and does **not** make it
> live. Production remains `NOT_LIVE` until the separate Slice 7 Go-Live Gate
> and an explicit go-live approval are completed by an authorized operator.

This runbook defines the **one real, end-to-end User Acceptance Test (UAT)**
that proves the DecisionCenter decision-report flow works against **live
backend services with no mocked responses**. It is operator-driven: it must be
executed on the target environment (the Hetzner host or an equivalent staging
host) after `make up`, by an operator who holds real credentials.

The matching automated harness lives in:

- `scripts/uat_check.py` — CI-safe static readiness checker (no live calls).
- `scripts/uat_flow.py` — operator-run live UAT driver (real backend, no mocks).
- `apps/edr/tests/integration/test_phase2d_slice6_uat.py` — CI enforces the
  readiness invariants; the live steps are marked `@pytest.mark.live_probe`
  and are skipped in CI.

---

## 0. Scope and Hard Rules

- **No mocked backend for final UAT proof.** The golden-path Playwright spec
  (`frontend/e2e/golden-path.spec.ts`) uses `page.route()` mocks and is **not**
  acceptable as UAT evidence. Final UAT proof must come from `scripts/uat_flow.py`
  (or manual cURL) executed against a running stack with real connectors.
- **Local dev-bypass is NOT acceptable as real UAT proof.** The `X-User-Role`/`X-User-Id` dev bypass (and any mocked path) prove nothing about real login or live connectors; only a real Entra/MSAL Bearer token exercised against live services counts as Slice 6 evidence.
- **No deploy. No go-live.** This runbook proves readiness; it never cuts over.
- **No secrets in git.** Bearer tokens, passwords, and connector credentials are
  read from the environment or entered interactively. They are never written to
  a tracked file. Raw, unredacted captures must never be committed.
- **Do not weaken governance.** RBAC (`_require_admin`), admin metadata-only
  isolation (C-1/C-6), self-approval block, write-once `/final`, and the quality
  gate stay intact during UAT.

---

## 1. Step 1 — Real Entra Login

The production frontend authenticates the operator through **Microsoft
Entra/MSAL** and obtains an access token. Server-side RBAC then resolves the
canonical role from the validated token (Slice 2).

1. On the target host, ensure `ENTRA_CLIENT_ID` and `ENTRA_TENANT_ID` are set in
   the server `.env` so the backend runs in **real-token mode** (not dev bypass).
   In real-token mode, `_extract_claims` rejects requests without
   `Authorization: Bearer <token>` (HTTP 401) and rejects the dev bypass headers
   in production (HTTP 400).
2. Sign in through the frontend (MSAL) as a **report-capable** user (e.g. a
   user mapped to a non-admin canonical role with `can_generate_report=true`).
3. Capture the access token for the API calls below. Validate identity:

   ```bash
   curl -fsS -H "Authorization: Bearer $UAT_BEARER_TOKEN" \
        "$UAT_BASE_URL/me"
   # → {"user_id_hash": "<hash>", "role": "<canonical-role>"}
   ```

   `GET /me` returns identity metadata only (hashed user id + canonical role).
   A non-empty, correctly-mapped `role` proves real login worked.

**Pass:** `/me` returns HTTP 200 with the expected canonical role.
**Fail:** 401/400, or a role that does not match the Entra group mapping.

---

## 2. Step 2 — Report Submission

Submit a real business question for a project that has a **complete** source
mapping (an incomplete mapping returns HTTP 422 by design — A-20).

```bash
curl -fsS -X POST "$UAT_BASE_URL/reports/staging" \
     -H "Authorization: Bearer $UAT_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"query":"<real business question>","project_code":"<PRJ-CODE>","output_formats":["markdown","pdf"]}'
```

The response carries `request_id`, `status`, `quality_gate`, `visited_nodes`,
and `exported_formats`. Record the `request_id` for the remaining steps.

**Pass:** HTTP 200 with a `request_id` and a non-empty `visited_nodes` list that
shows the 18-node workflow ran against live connectors.
**Fail:** 5xx, RBAC 403 for a report-capable role, or an empty workflow path.

---

## 3. Step 3 — Evidence Retrieval

Confirm the report is backed by **real retrieved evidence** (SharePoint,
ownCloud, Email/Graph, Odoo via n8n; Qdrant/Redis retrieval), not placeholder
text.

```bash
curl -fsS -H "Authorization: Bearer $UAT_BEARER_TOKEN" \
     "$UAT_BASE_URL/reports/$REQUEST_ID/content"
curl -fsS -H "Authorization: Bearer $UAT_BEARER_TOKEN" \
     "$UAT_BASE_URL/reports/$REQUEST_ID"
```

Inspect the evidence panel/citations in the content response.

**Pass:** Evidence items reference real source documents and the connectors
returned explicit results (or an explicit degraded/error state — never silent
empty success).
**Fail:** No evidence, fabricated citations, or a connector that returned a
silent empty success.

---

## 4. Step 4 — Quality Gate

The quality gate verdict is produced by the deterministic claim checker and
returned on the submit response and the content response (`quality_gate`).

**Pass:** The gate returns an explicit verdict (`pass` / `needs_review` /
`fail`) consistent with the report content. A `fail`/`needs_review` verdict that
correctly blocks export is itself a passing UAT observation.
**Fail:** The gate is missing, or a failing report is allowed to export.

---

## 5. Step 5 — Approval (Human Review Gate)

Approval must be performed by a **different** reviewer than the submitter
(self-approval is blocked, HTTP 403). Auditor is blocked. Admin may only use the
metadata-only override **with a mandatory comment**.

```bash
curl -fsS -X POST "$UAT_BASE_URL/reports/staging/$REQUEST_ID/approve" \
     -H "Authorization: Bearer $UAT_REVIEWER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"comment":"UAT approval"}'
```

**Pass:** HTTP 200, `new_state: "approved"`, and a `publish_status`.
**Fail:** Self-approval succeeds, auditor can approve, or admin override is
accepted without a comment.

---

## 6. Step 6 — Publish

Publish runs inside the approval step (node 17): the approved report is written
**write-once** to the `/final` location. A second approval on a finalized report
must return HTTP 409.

**Pass:** `publish_status` indicates the artifact was published to `/final`;
re-approval returns 409 (write-once preserved).
**Fail:** Publish silently no-ops, or `/final` is overwritten.

---

## 7. Step 7 — Download

Download the finalized artifact and confirm the bytes are a valid document of
the requested format.

```bash
curl -fsS -H "Authorization: Bearer $UAT_BEARER_TOKEN" \
     "$UAT_BASE_URL/reports/final/$REQUEST_ID/download/pdf" -o uat_final.pdf
```

**Pass:** HTTP 200 with a non-empty, well-formed file for each requested format.
**Fail:** 404/403 for an authorized user, or a corrupt/empty artifact.

---

## 8. No Mocked Backend — Why this is the real proof

| Layer | Mocked acceptance test | Real UAT (this runbook) |
|---|---|---|
| Auth | Dev `X-User-Role` bypass | Real Entra/MSAL Bearer token |
| Connectors | `page.route()` / `AsyncMock` | Live n8n → SharePoint/ownCloud/Email/Odoo |
| Retrieval | Stubbed | Live Qdrant + Redis |
| Persistence | In-memory / skipped | Live PostgreSQL + MinIO |
| Publish/download | Mocked bytes | Real MinIO `/final` artifact |

`scripts/uat_flow.py` performs the steps above over real HTTP against a running
stack and imports **no mocking library**. CI verifies that property
(`test_phase2d_slice6_uat.py`).

---

## 9. Missing Credentials — Safe Handling

If the target environment is not configured for a live run, the harness must
**skip safely**, never fake success:

- `scripts/uat_flow.py` prints `SKIP` and exits `0` when `UAT_BASE_URL` is unset
  or the target is unreachable, and when no Bearer token / dev role is available.
- `scripts/uat_check.py` is static and runs anywhere (CI included); it validates
  readiness artifacts only and never contacts a live service.
- The live `@pytest.mark.live_probe` tests skip when the target/credentials are
  absent and are excluded from CI via `-m "not live_probe"`.
- Tokens and credentials are supplied via environment variables
  (`UAT_BASE_URL`, `UAT_BEARER_TOKEN`, `UAT_REVIEWER_TOKEN`) or interactively.
  They are never committed.

---

## 10. Evidence Location

- **Redacted** UAT evidence (one markdown file per run) is committed to
  `docs/evidence/uat/UAT_RUN_<YYYY-MM-DD>.md`. See `docs/evidence/uat/README.md`
  for the required structure and redaction rules.
- **Raw / unredacted** captures (full report bodies, tokens, screenshots with
  business content) must **never** be committed. Keep them in a gitignored local
  path (e.g. `logs/`) or an operator-controlled secure store.
- `scripts/uat_flow.py --json` emits a machine-readable, already-sanitized
  step summary suitable for pasting into the redacted evidence file.

---

## 11. Go / No-Go for Slice 6

| Criterion | Required for Slice 6 sign-off |
|---|---|
| Real Entra login (`/me` correct role) | ✅ |
| Submission runs the live workflow | ✅ |
| Evidence is real (no silent empty success) | ✅ |
| Quality gate returns an explicit verdict | ✅ |
| Approval respects RBAC + self-approval block | ✅ |
| Publish is write-once to `/final` | ✅ |
| Download returns valid artifacts | ✅ |
| Evidence captured (redacted) | ✅ |
| Production still `NOT_LIVE` | ✅ |

When every row passes against the live stack, record the redacted evidence and
mark the UAT run complete. **This unblocks Slice 7 (Go-Live Gate) only after a
separate explicit user approval.** Production remains `NOT_LIVE`.
