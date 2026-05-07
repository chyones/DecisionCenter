# DecisionCenter — Connector Connection Guide

> **Scope:** All external services and internal infrastructure components DecisionCenter connects to.
> **Authority:** `apps/edr/config.py`, `.env.example`, `docker-compose.yml`, `docs/contracts/`
> **Audited at commit:** `3d77d534` (Phase 1C complete)
> **Do not add real credentials, tenant IDs, client secrets, or passwords to this file.**

---

## Contents

1. [Connection Maturity Levels](#1-connection-maturity-levels)
2. [Phase Boundary Table](#2-phase-boundary-table)
3. [Security Rules](#3-security-rules)
4. [Owner Checklist](#4-owner-checklist)
5. [Connectors](#5-connectors)
   - [5.1 Microsoft Entra ID](#51-microsoft-entra-id)
   - [5.2 Microsoft Graph / SharePoint](#52-microsoft-graph--sharepoint)
   - [5.3 Microsoft Graph / Email](#53-microsoft-graph--email)
   - [5.4 ownCloud / WebDAV](#54-owncloud--webdav)
   - [5.5 Odoo / JSON-RPC](#55-odoo--json-rpc)
   - [5.6 n8n](#56-n8n)
   - [5.7 Qdrant](#57-qdrant)
   - [5.8 Redis](#58-redis)
   - [5.9 Voyage Embeddings](#59-voyage-embeddings)
   - [5.10 Cohere Rerank](#510-cohere-rerank)
   - [5.11 Anthropic LLM](#511-anthropic-llm)
   - [5.12 MinIO](#512-minio)
   - [5.13 PostgreSQL](#513-postgresql)
   - [5.14 Langfuse](#514-langfuse)
   - [5.15 Caddy / TLS](#515-caddy--tls)
6. [Go/No-Go Checklist Before Production](#6-gonogo-checklist-before-production)

---

## 1. Connection Maturity Levels

Every connector has a maturity level that tracks how far along the connection process is.
These levels apply per environment (local, staging, production).

| Level | Name | What it means |
|---|---|---|
| **L0** | Documented | Key names exist in `.env.example` and `config.py`; no active call yet. |
| **L1** | Configured | `.env` has real values; service is reachable but the code path is not yet wired. |
| **L2** | Test-connected | A test or smoke probe successfully calls the service and validates the response shape. |
| **L3** | One-project validated | At least one real project's data retrieved end-to-end; RBAC gate confirmed active. |
| **L4** | Production-ready | Full RBAC enforcement, audit logging, error handling, and business-owner sign-off. |

Move a connector to the next level only when the current level's test condition passes.
Do not wire production credentials before the phase that activates the connector (see §2).

---

## 2. Phase Boundary Table

Connect each service only in the phase shown. Earlier wiring risks exposing credentials before
the receiving code enforces RBAC and audit logging.

| Service | Earliest config phase | Earliest active-call phase | Notes |
|---|---|---|---|
| **PostgreSQL** | 1A (health ping) | 1F (schema + writes) | Health ping only in 1A–1E. |
| **Redis** | 1A (health ping) | 1D (cache wiring) | No writes before 1D. |
| **Qdrant** | 1A (health ping + init) | 1D (vector insert) | `scripts/init_qdrant.py` runs at 1A; actual inserts in 1D. |
| **MinIO** | 1A (health ping) | 1F (staging writes) | Bucket `decision-center` must be created before 1F (blocker B10). |
| **n8n** | 1A (infra up) | 1C (workflow import + activation) | Workflows imported and activated during Phase 1C only. |
| **Microsoft Entra ID** | 1B (real JWT validation) | 1B | Bypass mode allowed in local/CI only. Entra required in production. |
| **SharePoint (MS Graph)** | 1C | 1C | n8n workflow calls Graph API; needs service account app registration. |
| **Email (MS Graph)** | 1C | 1C | Same app registration as SharePoint; excerpt-only policy enforced in n8n. |
| **ownCloud / WebDAV** | 1C | 1C | Basic-auth service account; read-only. |
| **Odoo / JSON-RPC** | 1C | 1C | API key user, read-only access only. Never write to Odoo. |
| **Voyage Embeddings** | 1D | 1D | API key required; `EmbeddingClient.embed()` raises `NotImplementedError` before 1D. |
| **Cohere Rerank** | 1D | 1D | API key required; `Reranker.rerank()` raises `NotImplementedError` before 1D. |
| **Anthropic LLM** | 1E | 1E | Required for Nodes 02–04, 11, 12. Daily cost cap configured from Phase 1A. |
| **Langfuse** | 1E | 1E | Optional (missing key → tracing disabled). Do not wire before LLM nodes exist. |
| **Caddy / TLS** | 1A | 1A | ACME email required from first deployment; HTTPS terminates external traffic. |

---

## 3. Security Rules

These rules apply to all connectors at all times:

1. **No secrets in Git.** `.env` is in `.gitignore`. Never put real tokens, passwords, API keys,
   tenant IDs, client secrets, or cookie values in any committed file.
2. **Least privilege.** Every service account must have the minimum permission set. Details per
   connector are in §5.
3. **Read-only where possible.** SharePoint, Email, ownCloud, and Odoo connectors must use
   read-only accounts. The system never writes to or modifies upstream source data.
4. **Test project first.** Before connecting a production source, validate the connector against
   a non-sensitive test project. Confirm RBAC gates are active before retrieving real data.
5. **Rotate credentials on suspected exposure.** Any key committed to Git, logged in plaintext,
   or shared outside `.env` must be rotated immediately.
6. **Entra in production.** The `ENTRA_CLIENT_ID` bypass mode is blocked at runtime when
   `APP_ENV=production`. Do not deploy to production without Entra configured.

---

## 4. Owner Checklist

These items must be provided by the IT/infrastructure owner before the system can be connected.
They are not available from code or configuration alone.

**Microsoft (Entra / Graph):**
- [ ] Azure AD tenant ID
- [ ] Registered app client ID (application permissions: `Files.Read.All`, `Mail.Read`)
- [ ] Client secret (or certificate) for the registered app
- [ ] SharePoint site ID and drive ID per project (from `docs/config/project_source_mapping.json`)
- [ ] Shared mailbox addresses per project (from `docs/config/project_source_mapping.json`)

**ownCloud:**
- [ ] ownCloud base URL
- [ ] Read-only service account username and password
- [ ] Root path per project in ownCloud

**Odoo:**
- [ ] Odoo base URL
- [ ] Database name
- [ ] Read-only API user email and API key
- [ ] Odoo project and cost model names per project

**Infrastructure (self-hosted):**
- [ ] Domain name pointing to the Hetzner server
- [ ] ACME contact email for Caddy TLS (currently `admin@elrace.com` in `Caddyfile` — update to a real address)
- [ ] Desired PostgreSQL and MinIO passwords (replace the `change-me` defaults)
- [ ] Desired MinIO access key (replace `decisioncenter` default if required)

**API keys (external services):**
- [ ] Anthropic API key
- [ ] Voyage API key
- [ ] Cohere API key
- [ ] Langfuse public key and secret key (optional but recommended)
- [ ] n8n webhook token (self-generated; used to authenticate calls from Python to n8n)

---

## 5. Connectors

---

### 5.1 Microsoft Entra ID

**Purpose:** Authenticates users. Every API request carries a Bearer JWT signed by Entra.
The JWT is validated against the tenant's JWKS endpoint. The `role` claim in the token maps
to DecisionCenter's 9 canonical roles.

**Related phase:** Phase 1B

**When configured:** Before the first external user request. Bypass mode (no Entra) is allowed
in local development and CI when `ENTRA_CLIENT_ID` is not set.

**When active:** All production API requests. Bypassed in local/CI when not configured.
Runtime enforces: if `APP_ENV=production` and `ENTRA_CLIENT_ID` is absent → HTTP 500.

**Who provides required info:** Microsoft 365 tenant administrator.

**Required `.env` values:**

```
ENTRA_CLIENT_ID=          # Azure AD app registration client ID
ENTRA_TENANT_ID=          # Azure AD tenant ID
ENTRA_CLIENT_SECRET=      # Client secret (not used in JWT validation path; may be needed for token exchange)
```

**Credential storage:** `.env` file on the server. Never commit.

**Access rule:** Read-only identity claim. Entra does not grant data access; RBAC logic
in `node_01_auth.py` maps the JWT role claim to allowed projects and mailboxes.

**JWKS endpoint (derived from tenant ID, no secret):**
`https://login.microsoftonline.com/{ENTRA_TENANT_ID}/discovery/v2.0/keys`

**Validation algorithm:** RS256. Audience must equal `ENTRA_CLIENT_ID`. Issuer must equal
`https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0`.

**Test readiness condition:** `POST /reports/staging` with a real Entra JWT returns 200;
admin role returns 403; unknown project returns 403.

**Production readiness condition:** JWT validation active (not bypassed), role claim maps to
all 9 canonical roles, all RBAC integration tests pass in CI.

**Common failure risks:**
- Wrong tenant ID → JWKS lookup fails → HTTP 401 on every request.
- App registration audience mismatch → `jwt.exceptions.InvalidAudienceError`.
- Client secret expired → relevant for token-exchange flows, not JWT validation.
- Role claim absent from JWT → bypass falls back to `X-User-Role` header, which is insecure
  in production. Ensure app roles are defined in the Entra app manifest and assigned to users.

---

### 5.2 Microsoft Graph / SharePoint

**Purpose:** Retrieves project documents (contracts, BOQ, invoices, RFIs, meeting minutes)
from SharePoint document libraries. Returns metadata and excerpts; never returns full file content
to the report. Evidence is normalized to `EvidenceObject` schema.

**Related phase:** Phase 1C (n8n workflow activated); Phase 1D (Python node wired to n8n)

**When configured:** Phase 1C. The n8n `sharepoint_search` workflow must be imported and
activated before any SharePoint evidence can be retrieved.

**When active:** Phase 1D, when `node_05_sharepoint.py` calls `connectors/sharepoint.py`.

**Who provides required info:** Microsoft 365 admin (app registration); project coordinator
(site_id and drive_id per project in `project_source_mapping.json`).

**Required values in n8n credential (Microsoft Graph OAuth2):**
- Tenant ID
- Client ID
- Client Secret
- Scope: `https://graph.microsoft.com/.default`
- Application permission: `Files.Read.All` (or `Sites.Read.All`)

**Required values in `project_source_mapping.json` per project:**
```json
"sharepoint": {
  "site_id": "<site-id from Graph>",
  "drive_id": "<drive-id from Graph>",
  "root_path": "/Projects/PRJ-XXX"
}
```

**n8n workflow file:** `n8n/sharepoint_search.json`

**n8n Graph API call:**
`GET https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root/search(q='{query}')`

**Credential storage:** n8n credential store (encrypted, not in `.env` or Git).

**Access rule:** Read-only. Application permission `Files.Read.All` scoped to the registered app.
The n8n code node filters by `project_code`. No SharePoint write operations are permitted.

**Test readiness condition:** `curl` the n8n webhook path with a sample payload and verify
at least one `EvidenceObject` returned. Run `pytest apps/edr/tests/integration/test_connectors.py`
(mocked; passes without live n8n).

**Production readiness condition:** Live n8n webhook returns real SharePoint results; RBAC
gate in `node_01_auth.py` restricts `site_id`/`drive_id` to allowed projects; evidence validates
against `docs/schemas/evidence-object.schema.json`.

**Common failure risks:**
- `site_id` or `drive_id` wrong → Graph returns 404.
- App permission not admin-consented → 403 from Graph.
- Token expired or not refreshed by n8n → 401 mid-workflow.
- Search query URL-encoding issue → empty results without error.
- `hash_sha256` absent from Graph response → normalization code must derive or set `"unknown"`.

---

### 5.3 Microsoft Graph / Email

**Purpose:** Retrieves email evidence from the requesting user's mailbox and authorized project
shared mailboxes. Returns **excerpt only** (≤ 500 characters). Full email bodies are never stored
or included in reports. See `docs/policies/email_retrieval_policy.md`.

**Related phase:** Phase 1C (n8n workflow); Phase 1D (Python node)

**When configured:** Phase 1C. Same app registration as SharePoint. Shared mailbox addresses
per project must be in `project_source_mapping.json`.

**When active:** Phase 1D, when `node_07_email.py` calls `connectors/email.py`.

**Who provides required info:** Microsoft 365 admin (permission grant); project coordinator
(shared mailbox addresses per project).

**Required app permissions:**
- `Mail.Read` — read user mailboxes
- `Mail.Read.Shared` — read shared mailboxes

**Required values in `project_source_mapping.json` per project:**
```json
"email": {
  "shared_mailboxes": ["project-prj-001@example.com"],
  "document_control_mailbox": "doc-control@example.com"
}
```

**n8n workflow file:** `n8n/email_search.json`

**n8n Graph API call:**
`GET https://graph.microsoft.com/v1.0/users/{user_mailbox}/messages?$search="{query}"&$top=25`

**Credential storage:** n8n credential store. Same OAuth2 credential as SharePoint.

**Access rule:** Read-only. The code node enforces excerpt-only output (≤ 500 chars). Full
message bodies are discarded in the normalization step.

**Test readiness condition:** Mocked connector test `test_email_connector_excerpt_truncated_to_500`
passes. Live test: curl the email webhook and confirm `excerpt` field is ≤ 500 characters.

**Production readiness condition:** RBAC gate confirms only mailboxes mapped to the requesting
user's project are searched. Excerpt limit verified. `hash_sha256` present on all items.

**Common failure risks:**
- Shared mailbox not delegated to the app → 403.
- Mailbox address not in `project_source_mapping.json` → RBAC gate blocks the search.
- `$search` OData query not supported on some mailbox types → empty results.
- Excerpt truncation not applied → full body in evidence pack violates data minimization policy.

---

### 5.4 ownCloud / WebDAV

**Purpose:** Lists and retrieves project documents from ownCloud, a secondary document source.
Follows the same RBAC, evidence normalization, and excerpt rules as SharePoint.
See `docs/contracts/owncloud_webdav_contract.md`.

**Related phase:** Phase 1C (n8n workflow); Phase 1D (Python node)

**When configured:** Phase 1C.

**When active:** Phase 1D, when `node_06_owncloud.py` calls `connectors/owncloud.py`.

**Who provides required info:** IT admin (ownCloud base URL, service account credentials);
project coordinator (root path per project).

**Required `.env` values:** None at the Python level (credentials passed in webhook payload
by the calling node; stored as n8n credential).

**Required values in n8n credential (HTTP Basic Auth):**
- Username: read-only service account
- Password: service account password

**n8n workflow file:** `n8n/owncloud_list.json`

**n8n WebDAV call:**
`PROPFIND {base_url}/remote.php/dav/files/{username}/{root_path}`
Header: `Depth: 1`

**Credential storage:** n8n credential store for the service account. `base_url`, `username`,
and `root_path` come from the Python node payload (sourced from `project_source_mapping.json`).

**Access rule:** Read-only. The service account must have read access to project folders only.
ownCloud evidence must not override SharePoint for the same document unless it is the later
approved source (see `docs/policies/evidence_priority_policy.md`).

**Test readiness condition:** Mocked connector test `test_owncloud_connector_valid_evidence` passes.
Live test: curl the ownCloud webhook with a test project path.

**Production readiness condition:** Service account scoped to project directories. Evidence
normalized with `revision` field when available. RBAC gate active.

**Common failure risks:**
- `PROPFIND` method not allowed by ownCloud firewall rules → 403 or 405.
- Basic auth credential not stored in n8n → n8n falls back to no-auth → 401.
- WebDAV response XML not parseable by code node → empty `evidence` array.
- Path URL-encoding for special characters (spaces, Arabic text) → 404.

---

### 5.5 Odoo / JSON-RPC

**Purpose:** Reads financial and operational records from Odoo. Odoo is the **sole source of
truth** for financial figures. The system never infers financial values from documents or email.
See `docs/contracts/odoo_api_contract.md` and `docs/policies/odoo_financial_truth_policy.md`.

**Related phase:** Phase 1C (n8n workflow); Phase 1D (Python node)

**When configured:** Phase 1C.

**When active:** Phase 1D, when `node_08_odoo.py` calls `connectors/odoo.py`.

**Who provides required info:** Odoo admin (read-only API user credentials, database name, URL).

**Required `.env` values:**
```
ODOO_URL=                  # Base URL of the Odoo instance (e.g. https://erp.example.com)
ODOO_DATABASE=             # Odoo database name
ODOO_USERNAME=             # Read-only API user email
ODOO_API_KEY=              # Odoo API key for that user
```

**n8n workflow file:** `n8n/odoo_read.json`

**n8n JSON-RPC call:**
`POST {odoo_url}/jsonrpc`
Method: `execute_kw`, model and domain from the Python payload.

**Credential storage:** `.env` on server for direct Python access. n8n credential store for
workflow-level auth. Never in Git.

**Access rule:** Strict read-only. The Odoo API user must have no write, create, delete, or
workflow-trigger permissions. Every evidence object must include `model`, `record_id`,
`timestamp`, and a source hash. Missing financial values must be returned as `"Not available"` —
the system must never infer or estimate them.

**Test readiness condition:** Mocked connector test `test_odoo_connector_returns_required_fields`
passes. Live test: curl the Odoo webhook and verify `metadata.model` and `metadata.record_id`
are present.

**Production readiness condition:** API user confirmed read-only in Odoo. RBAC gate restricts
Odoo records to the requesting user's allowed projects (`allowed_odoo_ids`). Financial section
absent from reports when user lacks finance permission.

**Common failure risks:**
- Odoo API key deactivated → 401 from `/jsonrpc`.
- Domain filter syntax error → Odoo returns 200 with an error payload (not HTTP 4xx).
- Financial figure absent from record → must surface as `"Not available"`, not omitted silently.
- Multiple Odoo databases → wrong `ODOO_DATABASE` value causes silent auth failure.

---

### 5.6 n8n

**Purpose:** Connector orchestrator. Each of the four source connectors (SharePoint, Email,
ownCloud, Odoo) is implemented as an n8n workflow. Python calls n8n webhooks; n8n calls the
upstream APIs and normalizes the response.

**Related phase:** Phase 1A (infra up, health reachable); Phase 1C (workflows imported and
activated)

**When configured:** Phase 1A (`docker-compose.yml` brings up n8n). Webhook token set in
Phase 1C before Python calls the webhooks.

**When active:** Phase 1C. Workflows must be manually imported (JSON → n8n UI → Activate).

**Who provides required info:** DevOps (self-generated webhook token); IT admin (upstream
credentials stored in n8n credential store).

**Required `.env` values:**
```
N8N_BASE_URL=http://n8n:5678           # Internal Docker network URL (do not expose externally)
N8N_WEBHOOK_TOKEN=                     # Self-generated secret; passed as Bearer token from Python
SHAREPOINT_SEARCH_WEBHOOK=/webhook/sharepoint-search
OWNCLOUD_LIST_WEBHOOK=/webhook/owncloud-list
EMAIL_SEARCH_WEBHOOK=/webhook/email-search
ODOO_READ_WEBHOOK=/webhook/odoo-read
```

**n8n version:** `n8nio/n8n:1.91.3` (pinned in `docker-compose.yml`)

**Workflow import:** Manual via n8n UI. See `n8n/README.md` for step-by-step instructions.
Docker Compose mounts `./n8n:/workflows:ro` for reference only — n8n does not auto-import.

**Credential storage:** n8n's internal encrypted credential store (stored in the `n8n-data`
Docker volume). The webhook token is in `.env`.

**Access rule:** n8n is internal only (not exposed through Caddy). Python backend calls n8n
on the internal Docker network (`http://n8n:5678`). n8n calls external APIs (Graph, ownCloud,
Odoo) with stored credentials.

**Test readiness condition:** `curl -X POST http://localhost:5678/webhook/sharepoint-search -H
"Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"query":"test",
"site_id":"x","drive_id":"y","project_code":"PRJ-001"}'` returns `{"evidence":[...]}`.

**Production readiness condition:** All four workflows active and verified against a test
project. Webhook token set and confirmed in `.env`. n8n UI password changed from default.

**Common failure risks:**
- Workflow not activated → n8n returns 404 on the webhook path.
- Webhook token mismatch → HTTP 401 from n8n.
- n8n credential not configured for an upstream service → workflow runs but HTTP Request node
  fails with 401/403 (workflow may still return 200 with an empty or error payload).
- n8n restart without persistent volume → credential store wiped; requires re-configuration.
- n8n UI exposed on port 5678 without authentication → unauthorized access to all credentials.
  Bind port to localhost only (`127.0.0.1:5678:5678`) in production or remove the port mapping.

---

### 5.7 Qdrant

**Purpose:** Vector store for evidence embeddings. One collection per `project_code`.
Used in Phase 1D for embedding storage and semantic retrieval.

**Related phase:** Phase 1A (health ping + collection init); Phase 1D (actual inserts and search)

**When configured:** Phase 1A. `scripts/init_qdrant.py` creates collections idempotently.

**When active:** Phase 1D, when the retrieval pipeline inserts and queries vectors.

**Who provides required info:** DevOps (no external account needed; self-hosted).

**Required `.env` values:**
```
QDRANT_URL=http://qdrant:6333          # Internal Docker network URL
```

**Qdrant version:** `qdrant/qdrant:v1.12.4` (pinned in `docker-compose.yml`)

**Collection schema:** One collection per `project_code`; vectors are 1024-dimensional (Voyage-3-large).

**Credential storage:** No auth by default in the Docker Compose setup. For production, enable
Qdrant API key auth and add `QDRANT_API_KEY` to `.env` and `config.py`.

**Access rule:** Internal only (not exposed externally by default). Port 6333 is exposed on the
host in `docker-compose.yml` — remove or restrict this port mapping in production.

**Test readiness condition:** `GET http://qdrant:6333/healthz` returns `{"status":"ok"}`.
`scripts/init_qdrant.py` runs twice without error (idempotency check).

**Production readiness condition:** Qdrant API key set. Collections initialized for all active
projects. Port 6333 not accessible externally. Qdrant data volume backed up.

**Common failure risks:**
- Collection not initialized → insert fails with `collection not found`.
- Vector dimension mismatch → insert fails when embedding model changed.
- Qdrant data volume not persisted → all vectors lost on container restart.
- Port 6333 exposed to internet → unauthenticated access to all project vectors.

---

### 5.8 Redis

**Purpose:** RBAC-aware cache for retrieval results. Cache key must include `user_id` and
`project_code` so cached results from one user are never served to another.

**Related phase:** Phase 1A (health ping); Phase 1D (cache wiring)

**When configured:** Phase 1A (Docker Compose).

**When active:** Phase 1D, when `MemoryCache` is replaced with a real Redis-backed cache.
Current `MemoryCache` in `apps/edr/retrieval/` is an in-process dict — not persistent and
not multi-user safe.

**Who provides required info:** DevOps (no external account).

**Required `.env` values:**
```
REDIS_URL=redis://redis:6379/0
```

**Redis version:** `redis:7-alpine` (pinned in `docker-compose.yml`), AOF persistence enabled.

**Credential storage:** No password set in the default Docker Compose configuration.
For production, add `requirepass` to the Redis command and update `REDIS_URL` accordingly.

**Access rule:** Internal only. Not exposed externally.

**Test readiness condition:** `GET /healthz` returns `"redis": "ok"`.

**Production readiness condition:** Redis password set. `MemoryCache` replaced with Redis-backed
implementation. Cache key format `{user_id}:{project_code}:{query_hash}` confirmed in tests.

**Common failure risks:**
- `MemoryCache` still in use → cache not shared across workers; memory leak under load.
- Redis without password → any container on the network can read or flush the cache.
- Cache key does not include `user_id` or `project_code` → cross-user cache contamination.

---

### 5.9 Voyage Embeddings

**Purpose:** Generates 1024-dimensional text embeddings using Voyage-3-large. Embeddings are
stored in Qdrant per project collection and used for semantic similarity search in Phase 1D.

**Related phase:** Phase 1D

**When configured:** Phase 1D. `VOYAGE_API_KEY` must be set before `EmbeddingClient.embed()`
is wired (currently raises `NotImplementedError`).

**When active:** Phase 1D, when the embedding client is wired to the Voyage API.

**Who provides required info:** Voyage AI account holder (API key). See `docs/operations/cost_model.md` — estimated USD 5/month.

**Required `.env` values:**
```
VOYAGE_API_KEY=            # Voyage AI API key
```

**Credential storage:** `.env` on server. Never in Git.

**Access rule:** Read-only (embedding generation only). No data is stored by Voyage beyond
normal API logging.

**Test readiness condition:** `EmbeddingClient.embed(["test"])` returns a list of one vector
with length 1024.

**Production readiness condition:** Vector dimension confirmed as 1024. Round-trip test: embed
a document chunk, insert into Qdrant, retrieve by similarity. Cost accumulator logs token count.

**Common failure risks:**
- API key invalid or rate-limited → `NotImplementedError` replaced by HTTP 401/429.
- Dimension mismatch with existing Qdrant collection → insert fails.
- Very long input text → Voyage truncates or rejects; chunk size must stay within model limits.

---

### 5.10 Cohere Rerank

**Purpose:** Reranks up to 50 retrieval candidates to return the top 10 most relevant evidence
objects using Cohere Rerank 3.5.

**Related phase:** Phase 1D

**When configured:** Phase 1D. `COHERE_API_KEY` must be set before `Reranker.rerank()` is
wired (currently raises `NotImplementedError`).

**When active:** Phase 1D, when the reranker is wired to the Cohere API.

**Who provides required info:** Cohere account holder (API key). See `docs/operations/cost_model.md` — estimated USD 10/month.

**Required `.env` values:**
```
COHERE_API_KEY=            # Cohere API key
```

**Credential storage:** `.env` on server. Never in Git.

**Access rule:** Read-only (reranking only). No data stored by Cohere beyond API logging.

**Input contract:** Maximum 50 candidates in; maximum 10 ranked results out.
Spec: `docs/workflows/EDR-AGENTIC-RAG-v2.1.md` Section 19.5.

**Test readiness condition:** `Reranker.rerank("test query", hits[:5])` returns a list of up to
5 `SearchHit` items sorted by relevance score.

**Production readiness condition:** Reranker integrated into Node 10 (or the retrieval pipeline
for Phase 1D). Cost accumulator includes Cohere calls.

**Common failure risks:**
- More than 50 candidates passed → Cohere returns an error; pre-filter required.
- API key rate-limited → reranker silently falls back or raises an exception.
- Reranker not called → retrieval uses RRF hybrid search only (lower quality).

---

### 5.11 Anthropic LLM

**Purpose:** Heavy LLM for report generation (Claude Sonnet 4.6 in Nodes 12, 13, 14) and light
LLM for classification and planning (Claude Haiku 4.5 in Nodes 02, 03, 04, 11).

**Related phase:** Phase 1E

**When configured:** Phase 1E. `ANTHROPIC_API_KEY` must be set before any LLM node is wired.

**When active:** Phase 1E, when Nodes 02–04, 11, 12, 13, 14 make real LLM calls.

**Who provides required info:** Anthropic account holder (API key). See `docs/operations/cost_model.md` — estimated USD 220/month (majority of monthly cost).

**Required `.env` values:**
```
ANTHROPIC_API_KEY=         # Anthropic API key
```

**Credential storage:** `.env` on server. Never in Git.

**Access rule:** Read-only from the API perspective. No data stored by Anthropic beyond normal
API logging. Prompt injection policy applies: `docs/policies/prompt_injection_policy.md`.

**Daily cost cap:** Controlled by `DAILY_COST_CAP_USD` (default: 12). When exceeded, new report
requests must be blocked until reviewed (Phase 1H for the circuit breaker).

**Budget controls:**
```
DAILY_COST_CAP_USD=12
MONTHLY_COST_TARGET_USD=300
```

**Test readiness condition:** Node 12 output validates against
`docs/schemas/executive-decision-report.schema.json`. Node 13 rejects any claim with no `evidence_id`.

**Production readiness condition:** Langfuse tracing active on every LLM call with token counts.
Daily cost cap enforced. Prompt injection guard tested. Financial values without Odoo `evidence_id`
surface as `"Not available"`.

**Common failure risks:**
- API key invalid → HTTP 401 on first LLM call in Phase 1E.
- Daily cost cap not enforced → unexpected spend without circuit breaker.
- Prompt injection via malicious document content → guard required before Phase 1E go-live.
- LLM returns invalid JSON → Node 12 must validate against schema before proceeding.

---

### 5.12 MinIO

**Purpose:** Object storage for report output files. Phase 1F writes four files per request to
`/staging/{request_id}/` (report.md, evidence-pack.json, audit-log.json, quality-gate-result.json).
After human approval (Phase 1G), files are moved to `/final/{request_id}/` and made immutable.

**Related phase:** Phase 1A (health ping); Phase 1F (bucket init + writes)

**When configured:** Phase 1A (Docker Compose). Bucket `decision-center` must be initialized
before Phase 1F — this is **open blocker B10** (no bucket init script exists yet).

**When active:** Phase 1F, when `node_15_save_audit.py` writes staging files.

**Who provides required info:** DevOps (access key and password, replacing defaults).

**Required `.env` values:**
```
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=decisioncenter          # Replace default in production
MINIO_SECRET_KEY=change-me              # Replace default in production
MINIO_BUCKET=decision-center
```

**MinIO version:** `minio/minio:RELEASE.2025-04-22T22-12-26Z` (pinned)

**Console port:** 9001 (MinIO management UI). Restrict access in production.

**Credential storage:** `.env` on server. Replace `change-me` default before any production use.

**Access rule:** The application user has read/write access to the `decision-center` bucket only.
Final report objects must be set immutable after approval (Phase 1G).

**Open blocker (B10):** No bucket initialization script or startup hook exists. The first Phase 1F
write will fail with `S3Error: NoSuchBucket`. Before Phase 1F: create `scripts/init_minio.py`
that creates the bucket idempotently, or add bucket creation to the FastAPI startup event.

**Test readiness condition:** `GET /healthz` returns `"minio": "ok"`. Bucket creation script
runs twice without error.

**Production readiness condition:** `change-me` default replaced. Bucket initialized. MinIO
console port not publicly accessible. Volume backed up.

**Common failure risks:**
- Default `MINIO_SECRET_KEY=change-me` in production → credential trivially guessable.
- Bucket not created (B10) → Phase 1F write fails immediately.
- MinIO volume not persisted → all staging and final files lost on container restart.
- Console port 9001 exposed → unauthenticated object browser access in older MinIO versions.

---

### 5.13 PostgreSQL

**Purpose:** Stores audit log rows per request (hashed `user_id`, all node events, token counts,
cost estimate). Required for the human review gate (approval records) in Phase 1G.

**Related phase:** Phase 1A (health ping); Phase 1F (schema + audit writes); Phase 1G (approval records)

**When configured:** Phase 1A (Docker Compose). Schema and migrations written in Phase 1F.

**When active:** Phase 1F, when `node_15_save_audit.py` writes `AuditLog` rows.

**Who provides required info:** DevOps (replacing the `change-me` default password).

**Required `.env` values:**
```
POSTGRES_DB=decision_center
POSTGRES_USER=decision_center
POSTGRES_PASSWORD=change-me            # Replace default in production
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

**PostgreSQL version:** `postgres:16-alpine` (pinned)

**Credential storage:** `.env` on server. Replace `change-me` before production.

**Access rule:** The application user (`POSTGRES_USER`) has read/write access to
`decision_center` database only. No superuser access from the application.

**Schema:** No migration tooling exists yet. `AuditLog` schema is defined in
`docs/schemas/audit-log.schema.json` and the Pydantic model in `apps/edr/schemas/audit.py`.
Schema creation and migration are Phase 1F work.

**Test readiness condition:** `GET /healthz` returns `"postgres": "ok"`.

**Production readiness condition:** Default password replaced. Schema migrations applied and
version-controlled. Application user is not a superuser. Volume backed up.

**Common failure risks:**
- Default `POSTGRES_PASSWORD=change-me` in production → trivially guessable.
- Schema not migrated before Phase 1F goes live → `AuditLog` write fails.
- Postgres volume not persisted → audit log lost on container restart.
- Missing index on `request_id` → slow approval status lookups in Phase 1G.

---

### 5.14 Langfuse

**Purpose:** LLM observability and tracing. Every LLM call in Nodes 02–04, 11, 12 must produce
a trace with node name, token counts, latency, and cost estimate. Required for cost tracking and
Phase 1H evaluation.

**Related phase:** Phase 1E

**When configured:** Phase 1E. Keys are optional — missing keys disable tracing without
causing errors. Configure before LLM nodes go live so traces are captured from the start.

**When active:** Phase 1E, when LLM nodes are wired.

**Who provides required info:** Langfuse account holder (free cloud tier sufficient for the
deployment scale; see `docs/operations/cost_model.md`).

**Required `.env` values:**
```
LANGFUSE_PUBLIC_KEY=       # Langfuse project public key
LANGFUSE_SECRET_KEY=       # Langfuse project secret key
LANGFUSE_HOST=https://cloud.langfuse.com
```

**Credential storage:** `.env` on server. Never in Git.

**Access rule:** Write-only from the application (traces sent to Langfuse). Langfuse dashboard
is accessed by admins only.

**Self-hosted option:** Langfuse can be self-hosted if cloud tracing is a data residency concern.
Change `LANGFUSE_HOST` to the self-hosted URL.

**Test readiness condition:** After a test LLM call, the Langfuse dashboard shows the trace
with node name, token counts, and latency.

**Production readiness condition:** Traces visible for all 18 nodes. Token cost per request
logged. Daily cost cap alert wired.

**Common failure risks:**
- Keys absent → tracing silently disabled; no cost data or debugging traces.
- `LANGFUSE_HOST` points to wrong instance → traces sent to wrong project.
- Token count not included in trace → cost tracking incomplete.

---

### 5.15 Caddy / TLS

**Purpose:** Reverse proxy and TLS termination. Terminates HTTPS from the internet on ports
80 and 443 and proxies to the FastAPI app on port 8000. Handles automatic TLS certificate
issuance via Let's Encrypt (ACME).

**Related phase:** Phase 1A

**When configured:** Phase 1A, before any external request is served.

**When active:** All phases. Must be configured before the first external access.

**Who provides required info:** DevOps (domain name pointing to the server; ACME contact email).

**Required values in `Caddyfile`:**
```
{
    email your-real-email@example.com    # ACME contact; replace admin@elrace.com placeholder
}

your.domain.com {
    reverse_proxy app:8000
}
```

**Current `Caddyfile` state:** HTTP-only (`:80`), no domain configured, ACME email is a
placeholder (`admin@elrace.com`). This must be updated before production.

**Caddy version:** `caddy:2-alpine` (pinned in `docker-compose.yml`)

**Credential storage:** ACME email is not a secret. TLS private key is managed by Caddy and
stored in the `caddy-data` Docker volume — back up this volume.

**Access rule:** External traffic enters only through Caddy (ports 80/443). The app port 8000,
n8n port 5678, MinIO port 9000/9001, and Qdrant port 6333 must not be exposed externally
in production.

**Test readiness condition:** `curl -I https://your.domain.com/healthz` returns HTTP 200 with
a valid TLS certificate.

**Production readiness condition:** Domain configured. Placeholder email replaced. Certificate
issued by Let's Encrypt. Internal ports not exposed. `caddy-data` volume backed up.

**Common failure risks:**
- Domain not pointing to the server → ACME challenge fails → no certificate issued.
- Port 80 blocked by firewall → ACME HTTP-01 challenge fails.
- `email` directive absent → Let's Encrypt rate-limit notifications not received.
- Internal service ports (5678, 6333, 9000, 9001) exposed in `docker-compose.yml`
  port mappings → direct unauthenticated access to n8n, Qdrant, MinIO from the internet.
  Remove or bind to `127.0.0.1` in production.

---

## 6. Go/No-Go Checklist Before Production

Complete all items before serving real users with real company data.

### Identity and Auth
- [ ] `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_SECRET` set and tested
- [ ] All 9 canonical roles map correctly from Entra group assignments to JWT role claims
- [ ] `APP_ENV=production` set — Entra bypass mode blocked
- [ ] RBAC integration tests pass in CI

### Connectors (n8n workflows)
- [ ] `N8N_WEBHOOK_TOKEN` set (non-empty, ≥ 32 random characters)
- [ ] All four n8n workflows imported and activated
- [ ] Each workflow tested with a real project payload and returns valid `EvidenceObject` items
- [ ] n8n credentials configured for SharePoint, Email, ownCloud, and Odoo
- [ ] n8n port 5678 not accessible from the internet

### Infrastructure (self-hosted)
- [ ] `POSTGRES_PASSWORD` and `MINIO_SECRET_KEY` changed from `change-me`
- [ ] PostgreSQL schema migrated (Phase 1F)
- [ ] MinIO bucket `decision-center` initialized (B10 resolved before Phase 1F)
- [ ] Redis password set
- [ ] Qdrant API key set; collections initialized for all active projects
- [ ] Qdrant port 6333 not accessible from the internet
- [ ] MinIO console port 9001 not accessible from the internet
- [ ] All Docker volumes backed up

### External API keys
- [ ] `ANTHROPIC_API_KEY` set and tested
- [ ] `VOYAGE_API_KEY` set and tested (Phase 1D)
- [ ] `COHERE_API_KEY` set and tested (Phase 1D)
- [ ] `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` set (Phase 1E)

### TLS and Networking
- [ ] Caddy `Caddyfile` updated: real domain, real ACME email
- [ ] HTTPS confirmed: `curl -I https://your.domain.com/healthz` → 200
- [ ] Only ports 80 and 443 exposed to the internet

### Observability and Cost Control
- [ ] `DAILY_COST_CAP_USD` and `MONTHLY_COST_TARGET_USD` reviewed and set
- [ ] Langfuse dashboard shows traces for at least one test request
- [ ] Cost cap circuit breaker implemented and tested (Phase 1H)

### Data and Compliance
- [ ] No `.env` or any file with real credentials in Git history
- [ ] `project_source_mapping.json` reviewed: correct site IDs, drive IDs, mailboxes per project
- [ ] Email excerpt-only policy confirmed in n8n code node (≤ 500 characters)
- [ ] Odoo API user confirmed read-only
- [ ] One test project end-to-end validated before any production project is connected
