# EDR-AGENTIC-RAG v2.1
# Executive Decision Report — Workflow Specification
# Senior Management Deployment Profile

**Document ID:** EDR-AGENTIC-RAG-v2.1
**Status:** Implementation Specification — Locked for Deployment
**Output:** One Markdown executive decision report per request

This specification is a single source of truth. It is locked for a specific deployment profile (Section 0). Deviations during implementation MUST be reflected by updating this document, never by silent change.

Keywords MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY follow RFC 2119 meaning.

---

## 0. Deployment Profile

This deployment is sized and locked for the following profile. Implementation MUST follow the choices in this section. They are not options.

| Parameter | Value |
|---|---|
| Users | 5 senior management |
| Throughput | ≤ 25 requests per day, ≤ 5 concurrent |
| Languages | Arabic and English |
| Hosting | Single Hetzner Cloud CCX23 server (Section 23) |
| Heavy LLM | Claude Sonnet 4.6 (`claude-sonnet-4-6`) via Anthropic API |
| Light LLM | Claude Haiku 4.5 (`claude-haiku-4-5`) via Anthropic API |
| Embeddings | Voyage-3-large via Anthropic Voyage API |
| Reranker | Cohere Rerank 3.5 via API |
| Vector store | Qdrant, self-hosted on the same server |
| Orchestration | LangGraph in Python |
| Connectors layer | n8n self-hosted on the same server |
| Observability | Langfuse Cloud (free tier) |
| Storage | Local SSD + Hetzner Storage Box BX21 for backups |
| Identity | Microsoft Entra ID (Azure AD) SSO |
| Development model | Vibe coding with Claude Code in VS Code |
| Implementation budget | ≤ 30 hours total, distributed across phases (Section 31) |
| Monthly cost target | ≤ USD 300 all-in |

This profile assumes data sensitivity is normal-business, not regulated. If data residency in the UAE becomes a requirement (e.g. for a government contract), the hosting platform MUST be re-evaluated per Section 23.3.

---

## 1. Objective

Build an internal AI Decision Center where the 5 authorized senior managers submit one business question and receive one structured executive decision report grounded only in verified company evidence.

The system MUST:

- Accept one management question per request.
- Retrieve evidence from authorized company sources only.
- Analyze documents, emails, and ERP facts within RBAC limits.
- Produce one Markdown executive report per request.
- State missing data explicitly.
- Refuse to guess.
- Refuse to invent financial numbers.
- Refuse to execute any action in Phase 1.

---

## 2. Scope

### 2.1 Phase 1 — Read-Only Decision Reporting

In scope:

- Read access to SharePoint project documents.
- Read access to ownCloud project documents.
- Read access to user mailbox.
- Read access to authorized shared mailboxes.
- Read access to Odoo financial and operational records.
- Generation of `executive-decision-report.md`.
- Generation of `evidence-pack.json`.
- Generation of `audit-log.json`.
- Generation of `quality-gate-result.json`.

Out of scope:

- Any write or execute action.
- ERP updates.
- Email sending or replying.
- Approval creation in Odoo or any other system.
- Document modification.
- Automatic CAD processing.
- AI-generated financial numbers.

### 2.2 Phase 2 — Decision + Execute

Phase 2 is reserved and out of scope for this document. Phase 2 MUST NOT be enabled until:

- Phase 1 has passed all production readiness gates in Section 33.
- A separate Phase 2 specification is approved by the business owner.
- An Action Gateway with per-action human approval is in place.

---

## 3. Inputs and Outputs

### 3.1 Required Inputs

- `user_id` — authenticated user identifier from SSO.
- `query` — the management question, plain text.

### 3.2 Optional Inputs

- `project_code`
- `contract_no`
- `vendor`
- `date_range`
- `document_type`
- `mailbox_scope`

### 3.3 Output Files

Staging path:

```
/staging/{project_id}/{request_id}/executive-decision-report.md
/staging/{project_id}/{request_id}/evidence-pack.json
/staging/{project_id}/{request_id}/audit-log.json
/staging/{project_id}/{request_id}/quality-gate-result.json
```

Final path (only after human approval):

```
/final/{project_id}/{request_id}/executive-decision-report.md
/final/{project_id}/{request_id}/evidence-pack.json
/final/{project_id}/{request_id}/approval-log.json
```

Reports MUST NOT exist in the final path without an approval log.

---

## 4. Data Sources

### 4.1 SharePoint

Primary source for official project documents.

Document types:

- Contracts
- BOQ
- Invoices
- Letters
- Reports
- Submittals
- RFIs
- Meeting minutes
- Approved drawings (only when text-indexed)

Rules:

- Access through Microsoft Graph only.
- Filter by project mapping (Section 11).
- Filter by RBAC (Sections 8 and 9).
- Prefer the latest approved revision.
- Draft documents MUST be tagged as draft.
- Superseded documents MUST NOT be used as final evidence unless explicitly relevant to the query.

### 4.2 ownCloud

Secondary document source.

Rules:

- Same RBAC enforcement as SharePoint.
- Same evidence normalization pipeline.
- Same revision priority rules.
- Patching and access control MUST be current.
- ownCloud MUST NOT override SharePoint unless the file is the demonstrably latest approved source.

### 4.3 Emails

Authorized scopes only:

- The requesting user's own mailbox.
- Shared mailboxes mapped to the project (Section 10).
- Document Control mailboxes when the user role allows.
- Department shared mailboxes when RBAC allows.

Search filters:

- `project_code`
- `contract_no`
- `vendor`
- Sender domain
- Recipient domain
- `date_range`
- Keywords

Default keyword set:

```
Delay, RFI, Claim, Notice, Penalty, Variation,
Extension of Time, EOT, Revise and Resubmit,
Approved, Rejected, Under Review, Payment,
Invoice, Dispute
```

Email handling rules:

- Emails are timeline and responsibility evidence.
- Emails are not contractual authority by default.
- Formal notices sent by email MAY be treated as contractual evidence only when the contract terms allow it.
- Full email bodies MUST NOT be stored in the report.
- The system MUST store only: excerpt, `message_id`, mailbox, timestamp, and SHA-256 hash of the original body.
- Attachments MUST be processed as separate document evidence.

