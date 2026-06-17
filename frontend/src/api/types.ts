/**
 * API types — Phase 2A.
 *
 * Derived from backend Pydantic schemas in `apps/edr/app.py`.
 */

export type OutputFormat = 'md' | 'docx' | 'xlsx' | 'pdf' | 'pptx';

export interface ReportRequest {
  user_id: string;
  query: string;
  project_code?: string;
  contract_no?: string;
  vendor?: string;
  date_range?: string;
  document_type?: string;
  mailbox_scope?: string;
  output_formats: OutputFormat[];
  /** IDs returned by `POST /upload` for files attached to this request. */
  upload_ids?: string[];
}

export interface ReportResponse {
  request_id: string;
  status: string;
  quality_gate: string;
  visited_nodes: string[];
  exported_formats: string[];
  exports: Record<string, string>;
}

export interface ApproveRequest {
  comment?: string;
}

export interface RejectRequest {
  reason: string;
}

export interface RequestRevisionRequest {
  reason: string;
  comment?: string;
}

export interface ApiHealthResponse {
  status: string;
  workflow_nodes: number;
  postgres?: string;
  redis?: string;
  qdrant?: string;
  minio?: string;
}

/**
 * External report state names emitted by the backend. The five new endpoints
 * (GET /reports, GET /reports/{id}, GET /reports/{id}/status,
 * DELETE /reports/{id}) all use these strings.
 */
export type ReportState =
  | 'staging'
  | 'needs_review'
  | 'approved'
  | 'rejected'
  | 'revision_requested'
  | 'final'
  | 'cancelled'
  | 'failed';

