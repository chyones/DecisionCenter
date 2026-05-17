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

export interface SourceMappingOdoo {
  project_model: string;
  cost_model: string;
  project_external_id: string;
  project_name: string;
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