### 4.4 Odoo

Odoo is the sole source of truth for financial and operational numbers.

Records used:

- Budget
- Actual cost
- Invoices
- Purchase orders
- Payments
- Vendor balances
- Project cost records
- Timesheets (when available)
- Procurement status (when available)

Absolute rule:

```
Any financial number in the report MUST come from Odoo.
If a required financial value is not present in Odoo, the report MUST state: Not available.
```

The LLM MUST NOT calculate or infer missing financial numbers, with one narrow exception: a deterministic calculation where every input value comes from Odoo. In that case the formula MUST be shown in the report next to the result.

The Odoo connector MUST run with a read-only API user.

### 4.5 CAD / DWG / DXF / IFC

Phase 1 rules:

- CAD processing is disabled by default.
- CAD MUST be processed only when explicitly requested in the query and allowed by the user's role.
- CAD tools MUST run in a sandbox.
- CAD output is admissible as evidence only if the converted text or quantities are traceable to a specific drawing and revision.
- CAD-derived quantities MUST NOT override Odoo financial values.

---

## 5. Golden Rules

```
Documents = textual evidence
Emails = timeline and responsibility evidence
Odoo = numeric facts
LLM = analysis and writing only
```

Absolute prohibitions:

```
No evidence  -> no claim
No Odoo number  -> no financial value
No RBAC permission  -> no retrieval
No confidence  -> no conclusion
No source reference  -> no report statement
No human approval  -> no final publishing
```

---

## 6. Evidence Priority

When sources conflict, the system MUST resolve using this fixed priority order (highest first):

1. Odoo for financial numbers.
2. Signed contract.
3. Approved contract amendment.
4. Approved official letter.
5. Approved consultant or client instruction.
6. Approved BOQ.
7. Approved invoice or payment certificate.
8. Formal notice email when contractually valid.
9. Project shared mailbox correspondence.
10. User mailbox correspondence.
11. Internal notes.
12. Draft documents.
13. Unverified extracted text.

Rules:

- The latest approved revision overrides older revisions.
- Signed documents override drafts.
- Odoo overrides PDF or scanned numbers for financial values.
- Emails explain timeline but do not override signed documents.
- Conflicts MUST be disclosed in the report, not hidden.
- The LLM MUST NOT pick a winner by assumption.

---

## 7. Conflict Resolution

If evidence conflicts, the system MUST classify the conflict using one of these types:

```
financial_conflict
date_conflict
responsibility_conflict
contractual_conflict
document_revision_conflict
email_vs_document_conflict
missing_authority_conflict
```

Required behavior:

- Show both sides of the conflict.
- Show source references for both sides.
- Show confidence level for each side.
- Mark unresolved conflicts clearly.
- Do not force a conclusion.
- Add the conflict to both the Conflicts section and the Missing Data / Needs Review section.

Example wording the system MAY use:

```
The available evidence is conflicting. Odoo shows AED X, while Invoice Y shows AED Z.
Because Odoo is the financial source of truth, the report uses the Odoo value
and records the invoice discrepancy for review.
```

---

## 8. RBAC and Access Control

The system MUST enforce access control before retrieval, never after.

### 8.1 User Roles

```
executive
project_manager
finance
commercial
document_control
procurement
legal
admin
auditor
```

### 8.2 Role Capabilities

**Executive**
- View authorized projects.
- View executive reports.
- View financial summary when permitted.

**Project Manager**
- View assigned projects.
- View project documents and project mailboxes.
- View finance details only when finance permission is explicitly granted.

**Finance**
- View Odoo financial facts.
- View financial reports.
- View unrelated project mailboxes only when explicitly allowed.

**Document Control**
- View controlled project documents.
- View document-control mailboxes.
- View Odoo financial facts only when explicitly allowed.

**Legal / Commercial**
- View contracts, claims, notices, and related correspondence.
- View financial figures only when permitted.

**Procurement**
- View procurement documents.
- View PO-related financials.
- View other financial data only when permitted.

**Auditor**
- View report, evidence references, and audit logs.
- Source-content access depends on the original permissions assigned.

**Admin**
- Configure access.
- Admin role MUST NOT automatically grant business-data visibility.

### 8.3 RBAC Rules

- No global search is allowed by default.
- No mailbox search is allowed unless the mailbox is mapped to the project AND the user role permits it.
- No financial section appears in the report when the user lacks finance permission.
- No evidence excerpt from an unauthorized source MAY appear in any output.
- The report MUST be redacted when a user cannot view a specific source.
- The audit log MUST record denied sources without exposing their content.

---

## 9. RBAC Matrix

| Role | SharePoint Project Docs | ownCloud Project Docs | User Mailbox | Shared Mailboxes | Odoo Budget | Odoo Actual Cost | Approval | Audit Logs |
|---|---|---|---|---|---|---|---|---|
| executive | Allowed projects | Allowed projects | No | If mapped | If permitted | If permitted | Yes | Summary |
| project_manager | Assigned projects | Assigned projects | Own only | Project-mapped only | If permitted | If permitted | Review only | Own project |
| finance | If permitted | If permitted | Own only | If mapped | Yes | Yes | Finance review | Finance-related |
| commercial | Contracts and claims | Contracts and claims | Own only | If mapped | If permitted | If permitted | Commercial review | Commercial-related |
| document_control | Controlled docs | Controlled docs | Own only | Document-control mapped | No by default | No by default | Review only | Document-related |
| procurement | Procurement docs | Procurement docs | Own only | If mapped | PO-related only | If permitted | Review only | Procurement-related |
| legal | Contracts, notices, claims | Contracts, notices, claims | Own only | If mapped | If permitted | If permitted | Legal review | Legal-related |
| auditor | References only unless permitted | References only unless permitted | No | No by default | If permitted | If permitted | No | Yes |
| admin | Configure only | Configure only | No by default | No by default | No by default | No by default | No by default | System logs |

Rule:

```
Administrative capability MUST NOT equal business-data visibility.
```

---

## 10. Shared Mailbox Access Policy

Each project MUST define an explicit list of allowed mailboxes in its source mapping (Section 11).

Example mapping fragment:

```json
{
  "project_code": "PRJ-001",
  "allowed_mailboxes": [
    "project.prj001@company.com",
    "documentcontrol@company.com",
    "submissions.prj001@company.com"
  ],
  "allowed_roles": [
    "executive",
    "project_manager",
    "document_control",
    "commercial"
  ],
  "search_sent_items": true,
  "search_archives": true,
  "search_attachments": true
}
```

Rules:

- Shared mailbox access MUST be explicit per project.
- Personal mailbox access MUST be limited to the requesting user, except where formal delegation is recorded.
- Private and confidential emails MUST be excluded unless project policy explicitly allows them.
- Search results MUST store excerpts only.
- Full email bodies MUST NOT be persisted in any output or log.

---

## 11. Project Source Mapping

Each project MUST have a source mapping file. No mapping means no retrieval.

Example:

```json
{
  "project_code": "PRJ-001",
  "project_name": "Example Project",
  "sharepoint": {
    "site_id": "site-id",
    "drive_id": "drive-id",
    "root_path": "/Projects/PRJ-001"
  },
  "owncloud": {
    "base_url": "https://owncloud.company.com",
    "root_path": "/Projects/PRJ-001"
  },
  "odoo": {
    "project_model": "project.project",
    "project_id": 1001,
    "budget_model": "project.budget",
    "cost_model": "account.analytic.line",
    "invoice_model": "account.move",
    "purchase_order_model": "purchase.order"
  },
  "mailboxes": [
    "project.prj001@company.com",
    "documentcontrol@company.com"
  ],
  "contract_numbers": [
    "CON-001"
  ]
}
```

Rules:

- No project source mapping MUST mean no retrieval.
- No fallback to global search is allowed.
- The system MUST NOT guess project folders.
- Missing mapping MUST be reported under Missing Data.

---

## 12. Evidence Object

Every retrieved fact MUST be normalized into the following object before any analysis step.

```json
{
  "evidence_id": "ev_000001",
  "source_type": "sharepoint | owncloud | email | odoo | cad",
  "source_ref": "file_path | message_id | odoo_model:record_id",
  "source_title": "string",
  "excerpt": "text used in analysis",
  "timestamp": "ISO 8601 or null",
  "project_code": "string or null",
  "contract_no": "string or null",
  "vendor": "string or null",
  "confidence": "high | medium | low",
  "tags": ["contract", "boq", "invoice", "delay", "claim"],
  "hash": "sha256 of original content",
  "retrieved_at": "ISO 8601",
  "visible_to_user": true
}
```

Rules:

- The LLM MUST NOT receive any raw source content that has not been normalized into this object.
- `excerpt` MUST be the minimum text needed for analysis.
- `hash` MUST be computed over the original (not the excerpt) for integrity audit.
- `visible_to_user` MUST reflect the requesting user's RBAC for that source.

---

## 13. Evidence Confidence Scoring

Confidence MUST be assigned by deterministic rules, not by free LLM judgment.

### 13.1 High Confidence

All of the following MUST be true:

- Source is official.
- Date is clear.
- Revision status is approved or signed.
- Source is directly relevant to the query.
- Content is not contradicted by stronger evidence.

Examples: signed contract, approved BOQ, Odoo record, official approved letter, formal notice with timestamp.

### 13.2 Medium Confidence

At least one of:

- Source is relevant but not final.
- Date exists but revision status is unclear.
- Email confirms timeline but not contractual authority.
- Source partially supports the claim.

### 13.3 Low Confidence

At least one of:

- Draft document.
- Unclear date.
- Unclear authority.
- Extracted text is incomplete.
- Source is indirect.
- Source conflicts with stronger evidence.

Rule:

```
Low-confidence evidence MUST NOT support a final executive conclusion on its own.
```

---

## 14. Report JSON Schema (Schema-First)

The system MUST generate a structured JSON report and pass the quality gate before any Markdown is composed.

Internal report object:

```json
{
  "request_id": "string",
  "project_code": "string or null",
  "query": "string",
  "language": "string",
  "executive_summary": [
    {
      "claim": "string",
      "evidence_ids": ["ev_000001"],
      "confidence": "high | medium | low"
    }
  ],
  "financial_snapshot": {
    "budget": {
      "value": null,
      "currency": "AED",
      "evidence_id": null,
      "status": "available | not_available"
    },
    "actual_cost": {
      "value": null,
      "currency": "AED",
      "evidence_id": null,
      "status": "available | not_available"
    },
    "variance": {
      "value": null,
      "currency": "AED",
      "formula": null,
      "evidence_ids": []
    }
  },
  "key_findings": [],
  "root_causes": [],
  "delay_analysis": [],
  "contractual_implications": [],
  "recommended_actions": [],
  "missing_data": [],
  "conflicts": [],
  "sources": []
}
```

Rules:

- Markdown MUST NOT be generated until the JSON passes the quality gate (Section 17).
- Every list element that contains a claim MUST carry at least one `evidence_id`.
- The Markdown report MUST be a deterministic projection of the JSON.

---

## 15. Claim Checker

Before report generation the system MUST validate every claim.

A claim is any statement that:

- Says something happened.
- Says something caused something.
- Says something costs an amount.
- Says something delayed something.
- Asserts liability or responsibility.
- Recommends an action.

Rules:

```
Every claim MUST have at least one evidence_id.
Every financial number MUST have an Odoo evidence_id.
Every date MUST have an evidence_id.
Every responsibility statement MUST have an evidence_id.
Every recommendation MUST connect to a finding.
Every missing item MUST appear under Missing Data.
```

If a claim has no evidence the system MUST take exactly one of these actions:

- Remove the claim.
- Move the claim to Missing Data.
- Mark the claim as Needs Review.

Unsupported claims that remain MUST cause the quality gate to fail.

---

## 16. Workflow Nodes

The system runs a fixed graph of nodes implemented in LangGraph. Each node has defined inputs, outputs, and termination conditions. Nodes MUST execute in the order shown unless an explicit retry loop is specified.

### Node 0 — Begin

- Generate `request_id`.
- Detect query language.
- Persist `query` and `user_id`.
- Initialize the audit log.

### Node 1 — Auth and RBAC Gate