export interface ReportSummary {
  request_id: string;
  project_code: string | null;
  project_name?: string | null;
  query_excerpt: string | null;
  state: ReportState;
  quality_gate: string | null;
  requires_approval: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ReportListResponse {
  reports: ReportSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewDecisionView {
  action: string;
  reason: string | null;
  comment: string | null;
  created_at: string | null;
}

export interface ReportDetail {
  request_id: string;
  project_code: string | null;
  query: string | null;
  state: ReportState;
  quality_gate: string | null;
  requires_approval: boolean;
  created_at: string | null;
  updated_at: string | null;
  exported_formats: OutputFormat[];
  review_decisions: ReviewDecisionView[];
}

export interface ReportStatusResponse {
  request_id: string;
  state: ReportState;
  quality_gate: string | null;
  total_nodes: number;
  current_node: number;
  is_terminal: boolean;
  updated_at: string | null;
  qg_failure_reason: string | null;
}

export interface CancelReportResponse {
  request_id: string;
  state: ReportState;
}

export interface UploadResponse {
  upload_id: string;
  filename: string;
  size: number;
  content_type: string;
  content_hash: string;
}

export interface WorkspaceProject {
  project_code: string;
  project_name: string;
  contract_numbers: string[];
}

export interface WorkspaceContextResponse {
  user_id: string;
  role: string;
  allowed_projects: WorkspaceProject[];
  can_generate_report: boolean;
  can_approve: boolean;
  can_access_odoo_budget: boolean;
}

export interface EvidencePanelEntry {
  evidence_id: string;
  citation_label: string;
  source_type: string;
  title: string;
  confidence: string;
  hash_sha256: string;
  hash_short: string;
  excerpt: string;
  source_uri: string;
  timestamp: string | null;
}

export interface ReportContentResponse {
  request_id: string;
  project_code: string | null;
  project_name?: string | null;
  query: string | null;
  state: ReportState;
  quality_gate: string | null;
  requires_approval: boolean;
  markdown: string | null;
  evidence: EvidencePanelEntry[];
  quality_gate_flags: string[];
  content_available: boolean;
  content_unavailable_reason: string | null;
  can_review: boolean;
  is_requester: boolean;
  immutable: boolean;
}

/**
 * Optional query parameters accepted by `GET /reports`. The backend ignores
 * unknown fields and validates `limit`/`offset` bounds (1..200 / 0..).
 */
export interface ListReportsParams {
  state?: ReportState;
  project_code?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}


// ---------------------------------------------------------------------------
// Phase 2B Slice 2 — Connectors & APIs (read + probe). Derived from
// `apps/edr/admin/services_catalog.py`.
// ---------------------------------------------------------------------------

export type ConnectorCategory = 'infrastructure' | 'workflow';
export type ConnectorAuthMechanism =
  | 'tcp'
  | 'http'
  | 'webhook_header_token'
  | 'oauth_bearer'
  | 'basic'
  | 'none';
export type ConnectorProbeStatus = 'pass' | 'fail';
export type ConnectorLastProbeStatus = ConnectorProbeStatus | 'unknown';
export type ConnectorEventType =
  | 'connector.probe_success'
  | 'connector.error'
  | 'connector.latency_spike';
export type WorkflowStatus = 'empty' | 'deployed';

export interface EnvKeyStatus {
  name: string;
  present: boolean;
}

export interface ConnectorEventView {
  ts: string;
  event_type: ConnectorEventType;
  latency_ms: number | null;
  status_code: number | null;
  detail: string;
}

export interface ServiceSummary {
  name: string;
  display_name: string;
  category: ConnectorCategory;
  auth_mechanism: ConnectorAuthMechanism;
  hostname: string | null;
  last_probe_status: ConnectorLastProbeStatus;
  last_probe_at: string | null;
  last_latency_ms: number | null;
  workflow_status: WorkflowStatus | null;
}

export interface ServiceDetail extends ServiceSummary {
  description: string;
  env_keys: EnvKeyStatus[];
  workflow_node_count: number | null;
  recent_events: ConnectorEventView[];
}

export interface ProbeResult {
  service: string;
  status: ConnectorProbeStatus;
  latency_ms: number;
  status_code: number | null;
  detail: string;
  probed_at: string;
}

// ---------------------------------------------------------------------------
// Phase 2B Slice 3 — System Health + cost monitor.
// ---------------------------------------------------------------------------

export interface HealthServiceStatus {
  name: string;
  display_name: string;
  status: 'ok' | 'error' | 'unknown';
  latency_ms: number;
  sla_ms: number;
  sparkline_24h: number[];
}

export interface HealthLiveResponse {
  services: HealthServiceStatus[];
  checked_at: string;
}

export interface LlmBreakdownItem {
  model: string;
  calls: number;
  cost_usd: number;
}

export interface CostResponse {
  daily_cost: number;
  daily_cap: number;
  daily_percent: number;
  monthly_cost: number;
  monthly_cap: number;
  monthly_percent: number;
  llm_breakdown: LlmBreakdownItem[];
  warning: boolean;
  exceeded: boolean;
}

// Phase 2B Slice 4 — Audit Log screen.
// ---------------------------------------------------------------------------

export interface AuditEventSummary {
  event_id: string;
  event_type: string;
  ts: string;
  user_id_hash: string | null;
  project_code: string | null;
  service: string | null;
  detail: string;
}

export type AuditEventDetail = AuditEventSummary;

export interface AuditEventListResponse {
  events: AuditEventSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListAuditEventsParams {
  date_from?: string;
  date_to?: string;
  event_type?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Phase 2B Slice 5 — Permissions & Roles (Entra Group Mapping)
// ---------------------------------------------------------------------------

export interface EntraGroupMapping {
  entra_group_id: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export interface EntraGroupMappingUpsertRequest {
  role: string;
}

export interface EntraGroupMappingListResponse {
  mappings: EntraGroupMapping[];
}

// ---------------------------------------------------------------------------
// Phase 2B Slice 6 — Project Source Mapping
// ---------------------------------------------------------------------------

export interface SourceMappingSharePoint {
  site_id: string;
  drive_id: string;
  root_path: string;
}

export interface SourceMappingOwnCloud {
  base_path: string;
}

export interface SourceMappingEmail {
  shared_mailboxes: string[];
  document_control_mailbox: string;
  client_domains: string[];
  consultant_domains: string[];
  contractor_domains: string[];
}

export interface SourceMappingMicrosoftGroup {
  id: string;
  display_name: string;
  mail: string;
  mail_enabled: boolean;
}

export interface SourceMappingMicrosoftGroupMember {
  id: string;
  display_name: string;
  mail: string;
  user_principal_name: string;
  job_title: string;
  department: string;
  email: string;
}

export interface SourceMappingMicrosoft {
  group: SourceMappingMicrosoftGroup;
  group_members: SourceMappingMicrosoftGroupMember[];
  group_membership_status: string;
  member_count: number;
  missing_permissions: string[];
  blockers: string[];
}

export interface SourceMappingOdoo {
  project_model: string;
  cost_model: string;
  project_external_id: string;
  project_name: string;
  analytic_account_id: string;
}

export interface RelatedPeople {
  project_manager: string;
  commercial_manager: string;
  finance_owner: string;
  document_controller: string;
  other: string[];
}

export interface SourceMappingSummary {
  project_code: string;
  project_name: string;
  mapping_status: string;
  contract_numbers: string[];
}

export interface SourceMappingDetail {
  project_code: string;
  project_name: string;
  contract_numbers: string[];
  sharepoint: SourceMappingSharePoint;
  owncloud: SourceMappingOwnCloud;
  email: SourceMappingEmail;
  microsoft: SourceMappingMicrosoft;
  odoo: SourceMappingOdoo;
  related_people: RelatedPeople;
  enabled_sources: string[];
  allowed_roles: string[];
  mapping_status: string;
  last_validation_result: Record<string, unknown> | null;
  last_validated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  created_by_hash: string | null;
  updated_by_hash: string | null;
}

export interface SourceMappingListResponse {
  mappings: SourceMappingSummary[];
}

export interface SourceMappingUpsertRequest {
  project_name: string;
  contract_numbers: string[];
  sharepoint: SourceMappingSharePoint;
  owncloud: SourceMappingOwnCloud;
  email: SourceMappingEmail;
  microsoft: SourceMappingMicrosoft;
  odoo: SourceMappingOdoo;
  related_people: RelatedPeople;
  enabled_sources: string[];
  allowed_roles: string[];
}

export interface ValidationFieldError {
  field: string;
  message: string;
}

export interface SourceMappingValidateResponse {
  project_code: string;
  valid: boolean;
  status: string;
  errors: ValidationFieldError[];
}

// ---------------------------------------------------------------------------
// Phase 2B Slice 7 — Approval Queue
// ---------------------------------------------------------------------------

export interface ApprovalQueueItem {
  request_id: string;
  project_code: string | null;
  review_state: string;
  quality_gate_status: string | null;
  submitted_at: string;
  requester_hash: string | null;
  cost_total_usd: number;
}

export interface ApprovalQueueResponse {
  items: ApprovalQueueItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApprovalQueueDetail {
  request_id: string;
  project_code: string | null;
  review_state: string;
  quality_gate_status: string | null;
  submitted_at: string;
  requester_hash: string | null;
  cost_total_usd: number;
  token_counts: Record<string, number> | null;
  requires_approval: boolean;
  quality_gate_flags: string[];
}

export interface AdminOverrideRequest {
  comment: string;
}

export interface AdminOverrideResponse {
  request_id: string;
  action: string;
  new_state: string;
}

// Phase 2B Slice 8 — Dashboard
export interface DashboardServiceStatus {
  name: string;
  display_name: string;
  status: string;
}

export interface DashboardSummary {
  services_ok: number;
  services_total: number;
  approvals_pending: number;
  daily_cost: number;
  daily_cap: number;
  daily_percent: number;
  requests_today: number;
  failed_qg_today: number;
  monthly_cost: number;
  monthly_cap: number;
  monthly_percent: number;
  services: DashboardServiceStatus[];
  recent_events: AuditEventSummary[];
  checked_at: string;
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body: unknown = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}


// ---------------------------------------------------------------------------
// Connector Status Truth model — honest per-connector states.
// Backend: apps/edr/admin/connector_status.py · GET /admin/connectors/truth
// ---------------------------------------------------------------------------

export type ConnectorState =
  | 'NOT_CONFIGURED'
  | 'CONFIGURED_NOT_TESTED'
  | 'AUTH_FAILED'
  | 'PERMISSION_FAILED'
  | 'NETWORK_FAILED'
  | 'CONNECTED_NO_DATA'
  | 'VALIDATED'
  | 'PREVIOUSLY_VALIDATED_TOKEN_EXPIRED'
  | 'VERIFIED_FROM_EVIDENCE'
  | 'LIVE_OK'
  | 'MOCK_ONLY'
  | 'DISABLED'
  | 'UNKNOWN';

export type ConnectorGroup =
  | 'core_platform'
  | 'auth'
  | 'external_connector'
  | 'ai_provider'
  | 'edge';

export type ConnectorDataSource = 'live' | 'evidence' | 'mock' | 'fixture' | 'none';
export type Readiness = 'READY_FOR_UAT' | 'PARTIAL_READY' | 'NOT_READY';
export type ReportGeneration = 'READY' | 'DEGRADED' | 'BLOCKED';

export interface ConnectorTruth {
  name: string;
  display_name: string;
  group: ConnectorGroup;
  state: ConnectorState;
  summary: string;
  configured: boolean;
  missing_required_config: string[];
  secret_present: boolean;
  auth_ok: boolean | null;
  network_ok: boolean | null;
  permission_ok: boolean | null;
  live_data_ok: boolean | null;
  data_source: ConnectorDataSource;
  last_probe_at: string | null;
  last_success_at: string | null;
  token_expires_at: string | null;
  last_error_safe: string | null;
  sample_count: number | null;
  evidence: string;
  required_for_go_live: boolean;
  blocks_go_live: boolean;
}

export interface ConnectorTruthReport {
  readiness: Readiness;
  readiness_reason: string;
  report_generation: ReportGeneration;
  report_generation_reason: string;
  generated_at: string;
  core_platform: ConnectorTruth[];
  auth: ConnectorTruth[];
  external_connectors: ConnectorTruth[];
  ai_providers: ConnectorTruth[];
  edge: ConnectorTruth[];
  blocking: string[];
}
// ---------------------------------------------------------------------------
// Microsoft Mapping Rescan
// ---------------------------------------------------------------------------

export type MicrosoftMappingStatus =
  | 'AUTO_MAPPED'
  | 'NEEDS_CONFIRMATION'
  | 'MISSING_SHAREPOINT'
  | 'MISSING_MAILBOX'
  | 'CONFLICT'
  | 'DISABLED';

export interface SiteCandidate {
  site_id: string;
  display_name: string;
  web_url: string;
  drive_id: string | null;
  drive_name: string | null;
  root_item_count: number | null;
  match_strength: 'strong' | 'medium' | 'weak' | 'existing';
  confidence: number;
}

export interface MailboxCandidate {
  address: string;
  accessible: boolean;
  http_status: number;
}

export interface ProjectRescanResult {
  project_code: string;
  project_name: string;
  existing_site_id: string;
  existing_drive_id: string;
  sharepoint_status: MicrosoftMappingStatus;
  mailbox_status: MicrosoftMappingStatus;
  site_candidates: SiteCandidate[];
  mailbox_candidates: MailboxCandidate[];
  reason: string;
  recommended_site_id: string | null;
  recommended_drive_id: string | null;
  recommended_mailboxes: string[];
}

export interface MicrosoftRescanResponse {
  scanned_at: string;
  token_roles: string[];
  has_sites_read_all: boolean;
  has_mail_read: boolean;
  total_sites_discovered: number;
  project_results: ProjectRescanResult[];
  summary: string;
}

export interface MicrosoftRescanRequest {
  project_codes: string[];
}

export interface MicrosoftMappingConfirmRequest {
  site_id: string;
  drive_id: string;
  root_path?: string;
  mailboxes?: string[];
  document_control_mailbox?: string;
}

// ---------------------------------------------------------------------------
// Odoo + SharePoint Exact-Name Sync
// Backend: apps/edr/admin/odoo_sharepoint_sync.py
// POST /admin/source-mappings/sync-odoo-sharepoint
// ---------------------------------------------------------------------------

export interface OdooSitePairResult {
  internal_key: string;
  odoo_project_id: number;
  odoo_project_name: string;
  sharepoint_site_id: string;
  sharepoint_drive_id: string | null;
  sharepoint_site_name: string;
  sharepoint_display_name: string;
  sharepoint_web_url: string;
  match_confidence: number;
  mapping_status: string;
  mapping_method: string;
  project_member_emails: string[];
  member_read_status: string;
  auto_saved: boolean;
  save_skipped_reason: string | null;
}

export interface OdooSharePointSyncResult {
  scanned_at: string;
  odoo_configured: boolean;
  sharepoint_configured: boolean;
  odoo_projects_scanned: number;
  sharepoint_sites_scanned: number;
  token_roles: string[];
  exact_matches: number;
  no_match_count: number;
  multiple_match_count: number;
  auto_saved_count: number;
  matched_pairs: OdooSitePairResult[];
  unmatched_odoo_names: string[];
  unmatched_sharepoint_names: string[];
  odoo_emails_used: boolean;
  odoo_followers_used: boolean;
  summary: string;
}

export interface EmailGroup {
  id: string;
  display_name: string;
  mail: string;
  mail_enabled: boolean;
}

export interface EmailGroupMember {
  id: string;
  display_name: string;
  mail: string;
  user_principal_name: string;
  job_title: string;
  department: string;
  email: string;
}

export interface EmailGroupProjectResult {
  project_code: string;
  project_name: string;
  sharepoint_site_id: string;
  group_membership_status: string;
  group: EmailGroup;
  group_members: EmailGroupMember[];
  member_count: number;
  related_people: Record<string, unknown>;
  email_enabled: boolean;
  missing_permissions: string[];
  blockers: string[];
}

export interface EmailGroupEnrichmentResponse {
  scanned_at: string;
  verdict: string;
  token_roles: string[];
  missing_permissions: string[];
  project_results: EmailGroupProjectResult[];
  summary: string;
}

// ---------------------------------------------------------------------------
// Odoo Source Map (visibility) — GET/POST /admin/source-mappings/{code}/odoo-source-map
// ---------------------------------------------------------------------------

export interface OdooScanProgress {
  total: number;
  done: number;
  pending: number;
  running: number;
  completed: number;
  partial: number;
  capped: number;
  empty: number;
  failed: number;
  timeout: number;
  unmapped: number;
}

export interface OdooSourceMapEntry {
  key: string;
  group: string;
  groups: string[];
  source_name: string;
  model: string;
  link_path: string;
  link_scope: string;
  key_fields: string[];
  confidence: string;
  gap_type: string;
  aggregation: string;
  handled_inline: boolean;
  warning: string;
  mappable: boolean;
  link_value: string | null;
  last_scan_status: string;
  record_count: number | null;
  capped: boolean;
  // Rich batched-scan fields (defaults until a session scan touches the source):
  total: number | null;
  complete: boolean;
  error: string | null;
  duration_ms: number | null;
  scanned_at: string | null;
  pages_done: number;
}

export interface OdooSourceMapResponse {
  project_code: string;
  generic: boolean;
  odoo_enabled: boolean;
  extended_enabled: boolean;
  odoo_project_id: string | null;
  analytic_account_id: string | null;
  project_source_status: string;
  groups: string[];
  enabled_categories: string[];
  sources: OdooSourceMapEntry[];
  denylisted_paths: string[];
  missing_sources: string[];
  notes: string[];
  last_scanned_at: string | null;
  // Live batched-scan session metadata (null when no scan session is involved):
  scan_session_id: string | null;
  scan_state: string | null;
  scan_progress: OdooScanProgress | null;
  scan_count_supported: boolean | null;
}
