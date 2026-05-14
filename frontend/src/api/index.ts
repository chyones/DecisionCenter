/**
 * API layer — Phase 2A.
 */

export { ApiClient } from './client';
export type { AuthHeaders, ClientOptions } from './client';
export { useApi } from './useApi';
export {
  ApiError,
  isApiError,
  type OutputFormat,
  type ReportRequest,
  type ReportResponse,
  type ApproveRequest,
  type RejectRequest,
  type RequestRevisionRequest,
  type ApiHealthResponse,
  type ReportState,
  type ReportSummary,
  type ReportListResponse,
  type ReviewDecisionView,
  type ReportDetail,
  type ReportStatusResponse,
  type CancelReportResponse,
  type UploadResponse,
  type WorkspaceProject,
  type WorkspaceContextResponse,
  type EvidencePanelEntry,
  type ReportContentResponse,
  type ListReportsParams,
} from './types';