- Resolve user role from SSO (Entra ID).
- Resolve allowed projects.
- Resolve allowed mailboxes.
- Resolve allowed Odoo models and fields.
- Block all unauthorized access paths.

### Node 2 — Intent Classifier (Light tier)

Classify the query into one or more of:

```
budget_actual
delay
contract_risk
claim
procurement
document_control
payment
variation
general_project_status
```

### Node 3 — Scope Resolver (Light tier)

Extract from the query:

- `project_code`
- `contract_no`
- `vendor`
- `date_range`
- `document_type`
- `mailbox_scope`

If a scope value is missing the node MUST:

- Mark it under Missing Data.
- Continue with the safe partial scope.
- Refuse global search.

### Node 4 — Retrieval Plan (Light tier)

Decide which sources to query among SharePoint, ownCloud, Email, Odoo, CAD.

The plan MUST record a reason per source.

### Node 5 — SharePoint Retrieval

- Search allowed project folders only via Microsoft Graph.
- Prefer approved latest revisions.
- Extract chunks per Section 19.
- Emit Evidence Objects.

### Node 6 — ownCloud Retrieval

- Search allowed folders only via WebDAV.
- Extract chunks per Section 19.
- Emit Evidence Objects.
- MUST NOT override SharePoint without a stronger revision status.

### Node 7 — Email Retrieval

- Search the user mailbox via Microsoft Graph.
- Search mapped shared mailboxes.
- Search sent items when policy allows.
- Search attachments when policy allows.
- Store excerpts only.

### Node 8 — Odoo Facts Retrieval

- Read-only Odoo XML-RPC or REST access.
- Retrieve financial and operational facts within scope.
- Record snapshot timestamp.
- Record Odoo model and record reference per Evidence Object.
- MUST NOT write to Odoo under any condition.

### Node 9 — Normalize and Deduplicate (Light tier)

- Convert all retrieved content into Evidence Objects.
- Remove duplicates (by hash and by source_ref).
- Merge related evidence (revisions of the same document, threads of the same email).
- Detect document revisions.
- Detect email threads.

### Node 10 — Evidence Sufficiency Check (Light tier)

- Is the question answerable with the current evidence?
- Are required financial numbers present in Odoo?
- Are key claims supported?
- Are conflicts detected?
- Is data missing?

### Node 11 — Self-Correction Loop

Allowed corrective actions:

- Partial re-retrieval.
- Narrowed query.
- Different keyword set.
- Source retry.

Hard limit:

```
max_loops = 3
```

After the limit:

- Stop retrieval.
- Record what is missing.
- MUST NOT invent.

### Node 12 — Draft JSON Report (Heavy tier)

- Build the report JSON per Section 14.
- Attach `evidence_ids` to every claim.
- Attach `confidence` per claim.
- Populate `missing_data` and `conflicts`.

### Node 13 — Quality Gate

Validate per Section 17.

### Node 14 — Compose Markdown Report (Heavy tier, deterministic)

- Generate `executive-decision-report.md` only after the quality gate passes.
- Markdown MUST be a deterministic projection of the JSON.

### Node 15 — Save and Audit

Persist:

```
executive-decision-report.md
evidence-pack.json
audit-log.json
quality-gate-result.json
```

### Node 16 — Human Review

A human reviewer MAY:

- Approve.
- Reject.
- Request revision.
- Add manual comments.

### Node 17 — Publish

Only after approval:

- Move artifacts from staging to final.
- Lock the report version.
- Persist `approval-log.json`.

---

## 17. Quality Gate

The quality gate MUST run after Node 12 and before Node 14. It MUST emit `quality-gate-result.json` with a verdict of `passed`, `failed`, or `needs_review`.

Pass conditions (all MUST be true):

- Every claim has at least one valid `evidence_id`.
- Every financial number has an Odoo `evidence_id`.
- Every cited source is in the user's RBAC scope.
- Every detected conflict appears in the Conflicts section.
- Every missing required field appears in Missing Data.
- The Sources section lists every cited source.

Fail handling:

- If `failed`, the report MUST NOT advance to Markdown composition. The system MUST return to Node 11 if loop budget remains, otherwise produce a Needs Review output and stop.
- If `needs_review`, the report MAY proceed but MUST be flagged for mandatory human review with the failing checks attached.

---

## 18. Tool Budgets and Stop Rules

Default per-request tool budgets:

```
SharePoint calls: 3
ownCloud calls: 2
Email calls: 4
Odoo calls: 6
CAD calls: 0 (disabled by default)
max_loops: 3
```

Hard stop rules:

```
If a tool budget is reached       -> stop retrieval for that source.
If max_loops is reached           -> stop retry.
If RBAC fails on a source         -> block the source.
If Odoo is unavailable            -> financial values = Not available.
If evidence is insufficient       -> report Missing Data.
If a conflict is unresolved       -> report Conflict.
If the quality gate fails twice   -> mark Needs Review and stop.
```

The system MUST NEVER continue by assumption.

---

## 19. Retrieval Strategy

This section is binding.

### 19.1 Chunking

- Documents MUST be chunked using semantic chunking by section and paragraph boundary.
- Chunk size: target 500–800 tokens, hard maximum 1024 tokens.
- Overlap: 100–150 tokens between adjacent chunks.
- Each chunk MUST carry: `source_ref`, page or section number, revision tag, project_code.
- Tables MUST be chunked as a unit and preserved in Markdown form.
- Email threads MUST be chunked per message, with thread metadata retained.

### 19.2 Embedding Model

- Locked: `voyage-3-large` via Anthropic Voyage API.
- Reason: best multilingual quality for Arabic + English at this scale, no GPU needed locally, very low cost (≈ USD 0.18 / 1M tokens).
- Rotation requires a re-index plan and a documented decision in this spec.

### 19.3 Vector Store

- Locked: Qdrant, self-hosted as a Docker service on the same Hetzner server.
- Metadata filtering MUST be enforced on `project_code`, `source_type`, `revision_status`, and `date`.
- A separate collection per project MUST be used. No shared collections.

### 19.4 Hybrid Search

- Every retrieval call MUST run BM25 (lexical) and dense (vector) in parallel.
- Results MUST be fused with Reciprocal Rank Fusion (RRF) before reranking.
- Lexical search is required because contract numbers, vendor names, and IDs are lost by dense embeddings alone.

