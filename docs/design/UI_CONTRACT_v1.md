# DecisionCenter — UI Contract v1.0

> **Status:** LOCKED — Official UI specification. Supersedes `docs/design/UI_UX_SCOPE.md`.
> **Date locked:** 2026-05-06
> **Derived from:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md` (locked spec, all section references below are to this file)
> **Corrections applied:** Six corrections from design review (detailed in Section 0).
> **Revision:** v1.1 — 2026-05-06: Applied verification finding CF-2 (PDF/XLSX export format restriction corrected to spec-accurate content-section restriction); added N-1, N-2 footnotes.
> **Scope:** Specification only. No frontend code. No product logic.
> **Constraint:** Every element in this document maps to a named spec requirement. Nothing is decorative.

---

## 0. Corrections Applied to Prior Design

The following corrections from design review are incorporated throughout this document. Each correction is traced to the section where it is enforced.

| ID | Correction | Enforced In |
|---|---|---|
| C-1 | Admin role must not grant business-data visibility. Admin sees metadata and system controls only — no report content, no evidence excerpts, no evidence-pack contents. | Sections 3.5, 4.3, 8 |
| C-2 | `evidence-pack.json` and `audit-log.json` are RBAC-controlled artifacts, not freely downloadable. Visibility rules are defined per role and per state. | Sections 6, 5 |
| C-3 | Uploaded files must follow a documented retention and audit policy. Uncontrolled deletion is prohibited. Every file deletion is a logged event. | Section 6 |
| C-4 | A failed quality gate blocks all export paths at both UI and API layer. No download is served from any path when `quality_gate_status = "failed"`. | Sections 7, 8 |
| C-5 | `needs_review` state shows draft/watermarked output only to reviewers with `can_approve = True`. The report requester sees quality gate flags only — not the report content. | Sections 3.3, 7 |
| C-6 | Connector credentials are never displayed in any form — not masked, not truncated, not partially revealed. Only presence indicators are shown. | Section 4.2 |

---

## 1. Final UI Scope

### 1.1 Two Interfaces

| Interface | Purpose | Accessible to |
|---|---|---|
| **User Chat Workspace** | Submit management questions, view evidence-backed reports, download approved exports | Roles: `executive`, `project_manager`, `finance`, `commercial`, `document_control`, `procurement`, `legal` (full); `auditor` (read-only, no submit) |
| **Admin Visual Control Plane** | Configure connectors, manage role mappings, monitor health, review approvals, read audit log | Role: `admin` only. Admin sees system metadata — never business-data content. |

### 1.2 Design Principles

| Principle | Binding Rule |
|---|---|
| Evidence-first | Every rendered claim cites a source. No source = no rendered claim. |
| Role-bounded | The interface renders only what the authenticated role permits. Missing data is stated explicitly — never silently hidden. |
| State-explicit | Every screen has a named state. State is always visible. No unmarked loading spinners. |
| Minimal surface | A UI element that has no corresponding spec requirement must not exist. |
| Audit-visible | Every approval, rejection, configuration change, and deletion is logged before UI feedback is shown. |
| Progressive disclosure | Summaries are the default. Detail panels open on demand. |
| Admin is structural | Admin role grants system-configuration visibility only. It grants zero business-data access. |

### 1.3 Layout System

```
┌─────────────────────────────────────────────────────────────┐
│ TOPBAR — 48px fixed                                         │
│ Logo · Breadcrumb · [Interface label] · Role badge · Avatar │
├──────────────┬──────────────────────────────────────────────┤
│ SIDEBAR      │ MAIN CONTENT AREA                           │
│ 220px fixed  │ max-width 960px, horizontally centered       │
│ collapses to │                                              │
│ 48px icon    │ DETAIL PANEL — 380px, slide-in from right   │
│ rail         │ (context, evidence, event detail)            │
└──────────────┴──────────────────────────────────────────────┘
```

Minimum supported width: 768px (tablet). Mobile layout is out of scope.

### 1.4 Visual Tokens

**Color:**

| Token | Value | Usage |
|---|---|---|
| `surface-base` | `#0F1117` | Page background |
| `surface-raised` | `#1A1D27` | Cards, panels |
| `surface-overlay` | `#242736` | Modals |
| `border` | `#2D3142` | Separators |
| `accent` | `#4F6EF7` | Primary actions, links |
| `success` | `#22C55E` | ok, passed, connected, authorized |
| `warning` | `#F59E0B` | needs_review, degraded, cap warning |
| `error` | `#EF4444` | failed, disconnected, denied |
| `text-primary` | `#F1F5F9` | Main content |
| `text-secondary` | `#94A3B8` | Labels, metadata |
| `text-muted` | `#4B5563` | Timestamps, hashes |

**Typography:**

| Use | Spec |
|---|---|
| UI labels | Inter 12px–14px |
| Body / report content | Inter 14px–16px, line-height 1.6 |
| Headings | Inter Semibold 18px–24px |
| Monospace (hashes, IDs, paths) | JetBrains Mono 12px |

**Status pills** — every status value renders as `[icon] label` in the appropriate color token:

| Value | Color | Icon |
|---|---|---|
| `authorized` | success | shield-check |
| `processing` | accent (pulsing) | loader |
| `passed` | success | circle-check |
| `needs_review` | warning | triangle-alert |
| `failed` | error | x-circle |
| `staging` | warning | clock |
| `approved` | success | stamp |
| `rejected` | error | ban |
| `final` | accent | lock |
| `connected` | success | plug |
| `degraded` | warning | plug-zap |
| `disconnected` | error | plug-x |
| `unknown` | text-muted | circle-dashed |

### 1.5 Role-Based Navigation Routing

| Role | Default landing | Forbidden |
|---|---|---|
| `executive` | User Chat Workspace — Query Composer | All `/admin/*` routes |
| `project_manager` | User Chat Workspace — Query Composer | All `/admin/*` routes |
| `finance` | User Chat Workspace — Query Composer | All `/admin/*` routes |
| `commercial` | User Chat Workspace — Query Composer | All `/admin/*` routes |
| `document_control` | User Chat Workspace — Query Composer | All `/admin/*` routes |
| `procurement` | User Chat Workspace — Query Composer | All `/admin/*` routes |
| `legal` | User Chat Workspace — Query Composer | All `/admin/*` routes |
| `auditor` | User Chat Workspace — My Reports (read-only) | All `/admin/*` routes; Query Composer; any submit action |
| `admin` | Admin Visual Control Plane — Dashboard | All `/workspace/*` routes; Query Composer; Report View; any evidence or report content |

Access violations return HTTP 403 from the server. Client-side routing guards are UX only.

---

## 2. User Chat Workspace — Six Screens

### 2.1 Screen: Query Composer

