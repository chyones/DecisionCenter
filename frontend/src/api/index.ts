/**
 * API layer — Phase 2A Slice 1.
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
} from './types';