### 19.5 Reranking

- Locked: Cohere Rerank 3.5 via API.
- The reranker MUST receive at most 50 fused candidates and return at most 10 to the LLM.

### 19.6 Query Expansion

- For underspecified queries, the system MAY apply HyDE using the Light tier (Haiku 4.5).
- Expanded queries MUST be logged in the audit log alongside the original.

### 19.7 Caching

- A semantic cache MUST exist at the request level, keyed by `(user_id, normalized_query, project_code, RBAC fingerprint)`.
- Cache TTL: 6 hours by default, 0 for queries containing `delay`, `claim`, or `payment` keywords.
- The cache MUST NOT bypass RBAC; the RBAC fingerprint is part of the cache key.
- Anthropic prompt caching MUST be enabled on all heavy-tier calls for the system prompt and stable evidence segments.

---

## 20. Technology Stack — Locked

This section enumerates locked decisions for this deployment. They are not options.

### 20.1 LLM Tiers

| Tier | Model | Model ID | Used in nodes |
|---|---|---|---|
| Light | Claude Haiku 4.5 | `claude-haiku-4-5` | 2, 3, 4, 9, 10, HyDE |
| Heavy | Claude Sonnet 4.6 | `claude-sonnet-4-6` | 12, 14 |

Opus is not used in Phase 1. If a quality issue is reproducibly traced to Sonnet, an Opus 4.7 (`claude-opus-4-7`) escalation path MAY be added in Section 22.6, with a cost cap.

### 20.2 Orchestration

- Framework: LangGraph (Python).
- State schema: Pydantic v2 models.
- Each node MUST be independently testable with mocked inputs.
- Workflow checkpoints persisted in Postgres for resumability.

### 20.3 Connectors

- Layer: n8n self-hosted on the same server, used as a typed middleware between LangGraph and the data sources.
- SharePoint and email: n8n Microsoft Graph nodes.
- ownCloud: n8n WebDAV node.
- Odoo: n8n Odoo node configured against a read-only API user.
- LangGraph nodes call n8n webhook URLs internally; no LangGraph node calls a vendor API directly.
- Each connector MUST run with read-only credentials in Phase 1.

### 20.4 Data Stores

- Vector store: Qdrant (Docker).
- Relational store: PostgreSQL (Docker) for audit logs, approvals, and LangGraph checkpoints.
- Object store: MinIO (Docker, S3-compatible) for reports and evidence packs.
- Cache and queues: Redis (Docker).

### 20.5 Identity

- SSO: Microsoft Entra ID.
- Service-to-service auth: short-lived tokens.
- The system MUST NOT accept username and password directly.

### 20.6 Web Layer