**Route:** `/workspace/new`
**Purpose:** The only entry point for submitting a management question.
**Visible to:** All roles except `auditor` (read-only redirect) and `admin` (CP redirect).

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Project:  [PRJ-001 ▾]              [executive ●]   │
│                                                     │
│  ┌────────────────────────────────────────────────┐ │
│  │  What is the status of contract CON-001        │ │
│  │  and the outstanding payment position?         │ │
│  │                                        42/2000 │ │
│  └────────────────────────────────────────────────┘ │
│                                                     │
│  ▶ Filters (optional)                               │
│    Contract No. [        ]  Vendor [        ]       │
│    Date range   [        ]  Type   [        ▾]      │
│                                                     │
│  ▶ Upload supplementary files                       │
│                                                     │
│  Output formats:                                    │
│  [✓ MD] [✓ DOCX] [  PDF] [  XLSX] [  PPTX]         │
│                                                     │
│                           [Generate Report →]       │
└─────────────────────────────────────────────────────┘
```

**Fields:**

| Field | Type | Source | Constraint |
|---|---|---|---|
| Project | Dropdown | `DecisionState.allowed_projects` | Only projects the authenticated role is authorized for. Empty list shows "No authorized projects" and disables submit. |
| Query | Textarea | Free text | Min 10 chars, max 2000 chars. Character counter always visible. |
| Contract No. | Text | Optional | Auto-suggests from the selected project's `contract_numbers` in source mapping. |
| Vendor | Text | Optional | |
| Date range | Date pair | Optional | ISO 8601. Start must be ≤ end. |
| Document type | Dropdown | Optional | Contract · Invoice · Report · Email · Other |
| Upload | Expandable zone | See Section 6 | |
| MD | Toggle | Pre-selected | Always available. |
| DOCX | Toggle | Optional | Available to all content-producing roles. |
| PDF | Toggle | Optional | Available to all content-producing roles. Financial section within the generated PDF is conditionally rendered: absent with explicit "[Financial data not available for your role]" statement for roles without `can_access_odoo_budget` (spec Section 8.3). |
| XLSX | Toggle | Optional | Available to all content-producing roles. Financial rows within the generated XLSX are conditionally rendered per spec Section 8.3. |
| PPTX | Toggle | Optional | Available to all content-producing roles. |
| Submit | Button | — | Disabled until Project and Query are both set. |

**Screen states:**

| State | Condition | Visual |
|---|---|---|
| `idle` | Loaded, no input | Placeholder text in textarea |
| `draft` | Any field filled | Character counter active; submit enabled if project + query set |
| `submitting` | POST in flight | Submit button disabled; inline spinner replaces arrow |
| `queued` | 202 received | Immediate transition to Processing View |
| `error` | Server rejection | Inline error banner above submit. Fields remain editable. |
| `no_projects` | `allowed_projects` is empty | "No authorized projects for your role. Contact your administrator." Submit hidden. |

---

### 2.2 Screen: Processing View

**Route:** `/workspace/report/{request_id}/processing`
**Purpose:** Show workflow progress. Never expose system internals.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Generating report                     [Cancel ×]   │
│  PRJ-001 · "What is the status of contract CON…"    │
│                                                     │
│  ████████████████░░░░░░░░░░░░░░░░  51%              │
│                                                     │
│  ✓  Verifying access                                │
│  ✓  Understanding your question                     │
│  ✓  Determining scope                               │
│  ✓  Planning retrieval                              │
│  ✓  Searching SharePoint                            │
│  ↻  Searching ownCloud...              [pulsing]    │
│  ○  Searching email                                 │
│  ○  Reading Odoo records                            │
│  ○  Organizing evidence                             │
│  ○  Checking evidence quality                       │
│  ○  Refining search                                 │
│  ○  Drafting report                                 │
│  ○  Quality gate                                    │
│  ○  Composing report                                │
│  ○  Saving to staging                               │
│  ○  Awaiting reviewer                               │
│  ○  Publishing                                      │
│                                                     │
│  Elapsed: 00:42                                     │
└─────────────────────────────────────────────────────┘
```

**Node-to-label mapping** (internal names never exposed):

| Internal | User label |
|---|---|
| node_00_begin | Starting |
| node_01_auth | Verifying access |
| node_02_intent | Understanding your question |
| node_03_scope | Determining scope |
| node_04_plan | Planning retrieval |
| node_05_sharepoint | Searching SharePoint |
| node_06_owncloud | Searching ownCloud |
| node_07_email | Searching email |
| node_08_odoo | Reading Odoo records |
| node_09_normalize | Organizing evidence |
| node_10_sufficiency | Checking evidence quality |
| node_11_self_correct | Refining search |
| node_12_draft_json | Drafting report |
| node_13_quality_gate | Quality gate |
| node_14_compose_md | Composing report |
| node_15_save_audit | Saving to staging |
| node_16_review | Awaiting reviewer |
| node_17_publish | Publishing |

**Never expose:** node identifiers, evidence IDs, LLM model names, token counts, raw API responses, internal error tracebacks.

**Screen states:**

| State | Display |
|---|---|
| `running` | Active node label pulses. Progress bar advances. Elapsed timer counts up. |
| `self_correct_retry` | Label becomes "Refining search — attempt 2 of 3". Progress bar pauses briefly. |
| `quality_gate_passed` | Brief green flash on quality gate row. Transitions automatically. |
| `quality_gate_needs_review` | Orange banner: "Report flagged for mandatory review. Proceeding to staging." Non-dismissable. |
| `quality_gate_failed` | Red banner: "Evidence insufficient — report cannot be generated." New query button appears. All remaining steps greyed. |
| `awaiting_reviewer` | Blue banner: "Report submitted for review. You will be notified when a decision is made." |
| `timed_out` | Error banner with elapsed time and retry option. |
| `rbac_denied` | Red banner: "Access denied." Returns to Query Composer. |
| `cancelled` | All steps greyed. "Cancelled" badge replaces progress bar. |

**Cancel action:**
1. Confirmation modal: "Cancel this report? Progress cannot be recovered."
2. On confirm: DELETE request to API. Transition to idle Query Composer.
3. Audit event `report.cancelled` written.

---

### 2.3 Screen: Report View

**Route:** `/workspace/report/{request_id}`
**Purpose:** Display the evidence-backed executive report with source tracing.

**Layout (approved or final state):**
```
┌───────────────────────────────────┬──────────────────┐
│  REPORT CONTENT                   │ EVIDENCE PANEL   │
│                                   │                  │
│  [staging ●] PRJ-001              │ Evidence Pack    │
│  2026-05-06 14:22 · executive     │ ─────────────    │
│  Reviewer: —                      │ [1] SharePoint   │
│  ─────────────────────────────    │     Contract doc │
│                                   │     High · 0.94  │
│  ## Executive Summary             │                  │
│                                   │ [2] Odoo         │
│  Contract CON-001 with Vendor     │     Analytic line│
│  X is active. Outstanding         │     High · 0.91  │
│  payment is AED 142,000 as of ¹   │                  │
│  2026-04-30, per Odoo records. ²  │ [3] Email        │
│                                   │     Shared mbox  │
│  ## Financial Position            │     Med · 0.72   │
│  [rendered if finance permitted]  │                  │
│  [state message if not permitted] │ Filter:          │
│                                   │ [Source type ▾]  │
│  ## Conflicts Detected            │ [Confidence ▾]   │
│  [always rendered if non-empty]   │                  │
│                                   │                  │
│  ## Missing Data                  │                  │
│  [always rendered if non-empty]   │                  │
│                                   │                  │
│  ## Sources                       │                  │
│  [1] … [2] … [3] …               │                  │
│                                   │                  │
│  [Export ▾]                       │                  │
└───────────────────────────────────┴──────────────────┘
```

**Content rendering rules:**

- Superscript citations (`¹ ² ³`) anchor-link to the corresponding Evidence Panel entry.
- "Financial Position" section: renders only if role has `can_access_odoo_budget`. If absent, section reads: `[Financial data is not available for your role]` — stated, not hidden.
- "Conflicts Detected": always rendered if the JSON contains conflicts. Cannot be collapsed.
- "Missing Data": always rendered if the JSON contains missing fields. Cannot be collapsed.
- Raw `evidence_id` values are never shown. Evidence Panel shows: source label, source type, confidence label and score, truncated hash (last 8 hex chars).
- Email source excerpts are read-only (no copy action). Document source excerpts are copyable.

**Evidence Panel entry anatomy:**
```
[2] CON-001 — Payment Schedule
    Source: Odoo · account.analytic.line
    Date:   2026-04-30
    Confidence: High (0.91)
    Hash:   …c12d4e7f  [copy icon]
    [▶ View excerpt]  ← max 500 chars, read-only
```

**Report states and their visual rules:**

