# SPEC CHANGE — Owner-Operator Governance Model

- **Date:** 2026-05-31
- **Approved by:** Owner (ch.yones), explicit in-session approval
- **Status:** IMPLEMENTED_NOT_LIVE (branch `feat/owner-operator-model`)
- **Production status:** unchanged — remains `NOT_LIVE`
- **Supersedes:** the separation-of-duties controls in
  `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/security/rbac_matrix.md`,
  `docs/policies/rbac_policy.md`, and `docs/approvals/report_approval_policy.md`
  **for this deployment only**.

## Context

DecisionCenter will be used by **company owners only — approximately five equal
people** (more can be added later). One owner is also the system operator
(admin). The original design enforced a multi-department separation of duties
that does not fit this single-class, owner-operated deployment. The owner
reviewed the trade-offs and approved the changes below.

## Decisions (owner-approved)

1. **Admin is a full owner.** The `admin` role gains all business powers
   (generate, approve, read report content) **in addition to** system-settings
   access (`/admin/*`). `_require_admin` is unchanged, so only the operator
   reaches the settings endpoints.
2. **Shared report visibility.** All owners (roles with `can_view_all_reports`:
   `executive`, `admin`) can view/list/download **all** reports — the system is
   a shared decision-support tool for equal owners. Non-owner roles remain
   scoped to their own reports; `auditor` keeps read-only all-projects access.
3. **Self-approval allowed (two-person rule removed).** The owner who generates
   a report may finalize it themselves. The **automated quality/claim gate
   (`quality_gate == "passed"`) still gates publish**, and a `review_decisions`
   "finalized by <hashed id>" audit row is still written. Admin approves via the
   normal reviewer path (`action="approve"`); the separate metadata-only
   `/admin/approvals/*/override-*` endpoints are unchanged.
4. **Adding an owner later** = map their Entra group to `executive` (or `admin`
   for a second operator). No code change required.

## Controls REMOVED (explicitly approved)

- Separation of duties (admin vs business user).
- Admin content-blindness (C-6 admin-cannot-read-business-data).
- Two-person approval (self-approval block).

## Controls KEPT (NOT removed)

- Audit logging of every report read / approval / admin action (now more
  important, since admin reads content).
- Automated quality/claim gate before publish; write-once publish.
- Prompt-injection protection; per-tier token caps; daily cost cap.
- **Email scope stays project-scoped:** `can_access_own_mailbox=False`; the
  per-project Source Mapping mailbox **allowlist** + the n8n email-workflow
  allowlist gate remain the authority. No scanning of all/personal inboxes.
- `auditor` remains read-only (cannot generate or approve).
- `_require_admin` still gates all `/admin/*` settings endpoints.

## Implementation (this branch)

**Code**
- `apps/edr/rbac/roles.py` — add `can_view_all_reports`; elevate `Role.ADMIN`
  to full owner (`can_generate_report=True`, `can_approve=True`, sources on,
  own-mailbox off); `executive` gets `can_view_all_reports=True`.
- `apps/edr/app.py` — remove the hard `Role.ADMIN` denials at report
  read/list/content/workspace/cancel/upload/download; admin approves via the
  normal path in `_check_reviewer_rbac`; owners (`can_view_all_reports`) see all
  reports; self-approval/self-reject/self-revision blocks removed; `needs_review`
  content no longer hidden from an owner who can self-review.

**Tests**
- `test_phase1g.py` — self-approval now allowed; admin approves via normal path.
- `test_phase2a_backend.py` — admin allowed on workspace/list/get/status/content/
  cancel/upload; owners see all; non-owner negative cases use `finance`.
- `test_rbac.py` — admin is report-capable at `node_01_auth`.
- `test_phase2b_approvals.py` — unchanged (admin override queue retained).

## Verification

- Targeted mock-based suites pass on host:
  `test_phase1g`, `test_phase2a_backend`, `test_phase2b_approvals`, `test_rbac`,
  `test_phase2b_admin_rbac`, `test_me_endpoint` (165 tests). `ruff` clean;
  `compileall` OK; `check_doc_drift` + `check_ai_context` clean.
- **NOT run on host** (require the live compose stack / docker exec, unavailable
  in the implementing session): `make smoke`, full `make test`, `make eval`,
  `make test-ui`. Run these in-container (or CI) before any go-live.

## Still NOT_LIVE / still pending

Production remains `NOT_LIVE`. This change does not enable go-live and is
independent of the still-pending Microsoft/Entra and AI-provider credentials
(report generation and real login remain blocked until those are provided).
Slice 6 live UAT and Slice 7 go-live approval are unaffected and still required.
