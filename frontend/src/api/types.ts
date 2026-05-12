/**
 * API types — Phase 2A Slice 1.
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