| State | Condition | Content visible to requester | Export available | Actions available |
|---|---|---|---|---|
| `staging` | Awaiting reviewer | Full report | No — "Awaiting approval" | Requester: none. Reviewer: Approve, Reject, Request revision |
| `needs_review` | QG flagged; sent for review | **Requester: QG flags only. No report content.** (C-5) | No | Requester: none. Reviewer: sees watermarked draft. |
| `approved` | Reviewer approved | Full report | Yes — all generated formats | Requester: Export. Reviewer: Export. |
| `rejected` | Reviewer rejected | Full report + rejection reason | No | Requester: New query. |
| `final` | Published to MinIO final path | Full report, immutable | Yes | None (locked). |

For `needs_review` — requester sees:
```
┌─────────────────────────────────────────────────────┐
│  [needs_review ●] PRJ-001                           │
│                                                     │
│  Your report has been flagged for mandatory review. │
│  Report content is not available until a reviewer   │
│  has approved it.                                   │
│                                                     │
│  Quality gate flags:                                │
│  ⚠ Section 3 claim has no Odoo evidence_id          │
│  ⚠ Missing Data section is non-empty                │
│                                                     │
│  [New query]                                        │
└─────────────────────────────────────────────────────┘
```

For `needs_review` — reviewer (can_approve = True) sees:
```
┌─────────────────────────────────────────────────────┐
│  [needs_review ●] PRJ-001         DRAFT — AWAITING  │
│  ⚠ Quality gate flags (2):        REVIEW            │
│  ⚠ Section 3 claim: no Odoo ID                      │  ← non-dismissable
│  ⚠ Missing Data: non-empty                          │
│  ─────────────────────────────────────────────────  │
│  [full report content rendered below with           │
│   "DRAFT — AWAITING REVIEW" watermark on each       │
│   section header]                                   │
│                                                     │
│  Reviewer comment: [                          ]     │
│  [Approve]  [Reject]  [Request revision]            │
└─────────────────────────────────────────────────────┘
```

---

### 2.4 Screen: Export Panel

**Route:** Slide-out panel triggered from Report View `[Export ▾]`
**Purpose:** Download generated report artifacts.
**Visible:** Only when report state is `approved` or `final`.

**Layout:**
```
┌─────────────────────────────────────────┐
│  Export                          [×]    │
│  ──────────────────────────────────     │
│  Report formats                         │
│  [↓ Markdown (.md)]                     │
│  [↓ Word (.docx)]                       │
│  [↓ PDF (.pdf)]                         │
│  [↓ Excel (.xlsx)]                      │
│  [↓ PowerPoint (.pptx)]                 │
│  ──────────────────────────────────     │
│  Artifacts                              │
│  [↓ evidence-pack.json]  ← RBAC-gated  │
│  [↓ audit-log.json]      ← RBAC-gated  │
│  ──────────────────────────────────     │
│  State: approved · Version: 1           │
└─────────────────────────────────────────┘
```

Full export rules are in Section 7. The panel is not rendered at all when state is `staging`, `needs_review`, `failed`, or `rejected`.

---

### 2.5 Screen: Upload Zone

**Route:** Expandable section within Query Composer
**Purpose:** Attach supplementary context documents to a query.

Full upload rules are in Section 6.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  ▼ Upload supplementary files                       │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  Drag files here or [browse]                │   │
│  │                                             │   │
│  │  PDF · DOCX · XLSX · TXT · MSG             │   │
│  │  Max 10 MB per file · Max 5 files per query │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  contract-draft-v2.pdf      1.2 MB  [✓]  [✕]       │
│  site-survey-2026-04.docx   840 KB  [✓]  [✕]       │
│                                                     │
│  ℹ These files are used as context only.            │
│    They are not added to company evidence sources.  │
│    Files are deleted per the retention policy       │
│    (see docs/policies/upload_retention.md).         │
└─────────────────────────────────────────────────────┘
```

---

### 2.6 Screen: My Reports List

**Route:** `/workspace/reports`
**Purpose:** View prior and in-progress reports.

**Layout:**
```
┌──────────────────────────────────────────────────────┐
│  My Reports                         [Filter ▾]       │
│                                                      │
│  In progress                                         │
│  ──────────────────────────────────────────────────  │
│  ↻ What is the status of CON-001…  PRJ-001  00:42   │
│                                                      │
│  Awaiting review                                     │
│  ──────────────────────────────────────────────────  │
│  Contract review query…   PRJ-001  [needs_review ●] │
│                                                      │
│  Approved / Final                                    │
│  ──────────────────────────────────────────────────  │
│  Q1 vendor performance    PRJ-002  [final ●]  05-03 │
└──────────────────────────────────────────────────────┘
```

**Columns:** Query excerpt (60 chars max) · Project · Status pill · Timestamp or elapsed
**Actions:** Click row → Report View for that request.
**Filters:** By project (authorized only), by state, by date range.
**Search:** Not available. No full-text search across report content.
**Scope rules:**
- Each role sees only their own requests.
- `auditor` sees all reports for projects in their `allowed_projects` scope — read-only.
- `needs_review` state: requester sees the row but report content is blocked until approved.

---

## 3. Admin Visual Control Plane — Seven Screens

**Critical rule (C-1):** Admin sees system state, counts, statuses, and configuration metadata. Admin never sees report content, evidence excerpts, user queries, or any business-data artifact. Every admin screen in this section enforces this boundary.

### 3.1 Screen: Dashboard

**Route:** `/admin/dashboard`
**Purpose:** Single-pane summary of system health, operational counts, and cost posture. No business data.

**Layout:**
```
┌──────────────────────────────────────────────────────────┐
│  Dashboard                           2026-05-06 14:30    │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐         │
│  │ Services   │  │ Approvals  │  │ Daily Cost │         │
│  │  9/10  ok  │  │  3 pending │  │ $4.20/$12  │         │
│  │  1 degraded│  │            │  │ ████░░░░░░ │         │
│  └────────────┘  └────────────┘  └────────────┘         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐         │
│  │  Requests  │  │  Failed QG │  │  Monthly   │         │
│  │  Today: 12 │  │  Today:  1 │  │ $47/$300   │         │
│  └────────────┘  └────────────┘  └────────────┘         │
│                                                          │
│  External Services                                       │
│  ────────────────────────────────────────────────────    │
│  PostgreSQL ● ok    Redis    ● ok    Qdrant   ● ok       │
│  MinIO      ● ok    n8n      ● ok    Langfuse ● ok       │
│  SharePoint ● ok    Graph    ● ok    ownCloud ⚠ degraded │
│  Odoo       ● ok                                         │
│                                                          │
│  Recent System Events (last 10)                          │
│  ────────────────────────────────────────────────────    │
│  14:28  report.approved   PRJ-001  abc123                │
│  14:12  connector.error   ownCloud — 504 Gateway Timeout │
│  13:55  report.rejected   PRJ-001  def456                │
└──────────────────────────────────────────────────────────┘
```

**Cards:** Each navigates to the relevant screen on click.
**External Services grid:** Each entry navigates to Connectors & APIs with that service pre-selected.
**Recent Events:** System events only. Query text, report content, and evidence are never shown. Event entries show: timestamp, event type, project (if applicable), request ID (if applicable). Click → Audit Log filtered to that event.

---

### 3.2 Screen: Connectors & APIs

**Route:** `/admin/connectors`
**Purpose:** View connection status and `.env` configuration presence for all 10 external services. Read-only.

**Left panel: service list**
```
PostgreSQL        ● connected
Redis             ● connected
Qdrant            ● connected
MinIO             ● connected
n8n               ● connected
SharePoint        ● connected
Microsoft Graph   ● connected
ownCloud          ⚠ degraded
Odoo              ● connected
Langfuse          ● connected
```

**Right detail panel:**
```
┌─────────────────────────────────────────────────────┐
│  ownCloud                          ⚠ degraded       │
│  ─────────────────────────────────────────────────  │
│  Type:         WebDAV connector via n8n             │
│  Host:         cloud.example.com          [visible] │
│  Protocol:     https                                │
│  Auth type:    Basic (credentials in .env)          │
│                                                     │
│  .env key presence:                                 │
│    OWNCLOUD_LIST_WEBHOOK  ✓ set                      │
│    N8N_BASE_URL           ✓ set                      │
│    N8N_WEBHOOK_TOKEN      ✓ set                      │
│                                                     │
│  n8n workflow: owncloud_list.json                   │
│  Workflow nodes: ○ empty (not deployed)             │
│                                                     │
│  Last success: 2026-05-06 13:01                     │
│  Last error:   2026-05-06 13:58 — 504 Gateway TO   │
│  Latency (p95): 2340ms    SLA target: 500ms         │
│                                                     │
│  Error log (last 5):                                │
│  13:58  504 Gateway Timeout                         │
│  12:44  504 Gateway Timeout                         │
│  11:30  200 OK — 14 items returned                  │
│                                                     │
│  [Test connection]    [Open n8n ↗]                  │
└─────────────────────────────────────────────────────┘
```

**Credential display rules (C-6):**

The following are NEVER displayed, in any form:
- Passwords, tokens, API keys, client secrets, connection string values.
- Partially masked values such as `sk-...xxxx` or `Bearer ***`.
- Base64-encoded values.

The following MAY be displayed:
- Hostname or URL that does not embed credentials (e.g., `cloud.example.com`, `https://odoo.example.com`).
- Key name and presence indicator: `OWNCLOUD_WEBHOOK ✓ set` or `ODOO_API_KEY ✗ missing`.
- Auth mechanism type: Basic, Bearer, API key, OAuth2 — not the value.

