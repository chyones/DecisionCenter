> **⚠ SUPERSEDED FOR THE OWNER-OPERATOR DEPLOYMENT (2026-05-31).**
> The separation-of-duties controls described below — admin content-blindness,
> two-person approval, and own-report-only visibility — were intentionally
> relaxed per the owner-approved
> [`SPEC_CHANGE_2026-05-31_owner_operator_model`](../execution/SPEC_CHANGE_2026-05-31_owner_operator_model.md).
> Admin is now a full owner; owners share report visibility; self-approval is
> allowed. The automated quality gate, audit logging, and the project-scoped
> email allowlist remain in force. Production remains `NOT_LIVE`.

# RBAC Matrix

> **Authoritative source:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md` Sections 8 and 9.
> **Phase 0 lock decision:** this file uses the spec's 9 canonical roles. The previous
> 5-label planning matrix is superseded and MUST NOT be used for implementation.

## Canonical Roles

Implementation MUST use these role identifiers exactly until the locked spec is changed:

| Role ID | Scope Summary |
|---|---|
| `executive` | Authorized projects, executive reports, financial summary only when permitted |
| `project_manager` | Assigned projects, project documents, project mailboxes, finance details only when explicitly granted |
| `finance` | Odoo financial facts, financial reports, unrelated project mailboxes only when explicitly allowed |
| `commercial` | Contracts, claims, notices, related correspondence, financial figures only when permitted |
| `document_control` | Controlled project documents, document-control mailboxes, Odoo financial facts only when explicitly allowed |
| `procurement` | Procurement documents, PO-related financials, other financial data only when permitted |
| `legal` | Contracts, notices, claims, related correspondence, financial figures only when permitted |
| `auditor` | Reports, evidence references, and audit logs; source-content access depends on original permissions |
| `admin` | Configure access and system controls only; admin role does not grant business-data visibility |

## Permission Matrix

| Role | SharePoint Project Docs | ownCloud Project Docs | User Mailbox | Shared Mailboxes | Odoo Budget | Odoo Actual Cost | Approval | Audit Logs |
|---|---|---|---|---|---|---|---|---|
| `executive` | Allowed projects | Allowed projects | No | If mapped | If permitted | If permitted | Yes | Summary |
| `project_manager` | Assigned projects | Assigned projects | Own only | Project-mapped only | If permitted | If permitted | Review only | Own project |
| `finance` | If permitted | If permitted | Own only | If mapped | Yes | Yes | Finance review | Finance-related |
| `commercial` | Contracts and claims | Contracts and claims | Own only | If mapped | If permitted | If permitted | Commercial review | Commercial-related |
| `document_control` | Controlled docs | Controlled docs | Own only | Document-control mapped | No by default | No by default | Review only | Document-related |
| `procurement` | Procurement docs | Procurement docs | Own only | If mapped | PO-related only | If permitted | Review only | Procurement-related |
| `legal` | Contracts, notices, claims | Contracts, notices, claims | Own only | If mapped | If permitted | If permitted | Legal review | Legal-related |
| `auditor` | References only unless permitted | References only unless permitted | No | No by default | If permitted | If permitted | No | Yes |
| `admin` | Configure only | Configure only | No by default | No by default | No by default | No by default | No by default | System logs |

## Phase 0 Control Rules

- RBAC MUST be enforced before retrieval and again at every retrieval node.
- No global search is allowed by default.
- No mailbox search is allowed unless the mailbox is mapped to the project and the role permits it.
- No financial section appears in the report when the user lacks finance permission.
- No evidence excerpt from an unauthorized source may appear in any output.
- The audit log must record denied sources without exposing their content.
- Entra group-to-role mapping is not present in the repo yet and is a Phase 1B blocker.