- Reverse proxy and HTTPS: Caddy (automatic Let's Encrypt).
- Single domain with subdomains for: app, n8n, langfuse-self-hosted (if used), minio.

---

## 21. Observability

### 21.1 Tracing

- Default: Langfuse Cloud free tier (sufficient at 25 requests per day).
- Every request MUST produce a trace covering all 17 nodes.
- Each trace MUST capture: model, prompt template version, token counts, latency, tool calls, retrieval hits, reranker scores, evidence_ids surfaced, evidence_ids cited, and final verdict.
- Migration to self-hosted Langfuse is allowed if free-tier limits are reached.

### 21.2 Metrics

The system MUST export:

- Per-node latency p50, p95, p99.
- Per-tier token consumption per request.
- Cache hit rate (semantic + Anthropic prompt cache).
- Retrieval recall on the golden set.
- Reranker top-k precision.
- Quality gate pass rate.
- RBAC block count.

### 21.3 Alerts

Alerts MUST fire for:

- p95 end-to-end latency above 60 seconds.
- Daily token spend above USD 12.
- Quality gate failure rate above 10% over a rolling hour.
- Any RBAC bypass attempt.
- Any prompt injection attempt detected.

### 21.4 Logs

- Application logs MUST be structured JSON.
- Logs MUST NOT contain confidential source content.
- Logs MUST contain `request_id`, `user_id` (hashed), and node name.

---

## 22. Cost Model — Concrete Budget

### 22.1 Per-Request Token Estimates

| Component | Tokens (typical) | Model | Per-request cost |
|---|---|---|---|
| Light tier (nodes 2, 3, 4, 9, 10, retries) | 150K input + 10K output | Haiku 4.5 | ≈ $0.20 |
| Heavy tier (nodes 12, 14) | 80K input + 5K output | Sonnet 4.6 | ≈ $0.32 |
| Anthropic prompt caching savings | 60% of input cached | both tiers | −$0.18 |
| Embeddings | 30K tokens | voyage-3-large | ≈ $0.005 |
| Reranking | 50 candidates × 1 query | Cohere Rerank 3.5 | ≈ $0.012 |
| **Effective per request** | | | **≈ $0.36** |

### 22.2 Per-Request Hard Caps

The system MUST enforce per-request hard caps:

```
heavy_tier_input_tokens_max:  60000
heavy_tier_output_tokens_max:  4000
light_tier_input_tokens_max: 200000
light_tier_output_tokens_max: 10000
reranker_calls_max:                4
```

A request that would exceed any cap MUST stop, mark Needs Review, and emit a partial report with the reached-cap reason.

### 22.3 Daily Cap

```
daily_cost_cap_usd: 12
```

If the daily cap is reached, all new requests MUST be queued and the system owner MUST be notified.

### 22.4 Monthly Budget

| Line item | Estimate (USD/month) |
|---|---|
| Anthropic API (Sonnet + Haiku, caching enabled) | 220 |
| Voyage embeddings | 5 |
| Cohere reranker | 10 |
| Hetzner Cloud CCX23 | 35 |
| Hetzner Storage Box BX21 (1TB backups) | 5 |
| Domain + TLS | 1 |
| Langfuse Cloud free tier | 0 |
| Microsoft Entra (existing) | 0 |
| **Total** | **≈ 276** |

This is the authoritative monthly cost target. Variance above 20% MUST trigger a budget review.

### 22.5 Cost Reporting

- A daily cost report MUST be generated.
- Cost MUST be attributable per `request_id`.
- Cost MUST be visible to the system owner via the Langfuse dashboard.

### 22.6 Opus Escalation Path (Reserved)

Opus 4.7 (`claude-opus-4-7`) MAY be added to the heavy tier later if Sonnet underperforms on specific case types. If activated:

- Triggered only by an explicit `complexity = high` flag set by Node 10.
- Daily Opus token cap: USD 5.
- Use MUST be logged and reviewed weekly.

---

## 23. Hosting Platform

### 23.1 Locked Choice

- Provider: Hetzner Cloud.
- Plan: CCX23 (Dedicated CPU).
- Specs: 4 dedicated vCPU (AMD), 16 GB RAM, 160 GB NVMe SSD, 20 TB traffic.
- Region: Helsinki (FSN1) or Falkenstein (FSN1) for European latency to Microsoft Graph and Anthropic endpoints.
- Approximate price: EUR 30 per month plus VAT.

### 23.2 Why this plan

- Dedicated CPU avoids noisy-neighbor issues for embedding and Qdrant work.
- 16 GB RAM accommodates Qdrant, Postgres, n8n, MinIO, and the application concurrently.
- NVMe SSD keeps Qdrant query latency low.
- Hetzner has consistently the strongest price-to-performance ratio at this size class.

### 23.3 Alternative Platforms (If the Locked Choice is Blocked)

If Hetzner is not procurable for compliance or payment reasons, the alternatives in priority order are:

1. **OVHcloud** — VPS Comfort 4 or Advance series. EU-based. Comparable price.
2. **Contabo** — VPS L. Cheapest in class but lower reliability; only if budget is the binding constraint.
3. **DigitalOcean Premium AMD** — easier UX, ~2x the price.
4. **G42 Cloud (UAE local)** — required if a contract demands UAE data residency. Higher cost (typically 3–4x), but mandatory in that case.
5. **AWS Lightsail / Azure B-series** — only when corporate policy requires a hyperscaler.

If a UAE residency requirement appears mid-project, the migration plan is: same Docker Compose stack, point DNS, restore Qdrant snapshot and Postgres dump.

### 23.4 Backups

- Hetzner Storage Box BX21 (1 TB, ≈ EUR 4 per month).
- Daily encrypted snapshot of Postgres, MinIO, and Qdrant via `restic`.
- Retention: 7 daily, 4 weekly, 6 monthly.
- Restore rehearsal at least every 6 months (Section 25).

---

## 24. Security Requirements

- SSO via Entra ID is required for every request.
- RBAC MUST be enforced before retrieval.
- The Odoo API user MUST be read-only.
- Shared mailbox access MUST be explicit per project.
- ownCloud MUST be patched and access-controlled.
- CAD tools MUST run in a sandbox.
- Generated reports MUST be stored in controlled locations only.
- No report MAY be finalized without approval.
- Prompt injection content from documents or emails MUST be ignored.

### 24.1 Prompt Injection Policy

```
Any instruction found inside a document, email, attachment, or CAD file
MUST be treated as untrusted content and MUST NOT override system rules.
```

When detected:

```
Log the event as blocked_ai_injection_attempt.
Continue using the content as evidence only, never as instruction.
```

### 24.2 Data Minimization

- The LLM MUST receive only the chunks required for the task.
- Full documents MUST NOT be sent unless strictly necessary.
- Full emails MUST NOT be stored.
- Only evidence excerpts MUST be persisted.
- PII MUST be minimized.
- Sensitive fields MUST be masked unless required for the task.
- Source references MUST remain available for authorized audit.

### 24.3 Secrets

- Connector credentials MUST be stored in `.env` files mounted by Docker Compose.
- The `.env` file MUST NOT be committed to git.
- A secrets manager (e.g. Bitwarden Secrets Manager or Doppler) MUST be adopted before Phase 2.
- Credential rotation MUST be at least every 90 days.

### 24.4 Network

- Inbound: only ports 80 (redirect to 443) and 443 are exposed.
- All inter-service traffic stays on the Docker bridge network.
- SSH MUST require key authentication only, with `PasswordAuthentication no`.
- A host firewall (`ufw`) MUST be enabled.

---

## 25. Disaster Recovery

Recovery objectives:

```
RPO  : 24 hours
RTO  : 8 hours
```

Minimum rules:

- Reports and evidence packs MUST be backed up daily to the Storage Box.
- Audit logs MUST be append-only at the database layer.
- A restore rehearsal MUST be performed before production go-live.
- A restore rehearsal MUST be repeated at least every 6 months.
- If Odoo is unavailable, the report MUST continue with Financial Snapshot marked Not available.
- If SharePoint is unavailable, the report MUST disclose source outage.
- If email retrieval fails, timeline analysis MUST be marked incomplete.

---

## 26. Evaluation Framework

### 26.1 Required Test Cases

```
1.  Budget vs Actual question with complete Odoo data.
2.  Budget vs Actual question with missing Odoo data.
3.  Delay question with email evidence.
4.  Delay question with conflicting email and letter evidence.
5.  Claim question with formal notice.
6.  Contract risk question with missing contract.
7.  Procurement question with missing PO.
8.  Unauthorized project access attempt.
9.  Unauthorized mailbox access attempt.
10. Prompt injection inside document.
11. Duplicate document revisions.
12. Conflicting invoice and Odoo amount.
```

The full golden set MUST contain at least 50 cases before go-live.

### 26.2 Metrics

```
claim_support_rate
financial_source_accuracy
missing_data_detection_rate
conflict_detection_rate
rbac_block_success_rate
hallucination_rate
source_coverage_score
quality_gate_pass_rate
retrieval_recall_at_10
reranker_precision_at_5
```

### 26.3 Production Targets

```
hallucination_rate (financial)  = 0
unsupported_claims              = 0
rbac_bypass                     = 0
quality_gate_pass_rate          >= 95%
retrieval_recall_at_10          >= 0.85
```

### 26.4 Tooling

- RAGAS for retrieval and end-to-end metrics.
- LLM-as-judge metrics MUST use a different model than the one being evaluated. Default judge: `claude-opus-4-7`.
- Promptfoo for regression testing on every prompt or model change.

---

## 27. API Contract Requirements

Every connector MUST have a written API contract before implementation.

Required files:

```
docs/contracts/odoo_api_contract.md
docs/contracts/microsoft_graph_contract.md
docs/contracts/owncloud_webdav_contract.md
docs/contracts/email_graph_contract.md
```

Each contract MUST define:

- Authentication method.
- Required scopes.
- Endpoint list.
- Request shape.
- Response shape.
- Pagination rules.
- Rate limits.
- Timeout values.
- Retry policy.
- Error codes.
- Audit fields.
- Security constraints.
- Test cases.

A connector MUST NOT be considered production-ready without its contract.

---

## 28. Versioning and Approval

Every report MUST carry a version.

Example artifact set:

```
executive-decision-report.v1.md
executive-decision-report.v2.md
evidence-pack.v1.json
quality-gate-result.v1.json
approval-log.json
```

Approval log shape:

```json
{
  "request_id": "string",
  "version": "v1",
  "reviewer": "user_id",
  "decision": "approved | rejected | revision_requested",
  "timestamp": "ISO 8601",
  "comments": "string"
}
```

Rules:

- Staging reports MAY be revised.
- Final reports MUST be locked.
- Final reports MUST require approval.
- Revisions MUST create new versions.
- The evidence pack version MUST match the report version.

---

## 29. Final Report Structure

The Markdown report MUST contain these sections in this order:

```
1.  Executive Summary
2.  Financial Snapshot — Odoo
3.  Key Findings
4.  Root Causes
5.  Delay Analysis
6.  Contractual / Commercial Implications
7.  Recommended Actions — Proposal Only
8.  Conflicting Evidence
9.  Missing Data / Assumptions
10. Sources
11. Quality Gate Status
```

### 29.1 Report Rules

- Every claim MUST reference a source number.
- Every financial number MUST reference an Odoo source.
- Missing data MUST be explicit.
- Assumptions MUST NOT appear unless clearly marked as user-provided.
- Recommendations MUST be marked as proposals only.
- No execution language MAY appear in Phase 1.

### 29.2 Sources Section Format

Each source entry MUST include type, title, reference, date, confidence, and where it was used.

Document example:

```
[S1] Source Type: SharePoint
Title:      Contract Agreement
Reference:  /Project/Contracts/Contract-v3-signed.pdf
Date:       2025-04-10
Confidence: High
Used in:    Executive Summary, Contractual Implications
```

Email example:

```
[S2] Source Type: Email
Mailbox:      documentcontrol@company.com
Message ID:   masked-reference-id
Date:         2025-05-18
Excerpt Hash: sha256:...
Confidence:   Medium
Used in:      Delay Analysis
```

Odoo example:

```
[S3] Source Type:   Odoo
Model:              project.budget
Record ID:          12345
Snapshot Time:      2026-05-05T10:30:00Z
Confidence:         High
Used in:            Financial Snapshot
```

---

## 30. Audit Log

The system MUST persist `audit-log.json` for every request.

Shape:

```json
{
  "request_id": "string",
  "user_id": "string",
  "timestamp": "ISO 8601",
  "query": "string",
  "detected_language": "string",
  "authorized_projects": [],
  "authorized_mailboxes": [],
  "blocked_sources": [],
  "tools_called": [],
  "tool_budgets_used": {},
  "retrieval_loops": 0,
  "quality_gate_status": "passed | failed | needs_review",
  "final_status": "staging | approved | rejected | final"
}
```

The audit log MUST NOT include full confidential source content.

---

## 31. Implementation Sequence (Vibe Coding)

Implementation is delivered in focused Claude Code sessions, not weeks. Each phase below corresponds to one or more sessions and MUST end with a green test before the next phase begins.

### Phase 0 — Server and Skeleton (Session 1, ~2 hours)

- Provision Hetzner CCX23 (Section 23).
- DNS, SSH key, `ufw`, `fail2ban`.
- Install Docker and Docker Compose.
- Create the repo with the structure in Section 32.
- Bring up the base `docker-compose.yml`: Postgres, Qdrant, Redis, MinIO, Caddy, n8n, the LangGraph app skeleton.
- Health-check endpoints respond on all services.

Exit test: every container reports healthy; Caddy serves the app over HTTPS.

### Phase 1A — Minimal Decision Report (Session 2, ~4 hours)

Sources: SharePoint and Odoo.

- Implement Nodes 0, 1, 2, 3, 4, 5, 8, 9, 10, 12, 13, 14, 15.
- Implement the Evidence Object pipeline.
- Implement the Quality Gate.
- Render Markdown from JSON.

Exit test: 5 of the 12 baseline test cases pass (Sections 26.1 cases 1, 2, 6, 7, 12).

### Phase 1B — Email Evidence (Session 3, ~2 hours)

- Implement Node 7 (email retrieval) via n8n Microsoft Graph.
- Apply the email excerpt and hashing policy.
- Add email-thread merge in Node 9.

Exit test: cases 3, 4, 5 pass.

### Phase 1C — ownCloud (Session 4, ~2 hours)

- Implement Node 6 (ownCloud retrieval) via n8n WebDAV.
- Add SharePoint vs ownCloud deduplication and revision handling.

Exit test: deduplication validated on a folder with intentional duplicates.

### Phase 1D — Evidence Governance (Session 5, ~3 hours)

- Implement Node 11 (self-correction loop) with `max_loops = 3`.
- Implement the Claim Checker (Section 15).
- Implement the Conflict Resolution classifier (Section 7).
- Implement RBAC enforcement at Node 1 and at every retrieval node.

Exit test: cases 8, 9, 10, 11 pass; the full 12-case baseline passes.

### Phase 1E — Approval and Publishing (Session 6, ~2 hours)

- Implement Node 16 (human review) and Node 17 (publish).
- Implement versioning per Section 28.
- Implement the audit log writer per Section 30.

Exit test: a request flows from staging to final with a locked version.

### Phase 1F — Observability and Cost Caps (Session 7, ~2 hours)

- Wire Langfuse Cloud SDK into every node.
- Implement per-request token caps (Section 22.2).
- Implement the daily cost cap (Section 22.3).
- Wire alerts (Section 21.3).

Exit test: a synthetic over-cap request is correctly halted; the trace appears in Langfuse.

### Phase 1G — Evaluation and Hardening (Session 8, ~3 hours)

- Build the golden set to 50 cases.
- Wire RAGAS and Promptfoo into a `make eval` target.
- Run a restore rehearsal.
- Pass the readiness gates in Section 33.

Exit test: production targets in Section 26.3 are met.

### Total Effort

```
Sessions: 8
Hours: ~20
Calendar time: 2–4 working days at vibe-coding pace
```

If a session overruns its hour budget by 50%, the session MUST stop and the spec MUST be re-examined for a missing decision.

---

## 32. Required Repository Files

```
docker-compose.yml
.env.example

apps/edr/
  graph/                          # LangGraph node implementations
    node_00_begin.py
    node_01_auth.py
    node_02_intent.py
    node_03_scope.py
    node_04_plan.py
    node_05_sharepoint.py
    node_06_owncloud.py
    node_07_email.py
    node_08_odoo.py
    node_09_normalize.py
    node_10_sufficiency.py
    node_11_self_correct.py
    node_12_draft_json.py
    node_13_quality_gate.py
    node_14_compose_md.py
    node_15_save_audit.py
    node_16_review.py
    node_17_publish.py
  schemas/                        # Pydantic models
    evidence.py
    report.py
    audit.py
    quality_gate.py
  retrieval/
    chunking.py
    embeddings.py
    hybrid_search.py
    rerank.py
    cache.py
  connectors/                     # n8n webhook clients
    sharepoint.py
    owncloud.py
    email.py
    odoo.py
  prompts/
    intent_classifier.md
    draft_report.md
    compose_markdown.md
  evaluation/
    goldenset/
    metrics.py
    promptfoo.config.yaml

n8n/                              # exported n8n workflows as JSON
  sharepoint_search.json
  owncloud_list.json
  email_search.json
  odoo_read.json

docs/workflows/EDR-AGENTIC-RAG-v2.1.md

docs/templates/executive-decision-report.template.md

docs/schemas/
  evidence-object.schema.json
  executive-decision-report.schema.json
  evidence-pack.schema.json
  audit-log.schema.json
  quality-gate-result.schema.json

docs/contracts/
  odoo_api_contract.md
  microsoft_graph_contract.md
  owncloud_webdav_contract.md
  email_graph_contract.md

docs/security/rbac_matrix.md
docs/config/project_source_mapping.example.json

docs/policies/
  rbac_policy.md
  shared_mailbox_access_policy.md
  email_retrieval_policy.md
  data_minimization_policy.md
  evidence_priority_policy.md
  odoo_financial_truth_policy.md
  conflict_resolution_policy.md
  prompt_injection_policy.md
  disaster_recovery_policy.md

docs/evaluation/
  edr_test_cases.md
  edr_metrics.md
  edr_goldenset.md

docs/operations/
  hosting.md
  cost_model.md
  observability.md
  runbook.md
  backup_restore.md

docs/approvals/report_approval_policy.md
```

---

## 33. Production Readiness Gates

The system MUST NOT be promoted to production until every gate below has been verified and signed off in writing.

```
Gate 1.  RBAC blocks unauthorized projects.
Gate 2.  RBAC blocks unauthorized mailboxes.
Gate 3.  Financial numbers come only from Odoo.
Gate 4.  Unsupported claims are blocked.
Gate 5.  Conflicting evidence is disclosed.
Gate 6.  Missing data is reported.
Gate 7.  Prompt injection is ignored and logged.
Gate 8.  Evidence pack is generated correctly.
Gate 9.  Audit log is generated correctly.
Gate 10. Report approval creates a locked final version.
Gate 11. Evaluation suite passes the production targets in Section 26.3.
Gate 12. Backup and restore rehearsal completed within the last 90 days.
Gate 13. API contracts are implemented and tested.
Gate 14. Project source mapping exists for every active project.
Gate 15. RBAC matrix is approved by the business owner.
Gate 16. Tracing, metrics, alerts, and structured logs are live in Langfuse.
Gate 17. Per-request and daily cost caps are enforced.
Gate 18. Sizing matches the deployment profile in Section 0.
Gate 19. Secrets are stored outside git and rotated.
Gate 20. Odoo connector runs with a read-only user verified by penetration test.
Gate 21. Hetzner server is hardened: ufw enabled, SSH key-only, Caddy HTTPS.
Gate 22. Daily backups to Hetzner Storage Box are verified by a restore.
```

---

## 34. Quick Start Commands (Reference)

The following are reference commands the implementation team MAY adapt. They are not normative.

### 34.1 Server Bring-Up (Hetzner)

```bash
# As a non-root user with sudo
sudo apt update && sudo apt -y upgrade
sudo apt -y install ufw fail2ban docker.io docker-compose-plugin git

sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# SSH hardening: PasswordAuthentication no, key-only
```

### 34.2 Repository and Stack

```bash
git clone <repo-url> edr
cd edr
cp .env.example .env
# Fill .env: ANTHROPIC_API_KEY, VOYAGE_API_KEY, COHERE_API_KEY,
#           ENTRA_CLIENT_ID, ENTRA_TENANT_ID, ODOO_URL, etc.
docker compose pull
docker compose up -d
docker compose ps
```

### 34.3 Smoke Test

```bash
curl -fsS https://edr.example.com/healthz
docker compose exec app pytest -q apps/edr/tests/smoke
```

### 34.4 Run the Golden Set

```bash
docker compose exec app python -m apps.edr.evaluation.run --suite goldenset
```

---

## 35. Glossary

- **BOQ** — Bill of Quantities.
- **EOT** — Extension of Time.
- **Evidence Object** — the normalized record described in Section 12.
- **Heavy tier** — Claude Sonnet 4.6 in this deployment.
- **Light tier** — Claude Haiku 4.5 in this deployment.
- **Quality Gate** — the validation step in Node 13.
- **RBAC** — Role-Based Access Control.
- **RFI** — Request for Information.
- **RPO / RTO** — Recovery Point Objective / Recovery Time Objective.
- **SSO** — Single Sign-On.
- **Vibe coding** — AI-assisted rapid implementation with Claude Code in VS Code.

---

END OF SPECIFICATION