**Service detail fields by service:**

| Service | Fields shown |
|---|---|
| PostgreSQL | Host (hostname only), port, DB name, pool size, last ping latency |
| Redis | Host (hostname only), port, PING latency |
| Qdrant | Host (hostname only), collections list with vector count per collection, last write timestamp |
| MinIO | Host (hostname only), bucket name, staging file count, final file count |
| n8n | Host (hostname only), 4 workflow files with `empty / deployed` status, last webhook timestamp |
| SharePoint | Tenant ID (masked: first 4 chars only), client ID (presence only), token expiry datetime |
| Microsoft Graph | Delegated scopes list, allowed mailbox count (from project mapping), last call timestamp |
| ownCloud | Host (hostname only), last success timestamp, error log |
| Odoo | Host (hostname only), DB name, last RPC timestamp, last error |
| Langfuse | Host, public key (presence only), last trace timestamp, 30-day call count |

**Actions:**
- `[Test connection]` — lightweight probe (identical to `/healthz` per-service check). Does not modify state. Shows inline pass/fail with latency.
- `[Open n8n ↗]` — opens n8n admin URL in new tab. Only available when `N8N_BASE_URL` is set.
- No credential editing. No service restart. No workflow editing in this UI.

**States:** `connected` · `degraded` · `disconnected` · `unknown` (defined in Section 1.4 status pills).

---

### 3.3 Screen: Permissions & Roles

**Route:** `/admin/permissions`
**Purpose:** View RBAC matrix, manage Entra group-to-role mappings. Does not expose business data.

**Three tabs:**

**Tab 1 — Role Matrix (read-only)**
Renders the canonical RBAC table from `docs/security/rbac_matrix.md`. Not editable via UI. Changes require a spec update.

```
Role             SP Docs     OC Docs     Mailbox   Odoo Budget  Approve   Audit
──────────────────────────────────────────────────────────────────────────────
executive        Allowed     Allowed     No        If permitted Yes       Summary
project_manager  Assigned    Assigned    Own only  If permitted Review    Own proj
finance          If perm     If perm     Own only  Yes          Finance   Finance
commercial       Contracts   Contracts   Own only  If permitted Comm rev  Comm
document_control Ctrl docs   Ctrl docs   Own only  No           Review    Doc
procurement      Proc docs   Proc docs   Own only  PO-related   Review    Proc
legal            Contracts   Contracts   Own only  If permitted Legal rev Legal
auditor          Refs only   Refs only   No        If permitted No        Yes
admin            Config only Config only No        No           No        System
```

**Tab 2 — Entra Group Mapping**
```
┌──────────────────────────────────────────────────────┐
│  Entra Group → Role                                  │
│  ──────────────────────────────────────────────────  │
│  dc-executives       → executive         [Edit] [✕]  │
│  dc-project-managers → project_manager   [Edit] [✕]  │
│  dc-finance          → finance           [Edit] [✕]  │
│  dc-legal            → legal             [Edit] [✕]  │
│  dc-auditors         → auditor           [Edit] [✕]  │
│  dc-admin            → admin             [Edit] [✕]  │
│                                                      │
│  [+ Add mapping]                                     │
│                                                      │
│  ℹ Entra group IDs are resolved at login.            │
│    Changes take effect on next user login.           │
└──────────────────────────────────────────────────────┘
```

Edit: inline row editor. Role dropdown limited to 9 canonical identifiers. Entra group ID validated against Entra on save (when `ENTRA_CLIENT_ID` is configured). Save writes `admin.role_mapping_changed` to audit log.

**Tab 3 — Project Role Assignments (read-only)**
Shows `allowed_roles` from `project_source_mapping.json` per project:
```
PRJ-001  →  executive, project_manager, finance, commercial
PRJ-002  →  executive, project_manager, legal
```
Editing is performed via Source Mapping screen, not here.

---

### 3.4 Screen: Source Mapping

**Route:** `/admin/source-mapping`
**Purpose:** View and edit `docs/config/project_source_mapping.json`.

**Layout — left/right:**
```
Left: Project list          Right: Project editor
─────────────────           ──────────────────────
PRJ-001  ● active           ┌───────────────────────────────┐
PRJ-002  ● active           │ PRJ-001              [Save][✕]│
[+ Add project]             │ ──────────────────────────── │
                            │ SharePoint                    │
                            │   Site ID:  [site-id-001    ] │
                            │   Drive ID: [drive-id-001   ] │
                            │   Root:     [/Projects/PRJ-1] │
                            │                               │
                            │ ownCloud                      │
                            │   Base path: [/Projects/PRJ-1]│
                            │                               │
                            │ Email                         │
                            │   Shared mailboxes:           │
                            │   project@example.com    [✕]  │
                            │   [+ Add mailbox]             │
                            │   Doc control mailbox:        │
                            │   [docctrl@example.com     ]  │
                            │                               │
                            │ Odoo                          │
                            │   Project model: [proj.proj ] │
                            │   Cost model:    [acct.anal ] │
                            │   Ext. ID:       [PRJ-001   ] │
                            │                               │
                            │ Contracts: CON-001 [✕] [+Add] │
                            │                               │
                            │ Allowed roles:                │
                            │ [✓]exec [✓]pm [✓]fin [✓]comm │
                            │ [ ]doc  [ ]proc [ ]leg [ ]aud │
                            └───────────────────────────────┘
```

**Save behavior:**
1. Client-side JSON schema validation. Fails show inline per-field errors.
2. Diff preview modal: lists every field being added, changed, or removed.
3. Any change that removes an allowed role requires typing the project code to confirm.
4. On confirm: file written. Audit event `admin.source_mapping_changed` written first.
5. Toast: "Saved. Changes take effect on next report request."

**Delete project:**
1. Confirmation modal: "Remove PRJ-001? All source mappings for this project will be deleted. Existing reports are not affected."
2. User must type project code.
3. Audit event `admin.source_mapping_deleted` written.

---

### 3.5 Screen: Approval Queue

