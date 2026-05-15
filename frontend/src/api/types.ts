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