**Route:** `/admin/approvals`
**Purpose:** Surface reports pending human review. Admin sees operational metadata only — not report content (C-1).

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  Approval Queue                      3 pending          │
│  Filter: [All projects ▾] [All states ▾]               │
│                                                         │
│  abc123  PRJ-001  [staging ●]       14:22  u_a1b2c3d4  │
│  def456  PRJ-001  [needs_review ●]  13:01  u_e5f6g7h8  │
│  ghi789  PRJ-002  [staging ●]       12:44  u_i9j0k1l2  │
│                                                         │
│  [Load more]                                            │
└─────────────────────────────────────────────────────────┘
```

**Columns:** Request ID (truncated) · Project · Status pill · Submitted at · Requester hash (HMAC-SHA256, first 8 chars)

**Click row → Review Panel (admin view):**

Admin review panel shows ONLY system-level information. No business content.

```
┌─────────────────────────────────────────────────────┐
│  abc123                          [staging ●]        │
│  ─────────────────────────────────────────────────  │
│  Project:        PRJ-001                            │
│  Submitted:      2026-05-06 14:22                   │
│  Requester hash: u_a1b2c3d4                         │
│  Quality gate:   needs_review                       │
│                                                     │
│  Quality gate flags:                                │
│  ⚠ Section 3 claim has no Odoo evidence_id          │
│  ⚠ Missing Data section is non-empty                │
│                                                     │
│  [View audit log for this request →]                │
│                                                     │
│  ─── Admin action ────────────────────────────────  │
│  Admin override comment: [required               ]  │
│                                                     │
│  [Admin approve]  [Admin reject]                    │
│                                                     │
│  ⚠ Admin approval is logged as admin_override.     │
│    Content visibility is not granted to admin role. │
└─────────────────────────────────────────────────────┘
```

**What admin does NOT see in the review panel:**
- Report query text
- Report content
- Evidence excerpts
- Evidence pack data
- Source document names or paths

**Admin approval/rejection** is logged as event type `report.admin_override_approved` or `report.admin_override_rejected` — distinct from normal reviewer events. Admin comment is required.

**Reviewer access:** Roles with `can_approve = True` access the approval queue through their workspace (My Reports → queue view), not through the Admin CP. They see full draft content (with watermark for `needs_review`).

---

### 3.6 Screen: Audit Log

**Route:** `/admin/audit`
**Purpose:** Immutable, searchable system event log.

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  Audit Log                                              │
│  Filter: [Date range] [Event type ▾] [Project ▾]       │
│  Search: [request_id or user_hash          ] [Search]  │
│  ────────────────────────────────────────────────────   │
│  2026-05-06 14:28  report.approved      PRJ-001  abc123 │
│  2026-05-06 14:12  connector.error      ownCloud  —     │
│  2026-05-06 13:55  report.rejected      PRJ-001  def456 │
│  2026-05-06 13:22  report.submitted     PRJ-002  ghi789 │
│  2026-05-06 13:01  rbac.denied          —         —     │
│  ────────────────────────────────────────────────────   │
│  [Export CSV]                     Page 1/8   [← →]     │
└─────────────────────────────────────────────────────────┘
```

**Defined event types:**

| Category | Events |
|---|---|
| Report lifecycle | `report.submitted` · `report.approved` · `report.rejected` · `report.revision_requested` · `report.cancelled` · `report.admin_override_approved` · `report.admin_override_rejected` |
| RBAC | `rbac.authorized` · `rbac.denied` |
| Quality gate | `quality_gate.passed` · `quality_gate.failed` · `quality_gate.needs_review` |
| Connector | `connector.error` · `connector.latency_spike` · `connector.probe_success` |
| Upload | `upload.received` · `upload.rejected` · `upload.deleted` |
| Cost | `cost.daily_cap_warning` · `cost.daily_cap_exceeded` |
| Admin | `admin.source_mapping_changed` · `admin.source_mapping_deleted` · `admin.role_mapping_changed` |

**Event detail (slide-in panel):**
```
Event:        report.approved
Time:         2026-05-06 14:28:03 UTC
Request ID:   abc123
Project:      PRJ-001
User hash:    a1b2c3d4e5f6g7h8
Approver hash: x9y8z7w6v5u4t3s2
Comment:      "Evidence complete."
Quality gate: needs_review
Nodes visited: 18/18
Token counts: {node_02: 312, node_12: 4821, …}  ← admin only
Cost (USD):   $0.42                               ← admin only
```

**Audit log rules:**
- `user_id` is always shown as HMAC-SHA256 hash. Plain `user_id` never appears.
- Token counts and cost fields are rendered only when the viewer's role is `admin`.
- No log entry may be deleted, filtered out, or modified through any UI path.
- `auditor` role: project-scoped subset; sees report lifecycle and RBAC events for their projects. Does not see token counts, cost, or admin events.
- CSV export: cost and token columns are redacted to `[restricted]` for non-admin exporters.

---

### 3.7 Screen: System Health

**Route:** `/admin/health`
**Purpose:** Live service status with latency trends and cost posture.

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  System Health                  Last: 14:30:01          │
│  [Refresh]              Auto-refresh: [30s ▾]           │
│  ────────────────────────────────────────────────────   │
│  Service       Status   Latency  SLA      Trend         │
│  PostgreSQL    ● ok      12ms    200ms    [sparkline]    │
│  Redis         ● ok       3ms    100ms    [sparkline]    │
│  Qdrant        ● ok      28ms    300ms    [sparkline]    │
│  MinIO         ● ok      45ms    500ms    [sparkline]    │
│  n8n           ● ok     102ms    500ms    [sparkline]    │
│  SharePoint    ● ok     340ms   1000ms    [sparkline]    │
│  Graph API     ● ok     280ms   1000ms    [sparkline]    │
│  ownCloud      ⚠ deg   2340ms    500ms    [sparkline]    │
│  Odoo          ● ok     190ms    500ms    [sparkline]    │
│  Langfuse      ● ok     210ms    500ms    [sparkline]    │
│  ────────────────────────────────────────────────────   │
│  Cost Monitor                                           │
│  Today:    $4.20 / $12.00   ████░░░░░░  35%             │
│  Monthly:  $47.00 / $300.00 ██░░░░░░░░  16%  ⋯proj     │
│  ────────────────────────────────────────────────────   │
│  LLM Today                                             │
│  Claude Haiku 4.5    18 calls   $0.18                   │
│  Claude Sonnet 4.6    7 calls   $4.02                   │
└─────────────────────────────────────────────────────────┘
```

**Sparkline:** 24h inline chart. Click → full-width line chart in detail panel.
**Cost warning at 80%:** Yellow banner `[⚠ Daily cost at 80% — $9.60 / $12.00]` across top of screen.
**Cost exceeded:** Red banner `[✕ Daily cost cap reached — new report submissions blocked]`. This state is system-wide, not screen-local. The banner also appears in the user workspace.

---

## 4. RBAC Visibility Matrix

This matrix is the single authoritative reference for what each role may see in the UI. All sections above refer to this matrix. Server-side enforcement is the source of truth; UI suppression is an additional UX constraint only.

### 4.1 Report Content Visibility

| Data | exec | pm | finance | comm | doc_ctrl | proc | legal | auditor | admin |
|---|---|---|---|---|---|---|---|---|---|
| Executive summary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (ref) | ✗ |
| Financial Position section | If perm | If perm | ✓ | If perm | ✗ | PO only | If perm | If perm | ✗ |
| Conflicts Detected | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Missing Data | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Sources section | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Evidence excerpts (doc) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Ref only | ✗ |
| Evidence excerpts (email) | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✗ | ✗ |

### 4.2 Artifact Download Visibility

| Artifact | exec | pm | finance | comm | doc_ctrl | proc | legal | auditor | admin |
|---|---|---|---|---|---|---|---|---|---|
| report.md | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ final | ✗ |
| report.docx | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ final | ✗ |
| report.pdf | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ final | ✗ |
| report.xlsx | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ final | ✗ |
| report.pptx | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ approved | ✓ final | ✗ |
| evidence-pack.json | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ scope | ✗ |
| audit-log.json (per-req) | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ own req | ✓ scope | via UI only |

Notes:
- "own req" — only the user who submitted the request. No cross-user access.
- "scope" — auditor has read access across all projects in their `allowed_projects`.
- "approved" — state must be `approved` or `final`.
- "via UI only" — admin reads `audit-log.json` content via the Audit Log UI screen, not via download API.
- All download access is blocked when `quality_gate_status = "failed"` regardless of role.
- **N-2 (artifact scope):** `audit-log.json` in this table is the per-request MinIO artifact. It is a different artifact from the system-wide Audit Log (Admin screen Section 3.6). The RBAC matrix Audit Logs column ("Summary" for executive, "Own project" for project_manager, etc.) governs access to the system Audit Log screen, not the per-request artifact download.

### 4.3 Admin Screen Visibility

| Screen | admin | non-admin |
|---|---|---|
| Dashboard | ✓ (system metadata only) | ✗ HTTP 403 |
| Connectors & APIs | ✓ | ✗ |
| Permissions & Roles | ✓ | ✗ |
| Source Mapping | ✓ | ✗ |
| Approval Queue | ✓ (metadata + flags only; no report content) | ✗ |
| Audit Log | ✓ (full system log) | Auditor: project-scoped subset via workspace |
| System Health | ✓ | ✗ |

### 4.4 Action Availability

| Action | exec | pm | finance | comm | doc_ctrl | proc | legal | auditor | admin |
|---|---|---|---|---|---|---|---|---|---|
| Submit new query | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Approve report | ✓ | Review only | Finance rev | Comm rev | Review only | Review only | Legal rev | ✗ | Admin override |
| Reject report | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | Admin override |
| Request revision | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Edit source mapping | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Edit role mapping | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Test connector | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| View audit log (full) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Scoped | ✓ |
- **N-1 (admin override):** "Admin override" for Approve and Reject is an exceptional path, not a standard approval role. The RBAC matrix lists admin Approval as "No by default" (spec Section 9). Admin override is permitted only as an administrative action, requires a mandatory comment, and is logged with distinct event types `report.admin_override_approved` / `report.admin_override_rejected` — separate from all normal reviewer approval events.

---

## 5. Upload Rules

### 5.1 Purpose

Uploaded files are query context supplements. They are not added to company evidence sources, not indexed in Qdrant, and not retrievable by other users or queries.

### 5.2 Accepted Types

| MIME type | Extension | Accepted |
|---|---|---|
| `application/pdf` | .pdf | ✓ |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | .docx | ✓ |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | .xlsx | ✓ |
| `text/plain` | .txt | ✓ |
| `message/rfc822` | .msg, .eml | ✓ |
| `image/dwg`, `.dxf`, `.ifc`, `.rvt` | CAD formats | ✗ |
| All other types | — | ✗ |

CAD rejections show: "CAD files are not supported in this release. Contact your administrator." — not a generic error.

### 5.3 Limits

| Limit | Value |
|---|---|
| Max file size | 10 MB per file |
| Max files per query | 5 |
| Max total upload size | 30 MB per query |

Limits are enforced client-side (before upload) and server-side (on ingest). Server-side takes precedence.

### 5.4 Security Processing (server-side, before acceptance)

1. MIME type validation against actual file header (not extension).
2. Size validation.
3. Prompt injection scan: file content is checked for instruction patterns before being passed to any LLM. Files that fail the scan are rejected with: "File rejected: content policy."
4. File hash (SHA-256) computed on receipt and stored in the upload audit record.

### 5.5 Retention Policy (C-3)

Every uploaded file follows this lifecycle. Each transition is a logged audit event of type `upload.received`, `upload.deleted`.

| Event | Retention action |
|---|---|
| File received | Stored at `MinIO:/uploads/{request_id}/{filename}`. Audit record written with `sha256`, filename, size, request_id, user_id_hash, timestamp. |
| Quality gate passes | File deleted immediately after successful composition (node_14_compose_md completes). Audit event `upload.deleted` written with reason `quality_gate_passed`. |
| Quality gate fails | File retained for 7 days for diagnostic purposes. Deleted at T+7d. Audit event `upload.deleted` written with reason `retention_expired`. |
| Report rejected | File retained for 7 days. Deleted at T+7d. Audit event written. |
| Report approved | File deleted immediately after final path write. Audit event written with reason `report_finalized`. |
| User cancels before submission | File deleted immediately. Audit event written with reason `cancelled`. |

No user-accessible re-download of uploaded files is provided at any point after processing begins.

### 5.6 Upload UX States

| State | Display |
|---|---|
| `idle` | Empty drop zone with instruction text |
| `uploading` | Per-file progress bar (0–100%) |
| `scan_pending` | "Scanning file…" with spinner |
| `accepted` | Green check icon, file name, size, remove button |
| `rejected_size` | Inline error: "File exceeds 10 MB limit." |
| `rejected_type` | Inline error: "File type not accepted." |
| `rejected_cad` | Inline error: "CAD files are not supported in this release." |
| `rejected_policy` | Inline error: "File rejected: content policy." |
| `upload_failed` | Inline error with [Retry] button. |

---

## 6. Export Rules

### 6.1 Format Generation

Formats are generated only if selected at query submission time. Non-generated formats are shown in the Export Panel as greyed with label "Not generated."

| Format | When available | Role restriction |
|---|---|---|
| `.md` | Always selected by default | All content roles |
| `.docx` | When selected | All content roles |
| `.pdf` | When selected | All content roles. The Financial Position section within the generated PDF is conditionally rendered per spec Section 8.3: absent for roles without `can_access_odoo_budget`, replaced with explicit "[Financial data not available for your role]" statement. |
| `.xlsx` | When selected | All content roles. Financial rows within the generated XLSX are conditionally rendered per spec Section 8.3: financial data cells absent for roles without `can_access_odoo_budget`. |
| `.pptx` | When selected | All content roles |

### 6.2 State Gate

| Report state | Report formats | evidence-pack.json | audit-log.json |
|---|---|---|---|
| `processing` | Not available | Not available | Not available |
| `staging` | Blocked — "Awaiting approval" | Available (own req, auditor, scope) | Available (own req, auditor, scope) |
| `needs_review` | Blocked — "Awaiting review" | Available (own req, auditor, scope) | Available (own req, auditor, scope) |
| `failed` | **Blocked at API — HTTP 403 for all formats** (C-4) | **Blocked** | Available via Audit Log UI to admin/auditor only |
| `approved` | Available | Available (RBAC-gated per Section 4.2) | Available (RBAC-gated per Section 4.2) |
| `rejected` | Blocked | Available (own req, auditor, scope) | Available (own req, auditor, scope) |
| `final` | Available (immutable path) | Available (RBAC-gated) | Available (RBAC-gated) |

### 6.3 Quality Gate Export Enforcement (C-4)

When `quality_gate_status = "failed"`:

- The Export Panel is not rendered. Not collapsed, not disabled — completely absent from the DOM.
- The API returns HTTP 403 for any `GET /reports/staging/{id}/download/*` or `/reports/final/{id}/download/*` request.
- This applies to all formats including `evidence-pack.json`.
- `audit-log.json` for the failed request is accessible via the Audit Log UI screen to `admin` and `auditor` roles — it is not exposed via the download API.
- The staging MinIO files exist but are not served through any user-accessible path.

### 6.4 Download Behaviour

- Download triggers a `GET /reports/{staging|final}/{request_id}/download/{fmt}`.
- Response is a file stream with appropriate `Content-Type` and `Content-Disposition: attachment; filename="..."`.
- No page redirect. A toast notification confirms "Downloading report.md…"
- Failed downloads show an error toast with the HTTP status code.
- All download events are logged to the audit log as `report.downloaded`.

---

## 7. Quality Gate Rules

### 7.1 Three Verdicts

The quality gate (node_13) emits one of three verdicts and writes `quality-gate-result.json` to the staging path. (Spec Section 17.)

| Verdict | Meaning | Next step |
|---|---|---|
| `passed` | All pass conditions met | Proceeds to node_14 (composition) |
| `needs_review` | One or more pass conditions failed but report has sufficient evidence to be reviewed | Proceeds to node_14, flagged for mandatory human review |
| `failed` | Evidence insufficient; cannot produce a defensible report | Returns to node_11 if retry budget remains; otherwise stops. Report halted. |

Pass conditions (all must be true for `passed`):
- Every claim has ≥1 valid `evidence_id`.
- Every financial number has an Odoo `evidence_id`.
- Every cited source is within the user's RBAC scope.
- Every detected conflict appears in the Conflicts section.
- Every missing required field appears in Missing Data.
- The Sources section lists every cited source.

### 7.2 UI Behaviour per Verdict

**`passed`:**
- Processing View: brief success flash on "Quality gate" row.
- Transitions automatically to composition and staging.
- No special indicator on Report View.

**`needs_review` (C-5):**
- Processing View: orange non-dismissable banner "Report flagged for mandatory review."
- Report View — requester: quality gate flags list only. No report content. Watermark not shown (no content to watermark).
- Report View — reviewer (`can_approve = True`): full draft report rendered with `DRAFT — AWAITING REVIEW` watermark on every section header. Quality gate flags list pinned above content. Non-dismissable.
- Report View — admin: quality gate flags and metadata only. No content visible.
- Export Panel: not rendered. No downloads available.
- Audit event: `quality_gate.needs_review`.

**`failed`:**
- Processing View: red non-dismissable banner "Evidence insufficient — report cannot be generated." All remaining processing steps are shown as greyed/cancelled. "New query" button appears.
- Report View does not exist for `failed` state — there is no report to view. The request entry in My Reports shows status `failed` with no content link.
- Export Panel: not rendered. API blocks all download requests with HTTP 403.
- Audit event: `quality_gate.failed`.

### 7.3 Quality Gate Flag Display

Flags are shown verbatim from `quality-gate-result.json`. They are human-readable strings only — no internal IDs or system paths are exposed.

Example rendered flags:
```
⚠ A claim in the Financial Position section has no Odoo source reference.
⚠ The Missing Data section is non-empty — some requested values were not found.
⚠ A conflict was detected between SharePoint and Odoo values and requires review.
```

---

## 8. Security Rules

### 8.1 Authentication

- Every route requires a valid Entra ID JWT in the `Authorization: Bearer` header.
- JWT is validated on every API request: signature (RS256 against Entra JWKS), audience, issuer, expiry.
- Expired token: immediate redirect to Entra login, preserving `redirect_uri` for post-login return.
- No guest access. No API key bypass in production (`APP_ENV = "production"`).
- Bypass mode (when `ENTRA_CLIENT_ID` is not configured) is permitted only when `APP_ENV ≠ "production"` — for local dev and CI only.

### 8.2 Authorization — Defence in Depth

| Layer | Mechanism |
|---|---|
| UI layer | Conditional rendering based on role from JWT claims. Provides UX only — not enforcement. |
| API gateway (node_01_auth) | `RbacDeniedError` → HTTP 403 before any retrieval begins. |
| Retrieval nodes (Phase 1D+) | RBAC scope re-validated per retrieval node using `DecisionState.allowed_projects`, `.allowed_mailboxes`, `.allowed_odoo_ids`. |
| MinIO final path | Write requires a valid approval record in PostgreSQL. No approval record = no final write. |
| Download API | State and role checked on every download request. `quality_gate = "failed"` → HTTP 403 unconditionally. |

### 8.3 Credential Handling (C-6)

Credentials are defined as: passwords, tokens, API keys, client secrets, connection string values, HMAC keys, certificate private keys.

**Never shown in any UI surface:**
- Credential values in any form — plaintext, base64, partially masked (`sk-...xxxx`), or hashed.
- Connection strings that embed credentials.
- Certificate contents.

**May be shown:**
- Hostname or URL that contains no embedded credentials.
- Key name and presence indicator: `ODOO_API_KEY ✓ set` or `ODOO_API_KEY ✗ missing`.
- Auth mechanism type: `Basic`, `Bearer`, `OAuth2`, `API key` — not the value.
- Entra tenant ID: first 4 characters only (for identification in audit; not as a security measure).
- Token expiry date/time (not the token itself).

### 8.4 Data Isolation Rules

| Data | Constraint |
|---|---|
| `user_id` | HMAC-SHA256 hash everywhere in every UI. Never plain text. |
| Evidence excerpts (email) | Read-only in Evidence Panel. No copy action. Never shown in admin screens. |
| Report content | Never visible to `admin` role. Blocked from rendering. |
| `evidence-pack.json` | RBAC-gated download (Section 4.2). Not available to `admin` via download API. |
| `audit-log.json` (per-req) | RBAC-gated download (Section 4.2). Admin reads via Audit Log UI only. |
| Financial data | Hidden section with explicit "not available for your role" statement for roles without `can_access_odoo_budget`. Not silently omitted. |
| Token counts and API costs | Visible to `admin` in Audit Log detail view only. Never in user workspace. |
| Source mapping field values | Site IDs, drive IDs, and paths visible in admin Source Mapping editor. No credentials embedded in these fields. |

### 8.5 Admin Scope Isolation

The `admin` role is a configuration role, not a business-data role. (Spec Section 8.2: "Admin role MUST NOT automatically grant business-data visibility.")

Admin is forbidden from:
- Viewing report content, query text, or evidence excerpts in any screen.
- Downloading `evidence-pack.json` via the download API.
- Accessing the User Chat Workspace or Report View.

Admin is permitted to:
- Read system event metadata in the Audit Log (timestamps, event types, request IDs, hashed user IDs, token counts, costs).
- Read quality gate flags and operational metadata in the Approval Queue.
- Perform admin override approvals (logged with distinct event type).
- Read and edit source mapping and role mapping configuration.
- View connector status and presence indicators.

### 8.6 Destructive Action Protocol

All destructive or approval actions follow this protocol without exception:

1. User clicks action button.
2. Confirmation modal opens. Modal shows: action type, target entity, acting user (hashed), proposed timestamp.
3. For irreversible actions (approve, reject, delete project): user must type a confirmation string (the project code, request ID, or "CONFIRM").
4. Audit event is written to PostgreSQL before the action executes.
5. Action executes.
6. UI updates. Toast notification confirms result.
7. If action fails: error toast. Audit event `action.failed` is written.

### 8.7 Immutability

| Artifact | Immutability rule |
|---|---|
| `final/` MinIO path | Objects are written once. No overwrite. No delete via API. |
| `approval-log.json` | Written once on approval. Cannot be modified or deleted via UI or API. |
| Audit log entries (PostgreSQL) | No DELETE or UPDATE permitted on audit rows. New rows only. |
| Quality gate result | Written once per request. Cannot be changed after writing. |

---

## 9. Acceptance Criteria

### 9.1 User Chat Workspace

| # | Criterion | Maps to |
|---|---|---|
| U-01 | A user with `executive` role sees only their `allowed_projects` in the Project dropdown. No other projects appear. | Section 2.1, 4.1 |
| U-02 | A user with an empty `allowed_projects` list sees "No authorized projects for your role" and cannot submit. | Section 2.1 |
| U-03 | `auditor` role lands on My Reports. Query Composer is not rendered and the route is inaccessible. | Sections 1.5, 2.6 |
| U-04 | `admin` role is redirected to Admin CP. User Chat Workspace routes return HTTP 403. | Sections 1.5, 8.5 |
| U-05 | Processing View shows all 18 user-facing labels in correct order. Internal node identifiers are never shown. | Section 2.2 |
| U-06 | `quality_gate = "failed"`: Export Panel is absent from DOM. API returns HTTP 403 for all download paths. Error banner is non-dismissable. | Sections 2.2, 7.2, 6.3 |
| U-07 | `quality_gate = "needs_review"`: Requester sees quality gate flags only — no report content. Reviewer sees full draft with watermark. Export Panel absent. | Sections 2.3, 7.2 (C-5) |
| U-08 | Export Panel is not rendered until report state is `approved` or `final`. | Sections 2.4, 6.2 |
| U-09 | Financial Position section is absent for roles without `can_access_odoo_budget`. Its absence is stated: "[Financial data is not available for your role]" — not silently hidden. | Sections 2.3, 4.1 |
| U-10 | Superscript citations link to the corresponding Evidence Panel entry. Clicking `¹` scrolls to or highlights entry `[1]`. | Section 2.3 |
| U-11 | Evidence Panel shows source type, confidence score, and truncated hash. Raw `evidence_id` values are never shown. | Section 2.3 |
| U-12 | Uploading a file exceeding 10 MB shows an inline per-file error before upload begins. Server also rejects oversized files. | Section 5.3 |
| U-13 | Uploading a CAD file shows: "CAD files are not supported in this release. Contact your administrator." — not a generic rejection. | Sections 5.2, 5.6 |
| U-14 | `staging` state report shows "Awaiting review" banner. Approve, Reject, and Request revision buttons are visible only to roles with `can_approve = True`. | Section 2.3 |
| U-15 | `final` state report shows a locked immutable indicator. Approve, Reject, Request revision buttons are absent. Report content is read-only. | Sections 2.3, 8.7 |
| U-16 | Cancelling during processing shows a confirmation modal. On confirm, the workflow is terminated. No orphan session remains. Audit event `report.cancelled` is written. | Section 2.2 |

### 9.2 Admin Visual Control Plane

| # | Criterion | Maps to |
|---|---|---|
| A-01 | Any non-`admin` JWT receives HTTP 403 on all `/admin/*` routes. Client-side redirect is also enforced. | Sections 1.5, 3, 8.3 |
| A-02 | Dashboard "Services" card reflects live `/healthz` status. Stale data is labelled with the time of last check. | Section 3.1 |
| A-03 | Connector detail panel shows `✓ set` or `✗ missing` for all `.env` keys. No credential value is shown, even partially masked. | Sections 3.2, 8.3 (C-6) |
| A-04 | `[Test connection]` sends a read-only probe. No system state changes. Result shown inline with pass/fail and latency. | Section 3.2 |
| A-05 | n8n workflow status shows `empty` when `"nodes": []` and `deployed` when the array is non-empty. | Section 3.2 |
| A-06 | Source Mapping save fails and shows per-field errors when the submitted JSON fails schema validation. | Section 3.4 |
| A-07 | Source Mapping save shows a diff of all field changes and requires explicit confirmation before writing. | Section 3.4 |
| A-08 | Removing an allowed role from a project requires the admin to type the project code in a confirmation modal. | Section 3.4 |
| A-09 | Approval Queue shows only `staging` and `needs_review` reports. `final`, `failed`, and `rejected` reports are excluded. | Section 3.5 |
| A-10 | Approve action is blocked when the acting admin's hash matches the requester's hash. | Section 3.5 |
| A-11 | Admin Approval Queue panel shows quality gate flags and metadata only. Report content, evidence excerpts, query text, and evidence-pack data are not rendered. | Sections 3.5, 8.5 (C-1) |
| A-12 | `user_id` never appears in plain text in any audit log view. HMAC-SHA256 hash always used. | Sections 3.6, 8.4 |
| A-13 | Token counts and cost are visible in Audit Log event detail only when the viewer's role is `admin`. | Sections 3.6, 8.4 |
| A-14 | Cost Monitor shows a yellow warning banner when daily spend ≥ 80% of `DAILY_COST_CAP_USD`. | Section 3.7 |
| A-15 | When `DAILY_COST_CAP_USD` is reached, new report submissions are blocked system-wide. A red banner appears in both Admin Health and User Workspace. | Section 3.7 |
| A-16 | An `ownCloud` degraded state simultaneously updates the Dashboard service grid, Connectors list, and System Health screen. All three reflect the same status. | Sections 3.1, 3.2, 3.7 |
| A-17 | Entra group mapping edits require a confirmation modal and write `admin.role_mapping_changed` to the audit log before the save executes. | Sections 3.3, 8.6 |

---

## 10. Implementation Phase Recommendation

This section maps UI screens to backend phases. No frontend code should be written before the backend phase that provides the required data is complete.

| UI Screen | Depends on backend phase | Reason |
|---|---|---|
| Query Composer (RBAC-filtered) | Phase 1B ✓ complete | `allowed_projects` from `node_01_auth` |
| Processing View (live status) | Phase 1E | LangGraph stream events required for per-node updates |
| Report View (full content) | Phase 1E | Real structured JSON report from node_12 required |
| Evidence Panel | Phase 1D | Real evidence objects with `evidence_id` required |
| Export Panel (report formats) | Phase 1E | Real report content required for meaningful exports |
| Export Panel (evidence-pack.json) | Phase 1D | Real evidence pack required |
| Export Panel (audit-log.json) | Phase 1F | Real audit log written to MinIO required |
| My Reports List | Phase 1F | MinIO staging persistence required |
| Upload Zone | Phase 1D | Evidence pipeline must handle uploaded context |
| Admin Dashboard | Phase 1F | Real request counts and staging files required |
| Connectors & APIs | Phase 1C | n8n workflows must exist to show deployed status |
| Permissions & Roles (view) | Phase 1B ✓ complete | RBAC matrix and role data available |
| Permissions & Roles (Entra edit) | Phase 1B ✓ complete | Entra validation available |
| Source Mapping editor | Phase 1B ✓ complete | Mapping file exists and is loaded |
| Approval Queue | Phase 1G | Approval/reject API endpoints required |
| Audit Log | Phase 1F | PostgreSQL audit log rows required |
| System Health | Phase 1A ✓ complete | `/healthz` endpoint exists |
| Cost Monitor | Phase 1F | Per-request cost accumulator and Langfuse tracing required |

### Recommended frontend start point

**Earliest viable frontend build: after Phase 1F is complete.**

At that point, all backend data — RBAC-filtered projects, real reports, real evidence packs, MinIO persistence, audit log, and cost data — is available. Building the frontend earlier produces screens that require stubs and must be rewritten.

**Exception:** The Admin System Health screen (depends only on Phase 1A), the Permissions & Roles view tab, the Source Mapping read-only view, and the Query Composer shell (without RBAC-filtered project data from a running server) can be scaffolded earlier as static screens. Do not wire these to the API until the corresponding backend phase is complete.

---

## Appendix A: Out of Scope

These are explicitly forbidden from both interfaces, per the locked spec (Sections 2.1, 2.2, 8.3):

- Any write action to SharePoint, ownCloud, email, or Odoo.
- Email compose or reply.
- ERP approval creation.
- Document editing or version creation.
- AI-generated financial number input.
- CAD file viewer.
- Report template editor.
- User profile management (delegated to Entra).
- Phase 2 execution features (Action Gateway, automated actions).
- Mobile-native layout. Minimum supported width: 768px.
- Real-time collaboration or multi-user report editing.
- Notification email delivery (Phase 2).
- Any Admin screen that exposes report content, evidence, or query text.
